"""Vignette filter -- radial edge darkening.

Darkens the edges of the frame with a smooth radial falloff from center,
simulating camera lens light falloff. The falloff mask is LUT-cached and only
rebuilt when parameters or resolution change.

Inspired by the always-on vignette in Max Payne 3 that intensifies during pain
and drunk sequences.
"""

import numpy as np

from .base import BaseFilter


class VignetteFilter(BaseFilter):
    """Radial vignette with LUT-cached falloff mask."""

    name = "vignette"

    def __init__(
        self,
        inner_radius: float = 0.4,
        outer_radius: float = 1.0,
        intensity: float = 0.6,
        tint_bgr: tuple = (0, 0, 0),
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._inner_radius = inner_radius
        self._outer_radius = outer_radius
        self._intensity = intensity
        self._tint_bgr = tint_bgr
        # LUT cache.
        self._mask = None
        self._tint_layer = None
        self._cached_key = None

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._intensity <= 0.0:
            return frame

        h, w = frame.shape[:2]
        cache_key = (h, w, self._inner_radius, self._outer_radius, self._intensity, self._tint_bgr)

        if self._cached_key != cache_key:
            self._build_mask(h, w)
            self._cached_key = cache_key

        # Apply: blend frame toward tint color weighted by mask.
        if self._tint_bgr == (0, 0, 0):
            # Fast path: just darken.
            result = (frame.astype(np.float32) * self._mask).astype(np.uint8)
        else:
            flt = frame.astype(np.float32)
            darkened = flt * self._mask + self._tint_layer * (1.0 - self._mask)
            np.clip(darkened, 0, 255, out=darkened)
            result = darkened.astype(np.uint8)

        return np.ascontiguousarray(result)

    def _build_mask(self, h: int, w: int) -> None:
        """Precompute the radial falloff mask."""
        # Normalized coordinates from center.
        cy, cx = h / 2.0, w / 2.0
        # Use the diagonal as the normalization distance.
        diag = np.sqrt(cx * cx + cy * cy)

        y = np.arange(h, dtype=np.float32) - cy
        x = np.arange(w, dtype=np.float32) - cx
        yy, xx = np.meshgrid(y, x, indexing="ij")
        dist = np.sqrt(xx * xx + yy * yy) / diag

        # Smoothstep between inner and outer radius.
        inner = self._inner_radius
        outer = max(inner + 0.01, self._outer_radius)
        t = np.clip((dist - inner) / (outer - inner), 0.0, 1.0)
        # Hermite smoothstep.
        falloff = t * t * (3.0 - 2.0 * t)

        # mask = 1 at center, (1-intensity) at edges.
        self._mask = (1.0 - falloff * self._intensity).astype(np.float32)
        self._mask = self._mask[:, :, np.newaxis]  # Broadcast to 3 channels.

        # Pre-build tint layer for non-black tints.
        tint = np.array(self._tint_bgr, dtype=np.float32)
        self._tint_layer = np.full((h, w, 3), tint, dtype=np.float32)
