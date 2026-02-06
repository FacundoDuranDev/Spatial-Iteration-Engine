"""Bus de eventos central para comunicación desacoplada entre módulos."""

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from ..domain.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Bus de eventos thread-safe con suscripciones por tipo de evento."""

    def __init__(self) -> None:
        """Inicializa el bus de eventos."""
        self._subscribers: Dict[str, List[Callable[[BaseEvent], None]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._enabled = True

    def subscribe(self, event_type: str, callback: Callable[[BaseEvent], None]) -> None:
        """
        Suscribe un callback a un tipo de evento.

        Args:
            event_type: Tipo de evento (ej: "frame_captured", "analysis_complete")
            callback: Función que será llamada cuando se publique el evento
        """
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"Callback suscrito a evento '{event_type}'")

    def unsubscribe(self, event_type: str, callback: Callable[[BaseEvent], None]) -> None:
        """
        Desuscribe un callback de un tipo de evento.

        Args:
            event_type: Tipo de evento
            callback: Función a desuscribir
        """
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Callback desuscrito de evento '{event_type}'")

    def publish(self, event: BaseEvent, event_type: Optional[str] = None) -> None:
        """
        Publica un evento a todos los suscriptores.

        Args:
            event: Instancia del evento a publicar
            event_type: Tipo de evento (si no se proporciona, se infiere del nombre de la clase)
        """
        if not self._enabled:
            return

        if event_type is None:
            # Inferir tipo de evento del nombre de la clase
            class_name = event.__class__.__name__
            # Convertir CamelCase a snake_case y remover "Event"
            event_type = self._camel_to_snake(class_name).replace("_event", "")

        with self._lock:
            callbacks = self._subscribers[event_type].copy()

        # Ejecutar callbacks fuera del lock para evitar deadlocks
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    f"Error ejecutando callback para evento '{event_type}': {e}",
                    exc_info=True,
                )

    def publish_async(self, event: BaseEvent, event_type: Optional[str] = None) -> None:
        """
        Publica un evento de forma asíncrona (no bloqueante).

        Args:
            event: Instancia del evento a publicar
            event_type: Tipo de evento (si no se proporciona, se infiere del nombre de la clase)
        """
        if not self._enabled:
            return

        if event_type is None:
            class_name = event.__class__.__name__
            event_type = self._camel_to_snake(class_name).replace("_event", "")

        with self._lock:
            callbacks = self._subscribers[event_type].copy()

        # Ejecutar en thread separado para no bloquear
        def _async_publish() -> None:
            for callback in callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(
                        f"Error ejecutando callback asíncrono para evento '{event_type}': {e}",
                        exc_info=True,
                    )

        thread = threading.Thread(target=_async_publish, daemon=True)
        thread.start()

    def clear(self) -> None:
        """Limpia todas las suscripciones."""
        with self._lock:
            self._subscribers.clear()
            logger.debug("Todas las suscripciones han sido limpiadas")

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """
        Obtiene el número de suscriptores para un tipo de evento o total.

        Args:
            event_type: Tipo de evento (None para total)

        Returns:
            Número de suscriptores
        """
        with self._lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            return sum(len(callbacks) for callbacks in self._subscribers.values())

    def enable(self) -> None:
        """Habilita el bus de eventos."""
        self._enabled = True
        logger.debug("Event bus habilitado")

    def disable(self) -> None:
        """Deshabilita el bus de eventos (los eventos no se publicarán)."""
        self._enabled = False
        logger.debug("Event bus deshabilitado")

    def is_enabled(self) -> bool:
        """Verifica si el bus de eventos está habilitado."""
        return self._enabled

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """Convierte CamelCase a snake_case."""
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

