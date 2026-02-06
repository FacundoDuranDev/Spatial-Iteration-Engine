"""Ajuste dinámico de calidad basado en rendimiento."""

import logging
import time
from collections import deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class AdaptiveQuality:
    """Ajusta dinámicamente la calidad/resolución basándose en el rendimiento."""

    def __init__(
        self,
        target_fps: float = 30.0,
        min_quality: float = 0.5,
        max_quality: float = 1.0,
        quality_step: float = 0.1,
        history_size: int = 10,
    ) -> None:
        """
        Inicializa el ajustador de calidad adaptativo.

        Args:
            target_fps: FPS objetivo
            min_quality: Calidad mínima (0.0-1.0)
            max_quality: Calidad máxima (0.0-1.0)
            quality_step: Paso de ajuste de calidad
            history_size: Tamaño del historial de FPS
        """
        self.target_fps = target_fps
        self.min_quality = min(min_quality, max_quality)
        self.max_quality = max(min_quality, max_quality)
        self.quality_step = quality_step
        self.current_quality = max_quality
        self._fps_history = deque(maxlen=history_size)
        self._last_frame_time = None

    def update_frame_time(self, frame_time: float) -> None:
        """
        Actualiza el tiempo de procesamiento del frame.

        Args:
            frame_time: Tiempo de procesamiento en segundos
        """
        if frame_time > 0:
            fps = 1.0 / frame_time
            self._fps_history.append(fps)

    def adjust_quality(self) -> float:
        """
        Ajusta la calidad basándose en el rendimiento actual.

        Returns:
            Nueva calidad (0.0-1.0)
        """
        if len(self._fps_history) < 3:
            return self.current_quality

        avg_fps = sum(self._fps_history) / len(self._fps_history)

        if avg_fps < self.target_fps * 0.9:
            # FPS bajo, reducir calidad
            new_quality = max(
                self.min_quality,
                self.current_quality - self.quality_step,
            )
            if new_quality != self.current_quality:
                logger.debug(f"Reduciendo calidad: {self.current_quality:.2f} -> {new_quality:.2f} (FPS: {avg_fps:.1f})")
                self.current_quality = new_quality
        elif avg_fps > self.target_fps * 1.1:
            # FPS alto, aumentar calidad
            new_quality = min(
                self.max_quality,
                self.current_quality + self.quality_step,
            )
            if new_quality != self.current_quality:
                logger.debug(f"Aumentando calidad: {self.current_quality:.2f} -> {new_quality:.2f} (FPS: {avg_fps:.1f})")
                self.current_quality = new_quality

        return self.current_quality

    def get_resolution_scale(self) -> float:
        """
        Obtiene el factor de escala de resolución basado en la calidad actual.

        Returns:
            Factor de escala (0.0-1.0)
        """
        return self.current_quality

    def get_target_resolution(self, base_width: int, base_height: int) -> Tuple[int, int]:
        """
        Calcula la resolución objetivo basada en la calidad actual.

        Args:
            base_width: Ancho base
            base_height: Alto base

        Returns:
            Tupla (width, height) escalada
        """
        scale = self.get_resolution_scale()
        return (
            int(base_width * scale),
            int(base_height * scale),
        )

    def reset(self) -> None:
        """Resetea el ajustador a la calidad máxima."""
        self.current_quality = self.max_quality
        self._fps_history.clear()
        self._last_frame_time = None

    def get_stats(self) -> dict:
        """Obtiene estadísticas del ajustador."""
        if len(self._fps_history) == 0:
            return {
                "current_quality": self.current_quality,
                "avg_fps": 0.0,
                "target_fps": self.target_fps,
            }

        return {
            "current_quality": self.current_quality,
            "avg_fps": sum(self._fps_history) / len(self._fps_history),
            "min_fps": min(self._fps_history),
            "max_fps": max(self._fps_history),
            "target_fps": self.target_fps,
        }

