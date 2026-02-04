import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..core.config import EngineConfig
from ..core.types import RenderFrame


class AsciiRenderer:
    def __init__(
        self,
        font: Optional[ImageFont.ImageFont] = None,
        font_path: Optional[str] = None,
        font_size: int = 12,
    ) -> None:
        if font is not None and font_path is not None:
            raise ValueError("Usa font o font_path, no ambos.")
        if font is None:
            font = self._load_font(font_path, font_size)
        self._font = font
        bbox = self._font.getbbox("M")
        self._char_w = bbox[2] - bbox[0]
        self._char_h = bbox[3] - bbox[1]

    def _load_font(
        self, font_path: Optional[str], font_size: int
    ) -> ImageFont.ImageFont:
        if font_path:
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                pass

        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, font_size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        mode = getattr(config, "render_mode", "ascii")
        if mode == "raw":
            raw_w = getattr(config, "raw_width", None)
            raw_h = getattr(config, "raw_height", None)
            if raw_w and raw_h:
                return int(raw_w), int(raw_h)
        return config.grid_w * self._char_w, config.grid_h * self._char_h

    def _frame_to_image(
        self, frame: np.ndarray, output_size: Tuple[int, int]
    ) -> Image.Image:
        if frame.ndim == 2:
            rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if (rgb.shape[1], rgb.shape[0]) != output_size:
            rgb = cv2.resize(rgb, output_size, interpolation=cv2.INTER_AREA)
        return Image.fromarray(rgb)

    def _frame_to_lines(self, frame: np.ndarray, config: EngineConfig) -> List[str]:
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        small = cv2.resize(
            gray, (config.grid_w, config.grid_h), interpolation=cv2.INTER_AREA
        )
        chars = config.charset
        idx = (small / 255 * (len(chars) - 1)).astype(np.int32)
        return ["".join(chars[i] for i in row) for row in idx]

    def render(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> RenderFrame:
        metadata = {"analysis": analysis or {}}
        mode = getattr(config, "render_mode", "ascii")
        out_w, out_h = self.output_size(config)

        if mode == "raw":
            img = self._frame_to_image(frame, (out_w, out_h))
            return RenderFrame(image=img, text=None, lines=None, metadata=metadata)

        lines = self._frame_to_lines(frame, config)
        text = "\n".join(lines)
        img = Image.new("RGB", (out_w, out_h), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = 0
        for line in lines:
            draw.text((0, y), line, fill=(255, 255, 255), font=self._font)
            y += self._char_h
        return RenderFrame(image=img, text=text, lines=lines, metadata=metadata)
