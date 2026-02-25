"""Clase base para generadores de contenido."""

import time

import numpy as np


class BaseContentGenerator:
    """Clase base para generadores de contenido procedural."""

    name = "base_generator"

    def __init__(self) -> None:
        """Inicializa el generador."""
        self._start_time = time.time()
        self._last_update_time = self._start_time

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
        # Implementación básica: frame negro
        return np.zeros((height, width, 3), dtype=np.uint8)

    def update(self, delta_time: float) -> None:
        """
        Actualiza el estado del generador.

        Args:
            delta_time: Tiempo transcurrido desde la última actualización
        """
        self._last_update_time += delta_time

    def get_time(self) -> float:
        """Obtiene el tiempo transcurrido desde el inicio."""
        return time.time() - self._start_time
