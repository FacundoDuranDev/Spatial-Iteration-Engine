"""Analizador de landmarks faciales (C++ perception_cpp). MVP_03."""

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


class FaceLandmarkAnalyzer(BaseAnalyzer):
    """Landmarks faciales (~468 puntos). Delega en perception_cpp.detect_face."""

    name = "face"
    enabled = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None:
            return {}
        try:
            out = _perception_cpp.detect_face(frame)
            if out is None or out.size == 0:
                return {}
            return {"points": out}
        except Exception:
            return {}
