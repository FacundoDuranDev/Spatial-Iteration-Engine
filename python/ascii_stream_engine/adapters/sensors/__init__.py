"""Módulo de sensores."""

from .base import BaseSensor
from .sensor_fusion import SensorFusion

# Importar sensores con manejo de dependencias opcionales
try:
    from .audio_sensor import AudioSensor

    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    AudioSensor = None  # type: ignore

try:
    from .depth_sensor import DepthSensor

    DEPTH_AVAILABLE = True
except ImportError:
    DEPTH_AVAILABLE = False
    DepthSensor = None  # type: ignore

__all__ = [
    "BaseSensor",
    "SensorFusion",
]

if AUDIO_AVAILABLE:
    __all__.append("AudioSensor")

if DEPTH_AVAILABLE:
    __all__.append("DepthSensor")
