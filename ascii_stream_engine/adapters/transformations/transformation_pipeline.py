"""Pipeline de transformaciones espaciales."""

from typing import List

import numpy as np

from .base import BaseSpatialTransform


class TransformationPipeline:
    """Pipeline para aplicar múltiples transformaciones."""

    def __init__(self, transforms: List[BaseSpatialTransform] = None) -> None:
        """
        Inicializa el pipeline.

        Args:
            transforms: Lista de transformaciones
        """
        self._transforms: List[BaseSpatialTransform] = transforms or []

    def add_transform(self, transform: BaseSpatialTransform) -> None:
        """Agrega una transformación al pipeline."""
        self._transforms.append(transform)

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica todas las transformaciones en secuencia.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado
        """
        result = frame
        for transform in self._transforms:
            result = transform.transform(result)
        return result

    def apply_inverse(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica todas las transformaciones inversas en orden reverso.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado inversamente
        """
        result = frame
        for transform in reversed(self._transforms):
            result = transform.inverse(result)
        return result

