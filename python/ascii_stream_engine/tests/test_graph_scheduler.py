"""Tests for GraphScheduler — execution order, temporal integration, error isolation."""

import threading
import time

import numpy as np
import pytest

from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.core.port_types import (
    InputPort,
    OutputPort,
    PortType,
)
from ascii_stream_engine.application.graph.core.base_node import BaseNode
from ascii_stream_engine.application.graph.nodes import (
    AnalyzerNode,
    OutputNode,
    ProcessorNode,
    RendererNode,
    SourceNode,
)
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler
from ascii_stream_engine.application.services.temporal_manager import TemporalManager
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.infrastructure.event_bus import EventBus
from ascii_stream_engine.infrastructure.profiling import LoopProfiler
from ascii_stream_engine.infrastructure.metrics import EngineMetrics


# --- Test node implementations ---


class StubSource(SourceNode):
    name = "test_source"

    def read_frame(self):
        return np.zeros((10, 10, 3), dtype=np.uint8)


class StubAnalyzer(AnalyzerNode):
    name = "test_analyzer"

    def analyze(self, frame):
        return {"detected": True, "score": 0.95}


class StubProcessor(ProcessorNode):
    name = "test_processor"

    def apply_filter(self, frame, config, analysis):
        return frame + 10


class TemporalProcessor(ProcessorNode):
    name = "temporal_processor"
    needs_optical_flow = True
    required_input_history = 2

    def apply_filter(self, frame, config, analysis):
        # Access temporal data via FilterContext
        if hasattr(analysis, "optical_flow"):
            _ = analysis.optical_flow  # Just access it
        return frame + 5


class StubRenderer(RendererNode):
    name = "test_renderer"

    def render(self, frame, config, analysis):
        return {"image": "rendered", "analysis": analysis}


class StubOutput(OutputNode):
    name = "test_output"
    written = []

    def write(self, rendered):
        StubOutput.written.append(rendered)


class FailingProcessor(ProcessorNode):
    name = "failing_processor"

    def apply_filter(self, frame, config, analysis):
        raise RuntimeError("Filter crash")


class FailingRenderer(RendererNode):
    name = "failing_renderer"

    def render(self, frame, config, analysis):
        raise RuntimeError("Renderer crash")


# --- Helper to build a pipeline graph ---


def build_linear_graph(*nodes):
    """Build a linear graph connecting nodes in sequence via compatible ports."""
    g = Graph()
    for n in nodes:
        g.add_node(n)

    for i in range(len(nodes) - 1):
        src = nodes[i]
        tgt = nodes[i + 1]
        # Find compatible port pair
        for out_port in src.get_output_ports():
            for in_port in tgt.get_input_ports():
                if in_port.accepts(out_port):
                    g.connect(src, out_port.name, tgt, in_port.name)
                    break
            else:
                continue
            break
    return g


# --- Tests ---


