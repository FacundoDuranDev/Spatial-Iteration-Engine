"""Integration tests for graph branching: fan-out, composition, and GraphBuilder API."""

import numpy as np
import pytest
from PIL import Image

from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
from ascii_stream_engine.application.graph.core.base_node import BaseNode
from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.core.port_types import (
    InputPort,
    OutputPort,
    PortType,
)
from ascii_stream_engine.application.graph.nodes.composite_node import CompositeNode
from ascii_stream_engine.application.graph.nodes.mosaic_node import MosaicFilterNode
from ascii_stream_engine.application.graph.nodes.render_composite_node import (
    RenderFrameCompositeNode,
)
from ascii_stream_engine.application.graph.nodes.renderer_node import RendererNode
from ascii_stream_engine.application.graph.nodes.source_node import SourceNode
from ascii_stream_engine.application.graph.nodes.output_node import OutputNode
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


# --- Test helpers ---


class _TestSource(SourceNode):
    name = "test_source"

    def read_frame(self):
        return None


class _SimpleRenderer(RendererNode):
    def __init__(self, renderer_name: str = "renderer") -> None:
        super().__init__()
        self.name = renderer_name

    def render(self, frame, config, analysis):
        h, w = frame.shape[:2]
        img = Image.fromarray(frame[:, :, ::-1]).convert("RGBA")
        return RenderFrame(
            image=img,
            text=f"{self.name}_text",
            lines=[f"{self.name}_line"],
            metadata={self.name: True},
        )


class _TestOutput(OutputNode):
    name = "test_output"

    def __init__(self):
        super().__init__()
        self.last_render = None

    def write(self, rendered):
        self.last_render = rendered


# --- Integration tests ---


class TestFullBranchingPipeline:
    def test_source_fanout_mosaic_renderer_composite_output(self):
        """Source -> fan-out -> [Mosaic->Renderer_A, Renderer_B] -> RenderComposite -> Output"""
        g = Graph()

        # Nodes
        src = _TestSource()
        mosaic = MosaicFilterNode(default_block_size=0.1)
        mosaic.name = "mosaic"
        renderer_a = _SimpleRenderer("renderer_a")
        renderer_b = _SimpleRenderer("renderer_b")
        composite = RenderFrameCompositeNode(opacity=0.5)
        output = _TestOutput()

        # Add all nodes
        for node in [src, mosaic, renderer_a, renderer_b, composite, output]:
            g.add_node(node)

        # Source -> mosaic -> renderer_a (branch A)
        g.connect(src, "video_out", mosaic, "video_in")
        g.connect(mosaic, "video_out", renderer_a, "video_in")

        # Source -> renderer_b (branch B, raw video)
        g.connect(src, "video_out", renderer_b, "video_in")

        # Both renderers -> composite
        g.connect(renderer_a, "render_out", composite, "render_in_a")
        g.connect(renderer_b, "render_out", composite, "render_in_b")

        # Composite -> output
        g.connect(composite, "render_out", output, "render_in")

        # Execute
        config = EngineConfig()
        scheduler = GraphScheduler(graph=g, config=config)

        frame = np.random.randint(0, 256, (60, 80, 3), dtype=np.uint8)
        success, error = scheduler.process_frame(frame)

        assert success, f"Pipeline failed: {error}"
        assert output.last_render is not None
        assert isinstance(output.last_render, RenderFrame)
        assert output.last_render.image is not None
        # Text should be merged
        assert "renderer_a_text" in output.last_render.text
        assert "renderer_b_text" in output.last_render.text
        # Lines should be concatenated
        assert "renderer_a_line" in output.last_render.lines
        assert "renderer_b_line" in output.last_render.lines
        # Metadata from both
        assert output.last_render.metadata.get("renderer_a") is True
        assert output.last_render.metadata.get("renderer_b") is True


class TestGraphBuilderAddBranch:
    def test_add_branch(self):
        g = Graph()
        src = _TestSource()
        mosaic_a = MosaicFilterNode(default_block_size=0.05)
        mosaic_a.name = "mosaic_a"
        mosaic_b = MosaicFilterNode(default_block_size=0.1)
        mosaic_b.name = "mosaic_b"

        g.add_node(src)
        g.add_node(mosaic_a)
        g.add_node(mosaic_b)

        GraphBuilder.add_branch(g, src, "video_out", mosaic_a, mosaic_b)

        # Both should be connected
        conns_a = g.get_connections_to(mosaic_a)
        conns_b = g.get_connections_to(mosaic_b)
        assert len(conns_a) == 1
        assert conns_a[0].source_node is src
        assert len(conns_b) == 1
        assert conns_b[0].source_node is src


class TestGraphBuilderAddComposite:
    def test_add_composite(self):
        g = Graph()
        src = _TestSource()
        renderer_a = _SimpleRenderer("renderer_a")
        renderer_b = _SimpleRenderer("renderer_b")
        composite = RenderFrameCompositeNode()

        g.add_node(src)
        g.add_node(renderer_a)
        g.add_node(renderer_b)
        g.add_node(composite)

        g.connect(src, "video_out", renderer_a, "video_in")
        g.connect(src, "video_out", renderer_b, "video_in")

        GraphBuilder.add_composite(
            g, renderer_a, "render_out", renderer_b, "render_out", composite
        )

        conns = g.get_connections_to(composite)
        assert len(conns) == 2
        sources = {c.source_node.name for c in conns}
        assert "renderer_a" in sources
        assert "renderer_b" in sources


class TestGraphBuilderFanOut:
    def test_fan_out(self):
        g = Graph()
        src = _TestSource()
        mosaic_a = MosaicFilterNode(default_block_size=0.05)
        mosaic_a.name = "mosaic_a"
        mosaic_b = MosaicFilterNode(default_block_size=0.1)
        mosaic_b.name = "mosaic_b"

        g.add_node(src)
        g.add_node(mosaic_a)
        g.add_node(mosaic_b)

        GraphBuilder.fan_out(g, src, "video_out", [
            (mosaic_a, "video_in"),
            (mosaic_b, "video_in"),
        ])

        conns = g.get_connections_from(src)
        assert len(conns) == 2


class TestVideoCompositeInGraph:
    def test_video_composite_with_scheduler(self):
        """Source -> fan-out -> [Mosaic_A, Mosaic_B] -> CompositeNode -> Output-as-renderer."""
        g = Graph()
        src = _TestSource()
        mosaic_a = MosaicFilterNode(default_block_size=0.05)
        mosaic_a.name = "mosaic_a"
        mosaic_b = MosaicFilterNode(default_block_size=0.2)
        mosaic_b.name = "mosaic_b"
        composite = CompositeNode(mode="alpha", opacity=0.5)
        renderer = _SimpleRenderer("renderer")
        output = _TestOutput()

        for node in [src, mosaic_a, mosaic_b, composite, renderer, output]:
            g.add_node(node)

        g.connect(src, "video_out", mosaic_a, "video_in")
        g.connect(src, "video_out", mosaic_b, "video_in")
        g.connect(mosaic_a, "video_out", composite, "video_in_a")
        g.connect(mosaic_b, "video_out", composite, "video_in_b")
        g.connect(composite, "video_out", renderer, "video_in")
        g.connect(renderer, "render_out", output, "render_in")

        scheduler = GraphScheduler(graph=g, config=EngineConfig())
        frame = np.random.randint(0, 256, (40, 60, 3), dtype=np.uint8)
        success, error = scheduler.process_frame(frame)

        assert success, f"Pipeline failed: {error}"
        assert output.last_render is not None
