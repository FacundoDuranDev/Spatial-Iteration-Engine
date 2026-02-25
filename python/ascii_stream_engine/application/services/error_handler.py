"""Manejo centralizado de errores del engine."""

import logging
from typing import Any, Dict, Optional

from ...domain.events import ErrorEvent
from ...infrastructure.event_bus import EventBus

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Maneja errores del engine de forma centralizada."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        """
        Inicializa el manejador de errores.

        Args:
            event_bus: Bus de eventos para publicar errores (opcional)
        """
        self._event_bus = event_bus
        self._error_count: Dict[str, int] = {}

    def handle(
        self,
        error: Exception,
        error_type: str,
        module_name: str,
        context: Optional[Dict[str, Any]] = None,
        log_level: int = logging.ERROR,
    ) -> None:
        """
        Maneja un error de forma centralizada.

        Args:
            error: Excepción que ocurrió
            error_type: Tipo de error (ej: "capture", "analysis", "rendering")
            module_name: Nombre del módulo donde ocurrió el error
            context: Contexto adicional del error
            log_level: Nivel de logging a usar
        """
        error_message = str(error)

        # Incrementar contador de errores
        self._error_count[error_type] = self._error_count.get(error_type, 0) + 1

        # Log del error
        logger.log(
            log_level,
            f"Error en {module_name} ({error_type}): {error_message}",
            exc_info=error,
        )

        # Publicar evento de error si hay event bus
        if self._event_bus:
            event = ErrorEvent(
                error_type=error_type,
                error_message=error_message,
                module_name=module_name,
                exception=error,
            )
            self._event_bus.publish(event, "error")

    def handle_capture_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de captura.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "capture", "frame_source", context, logging.WARNING)

    def handle_analysis_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de análisis.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "analysis", "analyzer_pipeline", context, logging.ERROR)

    def handle_transformation_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de transformación.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "transformation", "transformation_pipeline", context, logging.ERROR)

    def handle_filtering_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de filtrado.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "filtering", "filter_pipeline", context, logging.ERROR)

    def handle_rendering_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de renderizado.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "rendering", "renderer", context, logging.ERROR)

    def handle_output_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Maneja un error de salida.

        Args:
            error: Excepción que ocurrió
            context: Contexto adicional
        """
        self.handle(error, "writing", "output_sink", context, logging.ERROR)

    def get_error_count(self, error_type: Optional[str] = None) -> int:
        """
        Obtiene el contador de errores.

        Args:
            error_type: Tipo de error específico (si None, retorna total)

        Returns:
            Número de errores
        """
        if error_type:
            return self._error_count.get(error_type, 0)
        return sum(self._error_count.values())

    def get_error_counts(self) -> Dict[str, int]:
        """
        Obtiene todos los contadores de errores.

        Returns:
            Diccionario con contadores por tipo de error
        """
        return dict(self._error_count)

    def reset_error_counts(self) -> None:
        """Resetea todos los contadores de errores."""
        self._error_count.clear()
