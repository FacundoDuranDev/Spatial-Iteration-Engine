"""Blending de múltiples fuentes."""

import cv2
import numpy as np

from .base import BaseSpatialTransform


class BlendTransformer(BaseSpatialTransform):
    """Combina múltiples fuentes de video."""

    name = "blend_transformer"

    def __init__(self, blend_mode: str = "alpha") -> None:
        """
        Inicializa el transformador de blending.

        Args:
            blend_mode: Modo de blending ("alpha", "add", "multiply", "screen")
        """
        self.blend_mode = blend_mode
        self._sources: list[np.ndarray] = []
        self._weights: list[float] = []

    def add_source(self, source: np.ndarray, weight: float = 1.0) -> None:
        """
        Agrega una fuente para blending.

        Args:
            source: Frame fuente
            weight: Peso de la fuente (0.0-1.0)
        """
        self._sources.append(source)
        self._weights.append(weight)

    def clear_sources(self) -> None:
        """Limpia todas las fuentes."""
        self._sources.clear()
        self._weights.clear()

    def transform(self, frame: np.ndarray) -> np.ndarray:
        """Aplica el blending."""
        if not self._sources:
            return frame

        result = frame.copy().astype(np.float32)

        for source, weight in zip(self._sources, self._weights):
            # Redimensionar fuente si es necesario
            if source.shape != frame.shape:
                source = cv2.resize(source, (frame.shape[1], frame.shape[0]))

            source_float = source.astype(np.float32)

            if self.blend_mode == "alpha":
                result = cv2.addWeighted(result, 1.0 - weight, source_float, weight, 0)
            elif self.blend_mode == "add":
                result = np.clip(result + source_float * weight, 0, 255)
            elif self.blend_mode == "multiply":
                result = np.clip(result * (1.0 + source_float / 255.0 * weight), 0, 255)
            elif self.blend_mode == "screen":
                result = 255 - np.clip(
                    (255 - result) * (255 - source_float) / 255.0 * weight, 0, 255
                )

        return result.astype(np.uint8)

    def inverse(self, frame: np.ndarray) -> np.ndarray:
        """Blending no tiene inverso, retorna frame original."""
        return frame
