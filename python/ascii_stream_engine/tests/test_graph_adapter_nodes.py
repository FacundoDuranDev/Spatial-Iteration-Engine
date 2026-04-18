"""Tests for adapter-backed node implementations."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.adapter_nodes.filter_nodes import (
    FILTER_NODE_CLASSES,
    _make_filter_node,
)
from ascii_stream_engine.application.graph.adapter_nodes.analyzer_nodes import ANALYZER_NODE_CLASSES
from ascii_stream_engine.application.graph.adapter_nodes.renderer_nodes import RENDERER_NODE_CLASSES
from ascii_stream_engine.application.graph.adapter_nodes.source_nodes import SOURCE_NODE_CLASSES
from ascii_stream_engine.application.graph.adapter_nodes.output_nodes import OUTPUT_NODE_CLASSES
from ascii_stream_engine.application.graph.adapter_nodes.tracker_nodes import TRACKER_NODE_CLASSES
from ascii_stream_engine.application.graph.adapter_nodes.transform_nodes import TRANSFORM_NODE_CLASSES
from ascii_stream_engine.application.graph.bridge.adapter_registry import (
    get_node_class,
    get_node_for_adapter,
    get_all_mappings,
)
from ascii_stream_engine.application.graph.nodes.processor_node import ProcessorNode
from ascii_stream_engine.adapters.processors.filters import BrightnessFilter, InvertFilter


class TestFilterNodeFactory:
    def test_make_filter_node_creates_processor_node(self):
        NodeCls = _make_filter_node(BrightnessFilter)
        assert issubclass(NodeCls, ProcessorNode)
        assert NodeCls.__name__ == "BrightnessFilterNode"

    def test_filter_node_copies_temporal_declarations(self):
        NodeCls = _make_filter_node(BrightnessFilter)
        # BrightnessFilter has default temporal declarations (all False/0)
        assert NodeCls.required_input_history == 0
        assert NodeCls.needs_optical_flow is False

    def test_filter_node_process(self):
        NodeCls = _make_filter_node(BrightnessFilter)
        node = NodeCls()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        from ascii_stream_engine.domain.config import EngineConfig

        node.config = EngineConfig()
        result = node.process({"video_in": frame})
        assert "video_out" in result
        assert result["video_out"].shape == frame.shape

    def test_filter_node_has_adapter(self):
        NodeCls = _make_filter_node(InvertFilter)
        node = NodeCls()
        assert isinstance(node.adapter, InvertFilter)


class TestFilterNodeDiscovery:
    def test_at_least_13_python_filters(self):
        """We have 13 pure-Python filters + up to 6 C++ filters."""
        assert len(FILTER_NODE_CLASSES) >= 13

    def test_brightness_filter_present(self):
        assert "BrightnessFilter" in FILTER_NODE_CLASSES

    def test_invert_filter_present(self):
        assert "InvertFilter" in FILTER_NODE_CLASSES


class TestAnalyzerNodeDiscovery:
    def test_analyzers_discovered(self):
        # May be 0 if perception deps missing, but structure should work
        assert isinstance(ANALYZER_NODE_CLASSES, dict)


class TestRendererNodeDiscovery:
    def test_renderers_discovered(self):
        assert isinstance(RENDERER_NODE_CLASSES, dict)
        assert len(RENDERER_NODE_CLASSES) >= 2  # At least Ascii + Passthrough


class TestSourceNodeDiscovery:
    def test_sources_discovered(self):
        assert isinstance(SOURCE_NODE_CLASSES, dict)


class TestOutputNodeDiscovery:
    def test_outputs_discovered(self):
        assert isinstance(OUTPUT_NODE_CLASSES, dict)


class TestTrackerNodeDiscovery:
    def test_trackers_discovered(self):
        assert isinstance(TRACKER_NODE_CLASSES, dict)


class TestTransformNodeDiscovery:
    def test_transforms_discovered(self):
        assert isinstance(TRANSFORM_NODE_CLASSES, dict)


class TestAdapterRegistry:
    def test_get_node_class_by_name(self):
        node_cls = get_node_class("BrightnessFilter")
        assert node_cls is not None
        assert issubclass(node_cls, ProcessorNode)

    def test_get_node_class_unknown(self):
        assert get_node_class("NonexistentFilter") is None

    def test_get_node_for_adapter_instance(self):
        adapter = BrightnessFilter()
        node_cls = get_node_for_adapter(adapter)
        assert node_cls is not None

    def test_get_all_mappings(self):
        mappings = get_all_mappings()
        assert isinstance(mappings, dict)
        assert len(mappings) > 0
