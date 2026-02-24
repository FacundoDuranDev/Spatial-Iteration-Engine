"""Pipeline de procesamiento paralelo de frames."""

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from ..domain.config import EngineConfig

logger = logging.getLogger(__name__)


class FrameProcessor:
    """Procesador de frames en paralelo."""

    def __init__(
        self,
        num_workers: int = 4,
        max_queue_size: int = 10,
    ) -> None:
        """
        Inicializa el procesador paralelo.

        Args:
            num_workers: Número de workers para procesamiento paralelo
            max_queue_size: Tamaño máximo de la cola de frames
        """
        self.num_workers = max(1, num_workers)
        self.max_queue_size = max_queue_size
        self._executor: Optional[ThreadPoolExecutor] = None
        self._frame_queue: queue.Queue[Tuple[np.ndarray, Dict[str, Any]]] = queue.Queue(
            maxsize=max_queue_size
        )
        self._result_queue: queue.Queue[Tuple[Any, Dict[str, Any]]] = queue.Queue(
            maxsize=max_queue_size
        )
        self._running = False

    def start(self) -> None:
        """Inicia el procesador."""
        if self._running:
            return

        self._executor = ThreadPoolExecutor(max_workers=self.num_workers)
        self._running = True
        logger.info(f"Procesador paralelo iniciado con {self.num_workers} workers")

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        """
        Detiene el procesador.

        Args:
            timeout: Tiempo máximo para esperar que terminen los workers
        """
        if not self._running:
            return

        self._running = False

        if self._executor:
            self._executor.shutdown(wait=True, timeout=timeout)

        # Limpiar colas
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Procesador paralelo detenido")

    def process_frame(
        self,
        frame: np.ndarray,
        processor_func: Callable[[np.ndarray, Dict[str, Any]], Any],
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Optional[Any]:
        """
        Procesa un frame en paralelo.

        Args:
            frame: Frame a procesar
            processor_func: Función que procesa el frame
            context: Contexto adicional para el procesamiento
            timeout: Timeout para el procesamiento

        Returns:
            Resultado del procesamiento o None si falla
        """
        if not self._running or not self._executor:
            # Procesamiento secuencial si no está iniciado
            return processor_func(frame, context or {})

        try:
            future = self._executor.submit(processor_func, frame.copy(), context or {})
            result = future.result(timeout=timeout)
            return result
        except Exception as e:
            logger.error(f"Error procesando frame en paralelo: {e}", exc_info=True)
            return None

    def process_batch(
        self,
        frames: list[np.ndarray],
        processor_func: Callable[[np.ndarray, Dict[str, Any]], Any],
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> list[Any]:
        """
        Procesa múltiples frames en paralelo.

        Args:
            frames: Lista de frames a procesar
            processor_func: Función que procesa cada frame
            context: Contexto adicional
            timeout: Timeout por frame

        Returns:
            Lista de resultados
        """
        if not self._running or not self._executor:
            # Procesamiento secuencial
            return [processor_func(frame.copy(), context or {}) for frame in frames]

        results = []
        futures = {}

        # Enviar todos los frames
        for i, frame in enumerate(frames):
            future = self._executor.submit(processor_func, frame.copy(), context or {})
            futures[future] = i

        # Recopilar resultados
        for future in as_completed(futures, timeout=timeout * len(frames) if timeout else None):
            idx = futures[future]
            try:
                result = future.result(timeout=timeout)
                results.append((idx, result))
            except Exception as e:
                logger.error(f"Error procesando frame {idx} en batch: {e}", exc_info=True)
                results.append((idx, None))

        # Ordenar por índice original
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]

    def is_running(self) -> bool:
        """Verifica si el procesador está en ejecución."""
        return self._running


class ResultAggregator:
    """Agrega resultados de procesamiento paralelo."""

    def __init__(self) -> None:
        """Inicializa el agregador."""
        self._results: Dict[str, Any] = {}

    def add_result(self, key: str, result: Any) -> None:
        """
        Agrega un resultado.

        Args:
            key: Clave del resultado
            result: Resultado a agregar
        """
        self._results[key] = result

    def get_result(self, key: str) -> Optional[Any]:
        """
        Obtiene un resultado.

        Args:
            key: Clave del resultado

        Returns:
            Resultado o None si no existe
        """
        return self._results.get(key)

    def get_all_results(self) -> Dict[str, Any]:
        """Obtiene todos los resultados."""
        return self._results.copy()

    def clear(self) -> None:
        """Limpia todos los resultados."""
        self._results.clear()

    def merge_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusiona resultados externos con los internos.

        Args:
            results: Resultados a fusionar

        Returns:
            Resultados fusionados
        """
        merged = self._results.copy()
        merged.update(results)
        return merged
