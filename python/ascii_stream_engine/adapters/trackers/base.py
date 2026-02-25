"""Clase base para trackers de objetos."""

import time
from typing import Dict, Optional

import numpy as np

from ...domain.config import EngineConfig
from ...domain.tracking_data import TrackingData, Trajectory


class BaseTracker:
    """Clase base para implementaciones de tracking."""

    name = "base_tracker"

    def __init__(self, enabled: bool = True) -> None:
        """
        Inicializa el tracker.

        Args:
            enabled: Si el tracker está habilitado
        """
        self.enabled = enabled
        self._trajectories: Dict[str, Trajectory] = {}

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
        if not self.enabled:
            return TrackingData(frame_id="", timestamp=time.time())

        start_time = time.time()
        frame_id = f"frame_{int(time.time() * 1000)}"
        timestamp = time.time()

        # Implementación básica: convertir detecciones a trayectorias
        for analyzer_name, detection_data in detections.items():
            if isinstance(detection_data, dict) and "detections" in detection_data:
                for det in detection_data["detections"]:
                    if "bbox" in det:
                        bbox = det["bbox"]
                        x = bbox[0] + bbox[2] / 2  # Centro x
                        y = bbox[1] + bbox[3] / 2  # Centro y
                        obj_id = f"{analyzer_name}_{det.get('class_id', len(self._trajectories))}"

                        if obj_id not in self._trajectories:
                            self._trajectories[obj_id] = Trajectory(
                                object_id=obj_id,
                                label=det.get("label", analyzer_name),
                            )

                        self._trajectories[obj_id].add_point(
                            x, y, timestamp, det.get("confidence", 1.0)
                        )
                        self._trajectories[obj_id].bbox = bbox
                        self._trajectories[obj_id].lost = False

        processing_time = time.time() - start_time
        active_objects = sum(1 for t in self._trajectories.values() if not t.lost)
        lost_objects = sum(1 for t in self._trajectories.values() if t.lost)

        return TrackingData(
            frame_id=frame_id,
            timestamp=timestamp,
            trajectories=self._trajectories.copy(),
            active_objects=active_objects,
            lost_objects=lost_objects,
            processing_time=processing_time,
        )

    def reset(self) -> None:
        """Resetea el estado del tracker."""
        self._trajectories.clear()

    def get_trajectories(self) -> dict:
        """
        Obtiene todas las trayectorias actuales.

        Returns:
            Diccionario con trayectorias por object_id
        """
        return {obj_id: traj.to_dict() for obj_id, traj in self._trajectories.items()}
