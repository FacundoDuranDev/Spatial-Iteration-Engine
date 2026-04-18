"""Kinetic typography filter -- animated text overlay on video.

Renders bold text on screen with scale-in/fade animation, configurable position,
color, and blend modes. Uses PIL for high-quality text rendering when available,
falling back to OpenCV putText.

Inspired by Max Payne 3's signature cutscene text overlays that display dialogue
keywords in bold sans-serif typography.
"""

import cv2
import numpy as np

from .base import BaseFilter

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


class KineticTypographyFilter(BaseFilter):
    """Animated text overlay with scale/fade animation."""

    name = "kinetic_typography"

    def __init__(
        self,
        text: str = "",
        font_size: int = 48,
        color_bgr: tuple = (255, 255, 255),
        position: tuple = (0.5, 0.8),
        blend_mode: str = "alpha",
        animation: str = "scale_in",
        duration_frames: int = 30,
        opacity: float = 0.85,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._text = text
        self._font_size = font_size
        self._color_bgr = color_bgr
        self._position = position
        self._blend_mode = blend_mode
        self._animation = animation
        self._duration_frames = duration_frames
        self._opacity = opacity
        self._frame_counter = 0
        # Text render cache.
        self._text_image = None
        self._cached_text_key = None

    def reset(self):
        self._frame_counter = 0
        self._text_image = None
        self._cached_text_key = None

    def apply(self, frame, config, analysis=None):
        if not self.enabled or not self._text:
            return frame

        self._frame_counter += 1
        h, w = frame.shape[:2]

        # Animation progress: 0.0 to 1.0.
        duration = max(1, self._duration_frames)
        progress = min(1.0, self._frame_counter / duration)

        # Compute animated opacity and scale.
        anim_opacity, anim_scale = self._compute_animation(progress)
        if anim_opacity <= 0.01:
            return frame

        # Render text image (cached).
        text_img = self._get_text_image(w, h, anim_scale)
        if text_img is None:
            return frame

        # Position the text.
        th, tw = text_img.shape[:2]
        px = int(self._position[0] * w - tw / 2)
        py = int(self._position[1] * h - th / 2)

        # Clamp to frame bounds.
        src_y0 = max(0, -py)
        src_x0 = max(0, -px)
        dst_y0 = max(0, py)
        dst_x0 = max(0, px)
        src_y1 = min(th, h - py) if py >= 0 else min(th, h)
        src_x1 = min(tw, w - px) if px >= 0 else min(tw, w)
        dst_y1 = dst_y0 + (src_y1 - src_y0)
        dst_x1 = dst_x0 + (src_x1 - src_x0)

        if dst_y1 <= dst_y0 or dst_x1 <= dst_x0:
            return frame

        result = frame.copy()
        roi = result[dst_y0:dst_y1, dst_x0:dst_x1]
        text_roi = text_img[src_y0:src_y1, src_x0:src_x1]

        # Blend.
        alpha = anim_opacity * self._opacity
        if self._blend_mode == "additive":
            blended = roi.astype(np.float32) + text_roi.astype(np.float32) * alpha
        elif self._blend_mode == "screen":
            inv_text = 1.0 - text_roi.astype(np.float32) / 255.0
            inv_roi = 1.0 - roi.astype(np.float32) / 255.0
            blended = (1.0 - inv_text * inv_roi) * 255.0
            blended = roi.astype(np.float32) * (1.0 - alpha) + blended * alpha
        else:  # alpha blend
            blended = roi.astype(np.float32) * (1.0 - alpha) + text_roi.astype(np.float32) * alpha

        np.clip(blended, 0, 255, out=blended)
        result[dst_y0:dst_y1, dst_x0:dst_x1] = blended.astype(np.uint8)
        return np.ascontiguousarray(result)

    def _compute_animation(self, progress):
        """Return (opacity, scale) based on animation type and progress."""
        if self._animation == "scale_in":
            # Scale from 0.5 to 1.0, opacity from 0 to 1.
            scale = 0.5 + 0.5 * self._ease_out(progress)
            opacity = self._ease_out(progress)
        elif self._animation == "fade_in":
            scale = 1.0
            opacity = self._ease_out(progress)
        elif self._animation == "hard_cut":
            scale = 1.0
            opacity = 1.0 if progress > 0.0 else 0.0
        else:
            scale = 1.0
            opacity = 1.0
        return opacity, scale

    @staticmethod
    def _ease_out(t):
        """Quadratic ease-out."""
        return 1.0 - (1.0 - t) ** 2

    def _get_text_image(self, frame_w, frame_h, scale):
        """Render text to a BGR numpy array. Cached until text/size changes."""
        font_size = max(8, int(self._font_size * scale))
        cache_key = (self._text, font_size, self._color_bgr)
        if self._cached_text_key == cache_key and self._text_image is not None:
            return self._text_image

        if _HAS_PIL:
            self._text_image = self._render_pil(font_size)
        else:
            self._text_image = self._render_cv2(font_size)

        self._cached_text_key = cache_key
        return self._text_image

    def _render_pil(self, font_size):
        """High-quality text rendering via PIL."""
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except (IOError, OSError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except (IOError, OSError):
                font = ImageFont.load_default()

        # Measure text.
        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), self._text.upper(), font=font)
        tw = bbox[2] - bbox[0] + 10
        th = bbox[3] - bbox[1] + 10

        # Render on black background.
        img = Image.new("RGB", (tw, th), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        # PIL uses RGB, our color is BGR.
        color_rgb = (self._color_bgr[2], self._color_bgr[1], self._color_bgr[0])
        draw.text((5, 5 - bbox[1]), self._text.upper(), font=font, fill=color_rgb)

        # Convert to BGR numpy.
        arr = np.array(img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    def _render_cv2(self, font_size):
        """Fallback text rendering via OpenCV."""
        scale = font_size / 30.0
        thickness = max(1, int(scale * 2))
        text = self._text.upper()

        (tw, th), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
        )
        tw += 10
        th += baseline + 10

        img = np.zeros((th, tw, 3), dtype=np.uint8)
        cv2.putText(
            img, text, (5, th - baseline - 5),
            cv2.FONT_HERSHEY_SIMPLEX, scale,
            self._color_bgr, thickness, cv2.LINE_AA,
        )
        return img