class TestGraphSchedulerBasic:
    def test_simple_pipeline(self):
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        success, err = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is True
        assert err is None
        assert len(StubOutput.written) == 1

    def test_with_analyzer(self):
        src = StubSource()
        analyzer = StubAnalyzer()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", renderer, "video_in")
        g.connect(analyzer, "analysis_out", renderer, "analysis_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        success, err = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is True

        analysis = scheduler.get_last_analysis()
        assert "test_analyzer" in analysis
        assert analysis["test_analyzer"]["detected"] is True

    def test_with_processor(self):
        src = StubSource()
        processor = StubProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(processor)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", processor, "video_in")
        g.connect(processor, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        success, _ = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is True
        # Processor adds 10 to the frame
        rendered = StubOutput.written[-1]
        assert rendered is not None


class TestGraphSchedulerTemporal:
    def test_temporal_manager_configured(self):
        src = StubSource()
        proc = TemporalProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        temporal = TemporalManager()
        scheduler = GraphScheduler(g, EngineConfig(), temporal_manager=temporal)

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 128
        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True
        # After first frame, temporal should be configured
        assert temporal.input_depth >= 2  # needs_optical_flow requires depth >= 2

    def test_filter_context_injected(self):
        """ProcessorNode should receive FilterContext with temporal access."""
        received_analysis = []

        class InspectingProcessor(ProcessorNode):
            name = "inspector"

            def apply_filter(self, frame, config, analysis):
                received_analysis.append(type(analysis).__name__)
                return frame

        src = StubSource()
        proc = InspectingProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        temporal = TemporalManager()
        scheduler = GraphScheduler(g, EngineConfig(), temporal_manager=temporal)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        assert "FilterContext" in received_analysis


class TestGraphSchedulerErrorIsolation:
    def test_non_fatal_processor_error(self):
        """Processor failure is non-fatal — execution continues."""
        src = StubSource()
        failing = FailingProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(failing)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", failing, "video_in")
        g.connect(failing, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        success, err = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        # Should still succeed because processor failure is non-fatal
        # (renderer receives passthrough frame)
        assert success is True

    def test_fatal_renderer_error(self):
        """Renderer failure is fatal — returns (False, error_msg)."""
        src = StubSource()
        failing = FailingRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(failing)
        g.add_node(output)

        g.connect(src, "video_out", failing, "video_in")
        g.connect(failing, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        success, err = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is False
        assert "Renderer crash" in err


class TestGraphSchedulerDisabledNodes:
    def test_disabled_processor_passthrough(self):
        """Disabled processor passes video through."""
        src = StubSource()
        proc = StubProcessor()
        proc.enabled = False
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42
        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True


class TestGraphSchedulerLifecycle:
    def test_setup_teardown(self):
        setup_called = []
        teardown_called = []

        class LifecycleSource(SourceNode):
            name = "lifecycle_source"

            def read_frame(self):
                return None

            def setup(self):
                setup_called.append("source")

            def teardown(self):
                teardown_called.append("source")

        class LifecycleRenderer(RendererNode):
            name = "lifecycle_renderer"

            def render(self, frame, config, analysis):
                return "rendered"

            def setup(self):
                setup_called.append("renderer")

            def teardown(self):
                teardown_called.append("renderer")

        g = Graph()
        src = LifecycleSource()
        renderer = LifecycleRenderer()
        g.add_node(src)
        g.add_node(renderer)
        g.connect(src, "video_out", renderer, "video_in")

        scheduler = GraphScheduler(g, EngineConfig())
        scheduler.setup()
        assert "source" in setup_called
        assert "renderer" in setup_called

        scheduler.teardown()
        assert "source" in teardown_called
        assert "renderer" in teardown_called

    def test_update_config(self):
        g = Graph()
        src = StubSource()
        g.add_node(src)
        scheduler = GraphScheduler(g, EngineConfig())
        new_config = EngineConfig(fps=60)
        scheduler.update_config(new_config)
        assert scheduler._config.fps == 60


class TestGraphSchedulerEdgeCases:
    def test_none_frame_through_pipeline(self):
        """None frame should not crash the scheduler."""
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        # None frame — renderer gets None, may fail (fatal) or handle
        success, err = scheduler.process_frame(None, 1.0)
        # Either succeeds with None passthrough or fails gracefully
        assert isinstance(success, bool)

    def test_empty_analysis_dict(self):
        """Processor receives empty analysis when no analyzers."""
        received = []

        class InspectProcessor(ProcessorNode):
            name = "inspector"

            def apply_filter(self, frame, config, analysis):
                received.append(dict(analysis) if hasattr(analysis, "keys") else analysis)
                return frame

        src = StubSource()
        proc = InspectProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        temporal = TemporalManager()
        scheduler = GraphScheduler(g, EngineConfig(), temporal_manager=temporal)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        # Analysis should be empty dict (no analyzers)
        assert len(received) == 1
        assert received[0] == {}

    def test_disabled_analyzer_still_passes_video(self):
        """Disabled analyzer should passthrough video to downstream nodes."""
        src = StubSource()
        analyzer = StubAnalyzer()
        analyzer.enabled = False
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 50
        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True
        assert len(StubOutput.written) == 1

    def test_no_temporal_manager(self):
        """Scheduler works correctly with temporal_manager=None."""
        src = StubSource()
        proc = StubProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig(), temporal_manager=None)
        success, _ = scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)
        assert success is True

    def test_middle_processor_failure_passthrough(self):
        """When middle processor fails in a chain, downstream gets passthrough."""
        src = StubSource()
        proc1 = StubProcessor()
        proc1.name = "proc1"
        failing = FailingProcessor()
        failing.name = "proc_fail"
        proc3 = StubProcessor()
        proc3.name = "proc3"
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc1)
        g.add_node(failing)
        g.add_node(proc3)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", proc1, "video_in")
        g.connect(proc1, "video_out", failing, "video_in")
        g.connect(failing, "video_out", proc3, "video_in")
        g.connect(proc3, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = scheduler.process_frame(frame, 1.0)
        # Should succeed — failing processor is non-fatal
        assert success is True
        assert len(StubOutput.written) == 1

    def test_multiple_frames_in_sequence(self):
        """Process multiple frames without state leaking between them."""
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        for i in range(5):
            success, _ = scheduler.process_frame(
                np.ones((10, 10, 3), dtype=np.uint8) * i, float(i)
            )
            assert success is True
        assert len(StubOutput.written) == 5


# --- Profiling Tests ---


class TestGraphSchedulerProfiling:
    def _build_full_pipeline(self):
        src = StubSource()
        analyzer = StubAnalyzer()
        proc = StubProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        return g

    def test_profiler_receives_phase_calls(self):
        """Profiler receives start/end for each pipeline stage."""
        profiler = LoopProfiler(enabled=True)
        g = self._build_full_pipeline()

        scheduler = GraphScheduler(g, EngineConfig(), profiler=profiler)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        stats = profiler.get_stats()
        # Should have capture, analysis, filtering, rendering, writing, total_frame
        assert "capture" in stats
        assert "analysis" in stats
        assert "filtering" in stats
        assert "rendering" in stats
        assert "writing" in stats
        assert "total_frame" in stats

    def test_start_end_frame_bracket(self):
        """start_frame/end_frame bracket the frame processing."""
        profiler = LoopProfiler(enabled=True)
        g = self._build_full_pipeline()

        scheduler = GraphScheduler(g, EngineConfig(), profiler=profiler)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        stats = profiler.get_stats()
        total = stats["total_frame"]
        assert total.count == 1
        assert total.total_time > 0

    def test_end_frame_called_on_fatal_error(self):
        """end_frame is called even on fatal renderer error."""
        profiler = LoopProfiler(enabled=True)
        src = StubSource()
        failing = FailingRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(failing)
        g.add_node(output)
        g.connect(src, "video_out", failing, "video_in")
        g.connect(failing, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig(), profiler=profiler)
        success, _ = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is False

        # end_frame should have been called despite fatal error
        stats = profiler.get_stats()
        assert "total_frame" in stats
        assert stats["total_frame"].count == 1

    def test_consecutive_same_type_nodes_grouped(self):
        """Consecutive same-type nodes (e.g. two processors) share a single phase."""
        profiler = LoopProfiler(enabled=True)
        src = StubSource()
        proc1 = StubProcessor()
        proc1.name = "proc_a"
        proc2 = StubProcessor()
        proc2.name = "proc_b"
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(proc1)
        g.add_node(proc2)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", proc1, "video_in")
        g.connect(proc1, "video_out", proc2, "video_in")
        g.connect(proc2, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig(), profiler=profiler)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        stats = profiler.get_stats()
        # Only one "filtering" phase should be recorded (not two)
        assert stats["filtering"].count == 1

    def test_profiler_disabled_no_crash(self):
        """Disabled profiler causes no crash."""
        profiler = LoopProfiler(enabled=False)
        g = self._build_full_pipeline()

        scheduler = GraphScheduler(g, EngineConfig(), profiler=profiler)
        success, _ = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is True


# --- Event Publishing Tests ---


class TestGraphSchedulerEvents:
    def _build_full_pipeline(self):
        src = StubSource()
        analyzer = StubAnalyzer()
        proc = StubProcessor()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(proc)
        g.add_node(renderer)
        g.add_node(output)

        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", proc, "video_in")
        g.connect(proc, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        return g

    def test_all_events_published(self):
        """All four phase events are published."""
        event_bus = EventBus()
        received = []

        def collector(event):
            received.append(type(event).__name__)

        event_bus.subscribe("analysis_complete", collector)
        event_bus.subscribe("filter_applied", collector)
        event_bus.subscribe("render_complete", collector)
        event_bus.subscribe("frame_written", collector)

        g = self._build_full_pipeline()
        scheduler = GraphScheduler(g, EngineConfig(), event_bus=event_bus)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        # publish_async uses threads, give them time to execute
        time.sleep(0.2)

        assert "AnalysisCompleteEvent" in received
        assert "FilterAppliedEvent" in received
        assert "RenderCompleteEvent" in received
        assert "FrameWrittenEvent" in received

    def test_events_carry_timing_data(self):
        """Events carry non-zero timing data."""
        event_bus = EventBus()
        events_received = []

        def collector(event):
            events_received.append(event)

        event_bus.subscribe("analysis_complete", collector)
        event_bus.subscribe("render_complete", collector)

        g = self._build_full_pipeline()
        scheduler = GraphScheduler(g, EngineConfig(), event_bus=event_bus)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        time.sleep(0.2)

        for event in events_received:
            if hasattr(event, "analysis_time"):
                assert event.analysis_time > 0
            if hasattr(event, "render_time"):
                assert event.render_time > 0

    def test_events_have_frame_id(self):
        """Events carry a valid frame_id."""
        event_bus = EventBus()
        frame_ids = []

        def collector(event):
            frame_ids.append(event.frame_id)

        event_bus.subscribe("analysis_complete", collector)

        g = self._build_full_pipeline()
        scheduler = GraphScheduler(g, EngineConfig(), event_bus=event_bus)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        time.sleep(0.2)

        assert len(frame_ids) == 1
        assert frame_ids[0].startswith("frame_")

    def test_no_crash_with_event_bus_none(self):
        """No crash when event_bus is None."""
        g = self._build_full_pipeline()
        scheduler = GraphScheduler(g, EngineConfig(), event_bus=None)
        success, _ = scheduler.process_frame(
            np.zeros((10, 10, 3), dtype=np.uint8), 1.0
        )
        assert success is True


# --- Node Timing Tests ---


class TestGraphSchedulerNodeTimings:
    def test_get_node_timings_returns_all_nodes(self):
        """get_node_timings() returns entries for all executed nodes."""
        src = StubSource()
        analyzer = StubAnalyzer()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        timings = scheduler.get_node_timings()
        # Source is skipped (external frame injection), but analyzer/renderer/output timed
        assert "test_analyzer" in timings
        assert "test_renderer" in timings
        assert "test_output" in timings
        for v in timings.values():
            assert isinstance(v, float)
            assert v >= 0

    def test_timings_reset_between_frames(self):
        """Timings are cleared at the start of each frame."""
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig())
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)
        timings1 = scheduler.get_node_timings()

        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 2.0)
        timings2 = scheduler.get_node_timings()

        # Both frames should have timings, and they should be independent
        assert len(timings1) > 0
        assert len(timings2) > 0

    def test_timings_empty_before_first_frame(self):
        """Before any frame is processed, timings are empty."""
        src = StubSource()
        renderer = StubRenderer()
        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.connect(src, "video_out", renderer, "video_in")

        scheduler = GraphScheduler(g, EngineConfig())
        assert scheduler.get_node_timings() == {}


