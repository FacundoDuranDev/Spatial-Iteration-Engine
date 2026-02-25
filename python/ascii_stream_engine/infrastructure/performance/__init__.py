"""Módulos de optimización de rendimiento."""

from .adaptive_quality import AdaptiveQuality
from .frame_skipper import FrameSkipper

# Importar acelerador GPU con manejo de dependencias opcionales
try:
    from .gpu_accelerator import GPUAccelerator

    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    GPUAccelerator = None  # type: ignore

__all__ = [
    "AdaptiveQuality",
    "FrameSkipper",
]

if GPU_AVAILABLE:
    __all__.append("GPUAccelerator")
