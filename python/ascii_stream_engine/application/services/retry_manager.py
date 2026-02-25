"""Gestor de reintentos para operaciones del engine."""

import logging
import time
from typing import Callable, Optional, Tuple

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.outputs import OutputSink
from ...ports.sources import FrameSource

logger = logging.getLogger(__name__)


class RetryManager:
    """Gestiona reintentos y reconexiones para fuentes y salidas."""

    # Constantes para manejo de errores
    MAX_CAMERA_RETRIES = 5
    CAMERA_RETRY_DELAY = 1.0  # segundos
    MAX_UDP_RETRIES = 3
    UDP_RETRY_DELAY_BASE = 0.1  # segundos (backoff exponencial)

    def __init__(
        self,
        max_camera_retries: int = MAX_CAMERA_RETRIES,
        camera_retry_delay: float = CAMERA_RETRY_DELAY,
        max_udp_retries: int = MAX_UDP_RETRIES,
        udp_retry_delay_base: float = UDP_RETRY_DELAY_BASE,
    ) -> None:
        """
        Inicializa el gestor de reintentos.

        Args:
            max_camera_retries: Número máximo de reintentos para cámara
            camera_retry_delay: Delay base entre reintentos de cámara
            max_udp_retries: Número máximo de reintentos para UDP
            udp_retry_delay_base: Delay base entre reintentos de UDP
        """
        self.max_camera_retries = max_camera_retries
        self.camera_retry_delay = camera_retry_delay
        self.max_udp_retries = max_udp_retries
        self.udp_retry_delay_base = udp_retry_delay_base

    def safe_close_source(self, source: FrameSource) -> None:
        """
        Cierra la fuente de forma segura, manejando errores.

        Args:
            source: Fuente a cerrar
        """
        try:
            source.close()
        except Exception as e:
            logger.warning(f"Error al cerrar fuente: {e}")

    def safe_close_sink(self, sink: OutputSink) -> None:
        """
        Cierra el sink de forma segura, manejando errores.

        Args:
            sink: Sink a cerrar
        """
        try:
            sink.close()
        except Exception as e:
            logger.warning(f"Error al cerrar sink: {e}")

    def reopen_source(
        self,
        source: FrameSource,
        stop_event: Optional[object] = None,
    ) -> bool:
        """
        Intenta reabrir la fuente (cámara) con reintentos.

        Args:
            source: Fuente a reabrir
            stop_event: Evento para detener los reintentos si está configurado

        Returns:
            True si se reabrió exitosamente, False en caso contrario
        """
        for attempt in range(self.max_camera_retries):
            if stop_event and stop_event.is_set():
                return False
            try:
                self.safe_close_source(source)
                time.sleep(self.camera_retry_delay * (attempt + 1))
                source.open()
                logger.info(f"Cámara reabierta exitosamente después de {attempt + 1} intento(s)")
                return True
            except Exception as e:
                logger.warning(
                    f"Intento {attempt + 1}/{self.max_camera_retries} de reabrir cámara falló: {e}"
                )
        logger.error("No se pudo reabrir la cámara después de todos los intentos")
        return False

    def write_with_retry(
        self,
        sink: OutputSink,
        rendered: RenderFrame,
        config: EngineConfig,
        output_size: Tuple[int, int],
        stop_event: Optional[object] = None,
    ) -> bool:
        """
        Intenta escribir al sink (UDP) con reintentos y reconexión si es necesario.

        Args:
            sink: Sink de salida
            rendered: Frame renderizado a escribir
            config: Configuración del engine
            output_size: Tamaño de salida (width, height)
            stop_event: Evento para detener los reintentos si está configurado

        Returns:
            True si se escribió exitosamente, False en caso contrario
        """
        last_exception = None
        for attempt in range(self.max_udp_retries):
            if stop_event and stop_event.is_set():
                return False
            try:
                sink.write(rendered)
                return True
            except (BrokenPipeError, OSError, IOError) as e:
                last_exception = e
                logger.warning(
                    f"Error al escribir UDP (intento {attempt + 1}/{self.max_udp_retries}): {e}"
                )
                if attempt < self.max_udp_retries - 1:
                    # Intentar reconectar el sink
                    try:
                        self.safe_close_sink(sink)
                        time.sleep(self.udp_retry_delay_base * (2**attempt))
                        sink.open(config, output_size)
                        logger.info("Sink UDP reconectado, reintentando escritura")
                    except Exception as reconnect_error:
                        logger.error(f"Error al reconectar sink UDP: {reconnect_error}")
                        time.sleep(self.udp_retry_delay_base * (2**attempt))
            except Exception as e:
                # Otros errores no relacionados con UDP, no reintentar
                logger.error(f"Error inesperado al escribir al sink: {e}")
                return False

        logger.error(
            f"No se pudo escribir al sink UDP después de {self.max_udp_retries} intentos: {last_exception}"
        )
        return False

    def execute_with_retry(
        self,
        operation: Callable[[], any],
        max_retries: int = 3,
        retry_delay: float = 0.1,
        stop_event: Optional[object] = None,
        operation_name: str = "operation",
    ) -> Tuple[bool, Optional[any], Optional[Exception]]:
        """
        Ejecuta una operación con reintentos.

        Args:
            operation: Función a ejecutar
            max_retries: Número máximo de reintentos
            retry_delay: Delay entre reintentos
            stop_event: Evento para detener los reintentos
            operation_name: Nombre de la operación (para logging)

        Returns:
            Tupla (success, result, error)
        """
        last_exception = None
        for attempt in range(max_retries + 1):
            if stop_event and stop_event.is_set():
                return False, None, None
            try:
                result = operation()
                return True, result, None
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"Error en {operation_name} (intento {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"Error en {operation_name} después de {max_retries + 1} intentos: {e}"
                    )

        return False, None, last_exception
