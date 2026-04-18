"""Tests for graph core: PortType, InputPort, OutputPort, BaseNode, Connection, Graph."""

import pytest

from ascii_stream_engine.application.graph.core.port_types import (
    InputPort,
    OutputPort,
    PortType,
)
from ascii_stream_engine.application.graph.core.base_node import BaseNode
from ascii_stream_engine.application.graph.core.connection import Connection
from ascii_stream_engine.application.graph.core.graph import Graph


# --- Helpers ---


class DummyProducer(BaseNode):
    name = "producer"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    def process(self, inputs):
        return {"video_out": "frame_data"}


class DummyConsumer(BaseNode):
    name = "consumer"

    def get_input_ports(self):
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self):
        return []

    def process(self, inputs):
        return {}


class DummyAnalysis(BaseNode):
    name = "analyzer"

    def get_input_ports(self):
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self):
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("analysis_out", PortType.ANALYSIS_DATA),
        ]

    def process(self, inputs):
        return {"video_out": inputs["video_in"], "analysis_out": {"face": {}}}


class DummyOptionalInput(BaseNode):
    name = "optional_consumer"

    def get_input_ports(self):
        return [
            InputPort("video_in", PortType.VIDEO_FRAME, required=True),
            InputPort("analysis_in", PortType.ANALYSIS_DATA, required=False),
        ]

    def get_output_ports(self):
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    def process(self, inputs):
        return {"video_out": inputs["video_in"]}


# --- PortType tests ---


class TestPortTypes:
    def test_port_type_values(self):
        assert PortType.VIDEO_FRAME is not None
        assert PortType.ANALYSIS_DATA is not None
        assert PortType.RENDER_FRAME is not None
        assert PortType.TRACKING_DATA is not None

    def test_input_port_accepts_matching_type(self):
        inp = InputPort("video_in", PortType.VIDEO_FRAME)
        out = OutputPort("video_out", PortType.VIDEO_FRAME)
        assert inp.accepts(out) is True

    def test_input_port_rejects_mismatched_type(self):
        inp = InputPort("video_in", PortType.VIDEO_FRAME)
        out = OutputPort("analysis_out", PortType.ANALYSIS_DATA)
        assert inp.accepts(out) is False

    def test_input_port_frozen(self):
        inp = InputPort("video_in", PortType.VIDEO_FRAME)
        with pytest.raises(AttributeError):
            inp.name = "other"

    def test_output_port_frozen(self):
        out = OutputPort("video_out", PortType.VIDEO_FRAME)
        with pytest.raises(AttributeError):
            out.name = "other"

    def test_optional_input_default(self):
        inp = InputPort("analysis_in", PortType.ANALYSIS_DATA, required=False, default_value={})
        assert inp.required is False
        assert inp.default_value == {}


# --- BaseNode tests ---


class TestBaseNode:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseNode()

    def test_concrete_node(self):
        node = DummyProducer()
        assert node.name == "producer"
        assert node.enabled is True
        assert len(node.get_input_ports()) == 0
        assert len(node.get_output_ports()) == 1

    def test_config_injection(self):
        node = DummyProducer()
        assert node.config is None
        node.config = {"fps": 30}
        assert node.config == {"fps": 30}

    def test_temporal_declarations_default(self):
        node = DummyProducer()
        assert node.required_input_history == 0
        assert node.needs_optical_flow is False
        assert node.needs_delta_frame is False
        assert node.needs_previous_output is False

    def test_get_port_by_name(self):
        node = DummyAnalysis()
        assert node.get_input_port("video_in") is not None
        assert node.get_input_port("nonexistent") is None
        assert node.get_output_port("analysis_out") is not None
        assert node.get_output_port("nonexistent") is None

    def test_lifecycle_methods_are_noop(self):
        node = DummyProducer()
        node.setup()
        node.teardown()
        node.reset()

    def test_repr(self):
        node = DummyProducer()
        assert "producer" in repr(node)


# --- Connection tests ---


