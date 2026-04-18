"""Integration tests: StreamEngine with use_graph=True produces frames."""

import numpy as np
import pytest

from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import FilterPipeline
from ascii_stream_engine.adapters.processors.filters import BrightnessFilter, InvertFilter
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


# --- Dummy adapters ---


class DummySource:
    def __init__(self, frame=None):
        self._frame = frame if frame is not None else np.ones((10, 10, 3), dtype=np.uint8) * 128
        self.opened = False

    def open(self):
        self.opened = True

    def read(self):
        return self._frame.copy()

    def close(self):
        self.opened = False


class DummyRenderer:
    def __init__(self):
        self.last_frame = None

    def output_size(self, config):
        return (10, 10)

    def render(self, frame, config, analysis=None):
        self.last_frame = frame
        return RenderFrame(image=object(), text="x", lines=["x"])


class DummySink:
    def __init__(self):
        self.frames = []

    def open(self, config, output_size):
        pass

    def write(self, frame):
        self.frames.append(frame)

    def close(self):
        pass


class TestGraphIntegration:
    def test_use_graph_produces_frames(self):
        """StreamEngine(use_graph=True) produces frames through the graph."""
        sink = DummySink()
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
            use_graph=True,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = engine._orchestrator.process_frame(frame, 1.0)

        assert success is True
        assert err is None
        assert len(sink.frames) == 1

    def test_use_graph_with_filters(self):
        """Graph mode with filters processes frames correctly."""
        sink = DummySink()
        renderer = DummyRenderer()
        pipeline = FilterPipeline([BrightnessFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=renderer,
            sink=sink,
            filters=pipeline,
            use_graph=True,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = engine._orchestrator.process_frame(frame, 1.0)

        assert success is True
        assert len(sink.frames) == 1
        # Renderer received a processed frame
        assert renderer.last_frame is not None

    def test_use_graph_with_multiple_filters(self):
        """Graph mode chains multiple filters correctly."""
        sink = DummySink()
        renderer = DummyRenderer()
        pipeline = FilterPipeline([BrightnessFilter(), InvertFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=renderer,
            sink=sink,
            filters=pipeline,
            use_graph=True,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = engine._orchestrator.process_frame(frame, 1.0)
        assert success is True

    def test_parity_with_pipeline_orchestrator(self):
        """Graph mode produces same output structure as PipelineOrchestrator mode."""
        sink_graph = DummySink()
        renderer_graph = DummyRenderer()
        sink_pipeline = DummySink()
        renderer_pipeline = DummyRenderer()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        pipeline = FilterPipeline([BrightnessFilter()])

        # Graph mode
        engine_graph = StreamEngine(
            source=DummySource(),
            renderer=renderer_graph,
            sink=sink_graph,
            filters=pipeline,
            use_graph=True,
        )
        engine_graph._create_orchestrator()
        success_g, _ = engine_graph._orchestrator.process_frame(frame.copy(), 1.0)

        # Pipeline mode (need a fresh pipeline since FilterPipeline may have state)
        pipeline2 = FilterPipeline([BrightnessFilter()])
        engine_pipeline = StreamEngine(
            source=DummySource(),
            renderer=renderer_pipeline,
            sink=sink_pipeline,
            filters=pipeline2,
            use_graph=False,
        )
        engine_pipeline._create_orchestrator()
        success_p, _ = engine_pipeline._orchestrator.process_frame(frame.copy(), 1.0)

        assert success_g is True
        assert success_p is True
        assert len(sink_graph.frames) == 1
        assert len(sink_pipeline.frames) == 1

        # Both should produce RenderFrame objects
        assert isinstance(sink_graph.frames[0], RenderFrame)
        assert isinstance(sink_pipeline.frames[0], RenderFrame)

    def test_use_graph_false_unchanged(self):
        """use_graph=False still uses PipelineOrchestrator."""
        from ascii_stream_engine.application.orchestration import PipelineOrchestrator

        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            use_graph=False,
        )
        engine._create_orchestrator()
        assert isinstance(engine._orchestrator, PipelineOrchestrator)

    def test_use_graph_true_uses_scheduler(self):
        """use_graph=True creates a GraphScheduler."""
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            use_graph=True,
        )
        engine._create_orchestrator()
        assert isinstance(engine._orchestrator, GraphScheduler)

    def test_graph_get_last_analysis(self):
        """Graph mode's get_last_analysis works like pipeline mode."""
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            use_graph=True,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        engine._orchestrator.process_frame(frame, 1.0)

        analysis = engine._orchestrator.get_last_analysis()
        assert isinstance(analysis, dict)
        assert "timestamp" in analysis

    def test_graph_update_config(self):
        """Graph mode's update_config works."""
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            use_graph=True,
        )
        engine._create_orchestrator()
        engine._orchestrator.update_config(EngineConfig(fps=60))
        assert engine._orchestrator._config.fps == 60

    def test_graph_with_temporal(self):
        """Graph mode with temporal manager enabled."""
        sink = DummySink()
        config = EngineConfig(enable_temporal=True)
        pipeline = FilterPipeline([BrightnessFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
            config=config,
            filters=pipeline,
            use_graph=True,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = engine._orchestrator.process_frame(frame, 1.0)
        assert success is True
        assert len(sink.frames) == 1


# --- Complex Integration Tests ---


class DummyAnalyzer:
    """Minimal analyzer for integration tests."""
    name = "dummy_analyzer"
    enabled = True

    def analyze(self, frame, config):
        return {"detected": True, "mean": float(np.mean(frame))}


class DummyTracker:
    """Minimal tracker for integration tests."""
    name = "dummy_tracker"
    enabled = True

    def track(self, frame, detections, config):
        return {"tracked_objects": [{"id": 1, "bbox": [0, 0, 5, 5]}]}


class DummyTransform:
    """Minimal transform that doubles pixel values (clamped)."""
    name = "dummy_transform"

    def transform(self, frame):
        return np.clip(frame.astype(np.int16) * 2, 0, 255).astype(np.uint8)


class TestGraphComplexPipelines:
    """Complex pipeline integration tests using GraphBuilder + GraphScheduler."""

    def test_analyzer_plus_tracker(self):
        """Full pipeline: source -> analyzer -> merge -> tracker -> renderer -> output."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        renderer = DummyRenderer()

        g = GraphBuilder.build(
            renderer=renderer,
            sink=sink,
            analyzers=[DummyAnalyzer()],
            trackers=[DummyTracker()],
        )
        errors = g.validate()
        assert errors == []

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 80
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        assert err is None
        assert len(sink.frames) == 1

        # Analysis should contain both analyzer and tracking data
        analysis = scheduler.get_last_analysis()
        assert "dummy_analyzer" in analysis
        assert analysis["dummy_analyzer"]["detected"] is True
        assert "tracking" in analysis

    def test_analyzer_tracker_filter_chain(self):
        """Full pipeline: analyzer -> tracker -> filter -> renderer."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        renderer = DummyRenderer()
        pipeline = FilterPipeline([BrightnessFilter()])

        g = GraphBuilder.build(
            renderer=renderer,
            sink=sink,
            analyzers=[DummyAnalyzer()],
            trackers=[DummyTracker()],
            filters=pipeline,
        )
        errors = g.validate()
        assert errors == []

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        assert len(sink.frames) == 1

    def test_transform_plus_filter_chain(self):
        """Pipeline: source -> transform -> filter -> renderer -> output."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        renderer = DummyRenderer()

        g = GraphBuilder.build(
            renderer=renderer,
            sink=sink,
            transforms=[DummyTransform()],
            filters=FilterPipeline([BrightnessFilter()]),
        )
        errors = g.validate()
        assert errors == []

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 50
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        assert len(sink.frames) == 1
        # Transform doubled pixels from 50->100, then brightness filter applied
        assert renderer.last_frame is not None

    def test_multi_frame_state_isolation(self):
        """Process multiple frames — no state leaks between frames."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        renderer = DummyRenderer()

        g = GraphBuilder.build(
            renderer=renderer,
            sink=sink,
            analyzers=[DummyAnalyzer()],
            filters=FilterPipeline([BrightnessFilter()]),
        )

        scheduler = GraphScheduler(g, EngineConfig())

        for i in range(5):
            frame = np.ones((10, 10, 3), dtype=np.uint8) * (20 * i + 10)
            success, err = scheduler.process_frame(frame, float(i))
            assert success is True
            assert err is None

        assert len(sink.frames) == 5
        # Each analysis timestamp should match the last frame
        analysis = scheduler.get_last_analysis()
        assert analysis["timestamp"] == 4.0

    def test_multiple_analyzers_with_tracker(self):
        """Two analyzers fan out from source, merge, then tracker uses merged data."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        a1 = DummyAnalyzer()
        a1.name = "analyzer_faces"
        a2 = DummyAnalyzer()
        a2.name = "analyzer_poses"

        sink = DummySink()

        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=sink,
            analyzers=[a1, a2],
            trackers=[DummyTracker()],
        )

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 128
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        analysis = scheduler.get_last_analysis()
        assert "analyzer_faces" in analysis
        assert "analyzer_poses" in analysis
        assert "tracking" in analysis

    def test_full_pipeline_all_stages(self):
        """Every stage: source -> analyzers -> tracker -> transform -> filter -> renderer -> output."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        renderer = DummyRenderer()

        g = GraphBuilder.build(
            renderer=renderer,
            sink=sink,
            analyzers=[DummyAnalyzer()],
            trackers=[DummyTracker()],
            transforms=[DummyTransform()],
            filters=FilterPipeline([BrightnessFilter(), InvertFilter()]),
        )
        errors = g.validate()
        assert errors == []

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 60
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        assert len(sink.frames) == 1
        assert renderer.last_frame is not None

    def test_byte_level_parity_brightness(self):
        """Graph and pipeline produce identical pixel values for BrightnessFilter."""
        sink_graph = DummySink()
        renderer_graph = DummyRenderer()
        sink_pipe = DummySink()
        renderer_pipe = DummyRenderer()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100

        # Graph mode
        engine_graph = StreamEngine(
            source=DummySource(),
            renderer=renderer_graph,
            sink=sink_graph,
            filters=FilterPipeline([BrightnessFilter()]),
            use_graph=True,
        )
        engine_graph._create_orchestrator()
        engine_graph._orchestrator.process_frame(frame.copy(), 1.0)

        # Pipeline mode
        engine_pipe = StreamEngine(
            source=DummySource(),
            renderer=renderer_pipe,
            sink=sink_pipe,
            filters=FilterPipeline([BrightnessFilter()]),
            use_graph=False,
        )
        engine_pipe._create_orchestrator()
        engine_pipe._orchestrator.process_frame(frame.copy(), 1.0)

        # Both renderers should have received the same processed frame
        assert renderer_graph.last_frame is not None
        assert renderer_pipe.last_frame is not None
        np.testing.assert_array_equal(
            renderer_graph.last_frame,
            renderer_pipe.last_frame,
        )

    def test_byte_level_parity_chained_filters(self):
        """Graph and pipeline produce identical results for chained Brightness + Invert."""
        sink_graph = DummySink()
        renderer_graph = DummyRenderer()
        sink_pipe = DummySink()
        renderer_pipe = DummyRenderer()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 80

        engine_graph = StreamEngine(
            source=DummySource(),
            renderer=renderer_graph,
            sink=sink_graph,
            filters=FilterPipeline([BrightnessFilter(), InvertFilter()]),
            use_graph=True,
        )
        engine_graph._create_orchestrator()
        engine_graph._orchestrator.process_frame(frame.copy(), 1.0)

        engine_pipe = StreamEngine(
            source=DummySource(),
            renderer=renderer_pipe,
            sink=sink_pipe,
            filters=FilterPipeline([BrightnessFilter(), InvertFilter()]),
            use_graph=False,
        )
        engine_pipe._create_orchestrator()
        engine_pipe._orchestrator.process_frame(frame.copy(), 1.0)

        np.testing.assert_array_equal(
            renderer_graph.last_frame,
            renderer_pipe.last_frame,
        )

    def test_disabled_filter_parity(self):
        """Disabled filter in graph produces same result as pipeline (passthrough)."""
        sink_graph = DummySink()
        renderer_graph = DummyRenderer()
        sink_pipe = DummySink()
        renderer_pipe = DummyRenderer()

        # BrightnessFilter starts enabled, InvertFilter disabled
        bf_graph = BrightnessFilter()
        inv_graph = InvertFilter()
        inv_graph.enabled = False

        bf_pipe = BrightnessFilter()
        inv_pipe = InvertFilter()
        inv_pipe.enabled = False

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 120

        engine_graph = StreamEngine(
            source=DummySource(),
            renderer=renderer_graph,
            sink=sink_graph,
            filters=FilterPipeline([bf_graph, inv_graph]),
            use_graph=True,
        )
        engine_graph._create_orchestrator()
        engine_graph._orchestrator.process_frame(frame.copy(), 1.0)

        engine_pipe = StreamEngine(
            source=DummySource(),
            renderer=renderer_pipe,
            sink=sink_pipe,
            filters=FilterPipeline([bf_pipe, inv_pipe]),
            use_graph=False,
        )
        engine_pipe._create_orchestrator()
        engine_pipe._orchestrator.process_frame(frame.copy(), 1.0)

        np.testing.assert_array_equal(
            renderer_graph.last_frame,
            renderer_pipe.last_frame,
        )

    def test_graph_setup_teardown(self):
        """GraphScheduler setup/teardown lifecycle works via StreamEngine."""
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
            use_graph=True,
        )
        engine._create_orchestrator()
        assert isinstance(engine._orchestrator, GraphScheduler)

        # setup/teardown should not crash
        engine._orchestrator.setup()
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = engine._orchestrator.process_frame(frame, 1.0)
        assert success is True
        engine._orchestrator.teardown()
