"""Pipeline genérico reutilizable para procesadores de frames."""

import threading
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List, Optional, TypeVar, Union

import numpy as np

from ...domain.config import EngineConfig
from ...ports.processors import FrameProcessor, ProcessorPipeline

T = TypeVar("T", bound=FrameProcessor)


class ProcessorPipelineImpl(ProcessorPipeline):
    """Implementación genérica de pipeline para procesadores de frames.

    Este pipeline puede usarse para cualquier tipo de procesador que implemente
    el protocolo FrameProcessor. Proporciona funcionalidad thread-safe para
    agregar, remover y ejecutar procesadores en secuencia.
    """

    def __init__(self, processors: Optional[Iterable[T]] = None) -> None:
        """
        Inicializa el pipeline.

        Args:
            processors: Lista inicial de procesadores
        """
        self._processors: List[T] = list(processors) if processors else []
        self._lock = threading.Lock()

    @property
    def processors(self) -> List[T]:
        """Obtiene la lista de procesadores."""
        return self._processors

    def snapshot(self) -> List[T]:
        """Obtiene una snapshot thread-safe de los procesadores."""
        with self._lock:
            return list(self._processors)

    def add(self, processor: FrameProcessor) -> None:
        """Agrega un procesador al pipeline."""
        with self._lock:
            self._processors.append(processor)  # type: ignore

    def remove(self, processor: FrameProcessor) -> None:
        """Remueve un procesador del pipeline."""
        with self._lock:
            self._processors.remove(processor)  # type: ignore

    def append(self, processor: T) -> None:
        """Agrega un procesador al pipeline (alias de add)."""
        self.add(processor)

    def extend(self, processors: Iterable[T]) -> None:
        """Extiende el pipeline con múltiples procesadores."""
        with self._lock:
            self._processors.extend(processors)

    def insert(self, index: int, processor: T) -> None:
        """Inserta un procesador en una posición específica."""
        with self._lock:
            self._processors.insert(index, processor)

    def pop(self, index: int = -1) -> T:
        """Remueve y retorna un procesador del pipeline."""
        with self._lock:
            return self._processors.pop(index)

    def clear(self) -> None:
        """Limpia todos los procesadores del pipeline."""
        with self._lock:
            self._processors.clear()

    def replace(self, processors: Iterable[T]) -> None:
        """Reemplaza todos los procesadores."""
        with self._lock:
            self._processors = list(processors)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """
        Habilita o deshabilita un procesador por nombre.

        Args:
            name: Nombre del procesador
            enabled: Estado deseado

        Returns:
            True si se encontró y modificó el procesador
        """
        changed = False
        with self._lock:
            for processor in self._processors:
                processor_name = getattr(processor, "name", processor.__class__.__name__)
                if processor_name == name:
                    if hasattr(processor, "enabled"):
                        processor.enabled = enabled
                        changed = True
        return changed

    def has_any(self) -> bool:
        """Verifica si hay procesadores en el pipeline."""
        with self._lock:
            return bool(self._processors)

    def process(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        context: Optional[dict] = None,
    ) -> Union[np.ndarray, dict]:
        """
        Procesa un frame a través de todos los procesadores del pipeline.

        Args:
            frame: Frame de video a procesar
            config: Configuración del engine
            context: Contexto adicional

        Returns:
            Resultado del procesamiento (frame procesado o resultados)
        """
        processors = self.snapshot()
        active_processors = [
            p for p in processors if not (hasattr(p, "enabled") and not getattr(p, "enabled"))
        ]

        if not active_processors:
            return frame if isinstance(frame, np.ndarray) else {}

        result: Union[np.ndarray, dict] = frame
        for processor in active_processors:
            result = processor.process(result, config, context)  # type: ignore

        return result

    @contextmanager
    def locked(self) -> Iterator[List[T]]:
        """Context manager para acceso thread-safe a los procesadores."""
        with self._lock:
            yield self._processors
