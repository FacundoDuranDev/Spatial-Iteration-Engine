"""Módulo de tracking de objetos."""

from .base import BaseTracker
from .kalman_tracker import KalmanTracker
from .multi_object_tracker import MultiObjectTracker
from .opencv_tracker import OpenCVTracker
# TrackingPipeline: implementación única en application.pipeline
from ...application.pipeline import TrackingPipeline

__all__ = [
    "BaseTracker",
    "OpenCVTracker",
    "KalmanTracker",
    "MultiObjectTracker",
    "TrackingPipeline",
]

