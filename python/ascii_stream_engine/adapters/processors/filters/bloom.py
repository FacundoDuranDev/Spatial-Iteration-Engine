"""Bloom filter -- additive glow from bright areas.

Extracts luminance above a threshold, blurs it with a large Gaussian kernel,
and additively blends back onto the frame. Optionally modulates bloom
intensity near hand centroids when perception data is available.
"""

import cv2
import numpy as np

from .base import BaseFilter


class BloomFilter(BaseFilter):
    """Additive glow from bright regions, optionally hand-reactive."""

    name = "bloom"

    def __init__(
        self,
        threshold: int = 200,
        blur_size: int = 31,
        intensity: float = 0.6,
        audio_reactive: float = 0.0,
        audio_band: str = "bass",
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._threshold = threshold
        self._blur_size = blur_size
        self._intensity = intensity
        # audio_reactive = 0.0 → no coupling (original behavior).
        # audio_reactive = 1.0 → bloom intensity doubles on loud peaks of
        # the chosen band.
        self._audio_reactive = float(audio_reactive)
        self._audio_band = audio_band

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        threshold = getattr(config, "bloom_threshold", self._threshold)
        blur_size = getattr(config, "bloom_blur_size", self._blur_size)
        intensity = getattr(config, "bloom_intensity", self._intensity)

        # Audio-reactive boost: multiply intensity by (1 + reactive * band).
        # analysis.audio is populated by FilterContext when the engine has
        # AudioAnalyzerService running; otherwise the key is absent / zero.
        if self._audio_reactive > 0.0 and analysis is not None:
            audio = getattr(analysis, "audio", None)
            if audio and audio.get("available"):
                band = float(audio.get(self._audio_band, 0.0))
                intensity = intensity * (1.0 + self._audio_reactive * band)

        if intensity <= 0.0:
            return frame

        # Ensure odd kernel size
        blur_size = blur_size | 1

        h, w = frame.shape[:2]

        # Extract bright areas via luminance threshold
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, bright_mask = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY)

        # Apply mask to isolate bright pixels
        bright = cv2.bitwise_and(frame, frame, mask=bright_mask)

        # Gaussian blur the bright areas
        bloom = cv2.GaussianBlur(bright, (blur_size, blur_size), 0)

        # Modulate intensity near hand centroids if perception data available
        if analysis and "hands" in analysis:
            hands = analysis["hands"]
            centroids = []
            for key in ("left", "right"):
                pts = hands.get(key)
                if pts is not None and len(pts) > 0:
                    cx = float(np.mean(pts[:, 0]))
                    cy = float(np.mean(pts[:, 1]))
                    centroids.append((cx, cy))

            if centroids:
                # Build a per-pixel intensity multiplier boosted near hand centroids
                yy, xx = np.mgrid[0:h, 0:w]
                xx_norm = xx.astype(np.float32) / max(w - 1, 1)
                yy_norm = yy.astype(np.float32) / max(h - 1, 1)
                boost = np.ones((h, w), dtype=np.float32)
                for cx, cy in centroids:
                    dist_sq = (xx_norm - cx) ** 2 + (yy_norm - cy) ** 2
                    boost += np.exp(-dist_sq / 0.02)
                np.clip(boost, 0.0, 2.0, out=boost)
                bloom = (bloom.astype(np.float32) * boost[:, :, np.newaxis]).clip(
                    0, 255
                ).astype(np.uint8)

        # Additive blend
        out = frame.copy(order="C")
        cv2.addWeighted(out, 1.0, bloom, float(intensity), 0.0, dst=out)
        return out
