"""Módulo de tracking de objetos."""

# TrackingPipeline: implementación única en application.pipeline
from ...application.pipeline import TrackingPipeline
from .base import BaseTracker
from .kalman_tracker import KalmanTracker
from .multi_object_tracker import MultiObjectTracker
from .opencv_tracker import OpenCVTracker

__all__ = [
    "BaseTracker",
    "OpenCVTracker",
    "KalmanTracker",
    "MultiObjectTracker",
    "TrackingPipeline",
]
