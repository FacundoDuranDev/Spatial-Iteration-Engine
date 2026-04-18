"""Motion blur filter -- directional blur driven by optical flow.

Uses the shared optical flow from FilterContext to blur each pixel along its
motion vector direction, simulating camera or object motion blur. Gracefully
degrades to a no-op when optical flow is unavailable.

Inspired by Max Payne 3's per-object motion blur and shootdodge blur trails.
"""

import cv2
import numpy as np

from .base import BaseFilter


class MotionBlurFilter(BaseFilter):
    """Optical-flow-driven directional motion blur."""

    name = "motion_blur"
    needs_optical_flow = True

    def __init__(
        self,
        strength: float = 1.0,
        samples: int = 5,
        scale: float = 1.0,
        quality: float = 1.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._strength = strength
        self._samples = samples
        self._scale = scale
        self._quality = quality

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._strength <= 0.0:
            return frame

        flow = getattr(analysis, "optical_flow", None) if analysis else None
        if flow is None:
            return frame

        h, w = frame.shape[:2]
        samples = max(2, min(16, self._samples))

        # Quality: process at reduced resolution.
        q = max(0.25, min(1.0, self._quality))
        if q < 1.0:
            sh, sw = max(1, int(h * q)), max(1, int(w * q))
            work = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
            flow_scaled = cv2.resize(flow, (sw, sh), interpolation=cv2.INTER_LINEAR)
            flow_scaled *= q  # Scale flow vectors proportionally.
        else:
            work = frame
            flow_scaled = flow
            sh, sw = h, w

        # Scale flow by strength.
        flow_xy = flow_scaled.astype(np.float32) * self._strength * self._scale

        # Base coordinate grids.
        y_coords = np.arange(sh, dtype=np.float32)
        x_coords = np.arange(sw, dtype=np.float32)
        base_x, base_y = np.meshgrid(x_coords, y_coords)

        # Accumulate samples along flow direction.
        result = np.zeros((sh, sw, 3), dtype=np.float32)
        for i in range(samples):
            t = (float(i) / (samples - 1) - 0.5)
            map_x = base_x + flow_xy[:, :, 0] * t
            map_y = base_y + flow_xy[:, :, 1] * t
            sampled = cv2.remap(
                work, map_x, map_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )
            result += sampled.astype(np.float32)

        result /= samples

        # Upscale back if quality < 1.
        if q < 1.0:
            result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR)

        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))
