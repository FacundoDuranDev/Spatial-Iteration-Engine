import logging
import threading
import time
from collections import deque
from typing import Dict, Optional, Tuple

from ..domain.config import EngineConfig
from .pipeline import AnalyzerPipeline, FilterPipeline
from ..domain.types import RenderFrame
from ..ports.outputs import OutputSink
from ..ports.renderers import FrameRenderer
from ..ports.sources import FrameSource
from ..infrastructure.profiling import LoopProfiler

logger = logging.getLogger(__name__)


class StreamEngine:
    # Constantes para manejo de errores
    MAX_CAMERA_RETRIES = 5
    CAMERA_RETRY_DELAY = 1.0  # segundos
    MAX_CONSECUTIVE_CAMERA_FAILURES = 10
    MAX_UDP_RETRIES = 3
    UDP_RETRY_DELAY_BASE = 0.1  # segundos (backoff exponencial)

    def __init__(
        self,
        source: FrameSource,
        renderer: FrameRenderer,
        sink: OutputSink,
        config: Optional[EngineConfig] = None,
        analyzers: Optional[AnalyzerPipeline] = None,
        filters: Optional[FilterPipeline] = None,
        enable_profiling: bool = False,
    ) -> None:
        self._config = config or EngineConfig()
        self._config_lock = threading.Lock()
        self._source = source
        self._renderer = renderer
        self._sink = sink
        self._analyzers = analyzers or AnalyzerPipeline()
        self._filters = filters or FilterPipeline()
        self._analysis_lock = threading.Lock()
        self._last_analysis: Dict[str, object] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._buffer_lock = threading.Lock()
        self._frame_buffer = deque(maxlen=self._config.frame_buffer_size)
        self._profiler = LoopProfiler(enabled=enable_profiling)
        self._camera_failure_lock = threading.Lock()
        self._consecutive_camera_failures = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_config(self) -> EngineConfig:
        with self._config_lock:
            # Crear nueva instancia para validar (__post_init__ se ejecuta)
            return EngineConfig(**vars(self._config))

    def update_config(self, **kwargs) -> None:
        with self._config_lock:
            for key, value in kwargs.items():
                if not hasattr(self._config, key):
                    raise ValueError(f"Parametro desconocido: {key}")
                setattr(self._config, key, value)
            # Validar la configuración completa después de actualizar
            # Crear una instancia temporal para validar
            try:
                EngineConfig(**vars(self._config))
            except ValueError as e:
                # Revertir cambios si la validación falla
                # (En una implementación más robusta, podríamos guardar el estado anterior)
                raise ValueError(f"Configuración inválida después de actualizar: {e}") from e

    def get_source(self) -> FrameSource:
        return self._source

    def set_source(self, source: FrameSource) -> None:
        self._source = source

    def get_renderer(self) -> FrameRenderer:
        return self._renderer

    def set_renderer(self, renderer: FrameRenderer) -> None:
        self._renderer = renderer

    def get_sink(self) -> OutputSink:
        return self._sink

    def set_sink(self, sink: OutputSink) -> None:
        self._sink = sink

    @property
    def analyzer_pipeline(self) -> AnalyzerPipeline:
        return self._analyzers

    @property
    def filter_pipeline(self) -> FilterPipeline:
        return self._filters

    @property
    def analyzers(self) -> list:
        return self._analyzers.analyzers

    @property
    def filters(self) -> list:
        return self._filters.filters

    def get_last_analysis(self) -> Dict[str, object]:
        with self._analysis_lock:
            return dict(self._last_analysis)

    @property
    def profiler(self) -> LoopProfiler:
        """Obtiene el profiler del engine."""
        return self._profiler

    def get_profiling_report(self) -> str:
        """
        Obtiene un reporte de texto con las estadísticas de profiling.

        Returns:
            String con el reporte formateado.
        """
        return self._profiler.get_report()

    def get_profiling_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Obtiene las estadísticas de profiling como diccionario.

        Returns:
            Diccionario con estadísticas por fase.
        """
        return self._profiler.get_summary_dict()

    def start(self, blocking: bool = False) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        if blocking:
            self._run()
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._safe_close_source()
        self._safe_close_sink()
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        if self._thread:
            self._thread.join(timeout=2)

    def _safe_close_source(self) -> None:
        try:
            self._source.close()
        except Exception as e:
            logger.warning(f"Error al cerrar fuente: {e}")

    def _safe_close_sink(self) -> None:
        try:
            self._sink.close()
        except Exception as e:
            logger.warning(f"Error al cerrar sink: {e}")

    def _reopen_source(self, config: EngineConfig) -> bool:
        """Intenta reabrir la fuente (cámara) con reintentos."""
        for attempt in range(self.MAX_CAMERA_RETRIES):
            if self._stop_event.is_set():
                return False
            try:
                self._safe_close_source()
                time.sleep(self.CAMERA_RETRY_DELAY * (attempt + 1))
                self._source.open()
                logger.info(f"Cámara reabierta exitosamente después de {attempt + 1} intento(s)")
                with self._camera_failure_lock:
                    self._consecutive_camera_failures = 0
                return True
            except Exception as e:
                logger.warning(
                    f"Intento {attempt + 1}/{self.MAX_CAMERA_RETRIES} de reabrir cámara falló: {e}"
                )
        logger.error("No se pudo reabrir la cámara después de todos los intentos")
        return False

    def _write_with_retry(
        self, rendered: RenderFrame, config: EngineConfig, output_size: Tuple[int, int]
    ) -> bool:
        """Intenta escribir al sink (UDP) con reintentos y reconexión si es necesario."""
        last_exception = None
        for attempt in range(self.MAX_UDP_RETRIES):
            if self._stop_event.is_set():
                return False
            try:
                self._sink.write(rendered)
                return True
            except (BrokenPipeError, OSError, IOError) as e:
                last_exception = e
                logger.warning(
                    f"Error al escribir UDP (intento {attempt + 1}/{self.MAX_UDP_RETRIES}): {e}"
                )
                if attempt < self.MAX_UDP_RETRIES - 1:
                    # Intentar reconectar el sink
                    try:
                        self._safe_close_sink()
                        time.sleep(self.UDP_RETRY_DELAY_BASE * (2 ** attempt))
                        self._sink.open(config, output_size)
                        logger.info("Sink UDP reconectado, reintentando escritura")
                    except Exception as reconnect_error:
                        logger.error(f"Error al reconectar sink UDP: {reconnect_error}")
                        time.sleep(self.UDP_RETRY_DELAY_BASE * (2 ** attempt))
            except Exception as e:
                # Otros errores no relacionados con UDP, no reintentar
                logger.error(f"Error inesperado al escribir al sink: {e}")
                return False

        logger.error(
            f"No se pudo escribir al sink UDP después de {self.MAX_UDP_RETRIES} intentos: {last_exception}"
        )
        return False

    def _start_capture_thread(self, config: EngineConfig) -> None:
        if config.frame_buffer_size <= 0:
            return
        self._frame_buffer = deque(maxlen=config.frame_buffer_size)

        def _capture_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    frame = self._source.read()
                except Exception as e:
                    logger.warning(f"Error al leer de la cámara: {e}")
                    with self._camera_failure_lock:
                        self._consecutive_camera_failures += 1
                        failures = self._consecutive_camera_failures

                    # Si hay muchos fallos consecutivos, intentar reabrir la cámara
                    if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                        logger.warning(
                            f"{failures} fallos consecutivos de cámara, intentando reabrir..."
                        )
                        if not self._reopen_source(config):
                            logger.error(
                                "No se pudo recuperar la cámara, deteniendo captura"
                            )
                            break
                    else:
                        time.sleep(config.sleep_on_empty)
                    continue

                if frame is None:
                    with self._camera_failure_lock:
                        self._consecutive_camera_failures += 1
                        failures = self._consecutive_camera_failures

                    # Si hay muchos frames None consecutivos, puede ser un problema de cámara
                    if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                        logger.warning(
                            f"{failures} frames None consecutivos, intentando reabrir cámara..."
                        )
                        if not self._reopen_source(config):
                            logger.error(
                                "No se pudo recuperar la cámara, deteniendo captura"
                            )
                            break
                    else:
                        time.sleep(config.sleep_on_empty)
                    continue

                # Éxito: resetear contador de fallos
                with self._camera_failure_lock:
                    if self._consecutive_camera_failures > 0:
                        logger.info("Cámara recuperada, captura normal reanudada")
                        self._consecutive_camera_failures = 0

                timestamp = time.time()
                with self._buffer_lock:
                    self._frame_buffer.append((frame, timestamp))

        self._capture_thread = threading.Thread(target=_capture_loop, daemon=True)
        self._capture_thread.start()

    def _get_latest_frame(self) -> Optional[Tuple[object, float]]:
        with self._buffer_lock:
            if not self._frame_buffer:
                return None
            frame, timestamp = self._frame_buffer.pop()
            self._frame_buffer.clear()
            return frame, timestamp

    def _run(self) -> None:
        cfg = self.get_config()
        try:
            self._source.open()
            logger.info("Fuente (cámara) abierta exitosamente")
        except Exception as e:
            logger.error(f"Error al abrir fuente (cámara): {e}")
            if not self._reopen_source(cfg):
                logger.error("No se pudo abrir la cámara, deteniendo engine")
                return

        self._start_capture_thread(cfg)
        output_size = self._renderer.output_size(cfg)
        try:
            self._sink.open(cfg, output_size)
            logger.info(f"Sink UDP abierto exitosamente en {cfg.host}:{cfg.port}")
        except Exception as e:
            logger.error(f"Error al abrir sink UDP: {e}")
            self._safe_close_source()
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
                # Inicio del frame completo
                self._profiler.start_frame()

                # Fase 1: Captura
                self._profiler.start_phase(LoopProfiler.PHASE_CAPTURE)
                if cfg.frame_buffer_size > 0:
                    latest = self._get_latest_frame()
                    if latest is None:
                        self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)
                        self._profiler.end_frame()
                        time.sleep(cfg.sleep_on_empty)
                        continue
                    frame, timestamp = latest
                else:
                    try:
                        frame = self._source.read()
                    except Exception as e:
                        self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)
                        self._profiler.end_frame()
                        logger.warning(f"Error al leer frame directamente de la fuente: {e}")
                        with self._camera_failure_lock:
                            self._consecutive_camera_failures += 1
                            failures = self._consecutive_camera_failures

                        if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                            logger.warning(
                                f"{failures} fallos consecutivos, intentando reabrir cámara..."
                            )
                            if not self._reopen_source(cfg):
                                logger.error("No se pudo recuperar la cámara, deteniendo engine")
                                break
                        else:
                            time.sleep(cfg.sleep_on_empty)
                        continue

                    if frame is None:
                        self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)
                        self._profiler.end_frame()
                        with self._camera_failure_lock:
                            self._consecutive_camera_failures += 1
                            failures = self._consecutive_camera_failures

                        if failures >= self.MAX_CONSECUTIVE_CAMERA_FAILURES:
                            logger.warning(
                                f"{failures} frames None consecutivos, intentando reabrir cámara..."
                            )
                            if not self._reopen_source(cfg):
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

                    timestamp = time.time()
                self._profiler.end_phase(LoopProfiler.PHASE_CAPTURE)

                cfg = self.get_config()
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
                    self._safe_close_sink()
                    try:
                        self._sink.open(cfg, desired_output_size)
                        sink_signature = desired_signature
                        logger.info("Sink reconectado exitosamente")
                    except Exception as e:
                        logger.error(f"Error al reconectar sink: {e}")
                        self._profiler.end_frame()
                        break

                # Fase 2: Análisis
                self._profiler.start_phase(LoopProfiler.PHASE_ANALYSIS)
                try:
                    analysis = (
                        self._analyzers.run(frame, cfg)
                        if self._analyzers.has_any()
                        else {}
                    )
                    analysis["timestamp"] = timestamp
                    with self._analysis_lock:
                        self._last_analysis = analysis
                except Exception as e:
                    self._profiler.end_phase(LoopProfiler.PHASE_ANALYSIS)
                    self._profiler.end_frame()
                    logger.error(f"Error en análisis de frame: {e}")
                    time.sleep(cfg.sleep_on_empty)
                    continue
                self._profiler.end_phase(LoopProfiler.PHASE_ANALYSIS)

                # Fase 3: Filtrado
                self._profiler.start_phase(LoopProfiler.PHASE_FILTERING)
                try:
                    filtered = self._filters.apply(frame, cfg, analysis)
                except Exception as e:
                    self._profiler.end_phase(LoopProfiler.PHASE_FILTERING)
                    self._profiler.end_frame()
                    logger.error(f"Error en filtrado de frame: {e}")
                    time.sleep(cfg.sleep_on_empty)
                    continue
                self._profiler.end_phase(LoopProfiler.PHASE_FILTERING)

                # Fase 4: Renderizado
                self._profiler.start_phase(LoopProfiler.PHASE_RENDERING)
                try:
                    rendered = self._renderer.render(filtered, cfg, analysis)
                    if isinstance(rendered, RenderFrame) and rendered.metadata is None:
                        rendered.metadata = {"analysis": analysis}
                except Exception as e:
                    self._profiler.end_phase(LoopProfiler.PHASE_RENDERING)
                    self._profiler.end_frame()
                    logger.error(f"Error en renderizado de frame: {e}")
                    time.sleep(cfg.sleep_on_empty)
                    continue
                self._profiler.end_phase(LoopProfiler.PHASE_RENDERING)

                # Fase 5: Escritura
                self._profiler.start_phase(LoopProfiler.PHASE_WRITING)
                # Usar método con reintentos para escribir UDP
                if not self._write_with_retry(rendered, cfg, desired_output_size):
                    self._profiler.end_phase(LoopProfiler.PHASE_WRITING)
                    self._profiler.end_frame()
                    logger.error("No se pudo escribir al sink después de reintentos, deteniendo")
                    break
                self._profiler.end_phase(LoopProfiler.PHASE_WRITING)

                # Fin del frame completo
                self._profiler.end_frame()

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
            self._safe_close_source()
            self._safe_close_sink()
            logger.info("Engine cerrado")
