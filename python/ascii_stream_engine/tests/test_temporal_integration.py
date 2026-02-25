"""Integration tests for TemporalManager + FilterContext + reactive filters.

Tests the full pipeline: TemporalManager configures from filter declarations,
FilterContext wraps analysis + temporal, filters access shared temporal state.
"""

import numpy as np
import pytest

from ascii_stream_engine.application.pipeline.filter_context import FilterContext
from ascii_stream_engine.application.pipeline.filter_pipeline import FilterPipeline
from ascii_stream_engine.application.services.temporal_manager import TemporalManager
from ascii_stream_engine.domain.config import EngineConfig


class TestTemporalIntegration:
    """Full pipeline integration: TemporalManager + FilterContext + filters."""

    def _make_frame(self, h=120, w=160, value=128):
        return np.full((h, w, 3), value, dtype=np.uint8)

    def test_zero_allocation_no_temporal_filters(self):
        """No filter declares needs -> zero allocations, zero copies."""
        from ascii_stream_engine.adapters.processors.filters.brightness import BrightnessFilter

        tm = TemporalManager()
        f = BrightnessFilter()
        tm.configure([f])

        assert tm.input_depth == 0
        assert tm.needs_output is False
        assert tm.has_allocations is False

        # push_input/push_output are no-ops
        frame = self._make_frame()
        tm.push_input(frame)
        tm.push_output(frame)
        assert tm.has_allocations is False

    def test_optical_flow_shared_across_filters(self):
        """Optical flow computed once when 2+ filters need it."""
        from ascii_stream_engine.adapters.processors.filters.crt_glitch import CRTGlitchFilter
        from ascii_stream_engine.adapters.processors.filters.optical_flow_particles import (
            OpticalFlowParticlesFilter,
        )

        tm = TemporalManager()
        filters = [CRTGlitchFilter(), OpticalFlowParticlesFilter()]
        tm.configure(filters)

        # Both declare needs_optical_flow, so input_depth should be >= 2
        assert tm.input_depth >= 2
        assert tm._needs_flow is True

        # Push two frames to enable flow computation
        frame1 = self._make_frame(value=100)
        frame2 = self._make_frame(value=150)

        tm.begin_frame()
        tm.push_input(frame1)

        tm.begin_frame()
        tm.push_input(frame2)

        # First access computes flow
        flow1 = tm.get_optical_flow()
        # Second access returns cached (same object)
        flow2 = tm.get_optical_flow()
        assert flow1 is flow2

    def test_feedback_loop_output_buffer(self):
        """Filters declaring needs_previous_output get feedback."""
        from ascii_stream_engine.adapters.processors.filters.crt_glitch import CRTGlitchFilter

        tm = TemporalManager()
        f = CRTGlitchFilter()
        tm.configure([f])

        assert tm.needs_output is True

        # First frame: no previous output
        frame1 = self._make_frame(value=100)
        tm.begin_frame()
        tm.push_input(frame1)
        assert tm.get_previous_output() is None

        # Push output after processing
        processed = self._make_frame(value=200)
        tm.push_output(processed)

        # Next frame: previous output available
        frame2 = self._make_frame(value=120)
        tm.begin_frame()
        tm.push_input(frame2)
        prev_out = tm.get_previous_output()
        assert prev_out is not None
        assert prev_out.mean() == pytest.approx(200.0, abs=1.0)

    def test_filter_context_bridges_temporal_and_analysis(self):
        """FilterContext provides both dict access and temporal properties."""
        tm = TemporalManager()

        class FlowFilter:
            needs_optical_flow = True

        tm.configure([FlowFilter()])

        # Push frames
        frame1 = self._make_frame(value=50)
        frame2 = self._make_frame(value=100)
        tm.begin_frame()
        tm.push_input(frame1)
        tm.begin_frame()
        tm.push_input(frame2)

        # Create context with both analysis and temporal
        analysis = {"face": {"landmarks": []}, "timestamp": 1.0}
        ctx = FilterContext(analysis, tm)

        # Dict access works
        assert "face" in ctx
        assert ctx.get("timestamp") == 1.0

        # Temporal access works
        prev = ctx.previous_input
        assert prev is not None
        flow = ctx.optical_flow
        # Flow should be computed (or None if frames identical — depends on cv2)
        # Just verify it doesn't crash

    def test_delta_frame_available(self):
        """Physarum-like filter can access delta frame."""
        tm = TemporalManager()

        class DeltaFilter:
            needs_delta_frame = True

        tm.configure([DeltaFilter()])
        assert tm._needs_delta is True

        # Push two different frames
        frame1 = self._make_frame(value=50)
        frame2 = self._make_frame(value=100)

        tm.begin_frame()
        tm.push_input(frame1)

        tm.begin_frame()
        tm.push_input(frame2)

        delta = tm.get_delta()
        assert delta is not None
        # absdiff(100, 50) = 50 for each channel
        assert delta.mean() == pytest.approx(50.0, abs=1.0)

    def test_filter_pipeline_wraps_in_context(self):
        """FilterPipeline wraps analysis in FilterContext for filters."""
        from ascii_stream_engine.adapters.processors.filters.base import BaseFilter

        received_analysis = {}

        class SpyFilter(BaseFilter):
            name = "spy"

            def apply(self, frame, config, analysis=None):
                received_analysis["type"] = type(analysis).__name__
                received_analysis["has_get"] = hasattr(analysis, "get")
                received_analysis["has_optical_flow"] = hasattr(analysis, "optical_flow")
                return frame

        pipeline = FilterPipeline([SpyFilter()])
        config = EngineConfig()
        frame = self._make_frame()

        # With temporal in analysis dict
        tm = TemporalManager()
        analysis = {"face": {"data": True}, "temporal": tm}
        pipeline.apply(frame, config, analysis)

        assert received_analysis["type"] == "FilterContext"
        assert received_analysis["has_get"] is True
        assert received_analysis["has_optical_flow"] is True

    def test_crt_glitch_reactive_no_crash(self):
        """CRT Glitch filter works with and without temporal data."""
        from ascii_stream_engine.adapters.processors.filters.crt_glitch import CRTGlitchFilter

        f = CRTGlitchFilter()
        config = EngineConfig()
        frame = self._make_frame()

        # Without temporal (analysis=None)
        out1 = f.apply(frame, config, None)
        assert out1.shape == frame.shape

        # With FilterContext but no temporal
        ctx = FilterContext({"face": None}, None)
        out2 = f.apply(frame, config, ctx)
        assert out2.shape == frame.shape

    def test_physarum_with_delta_no_crash(self):
        """Physarum filter works with delta frame from FilterContext."""
        from ascii_stream_engine.adapters.processors.filters.physarum import PhysarumFilter

        tm = TemporalManager()
        f = PhysarumFilter(num_agents=100, sim_scale=4)
        tm.configure([f])

        config = EngineConfig()
        frame1 = self._make_frame(value=50)
        frame2 = self._make_frame(value=100)

        # Frame 1
        tm.begin_frame()
        tm.push_input(frame1)
        ctx1 = FilterContext({}, tm)
        out1 = f.apply(frame1, config, ctx1)
        assert out1.shape == frame1.shape

        # Frame 2 (delta should be available)
        tm.begin_frame()
        tm.push_input(frame2)
        ctx2 = FilterContext({}, tm)
        out2 = f.apply(frame2, config, ctx2)
        assert out2.shape == frame2.shape

    def test_optical_flow_particles_shared_flow(self):
        """OpticalFlowParticles uses shared flow when available."""
        from ascii_stream_engine.adapters.processors.filters.optical_flow_particles import (
            OpticalFlowParticlesFilter,
        )

        tm = TemporalManager()
        f = OpticalFlowParticlesFilter(max_particles=100)
        tm.configure([f])

        config = EngineConfig()

        # Create two slightly different frames to generate flow
        frame1 = np.random.randint(0, 256, (120, 160, 3), dtype=np.uint8)
        frame2 = frame1.copy()
        frame2[:, 5:] = frame1[:, :-5]  # Shift right by 5px

        # Frame 1
        tm.begin_frame()
        tm.push_input(frame1)
        ctx1 = FilterContext({}, tm)
        out1 = f.apply(frame1, config, ctx1)
        assert out1.shape == frame1.shape

        # Frame 2
        tm.begin_frame()
        tm.push_input(frame2)
        ctx2 = FilterContext({}, tm)
        out2 = f.apply(frame2, config, ctx2)
        assert out2.shape == frame2.shape

    def test_buffer_sizing_max_across_filters(self):
        """Ring buffer size = max(required_input_history) across active filters."""

        class Filter1:
            required_input_history = 1
            needs_optical_flow = False
            needs_delta_frame = False
            needs_previous_output = False

        class Filter3:
            required_input_history = 3
            needs_optical_flow = False
            needs_delta_frame = False
            needs_previous_output = False

        tm = TemporalManager()
        tm.configure([Filter1(), Filter3()])
        # max(1,3) = 3, plus 1 for current = 4
        assert tm.input_depth == 4
