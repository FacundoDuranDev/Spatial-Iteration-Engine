"""Hand Frame filter -- applies effects inside a rectangle formed across both hands.

Uses the index finger tips (landmark 8) and thumb tips (landmark 4) from BOTH hands
as the four vertices of a rectangle. The effect is applied only inside that region.

Requires both hands visible. The 4 corners are:
  - Left hand index tip
  - Right hand index tip
  - Left hand thumb tip
  - Right hand thumb tip

When a hand is lost (e.g. finger goes off-screen), holds the last known position
for a configurable number of frames before deactivating.

Supports multiple effect modes: invert, blur, pixelate, edge, tint, ascii.
"""

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .base import BaseFilter

# Charset ordered by measured pixel density (DejaVuSansMono, light → dark).
# 48 unique glyphs give smooth brightness gradients for ASCII art.
_DEFAULT_ASCII_CHARSET = " `:'->u/!Lijc)s=ong[Jlt42m+YA&U*dT@OWD09F8N%PBM#"


def _load_mono_font(size=10):
    """Load a monospace font for ASCII rendering, with fallback."""
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


class HandFrameFilter(BaseFilter):
    """Apply visual effects inside a rectangle formed by index+thumb tips across both hands."""

    name = "hand_frame"

    # MediaPipe landmark indices
    THUMB_TIP = 4
    INDEX_TIP = 8

    def __init__(
        self,
        effect: str = "invert",
        effect_strength: float = 1.0,
        border_thickness: int = 2,
        border_color: tuple = (0, 255, 0),
        smoothing: float = 0.4,
        min_size: float = 0.02,
        hold_frames: int = 15,
        ascii_charset: str = _DEFAULT_ASCII_CHARSET,
        ascii_font_size: int = 10,
        ascii_color: tuple = (0, 255, 0),
        ascii_bg: tuple = (0, 0, 0),
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._effect = effect  # "invert", "blur", "pixelate", "edge", "tint", "ascii"
        self._effect_strength = effect_strength
        self._border_thickness = border_thickness
        self._border_color = border_color
        self._smoothing = smoothing
        self._min_size = min_size
        self._hold_frames = hold_frames
        self._ascii_charset = ascii_charset
        self._ascii_color = ascii_color
        self._ascii_bg = ascii_bg
        self._ascii_font = _load_mono_font(ascii_font_size)
        bbox = self._ascii_font.getbbox("M")
        self._ascii_char_w = bbox[2] - bbox[0]
        self._ascii_char_h = bbox[3] - bbox[1]
        self._ascii_glyphs = self._build_glyph_atlas()
        # State
        self._smooth_corners = None
        self._last_valid_corners = None
        self._frames_since_lost = 0

    @property
    def effect(self):
        return self._effect

    @effect.setter
    def effect(self, value):
        self._effect = value

    @property
    def effect_strength(self):
        return self._effect_strength

    @effect_strength.setter
    def effect_strength(self, value):
        self._effect_strength = value

    @property
    def border_thickness(self):
        return self._border_thickness

    @border_thickness.setter
    def border_thickness(self, value):
        self._border_thickness = value

    def reset(self):
        self._smooth_corners = None
        self._last_valid_corners = None
        self._frames_since_lost = 0

    def apply(self, frame, config, analysis=None):
        corners = self._extract_corners(analysis)

        if corners is not None:
            # Fresh detection — smooth and store
            corners = self._smooth_all_corners(corners)
            self._last_valid_corners = corners.copy()
            self._frames_since_lost = 0
        elif self._last_valid_corners is not None and self._frames_since_lost < self._hold_frames:
            # Lost detection — hold last known position
            corners = self._last_valid_corners
            self._frames_since_lost += 1
        else:
            # No data and hold expired
            return frame

        rect = self._corners_to_rect(corners, frame.shape[:2])
        if rect is None:
            return frame

        x1, y1, x2, y2 = rect
        out = frame.copy(order="C")

        roi = out[y1:y2, x1:x2]
        if roi.size == 0:
            return frame

        modified_roi = self._apply_effect(roi)
        out[y1:y2, x1:x2] = modified_roi

        if self._border_thickness > 0:
            cv2.rectangle(
                out, (x1, y1), (x2, y2),
                self._border_color, self._border_thickness,
            )

        return out

    def _extract_corners(self, analysis):
        """Extract 4 corners from both hands. Returns (4,2) array or None."""
        if not analysis:
            return None
        hands = analysis.get("hands") if hasattr(analysis, "get") else None
        if not hands or not isinstance(hands, dict):
            return None

        left_pts = hands.get("left")
        right_pts = hands.get("right")

        if left_pts is None or right_pts is None:
            return None
        min_len = max(self.THUMB_TIP, self.INDEX_TIP) + 1
        if not hasattr(left_pts, "__len__") or len(left_pts) < min_len:
            return None
        if not hasattr(right_pts, "__len__") or len(right_pts) < min_len:
            return None

        return np.array([
            [float(left_pts[self.INDEX_TIP][0]), float(left_pts[self.INDEX_TIP][1])],
            [float(right_pts[self.INDEX_TIP][0]), float(right_pts[self.INDEX_TIP][1])],
            [float(left_pts[self.THUMB_TIP][0]), float(left_pts[self.THUMB_TIP][1])],
            [float(right_pts[self.THUMB_TIP][0]), float(right_pts[self.THUMB_TIP][1])],
        ], dtype=np.float32)

    def _smooth_all_corners(self, corners):
        """Temporal smoothing for the 4 corner positions."""
        alpha = self._smoothing
        if self._smooth_corners is None:
            self._smooth_corners = corners.copy()
        else:
            self._smooth_corners = alpha * corners + (1.0 - alpha) * self._smooth_corners
        return self._smooth_corners

    def _corners_to_rect(self, corners, shape):
        """Convert 4 corners to axis-aligned (x1,y1,x2,y2) in pixels."""
        h, w = shape

        x_min = float(np.min(corners[:, 0]))
        x_max = float(np.max(corners[:, 0]))
        y_min = float(np.min(corners[:, 1]))
        y_max = float(np.max(corners[:, 1]))

        if (x_max - x_min) < self._min_size and (y_max - y_min) < self._min_size:
            return None

        x1 = int(np.clip(x_min * (w - 1), 0, w - 1))
        x2 = int(np.clip(x_max * (w - 1), 0, w - 1))
        y1 = int(np.clip(y_min * (h - 1), 0, h - 1))
        y2 = int(np.clip(y_max * (h - 1), 0, h - 1))

        if x2 <= x1 or y2 <= y1:
            return None
        return (x1, y1, x2, y2)

    def _apply_effect(self, roi):
        """Apply the selected effect to an ROI. Returns modified ROI."""
        effect = self._effect
        strength = self._effect_strength

        if effect == "invert":
            return cv2.addWeighted(roi, 1.0 - strength, 255 - roi, strength, 0)

        elif effect == "blur":
            ksize = max(3, int(strength * 30) | 1)
            return cv2.GaussianBlur(roi, (ksize, ksize), 0)

        elif effect == "pixelate":
            rh, rw = roi.shape[:2]
            factor = max(2, int(strength * 20))
            small_w = max(1, rw // factor)
            small_h = max(1, rh // factor)
            small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
            return cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)

        elif effect == "edge":
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            return cv2.addWeighted(roi, 1.0 - strength, edge_bgr, strength, 0)

        elif effect == "tint":
            tinted = roi.copy()
            tinted[:, :, 1] = np.clip(
                tinted[:, :, 1].astype(np.float32) * (1.0 + strength * 0.8), 0, 255
            ).astype(np.uint8)
            return tinted

        elif effect == "ascii":
            return self._apply_ascii(roi)

        else:
            return 255 - roi

    def _build_glyph_atlas(self):
        """Pre-render each character as a BGR numpy array (done once at init)."""
        fg_rgb = (self._ascii_color[2], self._ascii_color[1], self._ascii_color[0])
        bg_rgb = (self._ascii_bg[2], self._ascii_bg[1], self._ascii_bg[0])
        cw, ch = self._ascii_char_w, self._ascii_char_h
        chars = self._ascii_charset

        glyphs = np.zeros((len(chars), ch, cw, 3), dtype=np.uint8)
        for i, c in enumerate(chars):
            img = Image.new("RGB", (cw, ch), color=bg_rgb)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), c, fill=fg_rgb, font=self._ascii_font)
            rgb = np.asarray(img, dtype=np.uint8)
            glyphs[i] = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return glyphs

    def _apply_ascii(self, roi):
        """Convert ROI to ASCII art via glyph atlas blitting."""
        rh, rw = roi.shape[:2]
        if rh == 0 or rw == 0:
            return roi

        cw, ch = self._ascii_char_w, self._ascii_char_h
        grid_w = max(1, rw // cw)
        grid_h = max(1, rh // ch)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (grid_w, grid_h), interpolation=cv2.INTER_AREA)

        num_chars = len(self._ascii_charset)
        idx = np.clip(
            (small.astype(np.float32) * ((num_chars - 1) / 255.0)).astype(np.int32),
            0,
            num_chars - 1,
        )

        # Glyph lookup + reshape to canvas
        glyph_grid = self._ascii_glyphs[idx]  # (grid_h, grid_w, ch, cw, 3)
        canvas_h = grid_h * ch
        canvas_w = grid_w * cw
        canvas = (
            glyph_grid
            .transpose(0, 2, 1, 3, 4)
            .reshape(canvas_h, canvas_w, 3)
        )

        if canvas.shape[:2] != (rh, rw):
            canvas = cv2.resize(canvas, (rw, rh), interpolation=cv2.INTER_NEAREST)
        return canvas
