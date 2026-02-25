"""Protocolo para trackers de objetos."""

from typing import Any, Dict, Optional, Protocol

import numpy as np

from ..domain.config import EngineConfig
from ..domain.tracking_data import TrackingData


class ObjectTracker(Protocol):
    """Protocolo para trackers de objetos.

    Los trackers mantienen el seguimiento de objetos a través de múltiples frames,
    asociando detecciones con identidades persistentes y calculando trayectorias.
    """

    name: str
    """Nombre único del tracker."""

    enabled: bool
    """Indica si el tracker está habilitado."""

    def track(self, frame: np.ndarray, detections: dict, config: EngineConfig) -> TrackingData:
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
        """Resetea el estado del tracker, eliminando todas las trayectorias."""
        ...

    def get_trajectories(self) -> dict:
        """
        Obtiene todas las trayectorias actuales.

        Returns:
            Diccionario con trayectorias por object_id
        """
        ...

    def configure(self, **kwargs: Any) -> None:
        """
        Configura parámetros del tracker.

        Args:
            **kwargs: Parámetros de configuración específicos del tracker
        """
        ...

    def get_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuración actual del tracker.

        Returns:
            Diccionario con la configuración actual
        """
        ...
