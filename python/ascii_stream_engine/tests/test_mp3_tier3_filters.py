"""Tests for Max Payne 3 Tier 3 filters: MotionBlur, PanelCompositor,
KineticTypography, DepthOfField, LensFlare."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters import (
    DepthOfFieldFilter,
    KineticTypographyFilter,
    LensFlareFilter,
    MotionBlurFilter,
    PanelCompositorFilter,
)
from ascii_stream_engine.domain.config import EngineConfig


@pytest.fixture
def config():
    return EngineConfig()


@pytest.fixture
def frame_480():
    h, w = 480, 640
    frame = np.full((h, w, 3), 80, dtype=np.uint8)
    frame[200:280, 280:360] = 250  # Bright spot.
    return np.ascontiguousarray(frame)


@pytest.fixture
def fake_flow():
    """Synthetic optical flow: rightward motion in the center."""
    h, w = 480, 640
    flow = np.zeros((h, w, 2), dtype=np.float32)
    flow[200:280, 280:360, 0] = 5.0  # X flow.
    return flow


class FakeAnalysis:
    """Minimal analysis object for testing temporal access."""

    def __init__(self, flow=None, prev_output=None):
        self._flow = flow
        self._prev = prev_output
        self._data = {}

    @property
    def optical_flow(self):
        return self._flow

    @property
    def previous_output(self):
        return self._prev

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data


class TestMotionBlurFilter:
    def test_noop_without_flow(self, frame_480, config):
        f = MotionBlurFilter(strength=1.0)
        result = f.apply(frame_480, config, analysis=None)
        assert result is frame_480

    def test_noop_zero_strength(self, frame_480, config):
        f = MotionBlurFilter(strength=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config, fake_flow):
        f = MotionBlurFilter(strength=1.0, samples=4)
        analysis = FakeAnalysis(flow=fake_flow)
        result = f.apply(frame_480, config, analysis=analysis)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_blur_modifies_frame(self, frame_480, config, fake_flow):
        f = MotionBlurFilter(strength=2.0, samples=6)
        analysis = FakeAnalysis(flow=fake_flow)
        result = f.apply(frame_480, config, analysis=analysis)
        assert not np.array_equal(result, frame_480)

    def test_temporal_declaration(self):
        f = MotionBlurFilter()
        assert f.needs_optical_flow is True

    def test_disabled(self, frame_480, config):
        f = MotionBlurFilter(strength=1.0, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestPanelCompositorFilter:
    def test_noop_single_panel(self, frame_480, config):
        f = PanelCompositorFilter(layout="1x1")
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = PanelCompositorFilter(layout="2x1", border_width=3)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_2x2_layout(self, frame_480, config):
        f = PanelCompositorFilter(layout="2x2", border_width=2)
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_angled_divider(self, frame_480, config):
        f = PanelCompositorFilter(layout="2x1", angle=15.0)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape

    def test_disabled(self, frame_480, config):
        f = PanelCompositorFilter(layout="2x1", enabled=False)
        assert f.apply(frame_480, config) is frame_480

    def test_invalid_layout_fallback(self, frame_480, config):
        f = PanelCompositorFilter(layout="invalid")
        result = f.apply(frame_480, config)
        assert result is frame_480


class TestKineticTypographyFilter:
    def test_noop_empty_text(self, frame_480, config):
        f = KineticTypographyFilter(text="")
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = KineticTypographyFilter(text="PAIN", font_size=36)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_text_modifies_frame(self, frame_480, config):
        f = KineticTypographyFilter(
            text="MAX PAYNE", font_size=48, duration_frames=1
        )
        result = f.apply(frame_480, config)
        assert not np.array_equal(result, frame_480)

    def test_scale_in_animation(self, frame_480, config):
        f = KineticTypographyFilter(
            text="TEST", animation="scale_in", duration_frames=10
        )
        results = []
        for _ in range(5):
            results.append(f.apply(frame_480.copy(), config))
        # Later frames should differ from earlier frames due to animation.
        assert not np.array_equal(results[0], results[-1])

    def test_disabled(self, frame_480, config):
        f = KineticTypographyFilter(text="TEST", enabled=False)
        assert f.apply(frame_480, config) is frame_480

    def test_reset_clears_counter(self, frame_480, config):
        f = KineticTypographyFilter(text="TEST")
        f.apply(frame_480, config)
        assert f._frame_counter > 0
        f.reset()
        assert f._frame_counter == 0


class TestDepthOfFieldFilter:
    def test_noop_small_radius(self, frame_480, config):
        f = DepthOfFieldFilter(blur_radius=1)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = DepthOfFieldFilter(focal_y=0.5, blur_radius=15)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_focal_plane_sharper(self, frame_480, config):
        f = DepthOfFieldFilter(focal_y=0.5, focal_range=0.1, blur_radius=21)
        result = f.apply(frame_480, config)
        h = frame_480.shape[0]
        # Center row (at focal plane) should be closer to original.
        mid = h // 2
        center_diff = float(np.mean(np.abs(
            result[mid, :].astype(int) - frame_480[mid, :].astype(int)
        )))
        # Top row (far from focal plane) should differ more.
        top_diff = float(np.mean(np.abs(
            result[10, :].astype(int) - frame_480[10, :].astype(int)
        )))
        assert center_diff <= top_diff

    def test_disabled(self, frame_480, config):
        f = DepthOfFieldFilter(blur_radius=15, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestLensFlareFilter:
    def test_noop_zero_intensity(self, frame_480, config):
        f = LensFlareFilter(intensity=0.0)
        result = f.apply(frame_480, config)
        assert result is frame_480

    def test_output_shape_dtype(self, frame_480, config):
        f = LensFlareFilter(threshold=200, intensity=0.5)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]

    def test_flare_brightens_frame(self, frame_480, config):
        f = LensFlareFilter(threshold=200, intensity=0.8)
        result = f.apply(frame_480, config)
        assert np.mean(result) >= np.mean(frame_480)

    def test_anamorphic_stretches_horizontally(self, frame_480, config):
        f = LensFlareFilter(threshold=200, intensity=0.5, anamorphic=True)
        result = f.apply(frame_480, config)
        assert result.shape == frame_480.shape

    def test_disabled(self, frame_480, config):
        f = LensFlareFilter(intensity=0.5, enabled=False)
        assert f.apply(frame_480, config) is frame_480


class TestTier3Chain:
    def test_full_tier3_chain(self, frame_480, config):
        """Chain Tier 3 filters in MP3 order."""
        dof = DepthOfFieldFilter(focal_y=0.5, blur_radius=11)
        flare = LensFlareFilter(threshold=200, intensity=0.3)
        panel = PanelCompositorFilter(layout="2x1", border_width=2)
        text = KineticTypographyFilter(text="BULLET TIME", font_size=36, duration_frames=1)

        result = dof.apply(frame_480, config)
        result = flare.apply(result, config)
        result = panel.apply(result, config)
        result = text.apply(result, config)

        assert result.shape == frame_480.shape
        assert result.dtype == np.uint8
        assert result.flags["C_CONTIGUOUS"]
