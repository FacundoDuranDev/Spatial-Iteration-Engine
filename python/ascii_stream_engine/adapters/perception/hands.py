"""Analizador de landmarks de manos (C++ perception_cpp). MVP_03."""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer

try:
    import perception_cpp as _perception_cpp
    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False


class HandLandmarkAnalyzer(BaseAnalyzer):
    """Landmarks de manos (21 por mano). Delega en perception_cpp.detect_hands."""

    name = "hands"
    enabled = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None:
            return {}
        try:
            out = _perception_cpp.detect_hands(frame)
            if out is None or out.size == 0:
                return {}
            out = np.asarray(out, dtype=np.float32)
            if out.ndim != 2 or out.shape[0] == 0:
                return {}
            # Cuando C++ devuelva 42 puntos: left 21, right 21
            n = out.shape[0]
            if n >= 42:
                return {"left": out[:21], "right": out[21:42]}
            if n >= 21:
                return {"left": out[:21], "right": np.empty((0, 2), dtype=np.float32)}
            return {"left": out, "right": np.empty((0, 2), dtype=np.float32)}
        except Exception:
            return {}
