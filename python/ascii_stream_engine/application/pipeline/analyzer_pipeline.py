"""Pipeline para analizadores de frames."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List, Optional

import numpy as np

from ...domain.config import EngineConfig
from ...ports.processors import Analyzer, ProcessorPipeline


class AnalyzerPipeline(ProcessorPipeline):
    """Pipeline para ejecutar múltiples analizadores en secuencia.

    Los analizadores extraen información/metadata de los frames sin modificar
    el frame original. Los resultados se combinan en un diccionario.
    """

    def __init__(self, analyzers: Optional[Iterable[Analyzer]] = None) -> None:
        """
        Inicializa el pipeline de analizadores.

        Args:
            analyzers: Lista inicial de analizadores
        """
        self._analyzers: List[Analyzer] = list(analyzers) if analyzers else []
        self._lock = threading.Lock()
        self._version: int = 0

    @property
    def version(self) -> int:
        """Structural version counter, incremented on add/remove/replace mutations."""
        return self._version

    @property
    def analyzers(self) -> List[Analyzer]:
        """Obtiene la lista de analizadores."""
        return self._analyzers

    def snapshot(self) -> List[Analyzer]:
        """Obtiene una snapshot thread-safe de los analizadores."""
        with self._lock:
            return list(self._analyzers)

    def add(self, processor: Analyzer) -> None:
        """Agrega un analizador al pipeline."""
        with self._lock:
            self._analyzers.append(processor)
            self._version += 1

    def remove(self, processor: Analyzer) -> None:
        """Remueve un analizador del pipeline."""
        with self._lock:
            self._analyzers.remove(processor)
            self._version += 1

    def append(self, analyzer: Analyzer) -> None:
        """Agrega un analizador al pipeline."""
        self.add(analyzer)

    def extend(self, analyzers: Iterable[Analyzer]) -> None:
        """Extiende el pipeline con múltiples analizadores."""
        with self._lock:
            self._analyzers.extend(analyzers)
            self._version += 1

    def insert(self, index: int, analyzer: Analyzer) -> None:
        """Inserta un analizador en una posición específica."""
        with self._lock:
            self._analyzers.insert(index, analyzer)
            self._version += 1

    def pop(self, index: int = -1) -> Analyzer:
        """Remueve y retorna un analizador del pipeline."""
        with self._lock:
            result = self._analyzers.pop(index)
            self._version += 1
            return result

    def clear(self) -> None:
        """Limpia todos los analizadores del pipeline."""
        with self._lock:
            self._analyzers.clear()
            self._version += 1

    def replace(self, analyzers: Iterable[Analyzer]) -> None:
        """Reemplaza todos los analizadores."""
        with self._lock:
            self._analyzers = list(analyzers)
            self._version += 1

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """
        Habilita o deshabilita un analizador por nombre.

        Args:
            name: Nombre del analizador
            enabled: Estado deseado

        Returns:
            True si se encontró y modificó el analizador
        """
        changed = False
        with self._lock:
            for analyzer in self._analyzers:
                analyzer_name = getattr(analyzer, "name", analyzer.__class__.__name__)
                if analyzer_name == name:
                    if hasattr(analyzer, "enabled"):
                        analyzer.enabled = enabled
                        changed = True
        return changed

    def has_any(self) -> bool:
        """Verifica si hay analizadores en el pipeline."""
        with self._lock:
            return bool(self._analyzers)

    def run(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, object]:
        """
        Ejecuta todos los analizadores activos en el pipeline.

        Cuando hay más de un analizador activo, se ejecutan en paralelo usando
        ThreadPoolExecutor (requiere GIL release en C++ — Step 1).

        Args:
            frame: Frame de video a analizar
            config: Configuración del engine

        Returns:
            Diccionario con resultados de todos los analizadores
        """
        active = [a for a in self.snapshot() if not hasattr(a, "enabled") or getattr(a, "enabled")]
        if not active:
            return {}

        # Fast path: single analyzer, no threading overhead
        if len(active) == 1:
            a = active[0]
            name = getattr(a, "name", a.__class__.__name__)
            return {name: a.analyze(frame, config)}

        # Parallel path: multiple analyzers
        results: Dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=len(active)) as executor:
            futures = {
                executor.submit(a.analyze, frame, config): getattr(a, "name", a.__class__.__name__)
                for a in active
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = {}
        return results

    def process(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        context: Optional[dict] = None,
    ) -> dict:
        """
        Procesa un frame a través de todos los analizadores (alias de run).

        Args:
            frame: Frame de video a analizar
            config: Configuración del engine
            context: Contexto adicional (no usado en analizadores)

        Returns:
            Diccionario con resultados de todos los analizadores
        """
        return self.run(frame, config)

    @contextmanager
    def locked(self) -> Iterator[List[Analyzer]]:
        """Context manager para acceso thread-safe a los analizadores."""
        with self._lock:
            yield self._analyzers
