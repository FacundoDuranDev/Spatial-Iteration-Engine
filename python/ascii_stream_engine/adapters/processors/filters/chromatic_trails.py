"""Chromatic Trails filter — R/G/B channels pulled from different past frames.

Static scenes look normal; moving subjects smear into separated RGB ghosts.
"""

from collections import deque

import numpy as np

from .base import BaseFilter


class ChromaticTrailsFilter(BaseFilter):
    """Temporal RGB split: each color channel comes from a different past frame."""

    name = "chromatic_trails"

    def __init__(
        self,
        r_delay: int = 0,
        g_delay: int = 3,
        b_delay: int = 8,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._r_delay = int(r_delay)
        self._g_delay = int(g_delay)
        self._b_delay = int(b_delay)
        maxlen = max(self._r_delay, self._g_delay, self._b_delay) + 1
        self._buffer: "deque[np.ndarray]" = deque(maxlen=maxlen)

    def reset(self):
        self._buffer.clear()

    def _frame_at(self, delay: int) -> np.ndarray:
        # Most recent frame is buffer[-1]; delay=0 → current, delay=N → N frames back.
        idx = -1 - min(delay, len(self._buffer) - 1)
        return self._buffer[idx]

    def apply(self, frame, config, analysis=None):
        if not self.enabled or frame is None or frame.size == 0:
            return frame

        self._buffer.append(frame.copy())
        if len(self._buffer) < 2:
            return frame

        # BGR convention: [:,:,0]=B, [:,:,1]=G, [:,:,2]=R
        out = frame.copy()
        out[:, :, 0] = self._frame_at(self._b_delay)[:, :, 0]
        out[:, :, 1] = self._frame_at(self._g_delay)[:, :, 1]
        out[:, :, 2] = self._frame_at(self._r_delay)[:, :, 2]
        return out
