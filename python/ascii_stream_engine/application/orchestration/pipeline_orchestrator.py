"""Orquestador del pipeline completo de procesamiento de frames."""

import logging
import time
from typing import Dict, Optional, Tuple

import numpy as np

from ...domain.config import EngineConfig
from ...domain.events import (
    AnalysisCompleteEvent,
    FilterAppliedEvent,
    FrameCapturedEvent,
    FrameWrittenEvent,
    RenderCompleteEvent,
)
from ...domain.types import RenderFrame
from ...infrastructure.event_bus import EventBus
from ...infrastructure.profiling import LoopProfiler
from ...ports.outputs import OutputSink
from ...ports.renderers import FrameRenderer
from ...ports.sources import FrameSource
from ..pipeline import (
    AnalyzerPipeline,
    FilterPipeline,
    TransformationPipeline,
    TrackingPipeline,
)
from .stage_executor import StageExecutor, StageResult

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orquesta el flujo completo del pipeline de procesamiento de frames.

    Capas conceptuales (V1): Source → Perception → Semantic/Transformations
    → Visual Modifiers (filters) → Renderer → Output.
    Secuencia de ejecución: capture → analysis → tracking → transformation
    → filtering → render → output.
    """

    def __init__(
        self,
        source: FrameSource,
        renderer: FrameRenderer,
        sink: OutputSink,
        config: EngineConfig,
        analyzers: Optional[AnalyzerPipeline] = None,
        filters: Optional[FilterPipeline] = None,
        trackers: Optional[TrackingPipeline] = None,
        transformations: Optional[TransformationPipeline] = None,
        event_bus: Optional[EventBus] = None,
        profiler: Optional[LoopProfiler] = None,
    ) -> None:
        """
        Inicializa el orquestador.

        Args:
            source: Fuente de frames
            renderer: Renderer de frames
            sink: Salida de frames
            config: Configuración del engine
            analyzers: Pipeline de analizadores
            filters: Pipeline de filtros
            trackers: Pipeline de trackers
            transformations: Pipeline de transformaciones
            event_bus: Bus de eventos (opcional)
            profiler: Profiler de performance (opcional)
        """
        self._source = source
        self._renderer = renderer
        self._sink = sink
        self._config = config
        self._analyzers = analyzers
        self._filters = filters
        self._trackers = trackers
        self._transformations = transformations
        self._event_bus = event_bus
        self._profiler = profiler

        # Ejecutor de etapas con configuración
        self._stage_executor = StageExecutor(
            timeout=None,  # Sin timeout por defecto
            retry_count=0,  # Sin reintentos por defecto
        )

        # Estado interno
        self._last_analysis: Dict[str, object] = {}
        self._frame_id_counter = 0

    def process_frame(
        self, frame: Optional[np.ndarray] = None, timestamp: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Procesa un frame completo a través de todas las etapas del pipeline.

        Args:
            frame: Frame a procesar (si None, se lee de la fuente)
            timestamp: Timestamp del frame (si None, se genera)

        Returns:
            Tupla (success, error_message)
        """
        if timestamp is None:
            timestamp = time.time()

        # Generar ID único para el frame
        self._frame_id_counter += 1
        frame_id = f"frame_{int(timestamp * 1000)}_{self._frame_id_counter}"

        # Fase 1: Captura
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_CAPTURE)

        if frame is None:
            capture_result = self._stage_executor.execute_capture(
                lambda: self._source.read()
            )
            if not capture_result.success:
                if self._profiler:
                    self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)
                    self._profiler.end_frame()
                return False, f"Error en captura: {capture_result.error}"
            frame = capture_result.data
            if frame is None:
                if self._profiler:
                    self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)
                    self._profiler.end_frame()
                return False, "Frame capturado es None"

        if self._profiler:
            self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)

        # Publicar evento de captura
        if self._event_bus:
            event = FrameCapturedEvent(
                frame=frame,
                frame_id=frame_id,
                timestamp=timestamp,
            )
            self._event_bus.publish(event, "frame_captured")

        # Fase 2: Análisis
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_ANALYSIS)

        analysis: Dict[str, object] = {}
        if self._analyzers and self._analyzers.has_any():
            analysis_result = self._stage_executor.execute_analysis(
                lambda: self._analyzers.run(frame, self._config)
            )
            if not analysis_result.success:
                logger.warning(f"Error en análisis: {analysis_result.error}")
                analysis = {}
            else:
                analysis = analysis_result.data
                analysis["timestamp"] = timestamp

        # Tracking si está disponible
        if self._trackers and self._trackers.has_any() and analysis:
            try:
                tracking_result = self._trackers.run(frame, analysis, self._config)
                if hasattr(tracking_result, "to_dict"):
                    analysis["tracking"] = tracking_result.to_dict()
                else:
                    analysis["tracking"] = tracking_result
            except Exception as e:
                logger.warning(f"Error en tracking: {e}")

        self._last_analysis = analysis

        if self._profiler:
            analysis_time = self._profiler.get_phase_time(LoopProfiler.PHASE_ANALYSIS)
            self._profiler.end_phase(LoopProfiler.PHASE_ANALYSIS)

        # Publicar evento de análisis
        if self._event_bus:
            event = AnalysisCompleteEvent(
                frame_id=frame_id,
                results=analysis,
                timestamp=timestamp,
                analysis_time=analysis_time if self._profiler else 0.0,
            )
            self._event_bus.publish(event, "analysis_complete")

        # Fase 3: Transformaciones Espaciales
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_TRANSFORMATION)

        if self._transformations and self._transformations.transforms:
            transform_result = self._stage_executor.execute_transformation(
                lambda: self._transformations.apply(frame)
            )
            if not transform_result.success:
                logger.warning(f"Error en transformaciones: {transform_result.error}")
            else:
                frame = transform_result.data

        if self._profiler:
            self._profiler.end_phase(LoopProfiler.PHASE_TRANSFORMATION)

        # Fase 4: Filtrado
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_FILTERING)

        if self._filters and self._filters.has_any():
            filter_result = self._stage_executor.execute_filtering(
                lambda: self._filters.apply(frame, self._config, analysis)
            )
            if not filter_result.success:
                logger.warning(f"Error en filtrado: {filter_result.error}")
            else:
                frame = filter_result.data

                # Publicar evento de filtro aplicado
                if self._event_bus:
                    event = FilterAppliedEvent(
                        frame_id=frame_id,
                        filter_name="filter_pipeline",
                        timestamp=timestamp,
                    )
                    self._event_bus.publish(event, "filter_applied")

        if self._profiler:
            self._profiler.end_phase(LoopProfiler.PHASE_FILTERING)

        # Fase 5: Renderizado
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_RENDERING)

        render_result = self._stage_executor.execute_rendering(
            lambda: self._renderer.render(frame, self._config, analysis)
        )
        if not render_result.success:
            if self._profiler:
                self._profiler.end_phase(LoopProfiler.PHASE_RENDERING)
                self._profiler.end_frame()
            return False, f"Error en renderizado: {render_result.error}"

        rendered: RenderFrame = render_result.data
        if isinstance(rendered, RenderFrame) and rendered.metadata is None:
            rendered.metadata = {"analysis": analysis}

        if self._profiler:
            render_time = self._profiler.get_phase_time(LoopProfiler.PHASE_RENDERING)
            self._profiler.end_phase(LoopProfiler.PHASE_RENDERING)

        # Publicar evento de renderizado
        if self._event_bus:
            output_size = self._renderer.output_size(self._config)
            event = RenderCompleteEvent(
                frame_id=frame_id,
                timestamp=timestamp,
                render_time=render_time if self._profiler else 0.0,
                output_size=output_size,
            )
            self._event_bus.publish(event, "render_complete")

        # Fase 6: Salida
        if self._profiler:
            self._profiler.start_phase(LoopProfiler.PHASE_WRITING)

        write_start = time.perf_counter()
        output_result = self._stage_executor.execute_output(
            lambda: self._sink.write(rendered)
        )
        if not output_result.success:
            if self._profiler:
                self._profiler.end_phase(LoopProfiler.PHASE_WRITING)
                self._profiler.end_frame()
            return False, f"Error en salida: {output_result.error}"

        write_time = time.perf_counter() - write_start

        if self._profiler:
            self._profiler.end_phase(LoopProfiler.PHASE_WRITING)
            self._profiler.end_frame()

        # Publicar evento de escritura
        if self._event_bus:
            event = FrameWrittenEvent(
                frame_id=frame_id,
                timestamp=timestamp,
                write_time=write_time,
            )
            self._event_bus.publish(event, "frame_written")

        return True, None

    def get_last_analysis(self) -> Dict[str, object]:
        """Obtiene el último análisis realizado."""
        return dict(self._last_analysis)

    def update_config(self, config: EngineConfig) -> None:
        """Actualiza la configuración del orquestador."""
        self._config = config

