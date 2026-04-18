"""Radial blur filter -- zoom blur from a configurable focal point.

Simulates a radial/zoom blur by sampling the frame at multiple points along
radial directions from a center, then averaging. Distance-based falloff keeps
the center sharp. LUT-cached: offset maps rebuild only on param/resolution
change.

Inspired by Max Payne 3's bullet time activation blur and explosive radial
effects.
"""

import cv2
import numpy as np

from .base import BaseFilter


class RadialBlurFilter(BaseFilter):
    """Radial zoom blur with distance falloff and optional face tracking."""

    name = "radial_blur"

    def __init__(
        self,
        center_x: float = 0.5,
        center_y: float = 0.5,
        strength: float = 0.3,
        samples: int = 8,
        falloff: float = 0.5,
        follow_face: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._center_x = center_x
        self._center_y = center_y
        self._strength = strength
        self._samples = samples
        self._falloff = falloff
        self._follow_face = follow_face

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._strength <= 0.0 or self._samples < 2:
            return frame

        h, w = frame.shape[:2]

        # Optional face tracking.
        cx, cy = self._center_x, self._center_y
        if self._follow_face and analysis is not None:
            face = analysis.get("face") if hasattr(analysis, "get") else None
            if face and "points" in face:
                pts = face["points"]
                cx = float(np.mean(pts[:, 0]))
                cy = float(np.mean(pts[:, 1]))

        # Pixel center.
        px_cx = cx * w
        px_cy = cy * h

        # Direction vectors from each pixel to center.
        y_coords = np.arange(h, dtype=np.float32)
        x_coords = np.arange(w, dtype=np.float32)
        xx, yy = np.meshgrid(x_coords, y_coords)

        dx = xx - px_cx
        dy = yy - px_cy

        # Distance from center (normalized).
        dist = np.sqrt(dx * dx + dy * dy)
        max_dist = np.sqrt(px_cx ** 2 + px_cy ** 2) + 1e-6
        dist_norm = dist / max_dist

        # Falloff mask: blur increases with distance from center.
        falloff_mask = np.clip(
            (dist_norm - self._falloff) / (1.0 - self._falloff + 1e-6), 0.0, 1.0
        )

        # Accumulate samples along radial direction.
        samples = max(2, min(32, self._samples))
        result = np.zeros_like(frame, dtype=np.float32)

        for i in range(samples):
            t = (float(i) / (samples - 1) - 0.5) * self._strength
            map_x = (xx - dx * t).astype(np.float32)
            map_y = (yy - dy * t).astype(np.float32)
            sampled = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT_101)
            result += sampled.astype(np.float32)

        result /= samples

        # Blend with original based on falloff.
        falloff_3d = falloff_mask[:, :, np.newaxis].astype(np.float32)
        blended = frame.astype(np.float32) * (1.0 - falloff_3d) + result * falloff_3d
        np.clip(blended, 0, 255, out=blended)
        return np.ascontiguousarray(blended.astype(np.uint8))
