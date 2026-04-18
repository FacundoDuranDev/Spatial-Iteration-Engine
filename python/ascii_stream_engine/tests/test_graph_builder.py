"""Tests for GraphBuilder — builds Graph from StreamEngine pipeline objects."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.bridge.graph_builder import (
    AnalysisMergeNode,
    GraphBuilder,
)
from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler
from ascii_stream_engine.application.graph.nodes import (
    OutputNode,
    ProcessorNode,
    RendererNode,
    SourceNode,
)
from ascii_stream_engine.application.pipeline import FilterPipeline, AnalyzerPipeline
from ascii_stream_engine.adapters.processors.filters import BrightnessFilter, InvertFilter
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


# --- Dummy adapters matching existing test patterns ---


class DummySource:
    def __init__(self):
        self.opened = False

    def open(self):
        self.opened = True

    def read(self):
        return np.zeros((10, 10, 3), dtype=np.uint8)

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
        self.count = 0
        self.output_size_val = None

    def open(self, config, output_size):
        self.output_size_val = output_size

    def write(self, frame):
        self.count += 1

    def close(self):
        pass


class DummyAnalyzer:
    name = "dummy_analyzer"
    enabled = True

    def analyze(self, frame, config):
        return {"detected": True}


class TestGraphBuilder:
    def test_build_minimal(self):
        """Minimal graph: source -> renderer -> output."""
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
        )
        assert len(g) == 3  # source + renderer + output
        errors = g.validate()
        assert errors == []

    def test_build_with_filters(self):
        """Graph with filters in the pipeline."""
        pipeline = FilterPipeline([BrightnessFilter(), InvertFilter()])
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            filters=pipeline,
        )
        # source + 2 filters + renderer + output = 5
        assert len(g) == 5
        errors = g.validate()
        assert errors == []

    def test_build_with_analyzers(self):
        """Graph with analyzers + merge node."""
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            analyzers=[DummyAnalyzer()],
        )
        # source + 1 analyzer + merge + renderer + output = 5
        assert len(g) == 5
        errors = g.validate()
        assert errors == []

    def test_build_with_multiple_analyzers(self):
        """Multiple analyzers fan out from source and merge."""
        a1 = DummyAnalyzer()
        a1.name = "analyzer_a"
        a2 = DummyAnalyzer()
        a2.name = "analyzer_b"

        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            analyzers=[a1, a2],
        )
        # source + 2 analyzers + merge + renderer + output = 6
        assert len(g) == 6

    def test_execution_order(self):
        """Verify topological order matches pipeline semantics."""
        pipeline = FilterPipeline([BrightnessFilter()])
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            filters=pipeline,
        )
        order = g.get_execution_order()
        names = [n.name for n in order]

        # Source must come first, output last
        assert names[0] == "external_source"
        assert names[-1] == "output"
        # Renderer before output
        assert names.index("renderer") < names.index("output")

    def test_full_pipeline_execution(self):
        """Build graph from adapters and execute it through GraphScheduler."""
        sink = DummySink()
        pipeline = FilterPipeline([BrightnessFilter()])

        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=sink,
            filters=pipeline,
        )

        scheduler = GraphScheduler(g, EngineConfig())
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 100
        success, err = scheduler.process_frame(frame, 1.0)

        assert success is True
        assert err is None
        assert sink.count == 1


class TestAnalysisMergeNode:
    def test_merge_two_analyzers(self):
        node = AnalysisMergeNode(2)
        result = node.process({
            "video_in": "frame",
            "analysis_in_0": {"face": {"detected": True}},
            "analysis_in_1": {"pose": {"keypoints": []}},
        })
        assert result["video_out"] == "frame"
        assert result["analysis_out"]["face"]["detected"] is True
        assert "pose" in result["analysis_out"]

    def test_merge_missing_inputs(self):
        node = AnalysisMergeNode(2)
        result = node.process({
            "video_in": "frame",
            "analysis_in_0": {"face": {}},
            # analysis_in_1 missing
        })
        assert "face" in result["analysis_out"]

    def test_ports(self):
        node = AnalysisMergeNode(3)
        inputs = node.get_input_ports()
        assert len(inputs) == 4  # video_in + 3 analysis_in
        outputs = node.get_output_ports()
        assert len(outputs) == 2  # video_out + analysis_out

    def test_merge_non_dict_input_skipped(self):
        node = AnalysisMergeNode(2)
        result = node.process({
            "video_in": "frame",
            "analysis_in_0": {"face": {}},
            "analysis_in_1": "not_a_dict",
        })
        assert "face" in result["analysis_out"]
        assert len(result["analysis_out"]) == 1

    def test_merge_overlapping_keys(self):
        node = AnalysisMergeNode(2)
        result = node.process({
            "video_in": "frame",
            "analysis_in_0": {"score": 0.5},
            "analysis_in_1": {"score": 0.9},
        })
        # Last writer wins (dict.update behavior)
        assert result["analysis_out"]["score"] == 0.9

    def test_merge_zero_analyzers(self):
        node = AnalysisMergeNode(0)
        result = node.process({"video_in": "frame"})
        assert result["analysis_out"] == {}
        assert result["video_out"] == "frame"


class TestGraphBuilderValidation:
    def test_tracker_without_analyzer_raises(self):
        class DummyTracker:
            name = "tracker"
            enabled = True

            def track(self, frame, detections, config):
                return {}

        with pytest.raises(ValueError, match="Trackers require analysis"):
            GraphBuilder.build(
                renderer=DummyRenderer(),
                sink=DummySink(),
                trackers=[DummyTracker()],
            )

    def test_filters_without_analyzers_ok(self):
        """Filters should work without analyzers (analysis_in is optional)."""
        pipeline = FilterPipeline([BrightnessFilter()])
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            filters=pipeline,
        )
        errors = g.validate()
        assert errors == []

    def test_only_source_and_renderer(self):
        """Minimal viable graph: source + renderer + output."""
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
        )
        assert len(g) == 3
        errors = g.validate()
        assert errors == []

    def test_build_with_no_sink(self):
        """Graph with renderer but no sink."""
        g = GraphBuilder.build(renderer=DummyRenderer())
        # source + renderer only
        assert len(g) == 2

    def test_build_with_no_renderer(self):
        """Graph with no renderer and no sink — just source."""
        g = GraphBuilder.build()
        assert len(g) == 1  # only source

    def test_build_with_pipeline_objects(self):
        """GraphBuilder accepts pipeline objects, not just lists."""
        pipeline = FilterPipeline([BrightnessFilter(), InvertFilter()])
        analyzer_pipeline = AnalyzerPipeline([DummyAnalyzer()])
        g = GraphBuilder.build(
            renderer=DummyRenderer(),
            sink=DummySink(),
            filters=pipeline,
            analyzers=analyzer_pipeline,
        )
        assert len(g) >= 6  # source + analyzer + merge + 2 filters + renderer + output


class TestWrapperNodeEnabledDelegation:
    """Verify that wrapper nodes delegate enabled to the underlying adapter."""

    def test_processor_node_enabled_delegates(self):
        """Setting adapter.enabled=False should be reflected in node.enabled."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceProcessorNode,
        )

        f = BrightnessFilter()
        f.enabled = True
        node = _InstanceProcessorNode(f)
        assert node.enabled is True

        f.enabled = False
        assert node.enabled is False

    def test_processor_node_enabled_bidirectional(self):
        """Setting node.enabled=False should propagate to the adapter."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceProcessorNode,
        )

        f = BrightnessFilter()
        f.enabled = True
        node = _InstanceProcessorNode(f)
        node.enabled = False
        assert f.enabled is False

    def test_analyzer_node_enabled_delegates(self):
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceAnalyzerNode,
        )

        a = DummyAnalyzer()
        a.enabled = True
        node = _InstanceAnalyzerNode(a)
        assert node.enabled is True

        a.enabled = False
        assert node.enabled is False

    def test_analyzer_node_enabled_bidirectional(self):
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceAnalyzerNode,
        )

        a = DummyAnalyzer()
        node = _InstanceAnalyzerNode(a)
        node.enabled = False
        assert a.enabled is False

    def test_tracker_node_enabled_delegates(self):
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceTrackerNode,
        )

        class DummyTracker:
            name = "tracker"
            enabled = True

            def track(self, frame, detections, config):
                return {}

        t = DummyTracker()
        node = _InstanceTrackerNode(t)
        assert node.enabled is True

        t.enabled = False
        assert node.enabled is False

    def test_enabled_defaults_true_when_adapter_has_no_enabled(self):
        """Adapter without enabled attr should default to True."""
        from ascii_stream_engine.application.graph.bridge.graph_builder import (
            _InstanceProcessorNode,
        )

        class NoEnabledFilter:
            name = "no_enabled"

            def apply(self, frame, config, analysis=None):
                return frame

        node = _InstanceProcessorNode(NoEnabledFilter())
        assert node.enabled is True
