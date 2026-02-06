"""Sistema de logging estructurado para ascii_stream_engine.

Este módulo proporciona un sistema de logging estructurado con niveles apropiados
para el motor de streaming ASCII. Incluye configuración thread-safe y soporte
para logging estructurado con contexto adicional.
"""

import json
import logging
import sys
import threading
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Formatter que produce logs estructurados en formato JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el registro de log como JSON estructurado."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Agregar información de excepción si existe
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Agregar campos adicionales del contexto si existen
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Agregar información de thread si es relevante
        if threading.current_thread() != threading.main_thread():
            log_data["thread"] = threading.current_thread().name
            log_data["thread_id"] = threading.current_thread().ident

        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Formatter legible para consola con colores opcionales."""

    # Códigos ANSI para colores (si el terminal los soporta)
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        """Inicializa el formatter.

        Args:
            use_colors: Si True, usa colores ANSI en la salida.
        """
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el registro para consola."""
        level = record.levelname
        color = self.COLORS.get(level, "") if self.use_colors else ""
        reset = self.RESET if self.use_colors else ""

        # Formato: [TIMESTAMP] LEVEL logger: message
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        base_msg = f"[{timestamp}] {color}{level:8s}{reset} {record.name}: {record.getMessage()}"

        # Agregar información de thread si no es el thread principal
        if threading.current_thread() != threading.main_thread():
            thread_name = threading.current_thread().name
            base_msg = f"{base_msg} [thread:{thread_name}]"

        # Agregar campos extra si existen
        if hasattr(record, "extra_fields") and record.extra_fields:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            base_msg = f"{base_msg} {extra_str}"

        # Agregar excepción si existe
        if record.exc_info:
            base_msg = f"{base_msg}\n{self.formatException(record.exc_info)}"

        return base_msg


class StructuredLogger:
    """Wrapper thread-safe para logging estructurado."""

    _lock = threading.Lock()
    _configured = False

    @classmethod
    def configure(
        cls,
        level: str = "INFO",
        use_json: bool = False,
        use_colors: bool = True,
        log_file: Optional[str] = None,
    ) -> None:
        """Configura el sistema de logging.

        Args:
            level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            use_json: Si True, usa formato JSON estructurado. Si False, formato legible.
            use_colors: Si True y use_json=False, usa colores en consola.
            log_file: Ruta opcional a archivo para escribir logs.
        """
        with cls._lock:
            if cls._configured:
                # Reconfigurar si ya estaba configurado
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    root_logger.removeHandler(handler)
                    handler.close()

            # Configurar nivel
            numeric_level = getattr(logging, level.upper(), logging.INFO)
            root_logger = logging.getLogger()
            root_logger.setLevel(numeric_level)

            # Handler para consola
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)

            if use_json:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(ConsoleFormatter(use_colors=use_colors))

            root_logger.addHandler(console_handler)

            # Handler para archivo si se especifica
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setLevel(numeric_level)
                # Archivo siempre en formato JSON estructurado
                file_handler.setFormatter(StructuredFormatter())
                root_logger.addHandler(file_handler)

            # Evitar propagación a handlers de nivel superior
            root_logger.propagate = False

            cls._configured = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Obtiene un logger con el nombre especificado.

        Args:
            name: Nombre del logger (típicamente __name__ del módulo).

        Returns:
            Logger configurado.
        """
        if not cls._configured:
            # Configuración por defecto si no se ha configurado
            cls.configure()
        return logging.getLogger(name)

    @classmethod
    def log_with_context(
        cls,
        logger: logging.Logger,
        level: int,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Registra un mensaje con contexto adicional.

        Args:
            logger: Logger a usar.
            level: Nivel de logging (logging.DEBUG, logging.INFO, etc.).
            message: Mensaje a registrar.
            **kwargs: Campos adicionales para incluir en el log estructurado.
        """
        # Crear un LogRecord con campos extra
        record = logger.makeRecord(
            logger.name,
            level,
            "",  # filename
            0,  # lineno
            message,
            (),  # args
            None,  # exc_info
        )
        record.extra_fields = kwargs
        logger.handle(record)


# Funciones de conveniencia para logging estructurado
def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger configurado.

    Args:
        name: Nombre del logger (típicamente __name__).

    Returns:
        Logger configurado.
    """
    return StructuredLogger.get_logger(name)


def configure_logging(
    level: str = "INFO",
    use_json: bool = False,
    use_colors: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """Configura el sistema de logging global.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        use_json: Si True, usa formato JSON estructurado.
        use_colors: Si True y use_json=False, usa colores en consola.
        log_file: Ruta opcional a archivo para escribir logs.
    """
    StructuredLogger.configure(
        level=level,
        use_json=use_json,
        use_colors=use_colors,
        log_file=log_file,
    )


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """Registra un mensaje con contexto adicional.

    Args:
        logger: Logger a usar.
        level: Nivel de logging (logging.DEBUG, logging.INFO, etc.).
        message: Mensaje a registrar.
        **kwargs: Campos adicionales para incluir en el log estructurado.
    """
    StructuredLogger.log_with_context(logger, level, message, **kwargs)


