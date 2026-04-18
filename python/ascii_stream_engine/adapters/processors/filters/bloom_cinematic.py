"""Cinematic bloom filter -- multi-pass gaussian with warm tint and light leaks.

Extracts bright regions above a threshold, builds a mip chain with progressive
downsampling and gaussian blur at each level, then upsamples back and
accumulates into a multi-scale bloom. Supports warm tint, anamorphic horizontal
stretch, and light leak overlay.

Inspired by the warm-tinted bloom and anamorphic light leaks in Max Payne 3.
"""

import cv2
import numpy as np

from .base import BaseFilter


class BloomCinematicFilter(BaseFilter):
    """Multi-pass cinematic bloom with warm tint and anamorphic stretch."""

    name = "bloom_cinematic"

    def __init__(
        self,
        threshold: int = 200,
        intensity: float = 0.5,
        blur_passes: int = 3,
        warm_tint_bgr: tuple = (0, 20, 40),
        anamorphic_ratio: float = 1.0,
        light_leak: float = 0.0,
        quality: float = 1.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._threshold = threshold
        self._intensity = intensity
        self._blur_passes = blur_passes
        self._warm_tint_bgr = warm_tint_bgr
        self._anamorphic_ratio = anamorphic_ratio
        self._light_leak = light_leak
        self._quality = quality

    def apply(self, frame, config, analysis=None):
        if not self.enabled or self._intensity <= 0.0:
            return frame

        h, w = frame.shape[:2]

        # Quality scaling: process at reduced resolution.
        q = max(0.25, min(1.0, self._quality))
        if q < 1.0:
            sh, sw = max(1, int(h * q)), max(1, int(w * q))
            work = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
        else:
            work = frame

        # Extract bright regions.
        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, self._threshold, 255, cv2.THRESH_BINARY)
        bright = cv2.bitwise_and(work, work, mask=mask)

        # Build mip chain with progressive blur.
        mips = [bright.astype(np.float32)]
        current = bright
        passes = max(1, min(6, self._blur_passes))
        for _ in range(passes):
            current = cv2.pyrDown(current)
            # Anamorphic: wider horizontal blur.
            kh = 5
            kw = max(5, int(5 * self._anamorphic_ratio)) | 1  # Ensure odd.
            blurred = cv2.GaussianBlur(current, (kw, kh), 0)
            mips.append(blurred.astype(np.float32))

        # Upsample and accumulate from smallest mip back to full size.
        bloom = mips[-1]
        for i in range(len(mips) - 2, -1, -1):
            target_h, target_w = mips[i].shape[:2]
            bloom = cv2.resize(bloom, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            bloom = bloom + mips[i]

        # Normalize bloom intensity.
        max_val = bloom.max()
        if max_val > 0:
            bloom = bloom / max_val * 255.0

        # Upscale bloom back to original resolution if quality < 1.
        if q < 1.0:
            bloom = cv2.resize(bloom, (w, h), interpolation=cv2.INTER_LINEAR)

        # Apply warm tint.
        tint = np.array(self._warm_tint_bgr, dtype=np.float32)
        if np.any(tint > 0):
            tint_norm = tint / max(255.0, tint.max())
            bloom = bloom * (1.0 + tint_norm)

        # Light leak: soft additive wash at edges.
        if self._light_leak > 0.0:
            leak = cv2.GaussianBlur(bloom, (0, 0), sigmaX=w * 0.1)
            bloom = bloom + leak * self._light_leak

        # Additive composite.
        result = frame.astype(np.float32) + bloom * self._intensity
        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))
