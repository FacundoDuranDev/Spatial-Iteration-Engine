"""Filtro de brillo y contraste que delega en C++ (filters_cpp)."""

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


class CppBrightnessContrastFilter(BaseFilter):
    """Ajuste lineal de brillo y contraste vía módulo C++."""

    name = "cpp_brightness_contrast"
    enabled = True

    def __init__(
        self,
        enabled: bool = True,
        brightness_delta: Optional[int] = None,
        contrast_factor: Optional[float] = None,
    ) -> None:
        super().__init__(enabled=enabled)
        self._brightness_delta = brightness_delta
        self._contrast_factor = contrast_factor

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
        delta = self._brightness_delta if self._brightness_delta is not None else getattr(config, "brightness", 0)
        factor = self._contrast_factor if self._contrast_factor is not None else getattr(config, "contrast", 1.2)
        out = np.asarray(frame, dtype=np.uint8).copy(order="C")
        _filters_cpp.apply_brightness_contrast(out, int(delta), float(factor))
        return out
