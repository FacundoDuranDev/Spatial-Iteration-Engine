"""Lógica de frame skipping adaptativo."""

import logging
import time
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class FrameSkipper:
    """Salta frames cuando el procesamiento es lento."""

    def __init__(
        self,
        target_fps: float = 30.0,
        max_skip: int = 3,
        history_size: int = 10,
        skip_threshold: float = 0.8,
    ) -> None:
        """
        Inicializa el frame skipper.

        Args:
            target_fps: FPS objetivo
            max_skip: Número máximo de frames a saltar consecutivamente
            history_size: Tamaño del historial de tiempos de procesamiento
            skip_threshold: Umbral de tiempo de procesamiento para activar skip (fracción del tiempo de frame)
        """
        self.target_fps = target_fps
        self.max_skip = max_skip
        self.skip_threshold = skip_threshold
        self.frame_time = 1.0 / target_fps
        self._processing_times = deque(maxlen=history_size)
        self._consecutive_skips = 0
        self._total_skipped = 0
        self._total_processed = 0

    def should_skip(self, processing_time: float) -> bool:
        """
        Determina si se debe saltar el siguiente frame.

        Args:
            processing_time: Tiempo de procesamiento del frame actual

        Returns:
            True si se debe saltar el frame
        """
        self._processing_times.append(processing_time)
        self._total_processed += 1

        if len(self._processing_times) < 3:
            return False

        avg_processing_time = sum(self._processing_times) / len(self._processing_times)
        threshold_time = self.frame_time * self.skip_threshold

        # Si el tiempo promedio de procesamiento es mayor que el umbral
        if avg_processing_time > threshold_time:
            if self._consecutive_skips < self.max_skip:
                self._consecutive_skips += 1
                self._total_skipped += 1
                logger.debug(
                    f"Saltando frame (avg_time: {avg_processing_time:.3f}s, "
                    f"threshold: {threshold_time:.3f}s, "
                    f"consecutive_skips: {self._consecutive_skips})"
                )
                return True
            else:
                # Resetear contador si alcanzamos el máximo
                self._consecutive_skips = 0
        else:
            # Resetear contador si el procesamiento es rápido
            self._consecutive_skips = 0

        return False

    def reset(self) -> None:
        """Resetea el frame skipper."""
        self._processing_times.clear()
        self._consecutive_skips = 0
        self._total_skipped = 0
        self._total_processed = 0

    def get_skip_rate(self) -> float:
        """
        Obtiene la tasa de frames saltados.

        Returns:
            Tasa de skip (0.0-1.0)
        """
        if self._total_processed == 0:
            return 0.0
        return self._total_skipped / self._total_processed

    def get_stats(self) -> dict:
        """Obtiene estadísticas del frame skipper."""
        avg_processing_time = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times
            else 0.0
        )

        return {
            "total_processed": self._total_processed,
            "total_skipped": self._total_skipped,
            "skip_rate": self.get_skip_rate(),
            "consecutive_skips": self._consecutive_skips,
            "avg_processing_time": avg_processing_time,
            "target_fps": self.target_fps,
            "frame_time": self.frame_time,
        }
