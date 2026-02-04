from typing import Optional, Protocol, Tuple

import numpy as np
from PIL import Image

from .config import AsciiStreamConfig
from .image_processor import AsciiImageProcessor


class FrameRenderer(Protocol):
    def output_size(self, config: AsciiStreamConfig) -> Tuple[int, int]:
        ...

    def render(
        self, frame: np.ndarray, config: AsciiStreamConfig, analysis: Optional[dict] = None
    ) -> Image.Image:
        ...


class AsciiRenderer:
    def __init__(self, processor: Optional[AsciiImageProcessor] = None) -> None:
        self._processor = processor or AsciiImageProcessor()

    @property
    def processor(self) -> AsciiImageProcessor:
        return self._processor

    def output_size(self, config: AsciiStreamConfig) -> Tuple[int, int]:
        return self._processor.output_size(config)

    def render(
        self, frame: np.ndarray, config: AsciiStreamConfig, analysis: Optional[dict] = None
    ) -> Image.Image:
        return self._processor.render(frame, config, analysis)
