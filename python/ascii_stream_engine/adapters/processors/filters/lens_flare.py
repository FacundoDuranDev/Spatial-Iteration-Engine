"""Lens flare filter -- anamorphic streaks, ghosts, and dirt overlay.

Extracts bright pixels above a threshold, creates horizontal anamorphic
streaks, generates ghost reflections through the center, and optionally
overlays a dirt/smudge texture. All elements are additively composited.

Inspired by Max Payne 3's warm-tinted anamorphic lens flares during
bullet time and sun-facing exterior shots.
"""

import cv2
import numpy as np

from .base import BaseFilter


class LensFlareFilter(BaseFilter):
    """Anamorphic lens flare with streaks, ghosts, and dirt overlay."""

    name = "lens_flare"

    def __init__(
        self,
        threshold: int = 240,
        streak_length: float = 0.3,
        ghost_count: int = 3,
        ghost_scale: float = 0.5,
        tint_bgr: tuple = (0, 60, 120),
        anamorphic: bool = True,
        intensity: float = 0.5,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._threshold = threshold
        self._streak_length = streak_length
        self._ghost_count = ghost_count
        self._ghost_scale = ghost_scale
        self._tint_bgr = tint_bgr
        self._anamorphic = anamorphic
        self._intensity = intensity

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._intensity <= 0.0:
            return frame

        h, w = frame.shape[:2]

        # Extract bright regions.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, self._threshold, 255, cv2.THRESH_BINARY)
        bright = cv2.bitwise_and(frame, frame, mask=mask).astype(np.float32)

        if np.max(bright) < 1.0:
            return frame

        flare = np.zeros((h, w, 3), dtype=np.float32)

        # Anamorphic streaks: wide horizontal blur.
        if self._anamorphic and self._streak_length > 0.0:
            kw = max(3, int(w * self._streak_length)) | 1
            streak = cv2.GaussianBlur(bright, (kw, 1), 0)
            flare += streak

        # Ghost reflections: flip bright regions through center and scale.
        ghosts = max(0, min(7, self._ghost_count))
        if ghosts > 0:
            for i in range(1, ghosts + 1):
                scale = self._ghost_scale ** i
                # Flip through center.
                ghost = cv2.flip(bright, -1)  # Flip both axes.
                # Scale from center.
                gh, gw = int(h * scale), int(w * scale)
                if gh < 2 or gw < 2:
                    continue
                ghost_small = cv2.resize(ghost, (gw, gh), interpolation=cv2.INTER_LINEAR)
                # Place centered.
                gy = (h - gh) // 2
                gx = (w - gw) // 2
                flare[gy : gy + gh, gx : gx + gw] += ghost_small * (0.3 / i)

        # Apply warm tint.
        tint = np.array(self._tint_bgr, dtype=np.float32)
        if np.any(tint > 0):
            tint_norm = tint / max(1.0, tint.max())
            flare = flare * (0.5 + tint_norm * 0.5)

        # Soft blur the entire flare for smoothness.
        flare = cv2.GaussianBlur(flare, (0, 0), sigmaX=3)

        # Additive composite.
        result = frame.astype(np.float32) + flare * self._intensity
        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))
