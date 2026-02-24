"""Filtro de intercambio de canales que delega en C++ (filters_cpp)."""

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


class CppChannelSwapFilter(BaseFilter):
    """Permutación de canales BGR; (2,1,0) = BGR -> RGB."""

    name = "cpp_channel_swap"
    enabled = True

    def __init__(
        self,
        enabled: bool = True,
        dst_for_b: int = 2,
        dst_for_g: int = 1,
        dst_for_r: int = 0,
    ) -> None:
        super().__init__(enabled=enabled)
        self._perm = (dst_for_b, dst_for_g, dst_for_r)

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
        _filters_cpp.apply_channel_swap(out, self._perm[0], self._perm[1], self._perm[2])
        return out
