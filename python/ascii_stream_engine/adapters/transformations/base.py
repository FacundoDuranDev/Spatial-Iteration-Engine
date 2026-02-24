"""Clase base para transformaciones espaciales."""

import numpy as np


class BaseSpatialTransform:
    """Clase base para transformaciones espaciales."""

    name = "base_transform"

    def transform(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica la transformación.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado
        """
        return frame

    def inverse(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica la transformación inversa.

        Args:
            frame: Frame a transformar

        Returns:
            Frame transformado inversamente
        """
        return frame
