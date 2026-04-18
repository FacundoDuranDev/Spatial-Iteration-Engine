"""Integration tests — SpatialMapNode in a graph with GraphScheduler."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.spatial import (
    FaceSpatialSource,
    HandsSpatialSource,
    ManualRegionSource,
)
from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.nodes.composite_node import CompositeNode
from ascii_stream_engine.application.graph.nodes.source_node import SourceNode
from ascii_stream_engine.application.graph.nodes.spatial_map_node import SpatialMapNode
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler


class DummySourceNode(SourceNode):
    """Minimal source node for testing."""

    name = "test_source"

    def read_frame(self):
        return np.full((60, 80, 3), 128, dtype=np.uint8)


class TestSpatialMapInGraph:
    def _build_graph(self, spatial_source=None):
        """Build: Source → SpatialMap → (mask/video)."""
        graph = Graph()
        source = DummySourceNode()
        spatial = SpatialMapNode(source=spatial_source)
        spatial.name = "spatial"

        graph.add_node(source)
        graph.add_node(spatial)
        graph.connect(source, "video_out", spatial, "video_in")
        return graph, source, spatial

    def test_spatial_in_graph_no_source(self):
        graph, source, spatial = self._build_graph()
        scheduler = GraphScheduler(graph, config=None)
        frame = np.full((60, 80, 3), 128, dtype=np.uint8)
        ok, err = scheduler.process_frame(frame)
        assert ok is True
        assert err is None

    def test_spatial_with_manual_source(self):
        manual = ManualRegionSource()
        manual.set_region(0.25, 0.25, 0.5, 0.5)
        graph, source, spatial = self._build_graph(manual)
        scheduler = GraphScheduler(graph, config=None)

        frame = np.full((60, 80, 3), 128, dtype=np.uint8)
        ok, err = scheduler.process_frame(frame)
        assert ok is True

        outputs = scheduler._outputs.get("spatial", {})
        mask = outputs.get("mask_out")
        assert mask is not None
        assert mask.shape == (60, 80)
        assert mask[30, 40] == 255  # center inside ROI

        ctrl = outputs.get("control_out")
        assert ctrl["detected"] is True
        assert ctrl["center_x"] == pytest.approx(0.5)

    def test_runtime_source_switch(self):
        manual = ManualRegionSource()
        manual.set_region(0.0, 0.0, 0.5, 0.5)
        graph, source, spatial = self._build_graph(manual)
        scheduler = GraphScheduler(graph, config=None)

        frame = np.full((60, 80, 3), 128, dtype=np.uint8)
        ok, _ = scheduler.process_frame(frame)
        assert ok
        assert scheduler._outputs["spatial"]["control_out"]["detected"] is True

        # Switch to face source (no face data → not detected)
        spatial.set_source(FaceSpatialSource())
        ok, _ = scheduler.process_frame(frame)
        assert ok
        assert scheduler._outputs["spatial"]["control_out"]["detected"] is False

        # Switch back to manual
        manual2 = ManualRegionSource()
        manual2.set_region(0.1, 0.1, 0.2, 0.2)
        spatial.set_source(manual2)
        ok, _ = scheduler.process_frame(frame)
        assert ok
        assert scheduler._outputs["spatial"]["control_out"]["detected"] is True


class TestSpatialMapWithComposite:
    def test_spatial_mask_to_composite(self):
        """SpatialMap.mask_out → CompositeNode.mask_in flow."""
        graph = Graph()
        source = DummySourceNode()
        manual = ManualRegionSource()
        manual.set_region(0.0, 0.0, 0.5, 0.5)  # left half
        spatial = SpatialMapNode(source=manual)
        spatial.name = "spatial"
        composite = CompositeNode(mode="mask")
        composite.name = "composite"

        graph.add_node(source)
        graph.add_node(spatial)
        graph.add_node(composite)

        # Source → spatial.video_in
        graph.connect(source, "video_out", spatial, "video_in")
        # spatial.video_out → composite.video_in_a (original frame)
        graph.connect(spatial, "video_out", composite, "video_in_a")
        # spatial.mask_out → composite.mask_in
        graph.connect(spatial, "mask_out", composite, "mask_in")

        # Create a white frame as B input — use source video_out again
        # We'll just connect source to composite B for simplicity
        graph.connect(source, "video_out", composite, "video_in_b")

        scheduler = GraphScheduler(graph, config=None)
        frame = np.full((60, 80, 3), 100, dtype=np.uint8)
        ok, err = scheduler.process_frame(frame)
        assert ok is True
        assert err is None

        composite_out = scheduler._outputs.get("composite", {}).get("video_out")
        assert composite_out is not None
        assert composite_out.shape == frame.shape
