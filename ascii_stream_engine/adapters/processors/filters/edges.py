import cv2

from .base import BaseFilter
from .conversion_cache import get_cached_conversion


class EdgeFilter(BaseFilter):
    name = "edges"

    def __init__(self, low: int = 80, high: int = 160, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._low = low
        self._high = high

    def apply(self, frame, config, analysis=None):
        # Optimización: usar cache de conversiones para evitar conversiones redundantes
        if frame.ndim == 3:
            gray = get_cached_conversion(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        return cv2.Canny(gray, self._low, self._high)
