"""Protocolo para transformaciones espaciales."""

from typing import Protocol, Tuple

import numpy as np


class SpatialTransform(Protocol):
    """Protocolo para transformaciones espaciales."""

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

