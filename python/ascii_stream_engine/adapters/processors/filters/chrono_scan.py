"""Chrono-scan filter — each row (or column) of the output comes from a
different past frame, producing a temporal slit-scan smear effect.
"""

from collections import deque

import numpy as np

from .base import BaseFilter


class ChronoScanFilter(BaseFilter):
    """Temporal slit-scan: across one axis, each slice is pulled from a
    different past frame, linearly going from 0 frames old (one edge) to
    `max_delay` frames old (opposite edge).
    """

    name = "chrono_scan"

    def __init__(
        self,
        max_delay: int = 20,
        axis: str = "rows",  # "rows" or "cols"
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._max_delay = max(1, int(max_delay))
        self._axis = axis
        self._buffer: "deque[np.ndarray]" = deque(maxlen=self._max_delay + 1)

    @property
    def axis(self) -> str:
        return self._axis

    @axis.setter
    def axis(self, value: str) -> None:
        self._axis = value

    @property
    def max_delay(self) -> int:
        return self._max_delay

    @max_delay.setter
    def max_delay(self, value: int) -> None:
        self._max_delay = max(1, int(value))
        self._buffer = deque(
            list(self._buffer)[-(self._max_delay + 1):], maxlen=self._max_delay + 1
        )

    def reset(self):
        self._buffer.clear()

    def apply(self, frame, config, analysis=None):
        if not self.enabled or frame is None or frame.size == 0:
            return frame

        self._buffer.append(frame.copy())
        if len(self._buffer) < 2:
            return frame

        n_frames = len(self._buffer)
        h, w = frame.shape[:2]
        slices = h if self._axis == "rows" else w
        # Map each slice to a buffer index: 0 → newest, slices-1 → oldest.
        idxs = (
            np.linspace(0, n_frames - 1, slices).astype(np.int32)
        )  # 0 ... n_frames-1

        out = np.empty_like(frame)
        if self._axis == "rows":
            for y in range(slices):
                src = self._buffer[-1 - idxs[y]]
                out[y] = src[y]
        else:  # cols
            for x in range(slices):
                src = self._buffer[-1 - idxs[x]]
                out[:, x] = src[:, x]
        return out
