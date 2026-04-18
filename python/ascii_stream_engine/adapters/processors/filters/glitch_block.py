"""Block glitch filter -- digital corruption, RGB split, and interlacing.

Divides the frame into a grid of blocks and randomly corrupts a fraction of
them (displacing, freezing, or replacing with noise). Also applies uniform
RGB channel displacement, scanline interlacing, and horizontal static bands.

Inspired by Max Payne 3's trauma flashbacks and scene transition glitches.
"""

import numpy as np

from .base import BaseFilter


class GlitchBlockFilter(BaseFilter):
    """Digital block corruption with RGB split and interlacing."""

    name = "glitch_block"

    def __init__(
        self,
        block_size: int = 16,
        corruption_rate: float = 0.05,
        rgb_split: int = 3,
        interlace: bool = True,
        static_bands: int = 2,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._block_size = block_size
        self._corruption_rate = corruption_rate
        self._rgb_split = rgb_split
        self._interlace = interlace
        self._static_bands = static_bands
        self._frame_counter = 0

    def reset(self):
        self._frame_counter = 0

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        is_noop = (
            self._corruption_rate <= 0.0
            and self._rgb_split <= 0
            and not self._interlace
            and self._static_bands <= 0
        )
        if is_noop:
            return frame

        self._frame_counter += 1
        h, w = frame.shape[:2]
        result = frame.copy()
        rng = np.random.RandomState(self._frame_counter & 0x7FFFFFFF)

        # --- Block corruption ---
        if self._corruption_rate > 0.0:
            bs = max(4, self._block_size)
            rows = h // bs
            cols = w // bs
            n_blocks = rows * cols
            n_corrupt = max(0, int(n_blocks * self._corruption_rate))

            if n_corrupt > 0:
                indices = rng.choice(n_blocks, size=n_corrupt, replace=False)
                for idx in indices:
                    by = (idx // cols) * bs
                    bx = (idx % cols) * bs
                    ey = min(by + bs, h)
                    ex = min(bx + bs, w)

                    action = rng.randint(0, 3)
                    if action == 0:
                        # Shift block from a random source position.
                        src_y = rng.randint(0, max(1, h - bs))
                        src_x = rng.randint(0, max(1, w - bs))
                        bh, bw = ey - by, ex - bx
                        result[by:ey, bx:ex] = frame[
                            src_y : src_y + bh, src_x : src_x + bw
                        ]
                    elif action == 1:
                        # Fill block with noise.
                        result[by:ey, bx:ex] = rng.randint(
                            0, 256, size=(ey - by, ex - bx, 3), dtype=np.uint8
                        )
                    else:
                        # Color-shift block.
                        shift = rng.randint(-50, 51, size=3).astype(np.int16)
                        block = result[by:ey, bx:ex].astype(np.int16) + shift
                        np.clip(block, 0, 255, out=block)
                        result[by:ey, bx:ex] = block.astype(np.uint8)

        # --- Uniform RGB channel split ---
        if self._rgb_split > 0:
            split = self._rgb_split
            shifted = np.empty_like(result)
            # Shift R channel right, B channel left.
            shifted[:, :, 2] = np.roll(result[:, :, 2], split, axis=1)   # R right
            shifted[:, :, 1] = result[:, :, 1]                           # G stays
            shifted[:, :, 0] = np.roll(result[:, :, 0], -split, axis=1)  # B left
            result = shifted

        # --- Interlacing ---
        if self._interlace:
            # Shift odd scanlines by a small random offset.
            offset = rng.randint(1, 4)
            result[1::2] = np.roll(result[1::2], offset, axis=1)

        # --- Static/noise bands ---
        if self._static_bands > 0:
            for _ in range(self._static_bands):
                band_y = rng.randint(0, max(1, h - 20))
                band_h = rng.randint(2, 20)
                ey = min(band_y + band_h, h)
                result[band_y:ey] = rng.randint(
                    0, 256, size=(ey - band_y, w, 3), dtype=np.uint8
                )

        return np.ascontiguousarray(result)
