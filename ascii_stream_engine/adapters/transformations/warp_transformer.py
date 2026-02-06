"""Transformaciones de warping/distorsión."""

from typing import Optional

import cv2
import numpy as np

from .base import BaseSpatialTransform


class WarpTransformer(BaseSpatialTransform):
    """Aplica transformaciones de warping."""

    name = "warp_transformer"

    def __init__(self, warp_type: str = "affine") -> None:
        """
        Inicializa el transformador de warping.

        Args:
            warp_type: Tipo de warping ("affine", "perspective", "polynomial")
        """
        self.warp_type = warp_type
        self._matrix: Optional[np.ndarray] = None

    def set_transform_matrix(self, matrix: np.ndarray) -> None:
        """Establece la matriz de transformación."""
        self._matrix = matrix

    def transform(self, frame: np.ndarray) -> np.ndarray:
        """Aplica el warping."""
        if self._matrix is None:
            return frame

        h, w = frame.shape[:2]

        if self.warp_type == "affine":
            return cv2.warpAffine(frame, self._matrix, (w, h))
        elif self.warp_type == "perspective":
            return cv2.warpPerspective(frame, self._matrix, (w, h))
        else:
            return frame

    def inverse(self, frame: np.ndarray) -> np.ndarray:
        """Aplica el warping inverso."""
        if self._matrix is None:
            return frame

        try:
            if self.warp_type == "affine":
                inv_matrix = cv2.invertAffineTransform(self._matrix)
            elif self.warp_type == "perspective":
                inv_matrix = cv2.invert(self._matrix)[1]
            else:
                return frame

            h, w = frame.shape[:2]
            if self.warp_type == "affine":
                return cv2.warpAffine(frame, inv_matrix, (w, h))
            else:
                return cv2.warpPerspective(frame, inv_matrix, (w, h))
        except Exception:
            return frame

