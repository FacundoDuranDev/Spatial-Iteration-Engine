"""Corrección de perspectiva y distorsión."""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PerspectiveCorrector:
    """Corrige perspectiva y distorsión de imágenes."""

    def __init__(
        self,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
    ) -> None:
        """
        Inicializa el corrector de perspectiva.

        Args:
            camera_matrix: Matriz de cámara (de calibración)
            dist_coeffs: Coeficientes de distorsión (de calibración)
        """
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self._perspective_matrix: Optional[np.ndarray] = None

    def set_calibration(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ) -> None:
        """
        Establece parámetros de calibración.

        Args:
            camera_matrix: Matriz de cámara
            dist_coeffs: Coeficientes de distorsión
        """
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs

    def correct_distortion(self, image: np.ndarray) -> np.ndarray:
        """
        Corrige la distorsión de la imagen.

        Args:
            image: Imagen con distorsión

        Returns:
            Imagen corregida
        """
        if self.camera_matrix is None or self.dist_coeffs is None:
            logger.warning("No hay parámetros de calibración, retornando imagen original")
            return image

        h, w = image.shape[:2]
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix,
            self.dist_coeffs,
            (w, h),
            1,
            (w, h),
        )

        dst = cv2.undistort(image, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)
        return dst

    def set_perspective_transform(
        self,
        src_points: np.ndarray,
        dst_points: np.ndarray,
    ) -> None:
        """
        Establece la transformación de perspectiva.

        Args:
            src_points: Puntos fuente (4 puntos)
            dst_points: Puntos destino (4 puntos)
        """
        if len(src_points) != 4 or len(dst_points) != 4:
            raise ValueError("Se requieren exactamente 4 puntos")

        self._perspective_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        logger.debug("Matriz de perspectiva calculada")

    def apply_perspective_transform(self, image: np.ndarray, size: Optional[Tuple[int, int]] = None) -> np.ndarray:
        """
        Aplica la transformación de perspectiva.

        Args:
            image: Imagen a transformar
            size: Tamaño de salida (None para usar tamaño de entrada)

        Returns:
            Imagen transformada
        """
        if self._perspective_matrix is None:
            logger.warning("No hay matriz de perspectiva, retornando imagen original")
            return image

        if size is None:
            h, w = image.shape[:2]
            size = (w, h)

        dst = cv2.warpPerspective(image, self._perspective_matrix, size)
        return dst

    def correct(self, image: np.ndarray, apply_perspective: bool = True) -> np.ndarray:
        """
        Aplica todas las correcciones.

        Args:
            image: Imagen a corregir
            apply_perspective: Si aplicar transformación de perspectiva

        Returns:
            Imagen corregida
        """
        # Primero corregir distorsión
        corrected = self.correct_distortion(image)

        # Luego aplicar perspectiva si está configurada
        if apply_perspective and self._perspective_matrix is not None:
            corrected = self.apply_perspective_transform(corrected)

        return corrected

