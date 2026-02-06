"""Tracker usando OpenCV trackers (CSRT, KCF, etc.)."""

import time
from typing import Dict, Optional

import cv2
import numpy as np

from ...domain.config import EngineConfig
from ...domain.tracking_data import TrackingData, Trajectory

from .base import BaseTracker


class OpenCVTracker(BaseTracker):
    """Tracker usando algoritmos de OpenCV."""

    name = "opencv_tracker"

    def __init__(
        self,
        tracker_type: str = "CSRT",
        enabled: bool = True,
        max_lost_frames: int = 10,
    ) -> None:
        """
        Inicializa el tracker OpenCV.

        Args:
            tracker_type: Tipo de tracker ("CSRT", "KCF", "MOSSE", "MIL")
            enabled: Si el tracker está habilitado
            max_lost_frames: Número máximo de frames sin detección antes de marcar como perdido
        """
        super().__init__(enabled)
        self.tracker_type = tracker_type
        self.max_lost_frames = max_lost_frames
        self._trackers: Dict[str, cv2.Tracker] = {}
        self._lost_frames: Dict[str, int] = {}

    def _create_tracker(self) -> cv2.Tracker:
        """Crea un tracker OpenCV del tipo especificado."""
        tracker_map = {
            "CSRT": cv2.TrackerCSRT_create,
            "KCF": cv2.TrackerKCF_create,
            "MOSSE": cv2.TrackerMOSSE_create,
            "MIL": cv2.TrackerMIL_create,
        }

        create_func = tracker_map.get(self.tracker_type.upper(), cv2.TrackerCSRT_create)
        return create_func()

    def track(
        self, frame: np.ndarray, detections: dict, config: EngineConfig
    ) -> TrackingData:
        """
        Trackea objetos usando OpenCV trackers.

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

        # Convertir frame a formato adecuado si es necesario
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Inicializar nuevos trackers para detecciones sin tracker
        for analyzer_name, detection_data in detections.items():
            if isinstance(detection_data, dict) and "detections" in detection_data:
                for det in detection_data["detections"]:
                    if "bbox" in det:
                        bbox = det["bbox"]
                        obj_id = f"{analyzer_name}_{det.get('class_id', len(self._trackers))}"

                        if obj_id not in self._trackers:
                            tracker = self._create_tracker()
                            # OpenCV espera bbox como (x, y, width, height)
                            tracker.init(frame, tuple(bbox))
                            self._trackers[obj_id] = tracker
                            self._lost_frames[obj_id] = 0

                            # Crear trayectoria inicial
                            if obj_id not in self._trajectories:
                                x = bbox[0] + bbox[2] / 2
                                y = bbox[1] + bbox[3] / 2
                                traj = Trajectory(
                                    object_id=obj_id,
                                    label=det.get("label", analyzer_name),
                                )
                                traj.add_point(x, y, timestamp, det.get("confidence", 1.0))
                                traj.bbox = bbox
                                self._trajectories[obj_id] = traj

        # Actualizar trackers existentes
        objects_to_remove = []
        for obj_id, tracker in self._trackers.items():
            success, bbox = tracker.update(frame)
            if success and bbox:
                x = bbox[0] + bbox[2] / 2
                y = bbox[1] + bbox[3] / 2
                if obj_id in self._trajectories:
                    self._trajectories[obj_id].add_point(x, y, timestamp, 1.0)
                    self._trajectories[obj_id].bbox = tuple(bbox)
                    self._trajectories[obj_id].lost = False
                self._lost_frames[obj_id] = 0
            else:
                self._lost_frames[obj_id] = self._lost_frames.get(obj_id, 0) + 1
                if obj_id in self._trajectories:
                    self._trajectories[obj_id].lost = (
                        self._lost_frames[obj_id] >= self.max_lost_frames
                    )
                if self._lost_frames[obj_id] >= self.max_lost_frames:
                    objects_to_remove.append(obj_id)

        # Remover objetos perdidos
        for obj_id in objects_to_remove:
            if obj_id in self._trackers:
                del self._trackers[obj_id]
            if obj_id in self._lost_frames:
                del self._lost_frames[obj_id]

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
        self._trackers.clear()
        self._lost_frames.clear()

