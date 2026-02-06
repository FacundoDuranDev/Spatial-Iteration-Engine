"""Protocolo para transformaciones espaciales."""

from typing import Optional, Protocol

import numpy as np


class SpatialTransform(Protocol):
    """Protocolo para transformaciones espaciales.
    
    Las transformaciones espaciales modifican la geometría del frame,
    como rotaciones, escalados, warping, corrección de perspectiva, etc.
    """

    name: str
    """Nombre único de la transformación."""

    def transform(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica la transformación.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado
        """
        ...

    def inverse(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica la transformación inversa.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado inversamente
        """
        ...

    def validate(self, frame: np.ndarray) -> bool:
        """
        Valida si la transformación puede aplicarse al frame.

        Args:
            frame: Frame a validar

        Returns:
            True si la transformación es válida para este frame
        """
        ...

    def get_transform_matrix(self) -> Optional[np.ndarray]:
        """
        Obtiene la matriz de transformación si está disponible.

        Returns:
            Matriz de transformación o None si no está disponible
        """
        ...

