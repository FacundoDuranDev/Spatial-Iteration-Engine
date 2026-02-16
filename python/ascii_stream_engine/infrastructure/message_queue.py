"""Cola de mensajes thread-safe para comunicación entre threads."""

import logging
import queue
import threading
import time
from typing import Any, Callable, Optional, Tuple

from ..domain.events import BaseEvent

logger = logging.getLogger(__name__)


class MessageQueue:
    """Cola de mensajes thread-safe con procesamiento opcional en background."""

    def __init__(self, maxsize: int = 0) -> None:
        """
        Inicializa la cola de mensajes.

        Args:
            maxsize: Tamaño máximo de la cola (0 = ilimitado)
        """
        self._queue: queue.Queue[Tuple[BaseEvent, Optional[str]]] = queue.Queue(maxsize=maxsize)
        self._processor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._handler: Optional[Callable[[BaseEvent], None]] = None
        self._running = False

    def put(self, event: BaseEvent, event_type: Optional[str] = None, block: bool = True, timeout: Optional[float] = None) -> None:
        """
        Agrega un evento a la cola.

        Args:
            event: Evento a agregar
            event_type: Tipo de evento (opcional)
            block: Si True, bloquea hasta que haya espacio
            timeout: Timeout en segundos (None = sin timeout)
        """
        try:
            self._queue.put((event, event_type), block=block, timeout=timeout)
        except queue.Full:
            logger.warning(f"Cola de mensajes llena, evento '{event.__class__.__name__}' descartado")

    def put_nowait(self, event: BaseEvent, event_type: Optional[str] = None) -> None:
        """
        Agrega un evento a la cola sin bloquear.

        Args:
            event: Evento a agregar
            event_type: Tipo de evento (opcional)
        """
        self.put(event, event_type, block=False)

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Tuple[BaseEvent, Optional[str]]:
        """
        Obtiene un evento de la cola.

        Args:
            block: Si True, bloquea hasta que haya un evento
            timeout: Timeout en segundos (None = sin timeout)

        Returns:
            Tupla (evento, tipo_evento)
        """
        return self._queue.get(block=block, timeout=timeout)

    def get_nowait(self) -> Tuple[BaseEvent, Optional[str]]:
        """
        Obtiene un evento de la cola sin bloquear.

        Returns:
            Tupla (evento, tipo_evento)

        Raises:
            queue.Empty: Si la cola está vacía
        """
        return self._queue.get_nowait()

    def start_processing(self, handler: Callable[[BaseEvent], None]) -> None:
        """
        Inicia el procesamiento de eventos en background.

        Args:
            handler: Función que procesará cada evento
        """
        if self._running:
            logger.warning("El procesamiento ya está en ejecución")
            return

        self._handler = handler
        self._stop_event.clear()
        self._running = True
        self._processor_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._processor_thread.start()
        logger.debug("Procesamiento de mensajes iniciado")

    def stop_processing(self, timeout: Optional[float] = 5.0) -> None:
        """
        Detiene el procesamiento de eventos.

        Args:
            timeout: Tiempo máximo para esperar que termine el thread
        """
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._processor_thread:
            self._processor_thread.join(timeout=timeout)
            if self._processor_thread.is_alive():
                logger.warning("Thread de procesamiento no terminó a tiempo")

        logger.debug("Procesamiento de mensajes detenido")

    def _process_loop(self) -> None:
        """Loop de procesamiento de eventos en background."""
        while not self._stop_event.is_set():
            try:
                event, event_type = self.get(block=True, timeout=0.1)
                if self._handler:
                    try:
                        self._handler(event)
                    except Exception as e:
                        logger.error(
                            f"Error procesando evento '{event.__class__.__name__}': {e}",
                            exc_info=True,
                        )
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error en loop de procesamiento: {e}", exc_info=True)
                time.sleep(0.1)

    def qsize(self) -> int:
        """Retorna el tamaño actual de la cola."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Verifica si la cola está vacía."""
        return self._queue.empty()

    def full(self) -> bool:
        """Verifica si la cola está llena."""
        return self._queue.full()

    def clear(self) -> None:
        """Limpia todos los eventos pendientes de la cola."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.debug("Cola de mensajes limpiada")

    def is_running(self) -> bool:
        """Verifica si el procesamiento está en ejecución."""
        return self._running

