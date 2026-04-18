"""ASCII filter — renders the entire frame as ASCII glyphs."""

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .base import BaseFilter

# 48 glyphs ordered light → dark for smooth brightness gradients (DejaVuSansMono).
_DEFAULT_ASCII_CHARSET = " `:'->u/!Lijc)s=ong[Jlt42m+YA&U*dT@OWD09F8N%PBM#"


def _load_mono_font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class AsciiFilter(BaseFilter):
    """Full-frame ASCII rasterizer. Produces BGR output matching the input size."""

    name = "ascii"

    def __init__(
        self,
        charset: str = _DEFAULT_ASCII_CHARSET,
        font_size: int = 10,
        color: tuple = (0, 255, 0),
        bg: tuple = (0, 0, 0),
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._charset = charset
        self._color = color
        self._bg = bg
        self._font = _load_mono_font(font_size)
        bbox = self._font.getbbox("M")
        self._char_w = max(1, bbox[2] - bbox[0])
        self._char_h = max(1, bbox[3] - bbox[1])
        self._glyphs = self._build_glyph_atlas()

    def _build_glyph_atlas(self):
        fg_rgb = (self._color[2], self._color[1], self._color[0])
        bg_rgb = (self._bg[2], self._bg[1], self._bg[0])
        cw, ch = self._char_w, self._char_h
        glyphs = np.zeros((len(self._charset), ch, cw, 3), dtype=np.uint8)
        for i, c in enumerate(self._charset):
            img = Image.new("RGB", (cw, ch), color=bg_rgb)
            ImageDraw.Draw(img).text((0, 0), c, fill=fg_rgb, font=self._font)
            rgb = np.asarray(img, dtype=np.uint8)
            glyphs[i] = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return glyphs

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame
        if frame is None or frame.size == 0:
            return frame

        h, w = frame.shape[:2]
        cw, ch = self._char_w, self._char_h
        grid_w = max(1, w // cw)
        grid_h = max(1, h // ch)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        small = cv2.resize(gray, (grid_w, grid_h), interpolation=cv2.INTER_AREA)

        num_chars = len(self._charset)
        idx = np.clip(
            (small.astype(np.float32) * ((num_chars - 1) / 255.0)).astype(np.int32),
            0,
            num_chars - 1,
        )

        glyph_grid = self._glyphs[idx]  # (grid_h, grid_w, ch, cw, 3)
        canvas = (
            glyph_grid
            .transpose(0, 2, 1, 3, 4)
            .reshape(grid_h * ch, grid_w * cw, 3)
        )
        if canvas.shape[:2] != (h, w):
            canvas = cv2.resize(canvas, (w, h), interpolation=cv2.INTER_NEAREST)
        return canvas