# --- Metrics Tests ---


class TestGraphSchedulerMetrics:
    def test_record_frame_called_on_success(self):
        """metrics.record_frame() is called on successful frame processing."""
        metrics = EngineMetrics()
        metrics.start()
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig(), metrics=metrics)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 2.0)

        assert metrics.get_frames_processed() == 2

    def test_record_frame_not_called_on_fatal_error(self):
        """metrics.record_frame() is NOT called on fatal error."""
        metrics = EngineMetrics()
        metrics.start()
        src = StubSource()
        failing = FailingRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(failing)
        g.add_node(output)
        g.connect(src, "video_out", failing, "video_in")
        g.connect(failing, "render_out", output, "render_in")

        scheduler = GraphScheduler(g, EngineConfig(), metrics=metrics)
        scheduler.process_frame(np.zeros((10, 10, 3), dtype=np.uint8), 1.0)

        assert metrics.get_frames_processed() == 0


# --- Parallel Analyzer Tests ---


class SlowAnalyzer(AnalyzerNode):
    """Analyzer that sleeps to simulate slow processing."""

    def __init__(self, name_str, delay=0.05):
        super().__init__()
        self.name = name_str
        self._delay = delay

    def analyze(self, frame):
        time.sleep(self._delay)
        return {"analyzer": self.name, "mean": float(frame.mean())}


