"""Tests for category-specific node base classes."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.core.port_types import PortType
from ascii_stream_engine.application.graph.nodes import (
    AnalyzerNode,
    OutputNode,
    ProcessorNode,
    RendererNode,
    SourceNode,
    TrackerNode,
    TransformNode,
)


# --- Concrete test implementations ---


class TestSourceNode:
    def test_ports(self):
        class MySource(SourceNode):
            name = "cam"

            def read_frame(self):
                return np.zeros((10, 10, 3), dtype=np.uint8)

        node = MySource()
        assert len(node.get_input_ports()) == 0
        assert len(node.get_output_ports()) == 1
        assert node.get_output_ports()[0].data_type == PortType.VIDEO_FRAME

    def test_process(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class MySource(SourceNode):
            name = "cam"

            def read_frame(self):
                return frame

        node = MySource()
        result = node.process({})
        assert result["video_out"] is frame


class TestAnalyzerNode:
    def test_ports(self):
        class MyAnalyzer(AnalyzerNode):
            name = "face"

            def analyze(self, frame):
                return {"detected": True}

        node = MyAnalyzer()
        inputs = node.get_input_ports()
        outputs = node.get_output_ports()
        assert len(inputs) == 1
        assert inputs[0].data_type == PortType.VIDEO_FRAME
        assert len(outputs) == 2
        out_types = {o.name: o.data_type for o in outputs}
        assert out_types["video_out"] == PortType.VIDEO_FRAME
        assert out_types["analysis_out"] == PortType.ANALYSIS_DATA

    def test_passthrough(self):
        """Analyzer must not modify the frame — video_out is the same object."""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class MyAnalyzer(AnalyzerNode):
            name = "face"

            def analyze(self, f):
                return {"detected": True}

        node = MyAnalyzer()
        result = node.process({"video_in": frame})
        assert result["video_out"] is frame
        assert result["analysis_out"] == {"face": {"detected": True}}


class TestProcessorNode:
    def test_ports(self):
        class MyFilter(ProcessorNode):
            name = "bright"

            def apply_filter(self, frame, config, analysis):
                return frame + 10

        node = MyFilter()
        inputs = node.get_input_ports()
        assert len(inputs) == 2
        assert inputs[0].required is True
        assert inputs[1].required is False  # analysis_in optional

    def test_process(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class MyFilter(ProcessorNode):
            name = "bright"

            def apply_filter(self, f, config, analysis):
                return f + 10

        node = MyFilter()
        node.config = {}
        result = node.process({"video_in": frame})
        assert np.all(result["video_out"] == 10)


class TestRendererNode:
    def test_ports(self):
        class MyRenderer(RendererNode):
            name = "ascii"

            def render(self, frame, config, analysis):
                return "rendered"

        node = MyRenderer()
        outputs = node.get_output_ports()
        assert outputs[0].data_type == PortType.RENDER_FRAME

    def test_process(self):
        class MyRenderer(RendererNode):
            name = "ascii"

            def render(self, frame, config, analysis):
                return "rendered_frame"

        node = MyRenderer()
        node.config = {}
        result = node.process({"video_in": np.zeros((5, 5, 3), dtype=np.uint8)})
        assert result["render_out"] == "rendered_frame"


class TestOutputNode:
    def test_ports(self):
        class MyOutput(OutputNode):
            name = "udp"

            def write(self, rendered):
                pass

        node = MyOutput()
        assert len(node.get_input_ports()) == 1
        assert node.get_input_ports()[0].data_type == PortType.RENDER_FRAME
        assert len(node.get_output_ports()) == 0

    def test_process(self):
        written = []

        class MyOutput(OutputNode):
            name = "udp"

            def write(self, rendered):
                written.append(rendered)

        node = MyOutput()
        result = node.process({"render_in": "frame_data"})
        assert result == {}
        assert written == ["frame_data"]


class TestTrackerNode:
    def test_ports(self):
        class MyTracker(TrackerNode):
            name = "kalman"

            def track(self, frame, detections, config):
                return {"tracked": True}

        node = MyTracker()
        inputs = node.get_input_ports()
        assert len(inputs) == 2
        assert all(p.required for p in inputs)
        outputs = node.get_output_ports()
        out_types = {o.name: o.data_type for o in outputs}
        assert out_types["video_out"] == PortType.VIDEO_FRAME
        assert out_types["tracking_out"] == PortType.TRACKING_DATA

    def test_passthrough(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class MyTracker(TrackerNode):
            name = "kalman"

            def track(self, f, detections, config):
                return {"objects": []}

        node = MyTracker()
        node.config = {}
        result = node.process({"video_in": frame, "analysis_in": {"face": {}}})
        assert result["video_out"] is frame


class TestTransformNode:
    def test_ports(self):
        class MyTransform(TransformNode):
            name = "warp"

            def transform(self, frame):
                return frame

        node = MyTransform()
        assert len(node.get_input_ports()) == 1
        assert len(node.get_output_ports()) == 1

    def test_process(self):
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 42

        class MyTransform(TransformNode):
            name = "warp"

            def transform(self, f):
                return f * 2

        node = MyTransform()
        result = node.process({"video_in": frame})
        assert np.all(result["video_out"] == 84)
