"""Mapeo de mensajes de controladores a parámetros del engine."""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ControlMapping:
    """Mapea mensajes de controladores a acciones del engine."""

    def __init__(self) -> None:
        """Inicializa el mapeo."""
        self._mappings: Dict[str, Dict[str, Any]] = {}
        self._default_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def add_mapping(
        self,
        command: str,
        target: str,
        parameter: Optional[str] = None,
        transform: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """
        Agrega un mapeo de comando a parámetro.

        Args:
            command: Comando del controlador (ej: "note_on", "control_change")
            target: Objetivo del mapeo ("config", "filter", "renderer", etc.)
            parameter: Nombre del parámetro a modificar
            transform: Función para transformar el valor (opcional)
        """
        self._mappings[command] = {
            "target": target,
            "parameter": parameter,
            "transform": transform,
        }
        logger.debug(f"Mapeo agregado: {command} -> {target}.{parameter}")

    def remove_mapping(self, command: str) -> None:
        """
        Remueve un mapeo.

        Args:
            command: Comando a remover
        """
        if command in self._mappings:
            del self._mappings[command]
            logger.debug(f"Mapeo removido: {command}")

    def set_default_handler(self, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Establece un handler por defecto para comandos no mapeados.

        Args:
            handler: Función que maneja comandos no mapeados
        """
        self._default_handler = handler

    def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Procesa un mensaje y retorna la acción a ejecutar.

        Args:
            message: Mensaje del controlador

        Returns:
            Diccionario con acción a ejecutar o None si no hay mapeo
        """
        msg_type = message.get("type", "")
        command = message.get("command", "")

        # Buscar mapeo por tipo o comando
        mapping = self._mappings.get(msg_type) or self._mappings.get(command)

        if not mapping:
            if self._default_handler:
                self._default_handler(command, message)
            return None

        target = mapping["target"]
        parameter = mapping["parameter"]
        transform = mapping.get("transform")

        # Obtener valor
        value = message.get("value") or message.get("args", [None])[0]

        # Aplicar transformación si existe
        if transform:
            try:
                value = transform(value)
            except Exception as e:
                logger.error(f"Error aplicando transformación: {e}", exc_info=True)
                return None

        return {
            "target": target,
            "parameter": parameter,
            "value": value,
        }

    def get_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene todos los mapeos."""
        return self._mappings.copy()

    def clear(self) -> None:
        """Limpia todos los mapeos."""
        self._mappings.clear()
        logger.debug("Todos los mapeos han sido limpiados")

