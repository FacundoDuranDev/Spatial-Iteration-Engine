"""Tests for fan-out zero-copy safety in GraphScheduler."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.core.base_node import BaseNode
from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.core.port_types import (
    InputPort,
    OutputPort,
    PortType,
)
from ascii_stream_engine.application.graph.nodes.source_node import SourceNode
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler
from ascii_stream_engine.domain.config import EngineConfig


class _TestSource(SourceNode):
    name = "test_source"

    def read_frame(self):
        return None


class _PassthroughNode(BaseNode):
    """Passes video through unchanged — for testing fan-out read-only."""

    def __init__(self, node_name: str) -> None:
        super().__init__()
        self.name = node_name
        self.received_frame = None
        self.was_writeable = None

    def get_input_ports(self):
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self):
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    def process(self, inputs):
        frame = inputs["video_in"]
        self.received_frame = frame
        self.was_writeable = frame.flags.writeable if hasattr(frame, "flags") else None
        return {"video_out": frame}


class _AnalysisPassNode(BaseNode):
    """Node that outputs ANALYSIS_DATA — for testing non-ndarray passthrough."""

    name = "analysis_pass"

    def get_input_ports(self):
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self):
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("analysis_out", PortType.ANALYSIS_DATA),
        ]

    def process(self, inputs):
        return {
            "video_out": inputs["video_in"],
            "analysis_out": {"key": "value"},
        }


class TestFanOutMultiConsumer:
    def test_two_consumers_from_source(self):
        """Source -> [consumer_a, consumer_b] should work."""
        g = Graph()
        src = _TestSource()
        consumer_a = _PassthroughNode("consumer_a")
        consumer_b = _PassthroughNode("consumer_b")

        g.add_node(src)
        g.add_node(consumer_a)
        g.add_node(consumer_b)
        g.connect(src, "video_out", consumer_a, "video_in")
        g.connect(src, "video_out", consumer_b, "video_in")

        config = EngineConfig()
        scheduler = GraphScheduler(graph=g, config=config)

        frame = np.full((10, 10, 3), 42, dtype=np.uint8)
        success, error = scheduler.process_frame(frame)
        assert success
        assert error is None

        # Both consumers should have received the same frame data
        np.testing.assert_array_equal(consumer_a.received_frame, frame)
        np.testing.assert_array_equal(consumer_b.received_frame, frame)

    def test_three_consumers(self):
        """One source feeding three consumers."""
        g = Graph()
        src = _TestSource()
        a = _PassthroughNode("a")
        b = _PassthroughNode("b")
        c = _PassthroughNode("c")

        g.add_node(src)
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.connect(src, "video_out", a, "video_in")
        g.connect(src, "video_out", b, "video_in")
        g.connect(src, "video_out", c, "video_in")

        scheduler = GraphScheduler(graph=g, config=EngineConfig())
        frame = np.ones((5, 5, 3), dtype=np.uint8) * 100
        success, _ = scheduler.process_frame(frame)
        assert success


class TestFanOutZeroCopy:
    def test_fan_out_marks_writeable_false(self):
        """ndarray outputs on fan-out ports should be marked read-only."""
        g = Graph()
        src = _TestSource()
        consumer_a = _PassthroughNode("consumer_a")
        consumer_b = _PassthroughNode("consumer_b")

        g.add_node(src)
        g.add_node(consumer_a)
        g.add_node(consumer_b)
        g.connect(src, "video_out", consumer_a, "video_in")
        g.connect(src, "video_out", consumer_b, "video_in")

        scheduler = GraphScheduler(graph=g, config=EngineConfig())

        frame = np.full((10, 10, 3), 42, dtype=np.uint8)
        assert frame.flags.writeable is True  # Initially writeable

        success, _ = scheduler.process_frame(frame)
        assert success

        # The frame stored in scheduler._outputs for the source should be read-only
        stored = scheduler._outputs["test_source"]["video_out"]
        assert stored.flags.writeable is False

    def test_single_consumer_stays_writeable(self):
        """ndarray on a port with only one consumer should remain writeable."""
        g = Graph()
        src = _TestSource()
        consumer = _PassthroughNode("consumer")

        g.add_node(src)
        g.add_node(consumer)
        g.connect(src, "video_out", consumer, "video_in")

        scheduler = GraphScheduler(graph=g, config=EngineConfig())

        frame = np.full((10, 10, 3), 42, dtype=np.uint8)
        success, _ = scheduler.process_frame(frame)
        assert success

        stored = scheduler._outputs["test_source"]["video_out"]
        assert stored.flags.writeable is True


class TestFanOutNonNdarray:
    def test_non_ndarray_passthrough(self):
        """Non-ndarray values (dicts, etc.) should pass through fan-out safely."""
        g = Graph()
        src = _TestSource()
        analysis = _AnalysisPassNode()

        # Two consumers of the analysis_out port
        class _AnalysisConsumer(BaseNode):
            def __init__(self, n):
                super().__init__()
                self.name = n
                self.received = None

            def get_input_ports(self):
                return [InputPort("analysis_in", PortType.ANALYSIS_DATA)]

            def get_output_ports(self):
                return []

            def process(self, inputs):
                self.received = inputs.get("analysis_in")
                return {}

        cons_a = _AnalysisConsumer("cons_a")
        cons_b = _AnalysisConsumer("cons_b")

        g.add_node(src)
        g.add_node(analysis)
        g.add_node(cons_a)
        g.add_node(cons_b)
        g.connect(src, "video_out", analysis, "video_in")
        g.connect(analysis, "analysis_out", cons_a, "analysis_in")
        g.connect(analysis, "analysis_out", cons_b, "analysis_in")

        scheduler = GraphScheduler(graph=g, config=EngineConfig())
        frame = np.zeros((5, 5, 3), dtype=np.uint8)
        success, _ = scheduler.process_frame(frame)
        assert success

        # Both consumers should have received the dict
        assert cons_a.received == {"key": "value"}
        assert cons_b.received == {"key": "value"}
