"""Generador de patrones (Turing patterns, reacciones-difusión, etc.)."""

from typing import Optional

import numpy as np

from .base import BaseContentGenerator


class PatternGenerator(BaseContentGenerator):
    """Genera patrones procedurales."""

    name = "pattern_generator"

    def __init__(
        self,
        pattern_type: str = "turing",
        speed: float = 1.0,
    ) -> None:
        """
        Inicializa el generador de patrones.

        Args:
            pattern_type: Tipo de patrón ("turing", "reaction_diffusion", "noise")
            speed: Velocidad de animación
        """
        super().__init__()
        self.pattern_type = pattern_type
        self.speed = speed
        self._state: Optional[np.ndarray] = None

    def generate(self, width: int, height: int, time: float) -> np.ndarray:
        """Genera un frame con patrón."""
        if self._state is None or self._state.shape[:2] != (height, width):
            self._state = np.random.rand(height, width).astype(np.float32)

        t = time * self.speed

        if self.pattern_type == "turing":
            return self._generate_turing_pattern(width, height, t)
        elif self.pattern_type == "reaction_diffusion":
            return self._generate_reaction_diffusion(width, height, t)
        elif self.pattern_type == "noise":
            return self._generate_noise_pattern(width, height, t)
        else:
            return np.zeros((height, width, 3), dtype=np.uint8)

    def _generate_turing_pattern(self, width: int, height: int, time: float) -> np.ndarray:
        """Genera patrón de Turing."""
        x = np.linspace(0, 4 * np.pi, width)
        y = np.linspace(0, 4 * np.pi, height)
        X, Y = np.meshgrid(x, y)

        pattern = np.sin(X + time) * np.cos(Y + time * 0.5)
        pattern = (pattern + 1) / 2  # Normalizar a 0-1
        pattern = (pattern * 255).astype(np.uint8)

        return np.stack([pattern, pattern, pattern], axis=2)

    def _generate_reaction_diffusion(self, width: int, height: int, time: float) -> np.ndarray:
        """Genera patrón de reacción-difusión simplificado."""
        x = np.linspace(0, 2 * np.pi, width)
        y = np.linspace(0, 2 * np.pi, height)
        X, Y = np.meshgrid(x, y)

        pattern = np.sin(X * 2 + time) * np.cos(Y * 2 + time * 0.7)
        pattern = (pattern + 1) / 2
        pattern = (pattern * 255).astype(np.uint8)

        return np.stack([pattern, pattern, pattern], axis=2)

    def _generate_noise_pattern(self, width: int, height: int, time: float) -> np.ndarray:
        """Genera patrón de ruido."""
        np.random.seed(int(time * 1000) % 1000000)
        noise = np.random.rand(height, width)
        noise = (noise * 255).astype(np.uint8)

        return np.stack([noise, noise, noise], axis=2)
