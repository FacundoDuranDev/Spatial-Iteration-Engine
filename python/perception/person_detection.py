"""Detección de personas (stub / adapter MediaPipe o ONNX)."""

from typing import Any, Dict, List

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig


class PersonDetectionAnalyzer:
    """Analizador que detecta personas en el frame (bbox/keypoints).

    Implementa el protocolo Analyzer: analyze(frame, config) -> dict.
    Stub: devuelve lista vacía; TODO: MediaPipe o modelo ONNX.
    """

    name = "person_detection"
    enabled = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        """Analiza el frame y devuelve detecciones de personas.

        Returns:
            Dict con clave "detections": lista de dicts con "bbox" (x,y,w,h)
            y opcionalmente "keypoints".
        """
        # TODO: MediaPipe o ONNX person detection
        return {"detections": []}
