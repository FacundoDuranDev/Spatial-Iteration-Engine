"""Clase base para controladores externos."""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from ...domain.events import ControlEvent

logger = logging.getLogger(__name__)


class BaseController:
    """Clase base para implementaciones de controladores."""

    name = "base_controller"

    def __init__(self, enabled: bool = True) -> None:
        """
        Inicializa el controlador.

        Args:
            enabled: Si el controlador está habilitado
        """
        self.enabled = enabled
        self._connected = False
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        self._event_bus = None  # Se establecerá por el manager

    def connect(self) -> None:
        """Conecta el controlador."""
        if not self.enabled:
            logger.warning(f"Controlador '{self.name}' está deshabilitado")
            return

        if self._connected:
            logger.warning(f"Controlador '{self.name}' ya está conectado")
            return

        try:
            self._do_connect()
            self._connected = True
            logger.info(f"Controlador '{self.name}' conectado")
        except Exception as e:
            logger.error(f"Error conectando controlador '{self.name}': {e}", exc_info=True)
            raise

    def disconnect(self) -> None:
        """Desconecta el controlador."""
        if not self._connected:
            return

        try:
            self._do_disconnect()
            self._connected = False
            logger.info(f"Controlador '{self.name}' desconectado")
        except Exception as e:
            logger.error(f"Error desconectando controlador '{self.name}': {e}", exc_info=True)

    def is_connected(self) -> bool:
        """Verifica si el controlador está conectado."""
        return self._connected

    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Registra un callback para recibir mensajes.

        Args:
            callback: Función que será llamada con cada mensaje
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Remueve un callback.

        Args:
            callback: Callback a remover
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _notify_callbacks(self, message: Dict[str, Any]) -> None:
        """
        Notifica a todos los callbacks registrados.

        Args:
            message: Mensaje recibido
        """
        with self._lock:
            callbacks = self._callbacks.copy()

        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error en callback de controlador '{self.name}': {e}", exc_info=True)

    def _publish_event(self, command: str, params: Dict[str, Any], value: Optional[Any] = None) -> None:
        """
        Publica un evento de control.

        Args:
            command: Comando recibido
            params: Parámetros del comando
            value: Valor del comando (opcional)
        """
        if self._event_bus:
            from ...domain.events import ControlEvent

            event = ControlEvent(
                controller_name=self.name,
                command=command,
                params=params,
                value=value,
            )
            self._event_bus.publish(event, "control_received")

    def set_event_bus(self, event_bus) -> None:
        """Establece el bus de eventos para publicar eventos."""
        self._event_bus = event_bus

    def _do_connect(self) -> None:
        """Implementación específica de conexión (debe ser sobrescrita)."""
        raise NotImplementedError("_do_connect debe ser implementado por la subclase")

    def _do_disconnect(self) -> None:
        """Implementación específica de desconexión (debe ser sobrescrita)."""
        raise NotImplementedError("_do_disconnect debe ser implementado por la subclase")

