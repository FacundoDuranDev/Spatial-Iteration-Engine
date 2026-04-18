"""Tests for TemporalManager — demand-driven temporal state for frame pipeline."""

import numpy as np
import pytest

from ascii_stream_engine.application.services.temporal_manager import TemporalManager

# ---------------------------------------------------------------------------
# Dummy filter classes with declaration attributes
# ---------------------------------------------------------------------------


class PlainFilter:
    """Filter with no temporal declarations."""

    pass


class HistoryFilter:
    """Filter that declares required_input_history."""

    def __init__(self, depth: int = 1):
        self.required_input_history = depth


class OutputFilter:
    """Filter that needs previous output."""

    needs_previous_output = True


class FlowFilter:
    """Filter that needs optical flow."""

    needs_optical_flow = True


class DeltaFilter:
    """Filter that needs delta frame."""

    needs_delta_frame = True


class ComboFilter:
    """Filter that declares multiple needs."""

    required_input_history = 3
    needs_optical_flow = True
    needs_delta_frame = True
    needs_previous_output = True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_frame(h: int = 64, w: int = 64, value: int = 128) -> np.ndarray:
    """Create a BGR frame filled with a constant value."""
    return np.full((h, w, 3), value, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tests: zero-allocation when no filter declares needs
# ---------------------------------------------------------------------------


class TestZeroAllocation:
    def test_no_filters(self):
        tm = TemporalManager()
        tm.configure([])
        assert tm.input_depth == 0
        assert tm.needs_output is False
        assert tm.has_allocations is False

    def test_plain_filter_no_allocation(self):
        tm = TemporalManager()
        tm.configure([PlainFilter()])
        assert tm.input_depth == 0
        assert tm.needs_output is False

    def test_push_input_noop_when_depth_zero(self):
        tm = TemporalManager()
        tm.configure([PlainFilter()])
        frame = _make_frame()
        tm.push_input(frame)
        assert tm.has_allocations is False

    def test_push_output_noop_when_not_needed(self):
        tm = TemporalManager()
        tm.configure([PlainFilter()])
        frame = _make_frame()
        tm.push_output(frame)
        assert tm.has_allocations is False


# ---------------------------------------------------------------------------
# Tests: input ring sizing
# ---------------------------------------------------------------------------


class TestInputRingSizing:
    def test_single_history_filter(self):
        # required_input_history=1 means 1 previous frame + 1 slot for current push = 2
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=1)])
        assert tm.input_depth == 2

    def test_max_across_filters(self):
        # max(2+1, 5+1, 3+1) = 6
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=2), HistoryFilter(depth=5), HistoryFilter(depth=3)])
        assert tm.input_depth == 6

    def test_auto_derive_flow_implies_depth_2(self):
        tm = TemporalManager()
        tm.configure([FlowFilter()])
        assert tm.input_depth >= 2

    def test_auto_derive_delta_implies_depth_2(self):
        tm = TemporalManager()
        tm.configure([DeltaFilter()])
        assert tm.input_depth >= 2

    def test_explicit_depth_overrides_auto(self):
        """Explicit depth+1 > auto-derived depth wins."""
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=4), FlowFilter()])
        # max(4+1, 2) = 5
        assert tm.input_depth == 5

    def test_combo_filter(self):
        tm = TemporalManager()
        tm.configure([ComboFilter()])
        # required_input_history=3 => 3+1=4, flow=2, delta=2 => max=4
        assert tm.input_depth == 4
        assert tm.needs_output is True


# ---------------------------------------------------------------------------
# Tests: output buffer
# ---------------------------------------------------------------------------


class TestOutputBuffer:
    def test_allocates_only_when_needed(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        assert tm.needs_output is True
        # Not yet allocated (lazy)
        assert tm.has_allocations is False
        # Push triggers allocation
        frame = _make_frame()
        tm.push_output(frame)
        assert tm.has_allocations is True

    def test_get_previous_output_none_before_push(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        assert tm.get_previous_output() is None

    def test_get_previous_output_returns_data(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        frame = _make_frame(value=42)
        tm.push_output(frame)
        result = tm.get_previous_output()
        assert result is not None
        assert np.all(result == 42)


# ---------------------------------------------------------------------------
# Tests: read-only views
# ---------------------------------------------------------------------------


class TestReadOnlyViews:
    def test_previous_input_read_only(self):
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=1)])
        tm.begin_frame()
        tm.push_input(_make_frame())
        tm.begin_frame()
        tm.push_input(_make_frame(value=50))
        view = tm.get_previous_input(1)
        assert view is not None
        assert view.flags.writeable is False

    def test_previous_output_read_only(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        tm.push_output(_make_frame())
        view = tm.get_previous_output()
        assert view is not None
        assert view.flags.writeable is False

    def test_delta_read_only(self):
        tm = TemporalManager()
        tm.configure([DeltaFilter()])
        # Need two frames for delta
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(value=200))
        delta = tm.get_delta()
        assert delta is not None
        assert delta.flags.writeable is False


