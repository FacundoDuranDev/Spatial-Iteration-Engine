"""Motor principal de streaming de frames."""

import logging
import threading
import time
from typing import Dict, Optional, Tuple

from ..domain.config import EngineConfig
from ..domain.events import ConfigChangeEvent
from ..domain.types import RenderFrame
from ..infrastructure.event_bus import EventBus
from ..infrastructure.metrics import EngineMetrics
from ..infrastructure.plugins import PluginManager
from ..infrastructure.profiling import LoopProfiler
from ..ports.outputs import OutputSink
from ..ports.renderers import FrameRenderer
from ..ports.sources import FrameSource
from .graph.bridge.graph_builder import GraphBuilder
from .graph.scheduler.graph_scheduler import GraphScheduler
from .parallel_pipeline import FrameProcessor
from .pipeline import (
    AnalyzerPipeline,
    FilterPipeline,
    TrackingPipeline,
    TransformationPipeline,
)
from .services import ErrorHandler, FrameBuffer, RetryManager, TemporalManager

logger = logging.getLogger(__name__)


class StreamEngine:
    """Motor principal para streaming de frames en tiempo real.

    Orquesta el pipeline completo: captura → análisis → transformación →
    filtrado → tracking → renderizado → salida.
    """

    # Constantes para manejo de errores
    MAX_CONSECUTIVE_CAMERA_FAILURES = 10

    def __init__(
        self,
        source: FrameSource,
        renderer: FrameRenderer,
        sink: OutputSink,
        config: Optional[EngineConfig] = None,
        analyzers: Optional[AnalyzerPipeline] = None,
        filters: Optional[FilterPipeline] = None,
        trackers: Optional[TrackingPipeline] = None,
        transformations: Optional[TransformationPipeline] = None,
        sensors: Optional[list] = None,  # Lista de sensores
        enable_profiling: bool = False,
    ) -> None:
        """
        Inicializa el engine.

        Args:
            source: Fuente de frames
            renderer: Renderer de frames
            sink: Salida de frames
            config: Configuración del engine
            analyzers: Pipeline de analizadores
            filters: Pipeline de filtros
            trackers: Pipeline de trackers
            transformations: Pipeline de transformaciones
            sensors: Lista de sensores
            enable_profiling: Habilitar profiling de performance
        """
        self._config = config or EngineConfig()
        self._config_lock = threading.Lock()
        self._config_version = 0
        self._cached_config: Optional[EngineConfig] = None
        self._cached_config_version = -1
        self._source = source
        self._renderer = renderer
        self._sink = sink
        self._analyzers = analyzers or AnalyzerPipeline()
        self._filters = filters or FilterPipeline()
        self._trackers = trackers
        self._transformations = transformations
        self._sensors = sensors or []
        self._analysis_lock = threading.Lock()
        self._last_analysis: Dict[str, object] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._camera_failure_lock = threading.Lock()
        self._consecutive_camera_failures = 0

        # Servicios
        self._profiler = LoopProfiler(enabled=enable_profiling)
        self._metrics = EngineMetrics()
        self._retry_manager = RetryManager()
        self._frame_buffer = FrameBuffer(max_size=self._config.frame_buffer_size)
        self._temporal = TemporalManager() if self._config.enable_temporal else None

        # Sistema de eventos
        self._event_bus = EventBus() if self._config.enable_events else None
        self._error_handler = ErrorHandler(event_bus=self._event_bus)

        # Plugin manager
        if self._config.plugin_paths:
            self._plugin_manager = PluginManager(self._config.plugin_paths)
        else:
            self._plugin_manager = None

        # Procesamiento paralelo
        if self._config.parallel_workers > 0:
            self._frame_processor = FrameProcessor(num_workers=self._config.parallel_workers)
        else:
            self._frame_processor = None

        # Scheduler del graph
        self._orchestrator: Optional[GraphScheduler] = None
        self._pipeline_version_snapshot: int = 0

        # Configurar sensores con event bus
        if self._sensors and self._event_bus:
            for sensor in self._sensors:
                sensor.set_event_bus(self._event_bus)

    @property
    def is_running(self) -> bool:
        """Verifica si el engine está en ejecución."""
        return self._thread is not None and self._thread.is_alive()

    def get_config(self) -> EngineConfig:
        """Obtiene la configuración actual del engine."""
        with self._config_lock:
            return EngineConfig(**vars(self._config))

    def _get_config_snapshot(self) -> EngineConfig:
        """Fast config access for hot path — only copies when config changes."""
        with self._config_lock:
            if self._config_version != self._cached_config_version:
                self._cached_config = EngineConfig(**vars(self._config))
                self._cached_config_version = self._config_version
            return self._cached_config

    def update_config(self, **kwargs) -> None:
        """Actualiza la configuración del engine."""
        with self._config_lock:
            old_values = {}
            for key, value in kwargs.items():
                if not hasattr(self._config, key):
                    raise ValueError(f"Parametro desconocido: {key}")
                old_values[key] = getattr(self._config, key)
                setattr(self._config, key, value)
            self._config_version += 1
            try:
                EngineConfig(**vars(self._config))
            except ValueError as e:
                for key, old_value in old_values.items():
                    setattr(self._config, key, old_value)
                raise ValueError(f"Configuración inválida después de actualizar: {e}") from e

            if self._event_bus and old_values:
                event = ConfigChangeEvent(
                    changed_params=kwargs,
                    old_values=old_values,
                )
                self._event_bus.publish(event, "config_change")

            # Actualizar orquestador si existe
            if self._orchestrator:
                self._orchestrator.update_config(self._config)

            # Actualizar frame buffer si cambió el tamaño
            if "frame_buffer_size" in kwargs:
                self._frame_buffer.set_max_size(kwargs["frame_buffer_size"])

    def get_source(self) -> FrameSource:
        """Obtiene la fuente de frames."""
        return self._source

    def set_source(self, source: FrameSource) -> None:
        """Establece una nueva fuente de frames."""
        self._source = source
        if self._orchestrator:
            # Recrear orquestador con nueva fuente
            self._create_orchestrator()

    def get_renderer(self) -> FrameRenderer:
        """Obtiene el renderer."""
        return self._renderer

    def set_renderer(self, renderer: FrameRenderer) -> None:
        """Establece un nuevo renderer."""
        self._renderer = renderer
        if self._orchestrator:
            self._create_orchestrator()

    def get_sink(self) -> OutputSink:
        """Obtiene el sink de salida."""
        return self._sink

    def set_sink(self, sink: OutputSink) -> None:
        """Establece un nuevo sink de salida."""
        self._sink = sink
        if self._orchestrator:
            self._create_orchestrator()

    @property
    def analyzer_pipeline(self) -> AnalyzerPipeline:
        """Obtiene el pipeline de analizadores."""
        return self._analyzers

    @property
    def filter_pipeline(self) -> FilterPipeline:
        """Obtiene el pipeline de filtros."""
        return self._filters

    @property
    def transformation_pipeline(self) -> Optional[TransformationPipeline]:
        """Obtiene el pipeline de transformaciones."""
        return self._transformations

    @property
    def analyzers(self) -> list:
        """Obtiene la lista de analizadores."""
        return self._analyzers.analyzers

    @property
    def filters(self) -> list:
        """Obtiene la lista de filtros."""
        return self._filters.filters

    def get_last_analysis(self) -> Dict[str, object]:
        """Obtiene el último análisis realizado."""
        with self._analysis_lock:
            return dict(self._last_analysis)

    @property
    def profiler(self) -> LoopProfiler:
        """Obtiene el profiler del engine."""
        return self._profiler

    @property
    def metrics(self) -> EngineMetrics:
        """Obtiene el sistema de métricas del engine."""
        return self._metrics

    def get_event_bus(self) -> Optional[EventBus]:
        """Obtiene el bus de eventos."""
        return self._event_bus

    def get_plugin_manager(self) -> Optional[PluginManager]:
        """Obtiene el gestor de plugins."""
        return self._plugin_manager

    def get_profiling_report(self) -> str:
        """Obtiene un reporte de texto con las estadísticas de profiling."""
        return self._profiler.get_report()

    def get_profiling_stats(self) -> Dict[str, Dict[str, float]]:
        """Obtiene las estadísticas de profiling como diccionario."""
        return self._profiler.get_summary_dict()

    def _combined_pipeline_version(self) -> int:
        """Sum of all pipeline version counters for change detection."""
        v = getattr(self._filters, "version", 0)
        v += getattr(self._analyzers, "version", 0)
        if self._trackers:
            v += getattr(self._trackers, "version", 0)
        if self._transformations:
            v += getattr(self._transformations, "version", 0)
        return v

    def get_node_timings(self) -> Dict[str, float]:
        """Get per-node timing data from the graph scheduler.

        Returns:
            Dict mapping node names to their last execution time in seconds.
            Empty dict if not using graph mode or no timings available.
        """
        if self._orchestrator and hasattr(self._orchestrator, "get_node_timings"):
            return self._orchestrator.get_node_timings()
        return {}

    def build_graph(self):
        """Build and return a Graph pre-populated with the engine's current adapters.

        The returned graph mirrors the standard pipeline order and can be extended
        with add_branch() / add_composite() / fan_out() before passing to a
        GraphScheduler manually.

        Returns:
            A Graph instance ready for extension or direct execution.
        """
        return GraphBuilder.build(
            source=self._source,
            renderer=self._renderer,
            sink=self._sink,
            filters=self._filters,
            analyzers=self._analyzers,
            trackers=self._trackers,
            transforms=self._transformations,
        )

    def _create_orchestrator(self) -> None:
        """Build the GraphScheduler for the current pipelines."""
        graph = self.build_graph()
        self._orchestrator = GraphScheduler(
            graph=graph,
            config=self._config,
            temporal_manager=self._temporal,
            event_bus=self._event_bus,
            profiler=self._profiler,
            metrics=self._metrics,
        )

    def start(self, blocking: bool = False) -> None:
        """Inicia el engine."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._metrics.start()

        # Crear orquestador
        self._create_orchestrator()

        # Iniciar procesamiento paralelo si está habilitado
        if self._frame_processor:
            self._frame_processor.start()

        if blocking:
            self._run()
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Detiene el engine."""
        self._stop_event.set()

        # Detener procesamiento paralelo
        if self._frame_processor:
            self._frame_processor.stop()

        self._retry_manager.safe_close_source(self._source)
        self._retry_manager.safe_close_sink(self._sink)
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        if self._thread:
            self._thread.join(timeout=2)

    def _start_capture_thread(self, config: EngineConfig) -> None:
        """Inicia el thread de captura de frames."""
        if config.frame_buffer_size <= 0:
            return

        def _capture_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    frame = self._source.read()
                except Exception as e:
                    self._error_handler.handle_capture_error(e)
                    with self._camera_failure_lock:
                        self._consecutive_camera_failures += 1
                        failures = self._consecutive_camera_failures

                    if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                        logger.warning(
                            f"{failures} fallos consecutivos de cámara, intentando reabrir..."
                        )
                        if not self._retry_manager.reopen_source(self._source, self._stop_event):
                            logger.error("No se pudo recuperar la cámara, deteniendo captura")
                            break
                    else:
                        time.sleep(config.sleep_on_empty)
                    continue

                if frame is None:
                    with self._camera_failure_lock:
                        self._consecutive_camera_failures += 1
                        failures = self._consecutive_camera_failures

                    if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                        logger.warning(
                            f"{failures} frames None consecutivos, intentando reabrir cámara..."
                        )
                        if not self._retry_manager.reopen_source(self._source, self._stop_event):
                            logger.error("No se pudo recuperar la cámara, deteniendo captura")
                            break
                    else:
                        time.sleep(config.sleep_on_empty)
                    continue

                # Éxito: resetear contador
                with self._camera_failure_lock:
                    if self._consecutive_camera_failures > 0:
                        logger.info("Cámara recuperada, captura normal reanudada")
                        self._consecutive_camera_failures = 0

                self._frame_buffer.add(frame, time.time())

        self._capture_thread = threading.Thread(target=_capture_loop, daemon=True)
        self._capture_thread.start()

    def _run(self) -> None:
        """Loop principal del engine."""
        cfg = self._get_config_snapshot()
        try:
            self._source.open()
            logger.info("Fuente (cámara) abierta exitosamente")
        except Exception as e:
            logger.error(f"Error al abrir fuente (cámara): {e}")
            if not self._retry_manager.reopen_source(self._source, self._stop_event):
                logger.error("No se pudo abrir la cámara, deteniendo engine")
                return

        self._start_capture_thread(cfg)
        output_size = self._renderer.output_size(cfg)
        try:
            self._sink.open(cfg, output_size)
            logger.info("Sink abierto exitosamente")
        except Exception as e:
            logger.error(f"Error al abrir sink: {e}")
            self._retry_manager.safe_close_source(self._source)
            return

        sink_signature = (
            output_size,
            cfg.fps,
            cfg.host,
            cfg.port,
            cfg.pkt_size,
            cfg.bitrate,
            cfg.udp_broadcast,
        )

        last = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                # Obtener frame
                frame: Optional[any] = None
                timestamp: Optional[float] = None

                if cfg.frame_buffer_size > 0:
                    latest = self._frame_buffer.get_latest()
                    if latest is None:
                        time.sleep(cfg.sleep_on_empty)
                        continue
                    frame, timestamp = latest
                else:
                    try:
                        frame = self._source.read()
                        timestamp = time.time()
                    except Exception as e:
                        self._error_handler.handle_capture_error(e)
                        with self._camera_failure_lock:
                            self._consecutive_camera_failures += 1
                            failures = self._consecutive_camera_failures

                        if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                            logger.warning(
                                f"{failures} fallos consecutivos, intentando reabrir cámara..."
                            )
                            if not self._retry_manager.reopen_source(
                                self._source, self._stop_event
                            ):
                                logger.error("No se pudo recuperar la cámara, deteniendo engine")
                                break
                        else:
                            time.sleep(cfg.sleep_on_empty)
                        continue

                    if frame is None:
                        with self._camera_failure_lock:
                            self._consecutive_camera_failures += 1
                            failures = self._consecutive_camera_failures

                        if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                            logger.warning(
                                f"{failures} frames None consecutivos, intentando reabrir cámara..."
                            )
                            if not self._retry_manager.reopen_source(
                                self._source, self._stop_event
                            ):
                                logger.error("No se pudo recuperar la cámara, deteniendo engine")
                                break
                        else:
                            time.sleep(cfg.sleep_on_empty)
                        continue

                    # Éxito: resetear contador
                    with self._camera_failure_lock:
                        if self._consecutive_camera_failures > 0:
                            logger.info("Cámara recuperada")
                            self._consecutive_camera_failures = 0

                # Verificar si la configuración del sink cambió
                cfg = self._get_config_snapshot()
                desired_output_size = self._renderer.output_size(cfg)
                desired_signature = (
                    desired_output_size,
                    cfg.fps,
                    cfg.host,
                    cfg.port,
                    cfg.pkt_size,
                    cfg.bitrate,
                    cfg.udp_broadcast,
                )
                if desired_signature != sink_signature:
                    logger.info("Configuración de sink cambió, reconectando...")
                    self._retry_manager.safe_close_sink(self._sink)
                    try:
                        self._sink.open(cfg, desired_output_size)
                        sink_signature = desired_signature
                        logger.info("Sink reconectado exitosamente")
                    except Exception as e:
                        logger.error(f"Error al reconectar sink: {e}")
                        break

                # Auto-rebuild graph when pipelines are mutated at runtime
                current_v = self._combined_pipeline_version()
                if current_v != self._pipeline_version_snapshot:
                    self._create_orchestrator()
                    self._pipeline_version_snapshot = current_v

                # Procesar frame usando el orquestador
                if self._orchestrator:
                    success, error_msg = self._orchestrator.process_frame(frame, timestamp)
                    if not success:
                        if error_msg:
                            logger.error(f"Error procesando frame: {error_msg}")
                        # Continuar con el siguiente frame
                        time.sleep(cfg.sleep_on_empty)
                        continue

                    # Actualizar último análisis
                    with self._analysis_lock:
                        self._last_analysis = self._orchestrator.get_last_analysis()

                # Registrar frame procesado exitosamente
                self._metrics.record_frame()

                # Control de FPS
                target = 1.0 / max(1, int(cfg.fps))
                now = time.perf_counter()
                sleep = target - (now - last)
                if sleep > 0:
                    time.sleep(sleep)
                last = time.perf_counter()
        except KeyboardInterrupt:
            logger.info("Interrupción de teclado recibida")
        except Exception as e:
            logger.error(f"Error inesperado en loop principal: {e}", exc_info=True)
        finally:
            logger.info("Cerrando engine...")
            self._retry_manager.safe_close_source(self._source)
            self._retry_manager.safe_close_sink(self._sink)
            logger.info("Engine cerrado")
