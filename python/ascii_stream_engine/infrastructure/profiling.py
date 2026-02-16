"""Módulo de profiling para medir el rendimiento del loop principal del engine."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, stdev
from typing import Dict, List, Optional


@dataclass
class PhaseStats:
    """Estadísticas de una fase del loop principal."""

    name: str
    count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    times: List[float] = field(default_factory=list)

    def add_measurement(self, duration: float) -> None:
        """Agrega una medición de tiempo."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)

    @property
    def avg_time(self) -> float:
        """Tiempo promedio en segundos."""
        return self.total_time / self.count if self.count > 0 else 0.0

    @property
    def std_dev(self) -> float:
        """Desviación estándar del tiempo."""
        if len(self.times) < 2:
            return 0.0
        return stdev(self.times)

    def reset(self) -> None:
        """Reinicia las estadísticas."""
        self.count = 0
        self.total_time = 0.0
        self.min_time = float("inf")
        self.max_time = 0.0
        self.times.clear()


class LoopProfiler:
    """Profiler para medir el rendimiento de las fases del loop principal."""

    # Fases del loop principal
    PHASE_CAPTURE = "capture"
    PHASE_ANALYSIS = "analysis"
    PHASE_TRANSFORMATION = "transformation"
    PHASE_FILTERING = "filtering"
    PHASE_RENDERING = "rendering"
    PHASE_WRITING = "writing"
    PHASE_TOTAL = "total_frame"

    def __init__(self, enabled: bool = True, max_samples: int = 1000) -> None:
        """
        Inicializa el profiler.

        Args:
            enabled: Si está habilitado, mide tiempos. Si no, no hace nada.
            max_samples: Número máximo de muestras a mantener en memoria.
        """
        self._enabled = enabled
        self._max_samples = max_samples
        self._stats: Dict[str, PhaseStats] = {}
        self._current_frame_start: Optional[float] = None
        self._phase_stack: List[tuple[str, float]] = []

    @property
    def enabled(self) -> bool:
        """Indica si el profiler está habilitado."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Habilita o deshabilita el profiler."""
        self._enabled = value

    def _get_stats(self, phase: str) -> PhaseStats:
        """Obtiene o crea las estadísticas de una fase."""
        if phase not in self._stats:
            self._stats[phase] = PhaseStats(name=phase)
        return self._stats[phase]

    def start_frame(self) -> None:
        """Marca el inicio de un frame completo."""
        if not self._enabled:
            return
        self._current_frame_start = time.perf_counter()

    def end_frame(self) -> None:
        """Marca el fin de un frame completo."""
        if not self._enabled or self._current_frame_start is None:
            return
        duration = time.perf_counter() - self._current_frame_start
        stats = self._get_stats(self.PHASE_TOTAL)
        stats.add_measurement(duration)
        self._trim_samples(stats)
        self._current_frame_start = None

    def start_phase(self, phase: str) -> None:
        """Marca el inicio de una fase."""
        if not self._enabled:
            return
        self._phase_stack.append((phase, time.perf_counter()))

    def end_phase(self, phase: str) -> None:
        """Marca el fin de una fase."""
        if not self._enabled:
            return
        if not self._phase_stack:
            return
        popped_phase, start_time = self._phase_stack.pop()
        if popped_phase != phase:
            # Stack desbalanceado, ignorar
            return
        duration = time.perf_counter() - start_time
        stats = self._get_stats(phase)
        stats.add_measurement(duration)
        self._trim_samples(stats)

    def _trim_samples(self, stats: PhaseStats) -> None:
        """Recorta la lista de tiempos si excede max_samples."""
        if len(stats.times) > self._max_samples:
            # Mantener solo las últimas max_samples
            stats.times = stats.times[-self._max_samples :]
            # Recalcular total_time
            stats.total_time = sum(stats.times)
            stats.min_time = min(stats.times)
            stats.max_time = max(stats.times)

    def get_stats(self, phase: Optional[str] = None) -> Dict[str, PhaseStats]:
        """
        Obtiene las estadísticas.

        Args:
            phase: Si se especifica, retorna solo esa fase. Si es None, retorna todas.

        Returns:
            Diccionario con las estadísticas de las fases.
        """
        if phase:
            return {phase: self._stats[phase]} if phase in self._stats else {}
        return dict(self._stats)

    def reset(self) -> None:
        """Reinicia todas las estadísticas."""
        for stats in self._stats.values():
            stats.reset()
        self._current_frame_start = None
        self._phase_stack.clear()

    def get_report(self) -> str:
        """
        Genera un reporte de texto con las estadísticas.

        Returns:
            String con el reporte formateado.
        """
        if not self._stats:
            return "No hay datos de profiling disponibles."

        lines = ["=" * 70]
        lines.append("REPORTE DE PROFILING DEL LOOP PRINCIPAL")
        lines.append("=" * 70)
        lines.append("")

        # Orden de fases para mostrar
        phase_order = [
            self.PHASE_CAPTURE,
            self.PHASE_ANALYSIS,
            self.PHASE_TRANSFORMATION,
            self.PHASE_FILTERING,
            self.PHASE_RENDERING,
            self.PHASE_WRITING,
            self.PHASE_TOTAL,
        ]

        for phase in phase_order:
            if phase not in self._stats:
                continue
            stats = self._stats[phase]
            if stats.count == 0:
                continue

            lines.append(f"Fase: {stats.name.upper()}")
            lines.append(f"  Muestras: {stats.count}")
            lines.append(f"  Tiempo total: {stats.total_time:.6f} s")
            lines.append(f"  Promedio: {stats.avg_time*1000:.3f} ms")
            lines.append(f"  Mínimo: {stats.min_time*1000:.3f} ms")
            lines.append(f"  Máximo: {stats.max_time*1000:.3f} ms")
            if stats.count > 1:
                lines.append(f"  Desv. Est.: {stats.std_dev*1000:.3f} ms")
            lines.append("")

        # Análisis de cuellos de botella
        if self.PHASE_TOTAL in self._stats:
            total_stats = self._stats[self.PHASE_TOTAL]
            if total_stats.count > 0:
                lines.append("=" * 70)
                lines.append("ANÁLISIS DE CUellos DE BOTELLA")
                lines.append("=" * 70)
                lines.append("")

                # Calcular porcentajes de cada fase respecto al total
                phase_percentages = {}
                for phase in phase_order[:-1]:  # Excluir PHASE_TOTAL
                    if phase in self._stats:
                        phase_stats = self._stats[phase]
                        if phase_stats.count > 0 and total_stats.avg_time > 0:
                            percentage = (
                                phase_stats.avg_time / total_stats.avg_time * 100
                            )
                            phase_percentages[phase] = percentage

                # Ordenar por porcentaje descendente
                sorted_phases = sorted(
                    phase_percentages.items(), key=lambda x: x[1], reverse=True
                )

                for phase, percentage in sorted_phases:
                    phase_name = phase.replace("_", " ").title()
                    lines.append(
                        f"  {phase_name}: {percentage:.1f}% del tiempo total"
                    )

                lines.append("")
                lines.append(
                    f"FPS promedio: {1.0/total_stats.avg_time:.2f} (objetivo: variable)"
                )

        lines.append("=" * 70)

        return "\n".join(lines)

    def get_summary_dict(self) -> Dict[str, Dict[str, float]]:
        """
        Obtiene un resumen de las estadísticas como diccionario.

        Returns:
            Diccionario con estadísticas por fase.
        """
        summary = {}
        for phase, stats in self._stats.items():
            if stats.count > 0:
                summary[phase] = {
                    "count": stats.count,
                    "total_time": stats.total_time,
                    "avg_time": stats.avg_time,
                    "min_time": stats.min_time,
                    "max_time": stats.max_time,
                    "std_dev": stats.std_dev,
                }
        return summary

    def get_phase_time(self, phase: str) -> float:
        """
        Obtiene el tiempo promedio de una fase.

        Args:
            phase: Nombre de la fase

        Returns:
            Tiempo promedio en segundos (0.0 si no hay datos)
        """
        if phase in self._stats:
            return self._stats[phase].avg_time
        return 0.0

