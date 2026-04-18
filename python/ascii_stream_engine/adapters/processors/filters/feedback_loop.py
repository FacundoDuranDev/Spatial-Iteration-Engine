"""Feedback loop filter — infinite-tunnel / hall-of-mirrors video echo."""

import cv2
import numpy as np

from .base import BaseFilter


class FeedbackLoopFilter(BaseFilter):
    """Blends the current frame with a slightly scaled+rotated copy of the
    previous output, producing trailing "zoom tunnel" feedback.
    """

    name = "feedback_loop"

    def __init__(
        self,
        decay: float = 0.85,
        scale: float = 1.02,
        rotation_deg: float = 0.5,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._decay = float(decay)
        self._scale = float(scale)
        self._rotation = float(rotation_deg)
        self._last_output = None

    def reset(self):
        self._last_output = None

    def apply(self, frame, config, analysis=None):
        if not self.enabled or frame is None or frame.size == 0:
            return frame

        if self._last_output is None or self._last_output.shape != frame.shape:
            self._last_output = frame.copy()
            return frame

        h, w = frame.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), self._rotation, self._scale)
        warped = cv2.warpAffine(
            self._last_output, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        decay = float(np.clip(self._decay, 0.0, 0.99))
        out = cv2.addWeighted(frame, 1.0 - decay, warped, decay, 0.0)
        self._last_output = out
        return out
