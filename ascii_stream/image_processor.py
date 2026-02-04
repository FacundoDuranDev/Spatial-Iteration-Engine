from typing import Iterable, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import AsciiStreamConfig
from .constants import resolve_charset
from .filters import (
    ContrastBrightnessFilter,
    FilterPipeline,
    FrameFilter,
    GrayscaleFilter,
    InvertFilter,
)


class AsciiImageProcessor:
    def __init__(
        self,
        pipeline: Optional[FilterPipeline] = None,
        filters: Optional[Iterable[FrameFilter]] = None,
        font: Optional[ImageFont.ImageFont] = None,
    ) -> None:
        if pipeline is not None and filters is not None:
            raise ValueError("Usar pipeline o filters, no ambos.")
        if pipeline is None:
            if filters is None:
                filters = [
                    GrayscaleFilter(),
                    ContrastBrightnessFilter(),
                    InvertFilter(),
                ]
            pipeline = FilterPipeline(filters)
        self._pipeline = pipeline
        self._font = font or ImageFont.load_default()
        bbox = self._font.getbbox("A")
        self._char_w = bbox[2] - bbox[0]
        self._char_h = bbox[3] - bbox[1]

    @property
    def pipeline(self) -> FilterPipeline:
        return self._pipeline

    @property
    def filters(self) -> List[FrameFilter]:
        return self._pipeline.filters

    def set_filters(self, filters: Iterable[FrameFilter]) -> None:
        self._pipeline.replace(filters)

    def add_filter(self, filter_obj: FrameFilter) -> None:
        self._pipeline.append(filter_obj)

    def output_size(self, config: AsciiStreamConfig) -> Tuple[int, int]:
        return config.grid_w * self._char_w, config.grid_h * self._char_h

    def render(
        self, frame: np.ndarray, config: AsciiStreamConfig, analysis: Optional[dict] = None
    ) -> Image.Image:
        filters = self._pipeline.snapshot()

        processed = frame
        for filter_obj in filters:
            processed = filter_obj.apply(processed, config, analysis)

        if processed.ndim == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

        small = cv2.resize(
            processed, (config.grid_w, config.grid_h), interpolation=cv2.INTER_AREA
        )
        chars = resolve_charset(config.charset)
        idx = (small / 255 * (len(chars) - 1)).astype(np.int32)

        out_w, out_h = self.output_size(config)
        img = Image.new("RGB", (out_w, out_h), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = 0
        for row in idx:
            line = "".join(chars[i] for i in row)
            draw.text((0, y), line, fill=(255, 255, 255), font=self._font)
            y += self._char_h
        return img
