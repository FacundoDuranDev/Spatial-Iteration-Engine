"""Tests for Max Payne 3 Tier 2 filters: BloomCinematic, RadialBlur, DoubleVision, GlitchBlock."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters import (
    BloomCinematicFilter,
    DoubleVisionFilter,
    GlitchBlockFilter,
    RadialBlurFilter,
)
from ascii_stream_engine.domain.config import EngineConfig


@pytest.fixture
def config():
    return EngineConfig()


@pytest.fixture
def frame_480():
    """Synthetic 480p BGR frame with bright spots for bloom testing."""
    h, w = 480, 640
    frame = np.full((h, w, 3), 80, dtype=np.uint8)
    # Bright spot in center for bloom.
    frame[200:280, 280:360] = 250
    return np.ascontiguousarray(frame)


class TestBloomCinematicFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.5, threshold=200)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_bloom_brightens_around_source(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.8, threshold=200, blur_passes=3)
        result = f.apply(frame_480, config)
        # Area near bright spot should be brighter than in original.
        nearby = result[180:200, 280:360]
        original_nearby = frame_480[180:200, 280:360]
        assert np.mean(nearby) > np.mean(original_nearby)

    def test_quality_scaling(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.5, quality=0.5)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape

    def test_anamorphic_runs(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.5, anamorphic_ratio=3.0)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape

    def test_light_leak_runs(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.5, light_leak=0.5)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape

    def test_disabled_returns_same(self, frame_480, config):
        f = BloomCinematicFilter(intensity=0.5, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestRadialBlurFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = RadialBlurFilter(strength=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = RadialBlurFilter(strength=0.3, samples=6)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_blur_modifies_frame(self, frame_480, config):
        f = RadialBlurFilter(strength=0.5, samples=8, falloff=0.2)
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_center_stays_sharper(self, frame_480, config):
        f = RadialBlurFilter(strength=0.5, samples=8, falloff=0.5)
        result = f.apply(frame_480, config)
        h, w = frame_480.shape[:2]
        # Center pixel diff should be smaller than corner pixel diff.
        center_diff = np.abs(
            result[h // 2, w // 2].astype(int) - frame_480[h // 2, w // 2].astype(int)
        ).sum()
        corner_diff = np.abs(
            result[0, 0].astype(int) - frame_480[0, 0].astype(int)
        ).sum()
        assert center_diff <= corner_diff

    def test_disabled_returns_same(self, frame_480, config):
        f = RadialBlurFilter(strength=0.5, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestDoubleVisionFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = DoubleVisionFilter(offset_x=0.0, offset_y=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = DoubleVisionFilter(offset_x=10.0, offset_y=5.0)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_vision_modifies_frame(self, frame_480, config):
        f = DoubleVisionFilter(offset_x=15.0, offset_y=10.0)
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_temporal_declaration(self):
        f = DoubleVisionFilter()
        assert f.needs_previous_output is True

    def test_disabled_returns_same(self, frame_480, config):
        f = DoubleVisionFilter(offset_x=10.0, enabled=False)
        assert f.apply(frame_480, config) is frame_480

    def test_triple_vision(self, frame_480, config):
        f = DoubleVisionFilter(offset_x=10.0, copies=3)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape


class TestGlitchBlockFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = GlitchBlockFilter(
            corruption_rate=0.0, rgb_split=0, interlace=False, static_bands=0
        )
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = GlitchBlockFilter(corruption_rate=0.1, rgb_split=3)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_corruption_modifies_frame(self, frame_480, config):
        f = GlitchBlockFilter(corruption_rate=0.2)
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_rgb_split_shifts_channels(self, frame_480, config):
        f = GlitchBlockFilter(corruption_rate=0.0, rgb_split=5, interlace=False, static_bands=0)
        result = f.apply(frame_480, config)
        # R and B channels should differ from original due to horizontal shift.
        assert not np.array_equal(result[:, :, 0], frame_480[:, :, 0])
        assert not np.array_equal(result[:, :, 2], frame_480[:, :, 2])

    def test_interlace_shifts_odd_rows(self, frame_480, config):
        f = GlitchBlockFilter(corruption_rate=0.0, rgb_split=0, interlace=True, static_bands=0)
        result = f.apply(frame_480, config)
        # Even rows should match original.
        assert np.array_equal(result[0], frame_480[0])

    def test_disabled_returns_same(self, frame_480, config):
        f = GlitchBlockFilter(corruption_rate=0.1, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestTier2Chain:
    def test_full_tier2_chain(self, frame_480, config):
        """Chain Tier 2 filters in MP3 order: bloom -> radial -> glitch."""
        bloom = BloomCinematicFilter(intensity=0.3, threshold=200)
        radial = RadialBlurFilter(strength=0.2, samples=4)
        double = DoubleVisionFilter(offset_x=5.0)
        glitch = GlitchBlockFilter(corruption_rate=0.05, rgb_split=2)

        result = bloom.apply(frame_480, config)
        result = radial.apply(result, config)
        result = double.apply(result, config)
        result = glitch.apply(result, config)

        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]