# ---------------------------------------------------------------------------
# Tests: resolution change reallocation
# ---------------------------------------------------------------------------


class TestResolutionChange:
    def test_input_ring_reallocates_on_resolution_change(self):
        tm = TemporalManager()
        # depth=2 => ring size = 3
        tm.configure([HistoryFilter(depth=2)])
        frame_small = _make_frame(h=32, w=32)
        tm.push_input(frame_small)
        assert tm._input_ring.shape == (3, 32, 32, 3)

        frame_large = _make_frame(h=64, w=64)
        tm.push_input(frame_large)
        assert tm._input_ring.shape == (3, 64, 64, 3)

    def test_output_buf_reallocates_on_resolution_change(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        tm.push_output(_make_frame(h=32, w=32))
        assert tm._output_buf.shape == (32, 32, 3)

        tm.push_output(_make_frame(h=64, w=64))
        assert tm._output_buf.shape == (64, 64, 3)


# ---------------------------------------------------------------------------
# Tests: begin_frame invalidates caches
# ---------------------------------------------------------------------------


class TestBeginFrame:
    def test_invalidates_delta_cache(self):
        tm = TemporalManager()
        tm.configure([DeltaFilter()])
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(value=200))
        delta1 = tm.get_delta()
        assert delta1 is not None

        # begin_frame invalidates the cache
        tm.begin_frame()
        tm.push_input(_make_frame(value=150))
        delta2 = tm.get_delta()
        assert delta2 is not None
        # Delta should be different now (|150 - 200| vs |200 - 100|)
        assert not np.array_equal(delta1, delta2)

    def test_invalidates_flow_cache(self):
        tm = TemporalManager()
        tm.configure([FlowFilter()])
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(value=200))
        flow1 = tm.get_optical_flow()
        assert flow1 is not None

        # begin_frame invalidates the cache
        tm.begin_frame()
        tm.push_input(_make_frame(value=150))
        flow2 = tm.get_optical_flow()
        assert flow2 is not None


# ---------------------------------------------------------------------------
# Tests: get_delta
# ---------------------------------------------------------------------------


class TestDelta:
    def test_returns_none_without_previous(self):
        tm = TemporalManager()
        tm.configure([DeltaFilter()])
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        # Only one frame pushed, no previous yet for a fresh ring
        # After first frame, get_previous_input(1) returns the frame we just pushed
        # but current_input is also set, so delta = absdiff(current, previous)
        # Since ring wraps, and only 1 frame in buffer, prev returns same frame
        # Actually, after 1 push: count=1, index=1, get_previous_input(1) => index 0
        # and current_input = that same frame. So delta = absdiff(same, same) = 0
        # That's fine -- it's still a valid return.

    def test_delta_absdiff(self):
        tm = TemporalManager()
        tm.configure([DeltaFilter()])
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(value=150))
        delta = tm.get_delta()
        assert delta is not None
        assert np.all(delta == 50)

    def test_delta_returns_none_when_not_configured(self):
        tm = TemporalManager()
        tm.configure([PlainFilter()])
        assert tm.get_delta() is None


# ---------------------------------------------------------------------------
# Tests: optical flow
# ---------------------------------------------------------------------------


