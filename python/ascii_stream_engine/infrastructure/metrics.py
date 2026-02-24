"""Sistema de métricas para monitoreo del engine.

Este módulo proporciona un sistema de métricas thread-safe para rastrear
el rendimiento y estado del engine, incluyendo FPS, frames procesados y errores.
"""

import threading
import time
from collections import defaultdict
from typing import Dict, Optional


class EngineMetrics:
    """Sistema de métricas thread-safe para el engine.

    Rastrea:
    - FPS (frames por segundo) real
    - Frames procesados totales
    - Errores por componente
    - Latencia promedio
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames_processed = 0
        self._errors: Dict[str, int] = defaultdict(int)
        self._frame_times: list[float] = []
        self._max_frame_times = 100  # Mantener solo los últimos 100 tiempos
        self._start_time: Optional[float] = None
        self._last_frame_time: Optional[float] = None

    def start(self) -> None:
        """Inicia el tracking de métricas."""
        with self._lock:
            self._start_time = time.perf_counter()
            self._frames_processed = 0
            self._errors.clear()
            self._frame_times.clear()
            self._last_frame_time = None

    def record_frame(self) -> None:
        """Registra que se procesó un frame."""
        current_time = time.perf_counter()
        with self._lock:
            self._frames_processed += 1
            if self._last_frame_time is not None:
                frame_duration = current_time - self._last_frame_time
                self._frame_times.append(frame_duration)
                # Mantener solo los últimos N tiempos para evitar crecimiento ilimitado
                if len(self._frame_times) > self._max_frame_times:
                    self._frame_times.pop(0)
            self._last_frame_time = current_time

    def record_error(self, component: str) -> None:
        """Registra un error en un componente específico.

        Args:
            component: Nombre del componente donde ocurrió el error
                      (ej: 'capture', 'analysis', 'filtering', 'rendering', 'writing')
        """
        with self._lock:
            self._errors[component] += 1

    def get_fps(self) -> float:
        """Calcula el FPS real basado en los tiempos de frame recientes.

        Returns:
            FPS promedio basado en los últimos frames procesados.
            Retorna 0.0 si no hay datos suficientes.
        """
        with self._lock:
            if not self._frame_times:
                return 0.0
            # Calcular FPS promedio basado en los tiempos de frame
            avg_frame_time = sum(self._frame_times) / len(self._frame_times)
            if avg_frame_time > 0:
                return 1.0 / avg_frame_time
            return 0.0

    def get_frames_processed(self) -> int:
        """Retorna el número total de frames procesados.

        Returns:
            Número total de frames procesados desde el inicio.
        """
        with self._lock:
            return self._frames_processed

    def get_errors(self) -> Dict[str, int]:
        """Retorna un diccionario con el conteo de errores por componente.

        Returns:
            Diccionario con componente como clave y número de errores como valor.
        """
        with self._lock:
            return dict(self._errors)

    def get_total_errors(self) -> int:
        """Retorna el número total de errores registrados.

        Returns:
            Suma de todos los errores de todos los componentes.
        """
        with self._lock:
            return sum(self._errors.values())

    def get_latency_avg(self) -> float:
        """Calcula la latencia promedio por frame en segundos.

        Returns:
            Latencia promedio en segundos. Retorna 0.0 si no hay datos.
        """
        with self._lock:
            if not self._frame_times:
                return 0.0
            return sum(self._frame_times) / len(self._frame_times)

    def get_latency_min(self) -> float:
        """Retorna la latencia mínima registrada.

        Returns:
            Latencia mínima en segundos. Retorna 0.0 si no hay datos.
        """
        with self._lock:
            if not self._frame_times:
                return 0.0
            return min(self._frame_times)

    def get_latency_max(self) -> float:
        """Retorna la latencia máxima registrada.

        Returns:
            Latencia máxima en segundos. Retorna 0.0 si no hay datos.
        """
        with self._lock:
            if not self._frame_times:
                return 0.0
            return max(self._frame_times)

    def get_uptime(self) -> float:
        """Retorna el tiempo transcurrido desde el inicio en segundos.

        Returns:
            Tiempo transcurrido en segundos. Retorna 0.0 si no se ha iniciado.
        """
        with self._lock:
            if self._start_time is None:
                return 0.0
            return time.perf_counter() - self._start_time

    def get_summary(self) -> Dict[str, object]:
        """Retorna un resumen completo de todas las métricas.

        Returns:
            Diccionario con todas las métricas disponibles.
        """
        with self._lock:
            return {
                "fps": self.get_fps(),
                "frames_processed": self._frames_processed,
                "total_errors": sum(self._errors.values()),
                "errors_by_component": dict(self._errors),
                "latency_avg": self.get_latency_avg(),
                "latency_min": self.get_latency_min(),
                "latency_max": self.get_latency_max(),
                "uptime": self.get_uptime(),
            }

    def reset(self) -> None:
        """Reinicia todas las métricas."""
        with self._lock:
            self._frames_processed = 0
            self._errors.clear()
            self._frame_times.clear()
            self._start_time = None
            self._last_frame_time = None
