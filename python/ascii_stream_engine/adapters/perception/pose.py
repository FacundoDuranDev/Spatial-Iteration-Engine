"""Analizador de pose corporal (C++ perception_cpp). MVP_03."""

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


class PoseLandmarkAnalyzer(BaseAnalyzer):
    """Pose corporal (33 joints). Delega en perception_cpp.detect_pose."""

    name = "pose"
    enabled = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None:
            return {}
        try:
            out = _perception_cpp.detect_pose(frame)
            if out is None or out.size == 0:
                return {}
            # Normalizar coordenadas de píxeles absolutos a 0-1
            # El modelo YOLOv8 devuelve coordenadas en píxeles, pero el renderer espera 0-1
            h, w = frame.shape[:2]
            if h > 0 and w > 0:
                out[:, 0] /= w
                out[:, 1] /= h
                np.clip(out, 0.0, 1.0, out=out)
            return {"joints": out}
        except Exception:
            return {}