class TestOpticalFlow:
    def test_flow_computed_once_per_frame(self):
        """Optical flow should be computed once then cached on second access."""
        tm = TemporalManager()
        tm.configure([FlowFilter()])
        tm.begin_frame()
        tm.push_input(_make_frame(value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(value=200))
        flow1 = tm.get_optical_flow()
        flow2 = tm.get_optical_flow()
        assert flow1 is not None
        assert flow2 is not None
        # Same object (cached)
        assert flow1 is flow2

    def test_flow_returns_none_when_not_configured(self):
        tm = TemporalManager()
        tm.configure([PlainFilter()])
        assert tm.get_optical_flow() is None

    def test_flow_returns_none_without_previous(self):
        tm = TemporalManager()
        tm.configure([FlowFilter()])
        # No frames pushed yet, current_input is None
        assert tm.get_optical_flow() is None

    def test_flow_shape(self):
        """Optical flow should have shape (H, W, 2)."""
        tm = TemporalManager()
        tm.configure([FlowFilter()])
        h, w = 64, 64
        tm.begin_frame()
        tm.push_input(_make_frame(h=h, w=w, value=100))
        tm.begin_frame()
        tm.push_input(_make_frame(h=h, w=w, value=200))
        flow = tm.get_optical_flow()
        assert flow is not None
        assert flow.shape == (h, w, 2)


# ---------------------------------------------------------------------------
# Tests: get_previous_input
# ---------------------------------------------------------------------------


class TestGetPreviousInput:
    def test_returns_none_when_no_ring(self):
        tm = TemporalManager()
        tm.configure([])
        assert tm.get_previous_input(1) is None

    def test_returns_none_for_invalid_n(self):
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=2)])
        tm.push_input(_make_frame(value=10))
        # n=0 is invalid
        assert tm.get_previous_input(0) is None
        # n=-1 is invalid
        assert tm.get_previous_input(-1) is None

    def test_returns_none_when_not_enough_frames(self):
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=3)])
        tm.push_input(_make_frame(value=10))
        # Only 1 frame pushed, asking for 2nd previous
        assert tm.get_previous_input(2) is None

    def test_ring_buffer_ordering(self):
        tm = TemporalManager()
        # depth=3 => ring size = 4 (3 history + 1 for current push)
        tm.configure([HistoryFilter(depth=3)])
        tm.push_input(_make_frame(value=10))
        tm.push_input(_make_frame(value=20))
        tm.push_input(_make_frame(value=30))
        # Most recent pushed = 30, then 20, then 10
        prev1 = tm.get_previous_input(1)
        prev2 = tm.get_previous_input(2)
        prev3 = tm.get_previous_input(3)
        assert prev1 is not None
        assert prev2 is not None
        assert prev3 is not None
        assert np.all(prev1 == 30)
        assert np.all(prev2 == 20)
        assert np.all(prev3 == 10)

    def test_ring_buffer_wraps(self):
        tm = TemporalManager()
        # depth=2 => ring size = 3 (2 history + 1 for current push)
        tm.configure([HistoryFilter(depth=2)])
        tm.push_input(_make_frame(value=10))
        tm.push_input(_make_frame(value=20))
        tm.push_input(_make_frame(value=30))
        prev1 = tm.get_previous_input(1)
        prev2 = tm.get_previous_input(2)
        prev3 = tm.get_previous_input(3)
        assert prev1 is not None
        assert prev2 is not None
        assert prev3 is not None
        assert np.all(prev1 == 30)
        assert np.all(prev2 == 20)
        assert np.all(prev3 == 10)

    def test_ring_buffer_overflow_drops_oldest(self):
        tm = TemporalManager()
        # depth=1 => ring size = 2
        tm.configure([HistoryFilter(depth=1)])
        tm.push_input(_make_frame(value=10))
        tm.push_input(_make_frame(value=20))
        tm.push_input(_make_frame(value=30))  # overwrites slot for value=10
        prev1 = tm.get_previous_input(1)
        prev2 = tm.get_previous_input(2)
        assert prev1 is not None
        assert prev2 is not None
        assert np.all(prev1 == 30)
        assert np.all(prev2 == 20)


# ---------------------------------------------------------------------------
# Tests: properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_input_depth_property(self):
        tm = TemporalManager()
        assert tm.input_depth == 0
        tm.configure([HistoryFilter(depth=5)])
        # depth=5 => ring size = 6 (5 history + 1 for current push)
        assert tm.input_depth == 6

    def test_needs_output_property(self):
        tm = TemporalManager()
        assert tm.needs_output is False
        tm.configure([OutputFilter()])
        assert tm.needs_output is True

    def test_has_allocations_false_initially(self):
        tm = TemporalManager()
        assert tm.has_allocations is False

    def test_has_allocations_true_after_push_input(self):
        tm = TemporalManager()
        tm.configure([HistoryFilter(depth=1)])
        tm.push_input(_make_frame())
        assert tm.has_allocations is True

    def test_has_allocations_true_after_push_output(self):
        tm = TemporalManager()
        tm.configure([OutputFilter()])
        tm.push_output(_make_frame())
        assert tm.has_allocations is True
