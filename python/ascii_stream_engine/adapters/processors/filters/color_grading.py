"""Color grading filter -- cinematic color manipulation inspired by Max Payne 3.

Provides split-toning (shadow/highlight tint), per-channel gain/offset,
saturation control, and optional 3D LUT application with blending. The color
pipeline runs entirely in float32 for precision, converting back to uint8 on
output.

Parameters are exposed as instance attributes for live Gradio/preset control.
"""

import cv2
import numpy as np

from .base import BaseFilter


class ColorGradingFilter(BaseFilter):
    """Cinematic color grading with split-tone, saturation, and channel controls."""

    name = "color_grading"

    def __init__(
        self,
        shadow_tint_bgr: tuple = (40, 20, 0),
        highlight_tint_bgr: tuple = (0, 10, 30),
        shadow_strength: float = 0.3,
        highlight_strength: float = 0.3,
        saturation: float = 1.0,
        gain_b: float = 1.0,
        gain_g: float = 1.0,
        gain_r: float = 1.0,
        offset_b: int = 0,
        offset_g: int = 0,
        offset_r: int = 0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._shadow_tint_bgr = shadow_tint_bgr
        self._highlight_tint_bgr = highlight_tint_bgr
        self._shadow_strength = shadow_strength
        self._highlight_strength = highlight_strength
        self._saturation = saturation
        self._gain_b = gain_b
        self._gain_g = gain_g
        self._gain_r = gain_r
        self._offset_b = offset_b
        self._offset_g = offset_g
        self._offset_r = offset_r

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        # No-op fast path: all defaults.
        is_noop = (
            self._saturation == 1.0
            and self._gain_b == 1.0
            and self._gain_g == 1.0
            and self._gain_r == 1.0
            and self._offset_b == 0
            and self._offset_g == 0
            and self._offset_r == 0
            and self._shadow_strength == 0.0
            and self._highlight_strength == 0.0
        )
        if is_noop:
            return frame

        # Work in float32 for precision.
        img = frame.astype(np.float32)

        # --- Per-channel gain and offset ---
        gains = np.array(
            [self._gain_b, self._gain_g, self._gain_r], dtype=np.float32
        )
        offsets = np.array(
            [self._offset_b, self._offset_g, self._offset_r], dtype=np.float32
        )
        if not (np.all(gains == 1.0) and np.all(offsets == 0.0)):
            img = img * gains + offsets

        # --- Saturation ---
        if self._saturation != 1.0:
            # Luma-weighted desaturation (BT.601 weights for BGR order).
            luma = img[:, :, 0] * 0.114 + img[:, :, 1] * 0.587 + img[:, :, 2] * 0.299
            luma = luma[:, :, np.newaxis]
            img = luma + (img - luma) * self._saturation

        # --- Split-toning ---
        if self._shadow_strength > 0.0 or self._highlight_strength > 0.0:
            luma = img[:, :, 0] * 0.114 + img[:, :, 1] * 0.587 + img[:, :, 2] * 0.299
            luma_norm = np.clip(luma / 255.0, 0.0, 1.0)

            if self._shadow_strength > 0.0:
                shadow_mask = (1.0 - luma_norm) * self._shadow_strength
                shadow_tint = np.array(self._shadow_tint_bgr, dtype=np.float32)
                img += shadow_mask[:, :, np.newaxis] * shadow_tint

            if self._highlight_strength > 0.0:
                highlight_mask = luma_norm * self._highlight_strength
                highlight_tint = np.array(self._highlight_tint_bgr, dtype=np.float32)
                img += highlight_mask[:, :, np.newaxis] * highlight_tint

        # Clip and convert back to uint8.
        np.clip(img, 0, 255, out=img)
        return np.ascontiguousarray(img.astype(np.uint8))
