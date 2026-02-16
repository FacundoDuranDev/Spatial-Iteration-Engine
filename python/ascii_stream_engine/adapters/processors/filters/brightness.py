import cv2

from .base import BaseFilter


class BrightnessFilter(BaseFilter):
    name = "brightness"

    def apply(self, frame, config, analysis=None):
        if getattr(config, "contrast", 1.0) == 1.0 and getattr(
            config, "brightness", 0
        ) == 0:
            return frame
        return cv2.convertScaleAbs(
            frame,
            alpha=float(getattr(config, "contrast", 1.0)),
            beta=int(getattr(config, "brightness", 0)),
        )
