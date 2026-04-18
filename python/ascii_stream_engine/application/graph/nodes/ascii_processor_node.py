"""AsciiProcessorNode — converts a video frame to ASCII art rendered as a BGR image.

Uses a pre-rendered glyph atlas for fast blitting instead of per-frame PIL text
rendering. Each character is rendered once at init, then per-frame the node only
does numpy array indexing and block copies.

Extends ProcessorNode for GraphScheduler integration (phase tracking, temporal).
"""

import os
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .processor_node import ProcessorNode

# Charset ordered by measured pixel density (DejaVuSansMono, light -> dark).
# 48 unique glyphs give smooth brightness gradients for ASCII art.
_DEFAULT_CHARSET = " `:'->u/!Lijc)s=ong[Jlt42m+YA&U*dT@OWD09F8N%PBM#"


def _load_mono_font(size=10):
    """Load a monospace font with fallback."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _build_glyph_atlas(charset, font, char_w, char_h, fg_bgr, bg_bgr):
    """Pre-render each character as a BGR numpy array.

    Returns a (num_chars, char_h, char_w, 3) uint8 array — the glyph atlas.
    Each glyph[i] is the BGR bitmap for charset[i].
    """
    fg_rgb = (fg_bgr[2], fg_bgr[1], fg_bgr[0])
    bg_rgb = (bg_bgr[2], bg_bgr[1], bg_bgr[0])

    glyphs = np.zeros((len(charset), char_h, char_w, 3), dtype=np.uint8)
    for i, ch in enumerate(charset):
        img = Image.new("RGB", (char_w, char_h), color=bg_rgb)
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), ch, fill=fg_rgb, font=font)
        rgb = np.asarray(img, dtype=np.uint8)
        glyphs[i] = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    return glyphs


class AsciiProcessorNode(ProcessorNode):
    """Converts any video frame to ASCII art rendered back as a BGR image.

    Uses a glyph atlas for O(1) per-character rendering (numpy block copy).
    The output image has the same dimensions as the input frame.
    Inherits ProcessorNode ports: video_in + analysis_in (optional) -> video_out.

    Parameters:
        charset: Characters ordered from light to dark.
        font_size: Monospace font size (smaller = more detail).
        fg_color: Text color in BGR.
        bg_color: Background color in BGR.
    """

    name = "ascii_processor"

    def __init__(
        self,
        charset: str = _DEFAULT_CHARSET,
        font_size: int = 10,
        fg_color: tuple = (0, 255, 0),
        bg_color: tuple = (0, 0, 0),
    ) -> None:
        super().__init__()
        self._charset = charset
        self._fg_color = fg_color
        self._bg_color = bg_color
        self._font = _load_mono_font(font_size)
        bbox = self._font.getbbox("M")
        self._char_w = bbox[2] - bbox[0]
        self._char_h = bbox[3] - bbox[1]
        # Pre-render glyph atlas: (num_chars, char_h, char_w, 3)
        self._glyphs = _build_glyph_atlas(
            charset, self._font, self._char_w, self._char_h, fg_color, bg_color
        )
        # Reusable output buffer (lazily allocated per resolution)
        self._out_buf: Dict[tuple, np.ndarray] = {}

    def apply_filter(self, frame: Any, config: Any, analysis: Any) -> Any:
        """Convert frame to ASCII art as a BGR image of the same size."""
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return frame

        grid_w = max(1, w // self._char_w)
        grid_h = max(1, h // self._char_h)
        cw = self._char_w
        ch = self._char_h

        # Brightness → charset indices (vectorized)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
        num_chars = len(self._charset)
        idx = np.clip(
            (small.astype(np.float32) * ((num_chars - 1) / 255.0)).astype(np.int32),
            0,
            num_chars - 1,
        )

        # Blit glyphs into output buffer (pure numpy, no PIL per frame)
        canvas_h = grid_h * ch
        canvas_w = grid_w * cw
        canvas_key = (canvas_h, canvas_w)
        if canvas_key not in self._out_buf:
            self._out_buf[canvas_key] = np.empty((canvas_h, canvas_w, 3), dtype=np.uint8)
        canvas = self._out_buf[canvas_key]

        # Vectorized glyph lookup: glyphs[idx] → (grid_h, grid_w, ch, cw, 3)
        glyph_grid = self._glyphs[idx]  # (grid_h, grid_w, ch, cw, 3)

        # Reshape: merge grid rows with glyph rows, grid cols with glyph cols
        # (grid_h, grid_w, ch, cw, 3) → (grid_h*ch, grid_w*cw, 3)
        canvas[:] = (
            glyph_grid
            .transpose(0, 2, 1, 3, 4)      # (grid_h, ch, grid_w, cw, 3)
            .reshape(canvas_h, canvas_w, 3)
        )

        # Resize to match original frame if needed
        if canvas.shape[:2] != (h, w):
            return cv2.resize(canvas, (w, h), interpolation=cv2.INTER_NEAREST)
        return canvas
