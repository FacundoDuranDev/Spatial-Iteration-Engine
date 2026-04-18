"""Depth of field filter -- selective focus blur.

Simulates camera depth of field by blurring regions away from a focal plane.
Uses either a vertical position proxy (top=far, bottom=near) or a segmentation
mask from perception to determine depth. Regions at the focal distance stay
sharp; others blur proportionally to their distance from the focal plane.

Inspired by Max Payne 3's cinematic rack-focus during dialogue cutscenes.
"""

import cv2
import numpy as np

from .base import BaseFilter


class DepthOfFieldFilter(BaseFilter):
    """Selective focus with vertical depth proxy or segmentation mask."""

    name = "depth_of_field"

    def __init__(
        self,
        focal_y: float = 0.5,
        focal_range: float = 0.15,
        blur_radius: int = 15,
        use_segmentation: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._focal_y = focal_y
        self._focal_range = focal_range
        self._blur_radius = blur_radius
        self._use_segmentation = use_segmentation

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._blur_radius < 3:
            return frame

        h, w = frame.shape[:2]

        # Build depth/blur weight map.
        blur_weight = self._build_blur_weight(h, w, analysis)
        if blur_weight is None:
            return frame

        # If everything is in focus, skip.
        if np.max(blur_weight) < 0.01:
            return frame

        # Create blurred version.
        ksize = self._blur_radius | 1  # Ensure odd.
        blurred = cv2.GaussianBlur(frame, (ksize, ksize), 0)

        # Blend: sharp where weight=0, blurred where weight=1.
        weight_3d = blur_weight[:, :, np.newaxis].astype(np.float32)
        result = (
            frame.astype(np.float32) * (1.0 - weight_3d)
            + blurred.astype(np.float32) * weight_3d
        )
        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))

    def _build_blur_weight(self, h, w, analysis):
        """Build per-pixel blur weight map (0=sharp, 1=max blur)."""
        # Try segmentation mask first.
        if self._use_segmentation and analysis is not None:
            seg = analysis.get("silhouette_segmentation") if hasattr(analysis, "get") else None
            if seg is not None and "person_mask" in seg:
                mask = seg["person_mask"]
                if mask.shape[:2] == (h, w):
                    # Person is in focus (weight=0), background is blurred (weight=1).
                    return (1.0 - mask.astype(np.float32) / 255.0).clip(0, 1)

        # Fallback: vertical depth proxy.
        y_norm = np.linspace(0, 1, h, dtype=np.float32)
        distance = np.abs(y_norm - self._focal_y)
        focal_range = max(0.01, self._focal_range)
        weight = np.clip((distance - focal_range) / (1.0 - focal_range + 1e-6), 0, 1)

        # Smoothstep for gentle transition.
        weight = weight * weight * (3.0 - 2.0 * weight)

        # Broadcast to full frame.
        return np.tile(weight[:, np.newaxis], (1, w))
