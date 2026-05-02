"""SignalSources — adaptadores que traducen analysis dicts a señales del bus.

Hoy: MediaPipeSignalSource (face + hands).
Futuro: KinectSignalSource (body.* skeleton + depth), AudioSignalSource
(BPM / onset / RMS), MoveNetSignalSource (body.* sin Kinect).

El contrato `SignalSource` permite que el ModulationEngine sea agnóstico
del origen del tracking — sumar Kinect mañana es agregar un nuevo source
acá y registrarlo en `engine.py`. Cero cambios en el bus o el engine de
modulación.
"""
from .base import SignalSource
from .mediapipe_source import MediaPipeSignalSource

__all__ = ["SignalSource", "MediaPipeSignalSource"]
