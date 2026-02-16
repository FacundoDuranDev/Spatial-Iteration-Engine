"""Estimación de pose (stub)."""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig


class PoseEstimationAnalyzer:
    """Analizador que estima pose (keypoints) en el frame.

    Implementa el protocolo Analyzer.
    Stub: devuelve vacío; TODO: MediaPipe Pose o ONNX.
    """

    name = "pose_estimation"
    enabled = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        """Estima pose y devuelve keypoints."""
        # TODO: MediaPipe Pose o ONNX
        return {"keypoints": [], "persons": []}
