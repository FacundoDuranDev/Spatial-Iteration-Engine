"""Persistencia de parámetros de calibración."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CalibrationStorage:
    """Almacena y carga parámetros de calibración."""

    def __init__(self, storage_path: Optional[str] = None) -> None:
        """
        Inicializa el almacenamiento.

        Args:
            storage_path: Ruta del directorio de almacenamiento
        """
        self.storage_path = Path(storage_path) if storage_path else Path("calibrations")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_calibration(
        self,
        camera_id: str,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Guarda parámetros de calibración.

        Args:
            camera_id: ID de la cámara
            camera_matrix: Matriz de cámara
            dist_coeffs: Coeficientes de distorsión
            metadata: Metadata adicional

        Returns:
            True si se guardó exitosamente
        """
        try:
            data = {
                "camera_id": camera_id,
                "camera_matrix": camera_matrix.tolist(),
                "distortion_coefficients": dist_coeffs.tolist(),
                "metadata": metadata or {},
            }

            file_path = self.storage_path / f"{camera_id}_calibration.json"
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Calibración guardada para cámara '{camera_id}'")
            return True
        except Exception as e:
            logger.error(f"Error guardando calibración: {e}", exc_info=True)
            return False

    def load_calibration(self, camera_id: str) -> Optional[Dict]:
        """
        Carga parámetros de calibración.

        Args:
            camera_id: ID de la cámara

        Returns:
            Diccionario con parámetros o None si no existe
        """
        try:
            file_path = self.storage_path / f"{camera_id}_calibration.json"
            if not file_path.exists():
                logger.warning(f"Calibración no encontrada para cámara '{camera_id}'")
                return None

            with open(file_path, "r") as f:
                data = json.load(f)

            # Convertir listas a arrays numpy
            data["camera_matrix"] = np.array(data["camera_matrix"])
            data["distortion_coefficients"] = np.array(data["distortion_coefficients"])

            logger.info(f"Calibración cargada para cámara '{camera_id}'")
            return data
        except Exception as e:
            logger.error(f"Error cargando calibración: {e}", exc_info=True)
            return None

    def list_calibrations(self) -> List[str]:
        """
        Lista todas las calibraciones disponibles.

        Returns:
            Lista de IDs de cámaras con calibraciones
        """
        calibrations = []
        for file_path in self.storage_path.glob("*_calibration.json"):
            camera_id = file_path.stem.replace("_calibration", "")
            calibrations.append(camera_id)
        return calibrations
