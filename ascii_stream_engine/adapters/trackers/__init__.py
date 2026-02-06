"""Módulo de tracking de objetos."""

from .base import BaseTracker
from .kalman_tracker import KalmanTracker
from .multi_object_tracker import MultiObjectTracker
from .opencv_tracker import OpenCVTracker
# TrackingPipeline se ha movido a application.pipeline
# Mantener import para compatibilidad hacia atrás
import warnings

try:
    from ...application.pipeline import TrackingPipeline
except ImportError:
    # Fallback al archivo local si no está disponible en application
    from .tracking_pipeline import TrackingPipeline
    warnings.warn(
        "Importar TrackingPipeline desde adapters.trackers está deprecado. "
        "Usa 'from ascii_stream_engine.application.pipeline import TrackingPipeline'.",
        DeprecationWarning,
        stacklevel=2,
    )

__all__ = [
    "BaseTracker",
    "OpenCVTracker",
    "KalmanTracker",
    "MultiObjectTracker",
    "TrackingPipeline",
]

