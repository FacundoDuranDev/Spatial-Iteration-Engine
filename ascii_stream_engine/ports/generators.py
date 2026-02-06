"""Protocolo para generadores de contenido procedural."""

from typing import Any, Dict, Protocol, Tuple

import numpy as np


class ContentGenerator(Protocol):
    """Protocolo para generadores de contenido."""

    def generate(self, width: int, height: int, time: float) -> np.ndarray:
        """
        Genera un frame de contenido.

        Args:
            width: Ancho del frame
            height: Alto del frame
            time: Tiempo en segundos

        Returns:
            Frame generado
        """
        ...

    def update(self, delta_time: float) -> None:
        """
        Actualiza el estado del generador.

        Args:
            delta_time: Tiempo transcurrido desde la última actualización
        """
        ...

