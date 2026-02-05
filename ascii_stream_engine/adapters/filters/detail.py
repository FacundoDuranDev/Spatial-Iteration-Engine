import cv2
import numpy as np

from .base import BaseFilter


class DetailBoostFilter(BaseFilter):
    name = "detail_boost"

    def __init__(
        self,
        clip_limit: float = 2.0,
        tile_grid_size: tuple = (8, 8),
        sharpness: float = 0.6,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._clip_limit = clip_limit
        self._tile_grid_size = tile_grid_size
        self._sharpness = sharpness
        self._clahe = cv2.createCLAHE(
            clipLimit=self._clip_limit, tileGridSize=self._tile_grid_size
        )

    def apply(self, frame, config, analysis=None):
        # Optimización: evitar conversión de color si el frame ya es escala de grises
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            # Frame ya es escala de grises, usar directamente
            gray = frame

        eq = self._clahe.apply(gray)
        blur = cv2.GaussianBlur(eq, (0, 0), 1.0)
        sharp = cv2.addWeighted(eq, 1.0 + self._sharpness, blur, -self._sharpness, 0)

        if frame.ndim == 3:
            return cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)
        # Optimización: solo convertir tipo si es necesario
        if sharp.dtype != frame.dtype:
            return sharp.astype(frame.dtype)
        return sharp
