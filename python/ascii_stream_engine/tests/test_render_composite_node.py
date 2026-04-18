"""Tests for RenderFrameCompositeNode — PIL-based RenderFrame composition."""

import pytest
from PIL import Image

from ascii_stream_engine.application.graph.core.port_types import PortType
from ascii_stream_engine.application.graph.nodes.render_composite_node import (
    RenderFrameCompositeNode,
)
from ascii_stream_engine.domain.types import RenderFrame


@pytest.fixture
def red_render_frame():
    img = Image.new("RGBA", (40, 30), (255, 0, 0, 255))
    return RenderFrame(image=img, text="red", lines=["line_r"], metadata={"source": "A"})


@pytest.fixture
def blue_render_frame():
    img = Image.new("RGBA", (40, 30), (0, 0, 255, 255))
    return RenderFrame(image=img, text="blue", lines=["line_b"], metadata={"overlay": "B"})


class TestRenderFrameCompositeNodePorts:
    def test_input_ports(self):
        node = RenderFrameCompositeNode()
        ports = node.get_input_ports()
        names = {p.name for p in ports}
        assert "render_in_a" in names
        assert "render_in_b" in names

    def test_output_ports(self):
        node = RenderFrameCompositeNode()
        ports = node.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "render_out"
        assert ports[0].data_type == PortType.RENDER_FRAME


class TestPILComposite:
    def test_full_opacity_composite(self, red_render_frame, blue_render_frame):
        node = RenderFrameCompositeNode(opacity=1.0)
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": blue_render_frame,
        })
        rf = result["render_out"]
        assert isinstance(rf, RenderFrame)
        # B at full opacity over A -> should be blue
        pixel = rf.image.getpixel((0, 0))
        assert pixel[2] == 255  # Blue channel
        assert pixel[0] == 0  # Red channel

    def test_half_opacity_composite(self, red_render_frame, blue_render_frame):
        node = RenderFrameCompositeNode(opacity=0.5)
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": blue_render_frame,
        })
        rf = result["render_out"]
        pixel = rf.image.getpixel((0, 0))
        # Should be a mix
        assert pixel[0] > 0  # Some red
        assert pixel[2] > 0  # Some blue


class TestTextMerge:
    def test_both_texts(self, red_render_frame, blue_render_frame):
        node = RenderFrameCompositeNode()
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": blue_render_frame,
        })
        rf = result["render_out"]
        assert "red" in rf.text
        assert "blue" in rf.text

    def test_one_text_none(self, red_render_frame):
        rf_b = RenderFrame(image=Image.new("RGBA", (40, 30), (0, 255, 0, 255)))
        node = RenderFrameCompositeNode()
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": rf_b,
        })
        rf = result["render_out"]
        assert rf.text == "red"


class TestLinesMerge:
    def test_lines_concatenated(self, red_render_frame, blue_render_frame):
        node = RenderFrameCompositeNode()
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": blue_render_frame,
        })
        rf = result["render_out"]
        assert rf.lines == ["line_r", "line_b"]


class TestMetadataMerge:
    def test_metadata_merged(self, red_render_frame, blue_render_frame):
        node = RenderFrameCompositeNode()
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": blue_render_frame,
        })
        rf = result["render_out"]
        assert rf.metadata["source"] == "A"
        assert rf.metadata["overlay"] == "B"


class TestSizeMismatch:
    def test_resize_b_to_match_a(self, red_render_frame):
        small_img = Image.new("RGBA", (20, 15), (0, 255, 0, 255))
        rf_b = RenderFrame(image=small_img)
        node = RenderFrameCompositeNode()
        result = node.process({
            "render_in_a": red_render_frame,
            "render_in_b": rf_b,
        })
        rf = result["render_out"]
        assert rf.image.size == red_render_frame.image.size
