"""Kuwahara filter -- oil-painting / watercolor stylisation.

For each pixel the neighbourhood is split into four overlapping quadrants.
The quadrant with the lowest colour variance supplies the output value,
which preserves edges while smoothing flat regions.

This implementation is fully vectorised with cv2.blur to keep runtime
below 5 ms at 640x480.
"""

import cv2
import numpy as np

from .base import BaseFilter


class KuwaharaFilter(BaseFilter):
    """Edge-preserving smoothing via per-quadrant variance selection."""

    name = "kuwahara"

    def __init__(self, radius: int = 4, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._radius = radius

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        radius = int(getattr(config, "kuwahara_radius", self._radius))
        radius = max(2, min(radius, 8))

        if radius <= 0:
            return frame

        out = frame.copy(order="C")
        h, w = out.shape[:2]

        # Quadrant kernel size (radius + 1 so the quadrant covers pixels 0..radius)
        ks = radius + 1

        # Grayscale for variance computation
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # Precompute gray squared for variance: var = E[x^2] - E[x]^2
        gray_sq = gray * gray

        # Padded frame as float for colour mean computation
        frame_f = out.astype(np.float32)

        # We define four quadrant offsets.  Each quadrant is a (ks x ks) box
        # anchored at a different corner relative to the centre pixel.
        # OpenCV anchor convention: (0,0) = top-left of kernel.
        #   top-left quadrant:     anchor at (radius, radius)  -- kernel sits above-left
        #   top-right quadrant:    anchor at (0,     radius)   -- kernel sits above-right
        #   bottom-left quadrant:  anchor at (radius, 0)       -- kernel sits below-left
        #   bottom-right quadrant: anchor at (0,     0)        -- kernel sits below-right
        anchors = [
            (radius, radius),  # top-left
            (0, radius),       # top-right
            (radius, 0),       # bottom-left
            (0, 0),            # bottom-right
        ]

        best_var = np.full((h, w), np.inf, dtype=np.float32)
        result = np.zeros_like(frame_f)

        for anchor in anchors:
            # Local mean of grayscale
            mean_g = cv2.blur(gray, (ks, ks), anchor=anchor, borderType=cv2.BORDER_REFLECT)
            # Local mean of gray^2
            mean_g2 = cv2.blur(gray_sq, (ks, ks), anchor=anchor, borderType=cv2.BORDER_REFLECT)
            # Variance = E[x^2] - (E[x])^2
            var = mean_g2 - mean_g * mean_g
            np.maximum(var, 0.0, out=var)  # clamp numerical noise

            # Colour means for this quadrant (per-channel blur)
            mean_c = cv2.blur(frame_f, (ks, ks), anchor=anchor, borderType=cv2.BORDER_REFLECT)

            # Update where this quadrant has lower variance
            mask = var < best_var
            best_var[mask] = var[mask]
            mask3 = mask[:, :, np.newaxis]
            np.copyto(result, mean_c, where=mask3)

        np.clip(result, 0, 255, out=result)
        return result.astype(np.uint8)
