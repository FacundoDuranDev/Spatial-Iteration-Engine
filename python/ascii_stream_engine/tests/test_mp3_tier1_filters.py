"""Tests for Max Payne 3 Tier 1 filters: ColorGrading, FilmGrain, Vignette."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters import (
    ColorGradingFilter,
    FilmGrainFilter,
    VignetteFilter,
)
from ascii_stream_engine.domain.config import EngineConfig


@pytest.fixture
def config():
    return EngineConfig()


@pytest.fixture
def frame_480():
    """Synthetic 480p BGR frame with gradient."""
    h, w = 480, 640
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Horizontal gradient in blue channel.
    frame[:, :, 0] = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    # Vertical gradient in green channel.
    frame[:, :, 1] = np.tile(
        np.linspace(0, 255, h, dtype=np.uint8)[:, np.newaxis], (1, w)
    )
    frame[:, :, 2] = 128
    return np.ascontiguousarray(frame)


class TestColorGradingFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        """With all defaults at zero-effect, should return original frame."""
        f = ColorGradingFilter(shadow_strength=0.0, highlight_strength=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = ColorGradingFilter(saturation=0.5)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_desaturation(self, frame_480, config):
        """Saturation=0 should produce near-grayscale output."""
        f = ColorGradingFilter(saturation=0.0)
        result = f.apply(frame_480, config)
        # All channels should be equal (or very close) for grayscale.
        diffs = np.abs(result[:, :, 0].astype(int) - result[:, :, 1].astype(int))
        assert np.mean(diffs) < 2.0  # Allow small rounding differences.

    def test_channel_gain_boosts_red(self, frame_480, config):
        f = ColorGradingFilter(gain_r=2.0)
        result = f.apply(frame_480, config)
        # Red channel should be brighter.
        assert np.mean(result[:, :, 2]) > np.mean(frame_480[:, :, 2])

    def test_split_tone_modifies_frame(self, frame_480, config):
        f = ColorGradingFilter(
            shadow_tint_bgr=(100, 0, 0), shadow_strength=1.0,
            highlight_tint_bgr=(0, 0, 100), highlight_strength=1.0,
        )
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_disabled_returns_same(self, frame_480, config):
        f = ColorGradingFilter(saturation=0.0, enabled=False)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_handles_none_analysis(self, frame_480, config):
        f = ColorGradingFilter(saturation=0.5)
        result = f.apply(frame_480, config, analysis=None)
        assert result.shape == frame_480.shape


class TestFilmGrainFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.15)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_grain_modifies_frame(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.3)
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_grain_varies_per_frame(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.2)
        r1 = f.apply(frame_480.copy(), config)
        r2 = f.apply(frame_480.copy(), config)
        # Different frame counters should produce different noise.
        assert not np.array_equal(r1, r2)

    def test_large_grain_size(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.1, grain_size=4)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8

    def test_disabled_returns_same(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.3, enabled=False)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_reset_resets_counter(self, frame_480, config):
        f = FilmGrainFilter(intensity=0.1)
        f.apply(frame_480, config)
        f.apply(frame_480, config)
        assert f._frame_counter == 2
        f.reset()
        assert f._frame_counter == 0


class TestVignetteFilter:
    def test_noop_returns_same_ref(self, frame_480, config):
        f = VignetteFilter(intensity=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = VignetteFilter(intensity=0.6)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_darkens_edges(self, frame_480, config):
        f = VignetteFilter(intensity=0.8, inner_radius=0.2, outer_radius=0.8)
        result = f.apply(frame_480, config)
        # Center should be brighter than corners.
        h, w = frame_480.shape[:2]
        center_brightness = float(np.mean(result[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3]))
        corner_brightness = float(
            np.mean([
                np.mean(result[:10, :10]),
                np.mean(result[:10, -10:]),
                np.mean(result[-10:, :10]),
                np.mean(result[-10:, -10:]),
            ])
        )
        assert center_brightness > corner_brightness

    def test_mask_cached(self, frame_480, config):
        f = VignetteFilter(intensity=0.5)
        f.apply(frame_480, config)
        mask1 = f._mask
        f.apply(frame_480, config)
        mask2 = f._mask
        assert mask1 is mask2  # Same object, cache hit.

    def test_mask_rebuilt_on_param_change(self, frame_480, config):
        f = VignetteFilter(intensity=0.5)
        f.apply(frame_480, config)
        mask1 = f._mask
        f._intensity = 0.8
        f.apply(frame_480, config)
        mask2 = f._mask
        assert mask1 is not mask2  # Cache invalidated.

    def test_tinted_vignette(self, frame_480, config):
        f = VignetteFilter(intensity=0.8, tint_bgr=(0, 0, 100))
        result = f.apply(frame_480, config)
        # Corners should have red tint (high R value relative to original).
        assert result.shape == frame_480.shape

    def test_disabled_returns_same(self, frame_480, config):
        f = VignetteFilter(intensity=0.6, enabled=False)
        result = f.apply(frame_480, config)
        assert result is frame_480


class TestTier1Chain:
    def test_full_mp3_base_chain(self, frame_480, config):
        """Chain all three Tier 1 filters in MP3 order: grading -> grain -> vignette."""
        grading = ColorGradingFilter(
            saturation=0.7, shadow_tint_bgr=(40, 10, 0), shadow_strength=0.5
        )
        grain = FilmGrainFilter(intensity=0.1)
        vignette = VignetteFilter(intensity=0.5)

        result = grading.apply(frame_480, config)
        result = grain.apply(result, config)
        result = vignette.apply(result, config)

        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]
        assert not np.array_equal(result, frame_480)
