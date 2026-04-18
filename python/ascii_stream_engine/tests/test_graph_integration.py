"""Integration tests for StreamEngine's GraphScheduler pipeline."""

import numpy as np

from ascii_stream_engine.adapters.processors.filters import BrightnessFilter, InvertFilter
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import FilterPipeline
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
    def test_graph_produces_frames(self):
        """StreamEngine produces frames through the GraphScheduler."""
        sink = DummySink()
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = engine._orchestrator.process_frame(frame, 1.0)

        assert success is True
        assert err is None
        assert len(sink.frames) == 1

    def test_graph_with_filters(self):
        """Graph with filters processes frames correctly."""
        sink = DummySink()
        renderer = DummyRenderer()
        pipeline = FilterPipeline([BrightnessFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=renderer,
            sink=sink,
            filters=pipeline,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = engine._orchestrator.process_frame(frame, 1.0)

        assert success is True
        assert len(sink.frames) == 1
        assert renderer.last_frame is not None

    def test_graph_with_multiple_filters(self):
        """Graph chains multiple filters correctly."""
        sink = DummySink()
        renderer = DummyRenderer()
        pipeline = FilterPipeline([BrightnessFilter(), InvertFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=renderer,
            sink=sink,
            filters=pipeline,
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = engine._orchestrator.process_frame(frame, 1.0)
        assert success is True

    def test_engine_uses_graph_scheduler(self):
        """_create_orchestrator always builds a GraphScheduler."""
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
        )
        engine._create_orchestrator()
        assert isinstance(engine._orchestrator, GraphScheduler)

    def test_graph_get_last_analysis(self):
        """Graph's get_last_analysis returns a dict with a timestamp."""
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
        )
        engine._create_orchestrator()

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        engine._orchestrator.process_frame(frame, 1.0)

        analysis = engine._orchestrator.get_last_analysis()
        assert isinstance(analysis, dict)
        assert "timestamp" in analysis

    def test_graph_update_config(self):
        """Graph's update_config propagates the new config."""
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
        )
        engine._create_orchestrator()
        engine._orchestrator.update_config(EngineConfig(fps=60))
        assert engine._orchestrator._config.fps == 60

    def test_graph_with_temporal(self):
        """Graph honors EngineConfig(enable_temporal=True)."""
        sink = DummySink()
        config = EngineConfig(enable_temporal=True)
        pipeline = FilterPipeline([BrightnessFilter()])

        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
            config=config,
            filters=pipeline,
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

    def test_graph_setup_teardown(self):
        """GraphScheduler setup/teardown lifecycle works via StreamEngine."""
        from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

        sink = DummySink()
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=sink,
        )
        engine._create_orchestrator()
        assert isinstance(engine._orchestrator, GraphScheduler)

        engine._orchestrator.setup()
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, _ = engine._orchestrator.process_frame(frame, 1.0)
        assert success is True
        engine._orchestrator.teardown()
