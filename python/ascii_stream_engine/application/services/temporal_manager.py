"""Demand-driven temporal state manager for the frame pipeline.

Allocates nothing until filters declare needs. Buffer sizes derived
from filter declarations, not global config.
"""

import logging
import threading
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class TemporalManager:
    """Demand-driven temporal state: allocates nothing until filters declare needs.

    Two paths:
    - Cold path (configure): runs once when filter set changes, scans declarations
    - Hot path (begin_frame/push_input/push_output/get_*): runs every frame
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Demand flags (set by configure)
        self._input_depth: int = 0
        self._needs_output: bool = False
        self._needs_flow: bool = False
        self._needs_delta: bool = False
        # Buffers (lazy allocated on first push)
        self._input_ring: Optional[np.ndarray] = None  # (depth, H, W, 3) uint8
        self._input_index: int = 0
        self._input_count: int = 0
        self._output_buf: Optional[np.ndarray] = None  # (H, W, 3) uint8
        self._has_output: bool = False
        # Resolution tracking
        self._resolution: Optional[tuple] = None  # (H, W)
        # Per-frame caches (invalidated by begin_frame)
        self._current_input: Optional[np.ndarray] = None
        self._cached_delta: Optional[np.ndarray] = None
        self._cached_flow: Optional[np.ndarray] = None
        self._frame_active: bool = False

    def configure(self, filters: List) -> None:
        """Cold path: scan filter declarations and store demand flags.

        Does NOT allocate buffers -- allocation deferred to first push.
        """
        with self._lock:
            explicit_depth = 0
            any_flow = False
            any_delta = False
            any_output = False

            for f in filters:
                d = getattr(f, "required_input_history", 0)
                if d > explicit_depth:
                    explicit_depth = d
                if getattr(f, "needs_optical_flow", False):
                    any_flow = True
                if getattr(f, "needs_delta_frame", False):
                    any_delta = True
                if getattr(f, "needs_previous_output", False):
                    any_output = True

            # Auto-derive: flow and delta need at least 2 ring slots
            # (1 for the current push_input + 1 for the previous frame).
            # required_input_history=N means N previous frames accessible,
            # plus 1 slot for the current push.
            self._input_depth = max(
                explicit_depth + 1 if explicit_depth > 0 else 0,
                2 if any_flow else 0,
                2 if any_delta else 0,
            )
            self._needs_output = any_output
            self._needs_flow = any_flow
            self._needs_delta = any_delta

            # If demand changed, invalidate buffers (will reallocate on next push)
            # Don't deallocate -- lazy reallocation handles it
            logger.debug(
                "TemporalManager configured: input_depth=%d, output=%s, flow=%s, delta=%s",
                self._input_depth,
                self._needs_output,
                self._needs_flow,
                self._needs_delta,
            )

    def begin_frame(self) -> None:
        """Hot path: invalidate per-frame caches."""
        self._cached_delta = None
        self._cached_flow = None
        self._current_input = None
        self._frame_active = True

    def push_input(self, frame: np.ndarray) -> None:
        """Hot path: store current input frame in ring buffer.

        No-op if input_depth == 0 (no filter needs input history).
        """
        if self._input_depth <= 0:
            return

        h, w = frame.shape[:2]
        resolution = (h, w)

        # Allocate or reallocate if resolution changed
        if self._input_ring is None or self._resolution != resolution:
            self._input_ring = np.empty((self._input_depth, h, w, 3), dtype=np.uint8)
            self._input_index = 0
            self._input_count = 0
            self._resolution = resolution
            logger.debug(
                "TemporalManager: allocated input ring %s", self._input_ring.shape
            )

        # Store frame in ring buffer
        np.copyto(self._input_ring[self._input_index], frame)
        self._current_input = frame
        self._input_index = (self._input_index + 1) % self._input_depth
        self._input_count = min(self._input_count + 1, self._input_depth)

    def push_output(self, frame: np.ndarray) -> None:
        """Hot path: store processed output frame.

        No-op if no filter needs previous output.
        """
        if not self._needs_output:
            return

        h, w = frame.shape[:2]
        resolution = (h, w)

        # Allocate or reallocate if resolution changed
        if self._output_buf is None or self._resolution != resolution:
            self._output_buf = np.empty((h, w, 3), dtype=np.uint8)
            self._resolution = resolution
            logger.debug(
                "TemporalManager: allocated output buffer (%d, %d, 3)", h, w
            )

        np.copyto(self._output_buf, frame)
        self._has_output = True

    def get_previous_input(self, n: int = 1) -> Optional[np.ndarray]:
        """Get nth previous input frame (1 = last frame). Returns read-only view or None."""
        if self._input_ring is None or self._input_count < n or n < 1:
            return None
        idx = (self._input_index - n) % self._input_depth
        view = self._input_ring[idx]
        view.flags.writeable = False
        return view

    def get_previous_output(self) -> Optional[np.ndarray]:
        """Get previous processed output frame. Returns read-only view or None."""
        if self._output_buf is None or not self._has_output:
            return None
        view = self._output_buf.view()
        view.flags.writeable = False
        return view

    def get_delta(self) -> Optional[np.ndarray]:
        """Lazy: compute input frame diff on first access per frame, cache result.

        Uses get_previous_input(2) because slot 1 holds the current frame
        (from push_input) and slot 2 holds the actual previous frame.
        """
        if self._cached_delta is not None:
            return self._cached_delta
        if not self._needs_delta:
            return None
        prev = self.get_previous_input(2)
        if prev is None or self._current_input is None:
            return None
        self._cached_delta = cv2.absdiff(self._current_input, prev)
        self._cached_delta.flags.writeable = False
        return self._cached_delta

    def get_optical_flow(self) -> Optional[np.ndarray]:
        """Lazy: compute Farneback optical flow on first access per frame, cache result.

        Uses get_previous_input(2) because slot 1 holds the current frame
        (from push_input) and slot 2 holds the actual previous frame.
        """
        if self._cached_flow is not None:
            return self._cached_flow
        if not self._needs_flow:
            return None
        prev = self.get_previous_input(2)
        if prev is None or self._current_input is None:
            return None
        prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(self._current_input, cv2.COLOR_BGR2GRAY)
        self._cached_flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        self._cached_flow.flags.writeable = False
        return self._cached_flow

    @property
    def input_depth(self) -> int:
        """Current configured input ring buffer depth."""
        return self._input_depth

    @property
    def needs_output(self) -> bool:
        """Whether any filter needs previous output."""
        return self._needs_output

    @property
    def has_allocations(self) -> bool:
        """Whether any buffers are currently allocated."""
        return self._input_ring is not None or self._output_buf is not None
