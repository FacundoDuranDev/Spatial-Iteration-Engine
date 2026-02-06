"""Sincronización de múltiples cámaras."""

import logging
import time
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class MultiCameraSync:
    """Sincroniza múltiples cámaras para captura simultánea."""

    def __init__(self, max_time_diff: float = 0.1) -> None:
        """
        Inicializa el sincronizador.

        Args:
            max_time_diff: Diferencia máxima de tiempo entre frames (segundos)
        """
        self.max_time_diff = max_time_diff
        self._frames: Dict[str, tuple] = {}  # {camera_id: (frame, timestamp)}
        self._lock = None
        import threading
        self._lock = threading.Lock()

    def add_frame(self, camera_id: str, frame: np.ndarray, timestamp: Optional[float] = None) -> None:
        """
        Agrega un frame de una cámara.

        Args:
            camera_id: ID de la cámara
            frame: Frame capturado
            timestamp: Timestamp del frame (None para usar tiempo actual)
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self._frames[camera_id] = (frame, timestamp)

    def get_synchronized_frames(self, camera_ids: Optional[List[str]] = None) -> Optional[Dict[str, np.ndarray]]:
        """
        Obtiene frames sincronizados de múltiples cámaras.

        Args:
            camera_ids: IDs de cámaras a sincronizar (None para todas)

        Returns:
            Diccionario con frames sincronizados o None si no hay sincronización
        """
        with self._lock:
            if camera_ids is None:
                camera_ids = list(self._frames.keys())

            if len(camera_ids) < 2:
                return {cid: self._frames[cid][0] for cid in camera_ids if cid in self._frames}

            # Verificar que todos los frames estén dentro del rango de tiempo
            timestamps = [self._frames[cid][1] for cid in camera_ids if cid in self._frames]

            if len(timestamps) != len(camera_ids):
                return None  # No hay frames de todas las cámaras

            min_time = min(timestamps)
            max_time = max(timestamps)

            if max_time - min_time > self.max_time_diff:
                return None  # Frames no están sincronizados

            return {cid: self._frames[cid][0] for cid in camera_ids}

    def clear(self) -> None:
        """Limpia todos los frames almacenados."""
        with self._lock:
            self._frames.clear()

