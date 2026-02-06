"""Tracker usando filtro de Kalman para suavizado de trayectorias."""

import time
from typing import Dict, Optional

import cv2
import numpy as np

from ...domain.config import EngineConfig
from ...domain.tracking_data import TrackingData, Trajectory

from .base import BaseTracker


class KalmanTracker(BaseTracker):
    """Tracker con filtro de Kalman para suavizado."""

    name = "kalman_tracker"

    def __init__(
        self,
        enabled: bool = True,
        process_noise: float = 0.03,
        measurement_noise: float = 0.3,
    ) -> None:
        """
        Inicializa el tracker Kalman.

        Args:
            enabled: Si el tracker está habilitado
            process_noise: Ruido del proceso (Q)
            measurement_noise: Ruido de medición (R)
        """
        super().__init__(enabled)
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self._kalman_filters: Dict[str, cv2.KalmanFilter] = {}
        self._initialized: Dict[str, bool] = {}

    def _create_kalman_filter(self) -> cv2.KalmanFilter:
        """Crea un filtro de Kalman para tracking 2D."""
        kf = cv2.KalmanFilter(4, 2)  # 4 estados (x, y, vx, vy), 2 mediciones (x, y)

        # Matriz de transición (modelo de velocidad constante)
        kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
        )

        # Matriz de medición (solo medimos posición)
        kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)

        # Covarianza del proceso
        kf.processNoiseCov = (
            np.eye(4, dtype=np.float32) * self.process_noise
        )

        # Covarianza de medición
        kf.measurementNoiseCov = (
            np.eye(2, dtype=np.float32) * self.measurement_noise
        )

        # Covarianza del error a posteriori
        kf.errorCovPost = np.eye(4, dtype=np.float32)

        return kf

    def track(
        self, frame: np.ndarray, detections: dict, config: EngineConfig
    ) -> TrackingData:
        """
        Trackea objetos usando filtro de Kalman.

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

        # Procesar detecciones
        for analyzer_name, detection_data in detections.items():
            if isinstance(detection_data, dict) and "detections" in detection_data:
                for det in detection_data["detections"]:
                    if "bbox" in det:
                        bbox = det["bbox"]
                        x = bbox[0] + bbox[2] / 2  # Centro x
                        y = bbox[1] + bbox[3] / 2  # Centro y
                        obj_id = f"{analyzer_name}_{det.get('class_id', len(self._kalman_filters))}"

                        # Crear filtro de Kalman si no existe
                        if obj_id not in self._kalman_filters:
                            kf = self._create_kalman_filter()
                            kf.statePre = np.array([x, y, 0, 0], dtype=np.float32)
                            kf.statePost = np.array([x, y, 0, 0], dtype=np.float32)
                            self._kalman_filters[obj_id] = kf
                            self._initialized[obj_id] = True

                            # Crear trayectoria inicial
                            if obj_id not in self._trajectories:
                                traj = Trajectory(
                                    object_id=obj_id,
                                    label=det.get("label", analyzer_name),
                                )
                                traj.add_point(x, y, timestamp, det.get("confidence", 1.0))
                                traj.bbox = bbox
                                self._trajectories[obj_id] = traj

                        # Actualizar filtro de Kalman
                        kf = self._kalman_filters[obj_id]
                        measurement = np.array([[x], [y]], dtype=np.float32)

                        # Predicción
                        prediction = kf.predict()

                        # Corrección
                        kf.correct(measurement)

                        # Obtener estado estimado (suavizado)
                        state = kf.statePost
                        smoothed_x = float(state[0])
                        smoothed_y = float(state[1])
                        velocity_x = float(state[2])
                        velocity_y = float(state[3])

                        # Actualizar trayectoria
                        if obj_id in self._trajectories:
                            self._trajectories[obj_id].add_point(
                                smoothed_x, smoothed_y, timestamp, det.get("confidence", 1.0)
                            )
                            self._trajectories[obj_id].bbox = bbox
                            self._trajectories[obj_id].velocity = (velocity_x, velocity_y)
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
        super().reset()
        self._kalman_filters.clear()
        self._initialized.clear()

