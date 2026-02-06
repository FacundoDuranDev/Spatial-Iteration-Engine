"""Protocolo para trackers de objetos."""

from typing import Optional, Protocol

import numpy as np

from ..domain.config import EngineConfig
from ..domain.tracking_data import TrackingData


class ObjectTracker(Protocol):
    """Protocolo para trackers de objetos."""

    def track(
        self, frame: np.ndarray, detections: dict, config: EngineConfig
    ) -> TrackingData:
        """
        Trackea objetos en un frame basándose en detecciones.

        Args:
            frame: Frame de video
            detections: Diccionario con detecciones de analizadores
            config: Configuración del engine

        Returns:
            TrackingData con trayectorias actualizadas
        """
        ...

    def reset(self) -> None:
        """Resetea el estado del tracker."""
        ...

    def get_trajectories(self) -> dict:
        """
        Obtiene todas las trayectorias actuales.

        Returns:
            Diccionario con trayectorias por object_id
        """
        ...

