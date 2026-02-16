"""Segmentación de silueta / máscara de persona (stub)."""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig


class SilhouetteSegmentationAnalyzer:
    """Analizador que produce máscara de persona (silueta).

    Implementa el protocolo Analyzer. El resultado se usa en analysis["person_mask"].
    Stub: devuelve máscara vacía (zeros); TODO: modelo de segmentación ONNX.
    """

    name = "silhouette_segmentation"
    enabled = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        """Devuelve máscara binaria HxW (persona = 255, fondo = 0)."""
        h, w = frame.shape[:2]
        # Stub: máscara vacía
        # TODO: segmentación ONNX (person mask)
        person_mask = np.zeros((h, w), dtype=np.uint8)
        return {"person_mask": person_mask}