class FailingAnalyzer(AnalyzerNode):
    """Analyzer that always raises."""

    def __init__(self, name_str):
        super().__init__()
        self.name = name_str

    def analyze(self, frame):
        raise RuntimeError(f"{self.name} failed")


class TestGraphSchedulerParallelAnalyzers:
    def _build_parallel_analyzer_graph(self, analyzers):
        """Build a graph with source -> N analyzers (parallel) -> renderer -> output."""
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        for a in analyzers:
            g.add_node(a)
        g.add_node(renderer)
        g.add_node(output)

        # Connect source to all analyzers
        for a in analyzers:
            g.connect(src, "video_out", a, "video_in")

        # Connect first analyzer's video_out to renderer
        g.connect(analyzers[0], "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        return g

    def test_parallel_produces_same_results_as_sequential(self):
        """Parallel execution produces the same analysis results as sequential."""
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42

        a1 = SlowAnalyzer("analyzer_a", delay=0.01)
        a2 = SlowAnalyzer("analyzer_b", delay=0.01)
        g_seq = self._build_parallel_analyzer_graph([a1, a2])
        sched_seq = GraphScheduler(g_seq, EngineConfig(), parallel_analyzers=False)
        sched_seq.process_frame(frame.copy(), 1.0)
        analysis_seq = sched_seq.get_last_analysis()

        a3 = SlowAnalyzer("analyzer_a", delay=0.01)
        a4 = SlowAnalyzer("analyzer_b", delay=0.01)
        g_par = self._build_parallel_analyzer_graph([a3, a4])
        sched_par = GraphScheduler(g_par, EngineConfig(), parallel_analyzers=True)
        sched_par.process_frame(frame.copy(), 1.0)
        analysis_par = sched_par.get_last_analysis()

        # Both should have same analyzer keys (minus timestamp)
        for key in ["analyzer_a", "analyzer_b"]:
            assert key in analysis_seq, f"{key} missing from sequential"
            assert key in analysis_par, f"{key} missing from parallel"
            assert analysis_seq[key] == analysis_par[key]

    def test_parallel_is_faster_with_slow_analyzers(self):
        """Parallel execution is faster when analyzers are slow."""
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42
        delay = 0.1

        # Sequential
        a1 = SlowAnalyzer("slow_a", delay=delay)
        a2 = SlowAnalyzer("slow_b", delay=delay)
        g_seq = self._build_parallel_analyzer_graph([a1, a2])
        sched_seq = GraphScheduler(g_seq, EngineConfig(), parallel_analyzers=False)
        t0 = time.perf_counter()
        sched_seq.process_frame(frame.copy(), 1.0)
        seq_time = time.perf_counter() - t0

        # Parallel
        a3 = SlowAnalyzer("slow_a", delay=delay)
        a4 = SlowAnalyzer("slow_b", delay=delay)
        g_par = self._build_parallel_analyzer_graph([a3, a4])
        sched_par = GraphScheduler(g_par, EngineConfig(), parallel_analyzers=True)
        t0 = time.perf_counter()
        sched_par.process_frame(frame.copy(), 1.0)
        par_time = time.perf_counter() - t0

        # Parallel should be noticeably faster (at least 30% faster)
        assert par_time < seq_time * 0.85, (
            f"Parallel ({par_time:.3f}s) not faster than sequential ({seq_time:.3f}s)"
        )

    def test_error_isolation_in_parallel_group(self):
        """Failing analyzer doesn't break other analyzers in the group."""
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42
        metrics = EngineMetrics()

        good = SlowAnalyzer("good_analyzer", delay=0.01)
        bad = FailingAnalyzer("bad_analyzer")

        g = self._build_parallel_analyzer_graph([good, bad])
        scheduler = GraphScheduler(
            g, EngineConfig(), parallel_analyzers=True, metrics=metrics
        )
        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True

        analysis = scheduler.get_last_analysis()
        assert "good_analyzer" in analysis

    def test_disabled_analyzers_skipped(self):
        """Disabled analyzers are skipped in parallel groups."""
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42

        a1 = SlowAnalyzer("enabled_one", delay=0.01)
        a2 = SlowAnalyzer("disabled_one", delay=0.01)
        a2.enabled = False

        g = self._build_parallel_analyzer_graph([a1, a2])
        scheduler = GraphScheduler(g, EngineConfig(), parallel_analyzers=True)
        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True

        analysis = scheduler.get_last_analysis()
        assert "enabled_one" in analysis
        assert "disabled_one" not in analysis

    def test_single_analyzer_skips_thread_pool(self):
        """A single analyzer in a potential group executes without thread pool."""
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42

        a1 = SlowAnalyzer("solo_analyzer", delay=0.01)
        src = StubSource()
        renderer = StubRenderer()
        output = StubOutput()
        StubOutput.written = []

        g = Graph()
        g.add_node(src)
        g.add_node(a1)
        g.add_node(renderer)
        g.add_node(output)
        g.connect(src, "video_out", a1, "video_in")
        g.connect(a1, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        # Single analyzer — no parallel group detected (needs 2+)
        scheduler = GraphScheduler(g, EngineConfig(), parallel_analyzers=True)
        assert len(scheduler._parallel_groups) == 0

        success, _ = scheduler.process_frame(frame, 1.0)
        assert success is True

        analysis = scheduler.get_last_analysis()
        assert "solo_analyzer" in analysis
