"""Film grain filter -- animated photochemical noise overlay.

Generates per-frame noise that is luminance-adaptive (stronger in shadows and
midtones, weaker in highlights) to mimic real film stock behavior. Supports
per-channel color variation for organic color speckling. Inspired by the
ever-present film grain in Max Payne 3.

The noise texture is regenerated every frame using a counter-based seed for
animation, so no temporal declarations are needed.
"""

import cv2
import numpy as np

from .base import BaseFilter


class FilmGrainFilter(BaseFilter):
    """Animated luminance-adaptive film grain overlay."""

    name = "film_grain"

    def __init__(
        self,
        intensity: float = 0.15,
        grain_size: int = 1,
        color_variation: float = 0.1,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._intensity = intensity
        self._grain_size = grain_size
        self._color_variation = color_variation
        self._frame_counter = 0

    def reset(self):
        self._frame_counter = 0

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._intensity <= 0.0:
            return frame

        h, w = frame.shape[:2]
        self._frame_counter += 1

        # Compute noise at reduced resolution if grain_size > 1.
        gs = max(1, int(self._grain_size))
        noise_h, noise_w = max(1, h // gs), max(1, w // gs)

        rng = np.random.RandomState(self._frame_counter & 0x7FFFFFFF)

        # Base monochrome noise: centered at 0, range [-1, 1].
        noise = rng.standard_normal((noise_h, noise_w)).astype(np.float32)

        if self._color_variation > 0.0:
            # Per-channel variation for organic color speckling.
            noise_color = np.empty((noise_h, noise_w, 3), dtype=np.float32)
            noise_color[:, :, 0] = noise + rng.standard_normal(
                (noise_h, noise_w)
            ).astype(np.float32) * self._color_variation
            noise_color[:, :, 1] = noise + rng.standard_normal(
                (noise_h, noise_w)
            ).astype(np.float32) * self._color_variation
            noise_color[:, :, 2] = noise + rng.standard_normal(
                (noise_h, noise_w)
            ).astype(np.float32) * self._color_variation
        else:
            noise_color = np.stack([noise, noise, noise], axis=-1)

        # Upscale noise to frame size if grain_size > 1.
        if gs > 1:
            noise_color = cv2.resize(
                noise_color, (w, h), interpolation=cv2.INTER_NEAREST
            )

        # Luminance-adaptive mask: stronger in shadows/midtones, weaker in highlights.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # Mask peaks at ~0.3 luminance, falls off toward 1.0.
        grain_mask = 1.0 - np.clip((gray - 0.5) * 2.0, 0.0, 1.0)
        grain_mask = grain_mask[:, :, np.newaxis]

        # Apply grain: additive blend weighted by intensity and luminance mask.
        intensity_scale = self._intensity * 255.0
        result = frame.astype(np.float32) + noise_color * grain_mask * intensity_scale

        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))
