"""Pipeline para trackers de objetos."""

import threading
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List, Optional

import numpy as np

from ...domain.config import EngineConfig
from ...domain.tracking_data import TrackingData
from ...ports.trackers import ObjectTracker


class TrackingPipeline:
    """Pipeline para ejecutar múltiples trackers en secuencia.

    Los trackers mantienen el seguimiento de objetos a través de múltiples frames,
    asociando detecciones con identidades persistentes y calculando trayectorias.
    """

    def __init__(self, trackers: Optional[Iterable[ObjectTracker]] = None) -> None:
        """
        Inicializa el pipeline de tracking.

        Args:
            trackers: Lista inicial de trackers
        """
        self._trackers: List[ObjectTracker] = list(trackers) if trackers else []
        self._lock = threading.Lock()

    @property
    def trackers(self) -> List[ObjectTracker]:
        """Obtiene la lista de trackers."""
        return self._trackers

    def snapshot(self) -> List[ObjectTracker]:
        """Obtiene una snapshot thread-safe de los trackers."""
        with self._lock:
            return list(self._trackers)

    def append(self, tracker: ObjectTracker) -> None:
        """Agrega un tracker al pipeline."""
        with self._lock:
            self._trackers.append(tracker)

    def extend(self, trackers: Iterable[ObjectTracker]) -> None:
        """Extiende el pipeline con múltiples trackers."""
        with self._lock:
            self._trackers.extend(trackers)

    def insert(self, index: int, tracker: ObjectTracker) -> None:
        """Inserta un tracker en una posición específica."""
        with self._lock:
            self._trackers.insert(index, tracker)

    def remove(self, tracker: ObjectTracker) -> None:
        """Remueve un tracker del pipeline."""
        with self._lock:
            self._trackers.remove(tracker)

    def pop(self, index: int = -1) -> ObjectTracker:
        """Remueve y retorna un tracker del pipeline."""
        with self._lock:
            return self._trackers.pop(index)

    def clear(self) -> None:
        """Limpia todos los trackers del pipeline."""
        with self._lock:
            self._trackers.clear()

    def replace(self, trackers: Iterable[ObjectTracker]) -> None:
        """Reemplaza todos los trackers."""
        with self._lock:
            self._trackers = list(trackers)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """
        Habilita o deshabilita un tracker por nombre.

        Args:
            name: Nombre del tracker
            enabled: Estado deseado

        Returns:
            True si se encontró y modificó el tracker
        """
        changed = False
        with self._lock:
            for tracker in self._trackers:
                tracker_name = getattr(tracker, "name", tracker.__class__.__name__)
                if tracker_name == name:
                    if hasattr(tracker, "enabled"):
                        tracker.enabled = enabled
                        changed = True
        return changed

    def has_any(self) -> bool:
        """Verifica si hay trackers en el pipeline."""
        with self._lock:
            return bool(self._trackers)

    def run(self, frame: np.ndarray, detections: dict, config: EngineConfig) -> TrackingData:
        """
        Ejecuta todos los trackers activos en el pipeline.

        Args:
            frame: Frame de video
            detections: Diccionario con detecciones de analizadores
            config: Configuración del engine

        Returns:
            TrackingData combinado de todos los trackers
        """
        trackers = self.snapshot()
        active_trackers = [t for t in trackers if getattr(t, "enabled", True)]

        if not active_trackers:
            return TrackingData(frame_id="", timestamp=0.0)

        # Ejecutar trackers y combinar resultados
        combined_trajectories: Dict[str, any] = {}
        total_processing_time = 0.0
        active_objects = 0
        lost_objects = 0

        for tracker in active_trackers:
            try:
                result = tracker.track(frame, detections, config)
                combined_trajectories.update(result.trajectories)
                total_processing_time += result.processing_time
                active_objects = max(active_objects, result.active_objects)
                lost_objects = max(lost_objects, result.lost_objects)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error ejecutando tracker '{tracker.name}': {e}", exc_info=True)

        # Crear TrackingData combinado
        return TrackingData(
            frame_id=result.frame_id if active_trackers else "",
            timestamp=result.timestamp if active_trackers else 0.0,
            trajectories=combined_trajectories,
            active_objects=active_objects,
            lost_objects=lost_objects,
            processing_time=total_processing_time,
        )

    @contextmanager
    def locked(self) -> Iterator[List[ObjectTracker]]:
        """Context manager para acceso thread-safe a los trackers."""
        with self._lock:
            yield self._trackers
