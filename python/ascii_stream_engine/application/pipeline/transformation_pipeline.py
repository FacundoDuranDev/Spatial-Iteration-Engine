"""Pipeline para transformaciones espaciales."""

from typing import Iterable, List, Optional

import numpy as np

from ...ports.transformations import SpatialTransform


class TransformationPipeline:
    """Pipeline para aplicar múltiples transformaciones espaciales en secuencia.

    Las transformaciones espaciales modifican la geometría del frame,
    como rotaciones, escalados, warping, corrección de perspectiva, etc.
    """

    def __init__(self, transforms: Optional[Iterable[SpatialTransform]] = None) -> None:
        """
        Inicializa el pipeline.

        Args:
            transforms: Lista de transformaciones
        """
        self._transforms: List[SpatialTransform] = list(transforms) if transforms else []

    @property
    def transforms(self) -> List[SpatialTransform]:
        """Obtiene la lista de transformaciones."""
        return self._transforms

    def add_transform(self, transform: SpatialTransform) -> None:
        """Agrega una transformación al pipeline."""
        self._transforms.append(transform)

    def add(self, transform: SpatialTransform) -> None:
        """Agrega una transformación al pipeline (alias de add_transform)."""
        self.add_transform(transform)

    def remove(self, transform: SpatialTransform) -> None:
        """Remueve una transformación del pipeline."""
        self._transforms.remove(transform)

    def clear(self) -> None:
        """Limpia todas las transformaciones del pipeline."""
        self._transforms.clear()

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
