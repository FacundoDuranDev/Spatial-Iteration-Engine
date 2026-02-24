"""Gestor de múltiples controladores."""

import logging
from typing import Dict, List, Optional

from ...infrastructure.event_bus import EventBus
from .base import BaseController
from .control_mapping import ControlMapping

logger = logging.getLogger(__name__)


class ControllerManager:
    """Gestor que coordina múltiples controladores."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        """
        Inicializa el gestor de controladores.

        Args:
            event_bus: Bus de eventos para publicar eventos de control
        """
        self._controllers: Dict[str, BaseController] = {}
        self._mapping = ControlMapping()
        self._event_bus = event_bus

        # Suscribirse a eventos de control si hay event bus
        if self._event_bus:
            self._event_bus.subscribe("control_received", self._handle_control_event)

    def add_controller(self, controller: BaseController) -> None:
        """
        Agrega un controlador al gestor.

        Args:
            controller: Instancia del controlador
        """
        if self._event_bus:
            controller.set_event_bus(self._event_bus)

        self._controllers[controller.name] = controller
        logger.info(f"Controlador '{controller.name}' agregado al gestor")

    def remove_controller(self, name: str) -> None:
        """
        Remueve un controlador.

        Args:
            name: Nombre del controlador
        """
        if name in self._controllers:
            controller = self._controllers[name]
            if controller.is_connected():
                controller.disconnect()
            del self._controllers[name]
            logger.info(f"Controlador '{name}' removido del gestor")

    def connect_all(self) -> None:
        """Conecta todos los controladores."""
        for controller in self._controllers.values():
            if controller.enabled and not controller.is_connected():
                try:
                    controller.connect()
                except Exception as e:
                    logger.error(
                        f"Error conectando controlador '{controller.name}': {e}", exc_info=True
                    )

    def disconnect_all(self) -> None:
        """Desconecta todos los controladores."""
        for controller in self._controllers.values():
            if controller.is_connected():
                try:
                    controller.disconnect()
                except Exception as e:
                    logger.error(
                        f"Error desconectando controlador '{controller.name}': {e}", exc_info=True
                    )

    def get_controller(self, name: str) -> Optional[BaseController]:
        """
        Obtiene un controlador por nombre.

        Args:
            name: Nombre del controlador

        Returns:
            Instancia del controlador o None
        """
        return self._controllers.get(name)

    def get_all_controllers(self) -> List[BaseController]:
        """Obtiene todos los controladores."""
        return list(self._controllers.values())

    def set_mapping(self, mapping: ControlMapping) -> None:
        """
        Establece el mapeo de control.

        Args:
            mapping: Instancia de ControlMapping
        """
        self._mapping = mapping

    def get_mapping(self) -> ControlMapping:
        """Obtiene el mapeo de control."""
        return self._mapping

    def _handle_control_event(self, event) -> None:
        """
        Maneja eventos de control recibidos.

        Args:
            event: Evento de control
        """
        message = {
            "type": event.controller_name,
            "command": event.command,
            "params": event.params,
            "value": event.value,
        }

        action = self._mapping.process_message(message)
        if action:
            logger.debug(f"Acción mapeada: {action}")

    def clear(self) -> None:
        """Limpia todos los controladores."""
        self.disconnect_all()
        self._controllers.clear()
        logger.debug("Todos los controladores han sido limpiados")
