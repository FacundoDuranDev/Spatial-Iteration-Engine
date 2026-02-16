"""Tracker multi-objeto que gestiona múltiples objetos simultáneamente."""

import time
from typing import Dict, List, Optional

import numpy as np

from ...domain.config import EngineConfig
from ...domain.tracking_data import TrackingData, Trajectory

from .base import BaseTracker


class MultiObjectTracker(BaseTracker):
    """Tracker que gestiona múltiples objetos con matching de detecciones."""

    name = "multi_object_tracker"

    def __init__(
        self,
        enabled: bool = True,
        max_distance: float = 50.0,
        max_age: int = 30,
    ) -> None:
        """
        Inicializa el tracker multi-objeto.

        Args:
            enabled: Si el tracker está habilitado
            max_distance: Distancia máxima para asociar detección con trayectoria
            max_age: Edad máxima de una trayectoria sin actualizaciones antes de eliminarla
        """
        super().__init__(enabled)
        self.max_distance = max_distance
        self.max_age = max_age
        self._next_id = 0

    def _calculate_distance(self, point1: tuple, point2: tuple) -> float:
        """Calcula la distancia euclidiana entre dos puntos."""
        return np.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

    def _match_detections_to_trajectories(
        self, detections: List[dict], timestamp: float
    ) -> Dict[str, dict]:
        """
        Asocia detecciones con trayectorias existentes usando distancia.

        Args:
            detections: Lista de detecciones
            timestamp: Timestamp del frame

        Returns:
            Diccionario mapeando object_id a detección
        """
        matches: Dict[str, dict] = {}
        used_trajectories = set()

        # Ordenar detecciones por confianza (mayor primero)
        sorted_detections = sorted(
            detections, key=lambda d: d.get("confidence", 0.0), reverse=True
        )

        for det in sorted_detections:
            if "bbox" not in det:
                continue

            bbox = det["bbox"]
            center = (bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2)
            best_match_id = None
            best_distance = self.max_distance

            # Buscar trayectoria más cercana
            for obj_id, traj in self._trajectories.items():
                if obj_id in used_trajectories or traj.lost:
                    continue

                latest_point = traj.get_latest_point()
                if latest_point:
                    distance = self._calculate_distance(
                        center, (latest_point.x, latest_point.y)
                    )
                    if distance < best_distance:
                        best_distance = distance
                        best_match_id = obj_id

            if best_match_id:
                matches[best_match_id] = det
                used_trajectories.add(best_match_id)
            else:
                # Nueva detección, crear nueva trayectoria
                new_id = f"obj_{self._next_id}"
                self._next_id += 1
                matches[new_id] = det

        return matches

    def track(
        self, frame: np.ndarray, detections: dict, config: EngineConfig
    ) -> TrackingData:
        """
        Trackea múltiples objetos simultáneamente.

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

        # Recopilar todas las detecciones
        all_detections: List[dict] = []
        for analyzer_name, detection_data in detections.items():
            if isinstance(detection_data, dict) and "detections" in detection_data:
                for det in detection_data["detections"]:
                    det_copy = det.copy()
                    det_copy["analyzer_name"] = analyzer_name
                    all_detections.append(det_copy)

        # Asociar detecciones con trayectorias
        matches = self._match_detections_to_trajectories(all_detections, timestamp)

        # Actualizar trayectorias existentes y crear nuevas
        for obj_id, det in matches.items():
            bbox = det["bbox"]
            x = bbox[0] + bbox[2] / 2
            y = bbox[1] + bbox[3] / 2

            if obj_id in self._trajectories:
                # Actualizar trayectoria existente
                self._trajectories[obj_id].add_point(
                    x, y, timestamp, det.get("confidence", 1.0)
                )
                self._trajectories[obj_id].bbox = bbox
                self._trajectories[obj_id].lost = False
            else:
                # Crear nueva trayectoria
                traj = Trajectory(
                    object_id=obj_id,
                    label=det.get("label", det.get("analyzer_name", "unknown")),
                )
                traj.add_point(x, y, timestamp, det.get("confidence", 1.0))
                traj.bbox = bbox
                self._trajectories[obj_id] = traj

        # Marcar trayectorias sin actualizaciones como perdidas o eliminarlas
        objects_to_remove = []
        for obj_id, traj in self._trajectories.items():
            if obj_id not in matches:
                traj.age += 1
                if traj.age > self.max_age:
                    objects_to_remove.append(obj_id)
                elif traj.age > 5:  # Marcar como perdida después de 5 frames
                    traj.lost = True

        # Eliminar trayectorias muy antiguas
        for obj_id in objects_to_remove:
            if obj_id in self._trajectories:
                del self._trajectories[obj_id]

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
        super().reset()
        self._next_id = 0

