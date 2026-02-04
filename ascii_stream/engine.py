import threading
import time
from typing import Dict, List, Optional

from .analyzers import AnalyzerPipeline, FrameAnalyzer
from .base import Streamer
from .config import AsciiStreamConfig
from .renderers import FrameRenderer
from .sinks import OutputSink
from .sources import FrameSource


class StreamEngine(Streamer):
    def __init__(
        self,
        source: FrameSource,
        renderer: FrameRenderer,
        sink: OutputSink,
        config: Optional[AsciiStreamConfig] = None,
        analyzers: Optional[AnalyzerPipeline] = None,
    ) -> None:
        super().__init__()
        self._config = config or AsciiStreamConfig()
        self._config_lock = threading.Lock()
        self._source = source
        self._renderer = renderer
        self._sink = sink
        self._analyzers = analyzers or AnalyzerPipeline()
        self._analysis_lock = threading.Lock()
        self._last_analysis: Dict[str, object] = {}

    def get_config(self) -> AsciiStreamConfig:
        with self._config_lock:
            return AsciiStreamConfig(**vars(self._config))

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
    def analyzers(self) -> List[FrameAnalyzer]:
        return self._analyzers.analyzers

    def get_last_analysis(self) -> Dict[str, object]:
        with self._analysis_lock:
            return dict(self._last_analysis)

    def _run(self) -> None:
        cfg = self.get_config()
        self._source.open()
        output_size = self._renderer.output_size(cfg)
        self._sink.open(cfg, output_size)

        last = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                frame = self._source.read()
                if frame is None:
                    time.sleep(0.01)
                    continue

                cfg = self.get_config()
                analysis = (
                    self._analyzers.run(frame, cfg)
                    if self._analyzers.has_any()
                    else {}
                )
                with self._analysis_lock:
                    self._last_analysis = analysis

                img = self._renderer.render(frame, cfg, analysis)
                try:
                    self._sink.write(img)
                except (BrokenPipeError, OSError):
                    break

                target = 1.0 / max(1, int(cfg.fps))
                now = time.perf_counter()
                sleep = target - (now - last)
                if sleep > 0:
                    time.sleep(sleep)
                last = time.perf_counter()
        finally:
            self._source.close()
            self._sink.close()