class TestConnection:
    def test_valid_connection(self):
        src = DummyProducer()
        tgt = DummyConsumer()
        conn = Connection(src, "video_out", tgt, "video_in")
        assert conn.source_node is src
        assert conn.target_node is tgt

    def test_invalid_source_port(self):
        src = DummyProducer()
        tgt = DummyConsumer()
        with pytest.raises(ValueError, match="no output port"):
            Connection(src, "nonexistent", tgt, "video_in")

    def test_invalid_target_port(self):
        src = DummyProducer()
        tgt = DummyConsumer()
        with pytest.raises(ValueError, match="no input port"):
            Connection(src, "video_out", tgt, "nonexistent")

    def test_type_mismatch(self):
        src = DummyAnalysis()
        tgt = DummyConsumer()
        with pytest.raises(TypeError, match="Type mismatch"):
            Connection(src, "analysis_out", tgt, "video_in")

    def test_connection_frozen(self):
        src = DummyProducer()
        tgt = DummyConsumer()
        conn = Connection(src, "video_out", tgt, "video_in")
        with pytest.raises(AttributeError):
            conn.source_port = "other"


# --- Graph tests ---


class TestGraph:
    def test_add_node(self):
        g = Graph()
        g.add_node(DummyProducer())
        assert len(g) == 1

    def test_duplicate_name_raises(self):
        g = Graph()
        g.add_node(DummyProducer())
        with pytest.raises(ValueError, match="Duplicate"):
            g.add_node(DummyProducer())

    def test_connect(self):
        g = Graph()
        src = DummyProducer()
        tgt = DummyConsumer()
        g.add_node(src)
        g.add_node(tgt)
        conn = g.connect(src, "video_out", tgt, "video_in")
        assert conn in g.get_connections()

    def test_connect_node_not_in_graph(self):
        g = Graph()
        src = DummyProducer()
        tgt = DummyConsumer()
        g.add_node(src)
        with pytest.raises(ValueError, match="not in graph"):
            g.connect(src, "video_out", tgt, "video_in")

    def test_topological_sort_linear(self):
        g = Graph()
        src = DummyProducer()
        tgt = DummyConsumer()
        g.add_node(src)
        g.add_node(tgt)
        g.connect(src, "video_out", tgt, "video_in")
        order = g.get_execution_order()
        assert order == [src, tgt]

    def test_topological_sort_diamond(self):
        g = Graph()
        src = DummyProducer()
        analyzer = DummyAnalysis()
        processor = DummyOptionalInput()
        tgt = DummyConsumer()

        # Rename to avoid duplicates
        analyzer.name = "analyzer"
        processor.name = "processor"

        g.add_node(src)
        g.add_node(analyzer)
        g.add_node(processor)
        g.add_node(tgt)

        g.connect(src, "video_out", analyzer, "video_in")
        g.connect(analyzer, "video_out", processor, "video_in")
        g.connect(analyzer, "analysis_out", processor, "analysis_in")
        g.connect(processor, "video_out", tgt, "video_in")

        order = g.get_execution_order()
        assert order.index(src) < order.index(analyzer)
        assert order.index(analyzer) < order.index(processor)
        assert order.index(processor) < order.index(tgt)

    def test_cycle_detection(self):
        """Create a cycle: A -> B -> A."""

        class NodeA(BaseNode):
            name = "a"

            def get_input_ports(self):
                return [InputPort("in", PortType.VIDEO_FRAME, required=False)]

            def get_output_ports(self):
                return [OutputPort("out", PortType.VIDEO_FRAME)]

            def process(self, inputs):
                return {"out": None}

        class NodeB(BaseNode):
            name = "b"

            def get_input_ports(self):
                return [InputPort("in", PortType.VIDEO_FRAME)]

            def get_output_ports(self):
                return [OutputPort("out", PortType.VIDEO_FRAME)]

            def process(self, inputs):
                return {"out": None}

        g = Graph()
        a = NodeA()
        b = NodeB()
        g.add_node(a)
        g.add_node(b)
        g.connect(a, "out", b, "in")
        g.connect(b, "out", a, "in")

        errors = g.validate()
        assert any("cycle" in e.lower() for e in errors)

        with pytest.raises(ValueError, match="cycle"):
            g.get_execution_order()

    def test_validate_unconnected_required(self):
        g = Graph()
        tgt = DummyConsumer()
        g.add_node(tgt)
        errors = g.validate()
        assert any("video_in" in e for e in errors)

    def test_validate_optional_ok(self):
        g = Graph()
        src = DummyProducer()
        opt = DummyOptionalInput()
        g.add_node(src)
        g.add_node(opt)
        g.connect(src, "video_out", opt, "video_in")
        errors = g.validate()
        assert errors == []

    def test_get_connections_to_from(self):
        g = Graph()
        src = DummyProducer()
        tgt = DummyConsumer()
        g.add_node(src)
        g.add_node(tgt)
        g.connect(src, "video_out", tgt, "video_in")
        assert len(g.get_connections_to(tgt)) == 1
        assert len(g.get_connections_from(src)) == 1
        assert len(g.get_connections_to(src)) == 0

    def test_execution_order_cached(self):
        g = Graph()
        src = DummyProducer()
        tgt = DummyConsumer()
        g.add_node(src)
        g.add_node(tgt)
        g.connect(src, "video_out", tgt, "video_in")
        order1 = g.get_execution_order()
        order2 = g.get_execution_order()
        assert order1 == order2

    def test_get_node(self):
        g = Graph()
        src = DummyProducer()
        g.add_node(src)
        assert g.get_node("producer") is src
        assert g.get_node("nonexistent") is None

    def test_empty_graph(self):
        g = Graph()
        assert len(g) == 0
        assert g.get_execution_order() == []
        assert g.validate() == []
        assert g.get_nodes() == []
        assert g.get_connections() == []

    def test_single_node_no_connections(self):
        g = Graph()
        src = DummyProducer()
        g.add_node(src)
        order = g.get_execution_order()
        assert order == [src]

    def test_single_node_with_required_port(self):
        g = Graph()
        tgt = DummyConsumer()
        g.add_node(tgt)
        order = g.get_execution_order()
        assert order == [tgt]
        errors = g.validate()
        assert len(errors) == 1
        assert "video_in" in errors[0]

    def test_disconnected_subgraphs(self):
        """Two independent source->consumer pairs in one graph."""
        g = Graph()
        src1 = DummyProducer()
        src1.name = "src1"
        tgt1 = DummyConsumer()
        tgt1.name = "tgt1"
        src2 = DummyProducer()
        src2.name = "src2"
        tgt2 = DummyConsumer()
        tgt2.name = "tgt2"

        g.add_node(src1)
        g.add_node(tgt1)
        g.add_node(src2)
        g.add_node(tgt2)
        g.connect(src1, "video_out", tgt1, "video_in")
        g.connect(src2, "video_out", tgt2, "video_in")

        order = g.get_execution_order()
        assert len(order) == 4
        assert order.index(src1) < order.index(tgt1)
        assert order.index(src2) < order.index(tgt2)
        assert g.validate() == []

    def test_self_loop_detected(self):
        class SelfLoop(BaseNode):
            name = "self_loop"

            def get_input_ports(self):
                return [InputPort("in", PortType.VIDEO_FRAME, required=False)]

            def get_output_ports(self):
                return [OutputPort("out", PortType.VIDEO_FRAME)]

            def process(self, inputs):
                return {"out": None}

        g = Graph()
        node = SelfLoop()
        g.add_node(node)
        g.connect(node, "out", node, "in")
        errors = g.validate()
        assert any("cycle" in e.lower() for e in errors)

    def test_cache_invalidated_on_add_node(self):
        g = Graph()
        src = DummyProducer()
        g.add_node(src)
        order1 = g.get_execution_order()
        assert len(order1) == 1

        tgt = DummyConsumer()
        g.add_node(tgt)
        g.connect(src, "video_out", tgt, "video_in")
        order2 = g.get_execution_order()
        assert len(order2) == 2

    def test_repr(self):
        g = Graph()
        assert "nodes=0" in repr(g)
        g.add_node(DummyProducer())
        assert "nodes=1" in repr(g)
