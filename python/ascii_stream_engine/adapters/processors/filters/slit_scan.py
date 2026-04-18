"""Slit-Scan filter -- temporal displacement across spatial columns.

Maintains a circular buffer of N previous frames. For each column (or row)
of the output, samples from a different time index in the buffer. The time
index varies linearly across the frame width: left = oldest, right = newest
(reversible). Optionally reacts to hand position to shift the temporal
sampling curve.

Stateful: stores frame buffer, last shape for resolution change detection.
Analysis-reactive: shifts sampling curve based on right-hand x-position.

Memory usage:
  - _buffer: buffer_size * H * W * 3 bytes (uint8)
"""

import numpy as np

from .base import BaseFilter


class SlitScanFilter(BaseFilter):
    """Temporal slit-scan effect using a circular frame buffer."""

    name = "slit_scan"

    def __init__(
        self,
        buffer_size: int = 30,
        direction: str = "horizontal",
        reverse: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._buffer_size = max(2, buffer_size)
        self._direction = direction
        self._reverse = reverse
        # State
        self._buffer = []
        self._last_shape = None

    def reset(self):
        """Clear internal state. Called on pipeline reset."""
        self._buffer = []
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        h, w = frame.shape[:2]

        # Resolution change: reset buffer
        if (h, w) != self._last_shape:
            self._buffer = []
            self._last_shape = (h, w)

        # Append current frame to buffer (store a copy to avoid aliasing)
        self._buffer.append(frame.copy())

        # Trim buffer to max size
        if len(self._buffer) > self._buffer_size:
            self._buffer = self._buffer[-self._buffer_size :]

        buf_len = len(self._buffer)

        # Need at least 2 frames to produce the effect
        if buf_len < 2:
            return frame

        # Stack buffer into a single array: (buf_len, H, W, 3)
        stack = np.stack(self._buffer, axis=0)

        # Determine the spatial dimension to scan across
        if self._direction == "vertical":
            # Scan across rows (height axis)
            num_slices = h
        else:
            # Scan across columns (width axis)
            num_slices = w

        # Generate temporal indices: linearly map spatial position to buffer index
        # Left (or top) = oldest (index 0), right (or bottom) = newest (index buf_len - 1)
        t_indices = np.linspace(0, buf_len - 1, num_slices)

        if self._reverse:
            t_indices = t_indices[::-1]

        # Optional perception: shift sampling curve based on right-hand x-position
        if analysis and isinstance(analysis, dict):
            hands = analysis.get("hands")
            if hands and isinstance(hands, dict):
                right_hand = hands.get("right")
                if right_hand is not None and len(right_hand) > 0:
                    # right_hand: (21, 2) normalized 0-1, use mean x as shift
                    hand_x = float(np.mean(right_hand[:, 0]))
                    # Shift range: hand at center (0.5) = no shift
                    # hand at 0 = shift left by half buffer, hand at 1 = shift right
                    shift = (hand_x - 0.5) * (buf_len - 1)
                    t_indices = t_indices + shift
                    t_indices = np.clip(t_indices, 0, buf_len - 1)

        # Convert float indices to integer indices for nearest-neighbor sampling
        t_int = np.clip(np.round(t_indices).astype(np.intp), 0, buf_len - 1)

        # Build the output frame using fancy indexing
        out = frame.copy(order="C")

        if self._direction == "vertical":
            # Each row comes from a different time index
            for row in range(h):
                out[row, :, :] = stack[t_int[row], row, :, :]
        else:
            # Each column comes from a different time index
            for col in range(w):
                out[:, col, :] = stack[t_int[col], :, col, :]

        # Ensure C-contiguous output
        if not out.flags["C_CONTIGUOUS"]:
            out = np.ascontiguousarray(out)

        return out
