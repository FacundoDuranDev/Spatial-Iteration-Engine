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


class StreamEngine:
    def __init__(
        self,
        source: FrameSource,
        renderer: FrameRenderer,
        sink: OutputSink,
        config: Optional[EngineConfig] = None,
        analyzers: Optional[AnalyzerPipeline] = None,
        filters: Optional[FilterPipeline] = None,
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

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_config(self) -> EngineConfig:
        with self._config_lock:
            return EngineConfig(**vars(self._config))

    def update_config(self, **kwargs) -> None:
        with self._config_lock:
            for key, value in kwargs.items():
                if not hasattr(self._config, key):
                    raise ValueError(f"Parametro desconocido: {key}")
                setattr(self._config, key, value)

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
        except Exception:
            pass

    def _safe_close_sink(self) -> None:
        try:
            self._sink.close()
        except Exception:
            pass

    def _start_capture_thread(self, config: EngineConfig) -> None:
        if config.frame_buffer_size <= 0:
            return
        self._frame_buffer = deque(maxlen=config.frame_buffer_size)

        def _capture_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    frame = self._source.read()
                except Exception:
                    time.sleep(config.sleep_on_empty)
                    continue
                if frame is None:
                    time.sleep(config.sleep_on_empty)
                    continue
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
        self._source.open()
        self._start_capture_thread(cfg)
        output_size = self._renderer.output_size(cfg)
        self._sink.open(cfg, output_size)
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
                if cfg.frame_buffer_size > 0:
                    latest = self._get_latest_frame()
                    if latest is None:
                        time.sleep(cfg.sleep_on_empty)
                        continue
                    frame, timestamp = latest
                else:
                    frame = self._source.read()
                    if frame is None:
                        time.sleep(cfg.sleep_on_empty)
                        continue
                    timestamp = time.time()

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
                    self._safe_close_sink()
                    self._sink.open(cfg, desired_output_size)
                    sink_signature = desired_signature

                analysis = (
                    self._analyzers.run(frame, cfg)
                    if self._analyzers.has_any()
                    else {}
                )
                analysis["timestamp"] = timestamp
                with self._analysis_lock:
                    self._last_analysis = analysis

                filtered = self._filters.apply(frame, cfg, analysis)
                rendered = self._renderer.render(filtered, cfg, analysis)
                if isinstance(rendered, RenderFrame) and rendered.metadata is None:
                    rendered.metadata = {"analysis": analysis}

                try:
                    self._sink.write(rendered)
                except (BrokenPipeError, OSError):
                    break

                target = 1.0 / max(1, int(cfg.fps))
                now = time.perf_counter()
                sleep = target - (now - last)
                if sleep > 0:
                    time.sleep(sleep)
                last = time.perf_counter()
        finally:
            self._safe_close_source()
            self._safe_close_sink()
