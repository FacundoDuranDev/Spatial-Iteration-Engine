"""Mapeo de proyección (projection mapping)."""

import cv2
import numpy as np

from .base import BaseSpatialTransform


class ProjectionMapper(BaseSpatialTransform):
    """Mapea proyección a superficies no planas."""

    name = "projection_mapper"

    def __init__(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        """
        Inicializa el mapeador de proyección.

        Args:
            src_points: Puntos fuente (4 puntos)
            dst_points: Puntos destino (4 puntos)
        """
        if len(src_points) != 4 or len(dst_points) != 4:
            raise ValueError("Se requieren exactamente 4 puntos")
        self.src_points = src_points.astype(np.float32)
        self.dst_points = dst_points.astype(np.float32)
        self._matrix = cv2.getPerspectiveTransform(self.src_points, self.dst_points)
        self._inverse_matrix = cv2.getPerspectiveTransform(self.dst_points, self.src_points)

    def transform(self, frame: np.ndarray) -> np.ndarray:
        """Aplica el mapeo de proyección."""
        h, w = frame.shape[:2]
        return cv2.warpPerspective(frame, self._matrix, (w, h))

    def inverse(self, frame: np.ndarray) -> np.ndarray:
        """Aplica el mapeo inverso."""
        h, w = frame.shape[:2]
        return cv2.warpPerspective(frame, self._inverse_matrix, (w, h))
