"""Double vision filter -- drunken multi-image with temporal ghosting.

Duplicates the frame with oscillating spatial offsets and blends the copies
to simulate seeing double/triple when disoriented. Optional temporal blending
with the previous output frame creates persistent ghosting trails.

Inspired by Max Payne 3's drunk bar sequences and painkiller overdose effects.
"""

import numpy as np

from .base import BaseFilter


class DoubleVisionFilter(BaseFilter):
    """Oscillating double/triple vision with temporal ghosting."""

    name = "double_vision"
    needs_previous_output = True

    def __init__(
        self,
        offset_x: float = 10.0,
        offset_y: float = 5.0,
        oscillation_speed: float = 0.05,
        ghost_alpha: float = 0.3,
        temporal_blend: float = 0.3,
        copies: int = 2,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._oscillation_speed = oscillation_speed
        self._ghost_alpha = ghost_alpha
        self._temporal_blend = temporal_blend
        self._copies = copies
        self._frame_counter = 0

    def reset(self):
        self._frame_counter = 0

    def apply(self, frame, config, analysis=None):
        if not self.enabled or (self._offset_x <= 0.0 and self._offset_y <= 0.0):
            return frame

        self._frame_counter += 1
        h, w = frame.shape[:2]

        # Oscillating offset.
        phase = self._frame_counter * self._oscillation_speed
        dx = int(self._offset_x * np.sin(phase))
        dy = int(self._offset_y * np.cos(phase * 0.7))

        result = frame.astype(np.float32)
        copies = max(2, min(4, self._copies))
        alpha = self._ghost_alpha / (copies - 1)

        for i in range(1, copies):
            # Each copy gets a proportionally larger offset.
            shift_x = dx * i
            shift_y = dy * i

            shifted = np.zeros_like(frame, dtype=np.float32)
            # Compute valid source and destination slices.
            src_y0 = max(0, -shift_y)
            src_y1 = min(h, h - shift_y)
            src_x0 = max(0, -shift_x)
            src_x1 = min(w, w - shift_x)
            dst_y0 = max(0, shift_y)
            dst_y1 = min(h, h + shift_y)
            dst_x0 = max(0, shift_x)
            dst_x1 = min(w, w + shift_x)

            if dst_y1 > dst_y0 and dst_x1 > dst_x0:
                shifted[dst_y0:dst_y1, dst_x0:dst_x1] = frame[src_y0:src_y1, src_x0:src_x1]

            result = result * (1.0 - alpha) + shifted * alpha

        # Temporal ghosting with previous output.
        if self._temporal_blend > 0.0:
            prev = getattr(analysis, "previous_output", None) if analysis else None
            if prev is not None and prev.shape == frame.shape:
                result = result * (1.0 - self._temporal_blend) + prev.astype(np.float32) * self._temporal_blend

        np.clip(result, 0, 255, out=result)
        return np.ascontiguousarray(result.astype(np.uint8))
