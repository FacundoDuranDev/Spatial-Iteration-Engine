"""Tests for CppTemporalScanFilter — C++ + Python fallback parity."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters.cpp_temporal_scan import (
    CppTemporalScanFilter,
)
from ascii_stream_engine.domain.config import EngineConfig


@pytest.fixture
def config():
    return EngineConfig()


def _push(filter_obj, intensities, shape=(40, 60, 3)):
    out = None
    cfg = EngineConfig()
    for v in intensities:
        frame = np.full(shape, v, dtype=np.uint8)
        out = filter_obj.apply(frame, cfg)
    return out


class TestBasics:
    def test_construction_defaults(self):
        f = CppTemporalScanFilter()
        assert f.angle_deg == 0.0
        assert f.max_frames == 30
        assert f.curve == "linear"
        assert f.enabled is True

    def test_max_frames_clamped_to_two(self):
        f = CppTemporalScanFilter(max_frames=1)
        assert f.max_frames == 2

    def test_unknown_curve_is_ignored(self):
        f = CppTemporalScanFilter(curve="nonsense")
        assert f.curve == "linear"
        f.curve = "also-nonsense"
        assert f.curve == "linear"
        f.curve = "ease"
        assert f.curve == "ease"


class TestOutputShape:
    def test_apply_returns_same_shape(self, config):
        f = CppTemporalScanFilter(angle_deg=45.0, max_frames=5)
        frame = np.zeros((40, 60, 3), dtype=np.uint8)
        out = f.apply(frame, config)
        assert out.shape == frame.shape
        assert out.dtype == np.uint8

    def test_disabled_filter_returns_input(self, config):
        f = CppTemporalScanFilter(enabled=False)
        frame = np.full((20, 30, 3), 42, dtype=np.uint8)
        out = f.apply(frame, config)
        assert out is frame

    def test_passthrough_with_single_frame(self, config):
        f = CppTemporalScanFilter(max_frames=10)
        frame = np.full((20, 30, 3), 77, dtype=np.uint8)
        out = f.apply(frame, config)
        np.testing.assert_array_equal(out, frame)


class TestAngleSemantics:
    """Verify the angle convention: angle=0 puts newest on the left, oldest on
    the right; angle=180 flips; angle=90 puts newest at top, oldest at bottom.
    """

    def test_angle_zero_newest_on_left(self):
        f = CppTemporalScanFilter(angle_deg=0.0, max_frames=8)
        # Push frames with monotonically increasing intensity (0, 30, 60, ..., 210).
        out = _push(f, [i * 30 for i in range(8)])
        # Left column should be newest (= 210), right column oldest (= 0).
        left = out[:, 0, 0].mean()
        right = out[:, -1, 0].mean()
        assert left > right
        assert left > 150  # roughly newest half
        assert right < 60  # roughly oldest half

    def test_angle_180_flips(self):
        f = CppTemporalScanFilter(angle_deg=180.0, max_frames=8)
        out = _push(f, [i * 30 for i in range(8)])
        left = out[:, 0, 0].mean()
        right = out[:, -1, 0].mean()
        assert right > left

    def test_angle_90_newest_on_top(self):
        f = CppTemporalScanFilter(angle_deg=90.0, max_frames=8)
        out = _push(f, [i * 30 for i in range(8)])
        top = out[0, :, 0].mean()
        bottom = out[-1, :, 0].mean()
        assert top > bottom

    def test_angle_can_be_changed_at_runtime(self, config):
        f = CppTemporalScanFilter(angle_deg=0.0, max_frames=4)
        frame = np.full((20, 30, 3), 128, dtype=np.uint8)
        f.apply(frame, config)
        f.angle_deg = 270.0
        assert f.angle_deg == 270.0
        out = f.apply(frame, config)
        assert out.shape == frame.shape


class TestReset:
    def test_reset_clears_buffer(self, config):
        f = CppTemporalScanFilter(angle_deg=0.0, max_frames=4)
        _push(f, [255] * 4)
        f.reset()
        # After reset + one frame, still in single-frame passthrough territory
        out = f.apply(np.zeros((10, 10, 3), dtype=np.uint8), config)
        assert out.max() == 0  # just the zero frame, no leftover history

    def test_max_frames_setter_resets_state(self, config):
        f = CppTemporalScanFilter(angle_deg=0.0, max_frames=4)
        _push(f, [255] * 4)
        f.max_frames = 8
        assert f.max_frames == 8
        out = f.apply(np.zeros((10, 10, 3), dtype=np.uint8), config)
        assert out.max() == 0


class TestCurves:
    def test_linear_and_ease_both_run(self, config):
        for curve in ("linear", "ease"):
            f = CppTemporalScanFilter(angle_deg=45.0, max_frames=6, curve=curve)
            out = _push(f, [i * 40 for i in range(6)])
            assert out.shape == (40, 60, 3)
