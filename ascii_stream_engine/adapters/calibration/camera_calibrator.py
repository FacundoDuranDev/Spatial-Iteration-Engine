"""Calibración de parámetros intrínsecos y extrínsecos de cámaras."""

import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraCalibrator:
    """Calibra parámetros de cámara usando patrones de calibración."""

    def __init__(
        self,
        pattern_size: Tuple[int, int] = (9, 6),
        square_size: float = 1.0,
    ) -> None:
        """
        Inicializa el calibrador.

        Args:
            pattern_size: Tamaño del patrón de calibración (filas, columnas)
            square_size: Tamaño del cuadrado en unidades reales
        """
        self.pattern_size = pattern_size
        self.square_size = square_size
        self._object_points: List[np.ndarray] = []
        self._image_points: List[np.ndarray] = []
        self._calibrated = False
        self._camera_matrix: Optional[np.ndarray] = None
        self._dist_coeffs: Optional[np.ndarray] = None

    def add_calibration_image(self, image: np.ndarray) -> bool:
        """
        Agrega una imagen de calibración.

        Args:
            image: Imagen con patrón de calibración

        Returns:
            True si se detectó el patrón
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Buscar esquinas del tablero de ajedrez
        ret, corners = cv2.findChessboardCorners(gray, self.pattern_size, None)

        if ret:
            # Refinar esquinas
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Preparar puntos del objeto 3D
            objp = np.zeros((self.pattern_size[0] * self.pattern_size[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0 : self.pattern_size[0], 0 : self.pattern_size[1]].T.reshape(-1, 2)
            objp *= self.square_size

            self._object_points.append(objp)
            self._image_points.append(corners2)

            logger.debug(f"Patrón detectado en imagen (total: {len(self._image_points)})")
            return True
        else:
            logger.warning("No se detectó patrón de calibración en la imagen")
            return False

    def calibrate(self) -> bool:
        """
        Realiza la calibración.

        Returns:
            True si la calibración fue exitosa
        """
        if len(self._object_points) < 3:
            logger.error("Se necesitan al menos 3 imágenes de calibración")
            return False

        try:
            # Obtener tamaño de imagen del primer punto
            img_shape = self._image_points[0][0].shape if self._image_points else (480, 640)
            h, w = img_shape[0], img_shape[1]

            ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                self._object_points,
                self._image_points,
                (w, h),
                None,
                None,
            )

            if ret:
                self._camera_matrix = mtx
                self._dist_coeffs = dist
                self._calibrated = True
                logger.info("Calibración de cámara completada exitosamente")
                return True
            else:
                logger.error("Error en la calibración")
                return False
        except Exception as e:
            logger.error(f"Error durante la calibración: {e}", exc_info=True)
            return False

    def get_camera_matrix(self) -> Optional[np.ndarray]:
        """Obtiene la matriz de cámara."""
        return self._camera_matrix.copy() if self._camera_matrix is not None else None

    def get_distortion_coefficients(self) -> Optional[np.ndarray]:
        """Obtiene los coeficientes de distorsión."""
        return self._dist_coeffs.copy() if self._dist_coeffs is not None else None

    def is_calibrated(self) -> bool:
        """Verifica si la cámara está calibrada."""
        return self._calibrated

    def reset(self) -> None:
        """Resetea el calibrador."""
        self._object_points.clear()
        self._image_points.clear()
        self._calibrated = False
        self._camera_matrix = None
        self._dist_coeffs = None

    def get_calibration_data(self) -> Dict[str, any]:  # type: ignore
        """Obtiene los datos de calibración."""
        return {
            "calibrated": self._calibrated,
            "camera_matrix": self._camera_matrix.tolist() if self._camera_matrix is not None else None,
            "distortion_coefficients": self._dist_coeffs.tolist() if self._dist_coeffs is not None else None,
            "num_images": len(self._image_points),
        }

