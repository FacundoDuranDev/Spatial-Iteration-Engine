"""Filtro escala de grises (luma) que delega en C++ (filters_cpp)."""

from typing import Optional

import numpy as np

from ....domain.config import EngineConfig
from .base import BaseFilter

try:
    import filters_cpp as _filters_cpp
    _CPP_AVAILABLE = True
except ImportError:
    _filters_cpp = None
    _CPP_AVAILABLE = False


class CppGrayscaleFilter(BaseFilter):
    """Grayscale / Luma; salida sigue siendo 3 canales BGR, vía C++."""

    name = "cpp_grayscale"
    enabled = True

    @property
    def cpp_available(self) -> bool:
        return _CPP_AVAILABLE

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if not _CPP_AVAILABLE:
            return frame.copy()
        out = np.asarray(frame, dtype=np.uint8).copy(order="C")
        _filters_cpp.apply_grayscale(out)
        return out
