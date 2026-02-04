from typing import List, Optional

from .config import AsciiStreamConfig
from .engine import StreamEngine
from .filters import FilterPipeline, FrameFilter
from .image_processor import AsciiImageProcessor
from .renderers import AsciiRenderer
from .sinks import UdpFfmpegSink
from .sources import OpenCVCameraSource


class AsciiStreamer(StreamEngine):
    def __init__(
        self,
        config: Optional[AsciiStreamConfig] = None,
        image_processor: Optional[AsciiImageProcessor] = None,
        source: Optional[OpenCVCameraSource] = None,
        sink: Optional[UdpFfmpegSink] = None,
        renderer: Optional[AsciiRenderer] = None,
    ) -> None:
        cfg = config or AsciiStreamConfig()
        if renderer is None:
            renderer = AsciiRenderer(image_processor)
        if source is None:
            source = OpenCVCameraSource(camera_index=0)
        if sink is None:
            sink = UdpFfmpegSink()
        super().__init__(source=source, renderer=renderer, sink=sink, config=cfg)

    def get_config(self) -> AsciiStreamConfig:
        return super().get_config()

    def update_config(self, **kwargs) -> None:
        super().update_config(**kwargs)

    def get_processor(self) -> AsciiImageProcessor:
        renderer = self.get_renderer()
        if isinstance(renderer, AsciiRenderer):
            return renderer.processor
        raise ValueError("Renderer actual no expone un AsciiImageProcessor.")

    def set_processor(self, processor: AsciiImageProcessor) -> None:
        self.set_renderer(AsciiRenderer(processor))

    @property
    def pipeline(self) -> FilterPipeline:
        return self.get_processor().pipeline

    @property
    def filters(self) -> List[FrameFilter]:
        return self.get_processor().pipeline.filters

    def start(self, camera_index: int = 0) -> None:
        source = self.get_source()
        if isinstance(source, OpenCVCameraSource):
            source.set_camera_index(camera_index)
        super().start()
