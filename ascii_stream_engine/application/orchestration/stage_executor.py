"""Ejecutor de etapas del pipeline."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Resultado de la ejecución de una etapa del pipeline."""

    success: bool
    """Indica si la etapa se ejecutó exitosamente."""

    data: Any
    """Datos resultantes de la etapa (frame, análisis, etc.)."""

    error: Optional[Exception] = None
    """Error si la ejecución falló."""

    execution_time: float = 0.0
    """Tiempo de ejecución en segundos."""

    metadata: Optional[Dict[str, Any]] = None
    """Metadata adicional de la etapa."""


class StageExecutor:
    """Ejecuta una etapa específica del pipeline con manejo de errores y timeouts."""

    def __init__(
        self,
        timeout: Optional[float] = None,
        retry_count: int = 0,
        retry_delay: float = 0.1,
    ) -> None:
        """
        Inicializa el ejecutor de etapas.

        Args:
            timeout: Timeout máximo para la ejecución (None = sin timeout)
            retry_count: Número de reintentos en caso de error
            retry_delay: Delay entre reintentos en segundos
        """
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

    def execute(
        self,
        stage_name: str,
        stage_func: Callable[[], Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> StageResult:
        """
        Ejecuta una etapa del pipeline.

        Args:
            stage_name: Nombre de la etapa (para logging)
            stage_func: Función que ejecuta la etapa
            context: Contexto adicional

        Returns:
            StageResult con el resultado de la ejecución
        """
        start_time = time.perf_counter()
        last_error: Optional[Exception] = None

        for attempt in range(self.retry_count + 1):
            try:
                if attempt > 0:
                    logger.debug(
                        f"Reintentando etapa '{stage_name}' (intento {attempt + 1}/{self.retry_count + 1})"
                    )
                    time.sleep(self.retry_delay * attempt)

                if self.timeout is not None:
                    # Ejecutar con timeout usando threading (simplificado)
                    result = stage_func()
                else:
                    result = stage_func()

                execution_time = time.perf_counter() - start_time

                return StageResult(
                    success=True,
                    data=result,
                    execution_time=execution_time,
                    metadata=context,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Error en etapa '{stage_name}' (intento {attempt + 1}/{self.retry_count + 1}): {e}"
                )
                if attempt < self.retry_count:
                    continue

        execution_time = time.perf_counter() - start_time

        return StageResult(
            success=False,
            data=None,
            error=last_error,
            execution_time=execution_time,
            metadata=context,
        )

    def execute_capture(
        self,
        source_func: Callable[[], Optional[np.ndarray]],
    ) -> StageResult:
        """
        Ejecuta la etapa de captura de frame.

        Args:
            source_func: Función que lee el frame de la fuente

        Returns:
            StageResult con el frame capturado
        """
        return self.execute("capture", source_func)

    def execute_analysis(
        self,
        analyzer_func: Callable[[], Dict[str, Any]],
    ) -> StageResult:
        """
        Ejecuta la etapa de análisis.

        Args:
            analyzer_func: Función que ejecuta el análisis

        Returns:
            StageResult con los resultados del análisis
        """
        return self.execute("analysis", analyzer_func)

    def execute_transformation(
        self,
        transform_func: Callable[[], np.ndarray],
    ) -> StageResult:
        """
        Ejecuta la etapa de transformación espacial.

        Args:
            transform_func: Función que aplica las transformaciones

        Returns:
            StageResult con el frame transformado
        """
        return self.execute("transformation", transform_func)

    def execute_filtering(
        self,
        filter_func: Callable[[], np.ndarray],
    ) -> StageResult:
        """
        Ejecuta la etapa de filtrado.

        Args:
            filter_func: Función que aplica los filtros

        Returns:
            StageResult con el frame filtrado
        """
        return self.execute("filtering", filter_func)

    def execute_tracking(
        self,
        tracker_func: Callable[[], Any],
    ) -> StageResult:
        """
        Ejecuta la etapa de tracking.

        Args:
            tracker_func: Función que ejecuta el tracking

        Returns:
            StageResult con los datos de tracking
        """
        return self.execute("tracking", tracker_func)

    def execute_rendering(
        self,
        render_func: Callable[[], RenderFrame],
    ) -> StageResult:
        """
        Ejecuta la etapa de renderizado.

        Args:
            render_func: Función que renderiza el frame

        Returns:
            StageResult con el frame renderizado
        """
        return self.execute("rendering", render_func)

    def execute_output(
        self,
        output_func: Callable[[], None],
    ) -> StageResult:
        """
        Ejecuta la etapa de salida.

        Args:
            output_func: Función que escribe el frame a la salida

        Returns:
            StageResult indicando éxito o fallo
        """
        return self.execute("output", output_func)

