"""Adaptador que implementa FrameSource usando generadores."""

from typing import Optional

import numpy as np

from ...ports.sources import FrameSource
from .base import BaseContentGenerator


class GeneratorSource(FrameSource):
    """Fuente de frames usando un generador de contenido."""

    def __init__(
        self,
        generator: BaseContentGenerator,
        width: int = 640,
        height: int = 480,
    ) -> None:
        """
        Inicializa la fuente generadora.

        Args:
            generator: Generador de contenido
            width: Ancho de los frames
            height: Alto de los frames
        """
        self.generator = generator
        self.width = width
        self.height = height
        self._open = False
        self._last_time = 0.0
        import time
        self._time_module = time
        self._start_time = time.time()

    def open(self) -> None:
        """Abre la fuente."""
        self._open = True
        self._start_time = self._time_module.time()
        self._last_time = 0.0

    def read(self) -> Optional[np.ndarray]:
        """Lee un frame generado."""
        if not self._open:
            return None

        current_time = self._time_module.time() - self._start_time
        delta_time = current_time - self._last_time
        self._last_time = current_time

        self.generator.update(delta_time)
        frame = self.generator.generate(self.width, self.height, current_time)

        return frame

    def close(self) -> None:
        """Cierra la fuente."""
        self._open = False

