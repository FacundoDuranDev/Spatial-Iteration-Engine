import cv2

from .base import BaseFilter


class EdgeFilter(BaseFilter):
    name = "edges"

    def __init__(self, low: int = 80, high: int = 160, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._low = low
        self._high = high

    def apply(self, frame, config, analysis=None):
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        return cv2.Canny(gray, self._low, self._high)
