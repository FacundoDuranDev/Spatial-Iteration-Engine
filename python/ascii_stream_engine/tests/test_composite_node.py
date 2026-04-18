"""Tests for CompositeNode — video frame blending with multiple modes."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.core.port_types import PortType
from ascii_stream_engine.application.graph.nodes.composite_node import CompositeNode


@pytest.fixture
def white_frame():
    return np.full((20, 30, 3), 255, dtype=np.uint8)


@pytest.fixture
def black_frame():
    return np.zeros((20, 30, 3), dtype=np.uint8)


@pytest.fixture
def gray_frame():
    return np.full((20, 30, 3), 128, dtype=np.uint8)


class TestCompositeNodePorts:
    def test_input_ports(self):
        node = CompositeNode()
        ports = node.get_input_ports()
        names = {p.name: p for p in ports}
        assert "video_in_a" in names
        assert "video_in_b" in names
        assert "mask_in" in names
        assert "opacity" in names
        assert names["video_in_a"].required is True
        assert names["video_in_b"].required is True
        assert names["mask_in"].required is False
        assert names["opacity"].required is False

    def test_output_ports(self):
        node = CompositeNode()
        ports = node.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "video_out"
        assert ports[0].data_type == PortType.VIDEO_FRAME


class TestCompositeNodeBlendModes:
    def test_alpha_blend(self, white_frame, black_frame):
        node = CompositeNode(mode="alpha", opacity=0.5)
        result = node.process({"video_in_a": black_frame, "video_in_b": white_frame})
        out = result["video_out"]
        assert out.shape == black_frame.shape
        # 50% blend of 0 and 255 should be ~127-128
        assert 126 <= out.mean() <= 129

    def test_alpha_full_opacity(self, white_frame, black_frame):
        node = CompositeNode(mode="alpha", opacity=1.0)
        result = node.process({"video_in_a": black_frame, "video_in_b": white_frame})
        np.testing.assert_array_equal(result["video_out"], white_frame)

    def test_alpha_zero_opacity(self, white_frame, black_frame):
        node = CompositeNode(mode="alpha", opacity=0.0)
        result = node.process({"video_in_a": black_frame, "video_in_b": white_frame})
        np.testing.assert_array_equal(result["video_out"], black_frame)

    def test_additive_blend(self, gray_frame, black_frame):
        node = CompositeNode(mode="additive", opacity=1.0)
        result = node.process({"video_in_a": gray_frame, "video_in_b": gray_frame})
        out = result["video_out"]
        # 128 + 128 = 256, clamped to 255
        assert out.mean() == 255

    def test_multiply_blend(self, white_frame, gray_frame):
        node = CompositeNode(mode="multiply", opacity=1.0)
        result = node.process({"video_in_a": white_frame, "video_in_b": gray_frame})
        out = result["video_out"]
        # white * (gray/255) = gray
        assert 127 <= out.mean() <= 129

    def test_screen_blend(self, black_frame, gray_frame):
        node = CompositeNode(mode="screen", opacity=1.0)
        result = node.process({"video_in_a": black_frame, "video_in_b": gray_frame})
        out = result["video_out"]
        # screen(0, 128) = 255 - (255-0)*(255-128)/255 = 255 - 127 = 128
        assert 127 <= out.mean() <= 129

    def test_overlay_blend(self, gray_frame):
        node = CompositeNode(mode="overlay", opacity=1.0)
        result = node.process({"video_in_a": gray_frame, "video_in_b": gray_frame})
        out = result["video_out"]
        assert out.dtype == np.uint8
        assert out.shape == gray_frame.shape


class TestCompositeNodeOpacity:
    def test_opacity_from_input(self, white_frame, black_frame):
        node = CompositeNode(mode="alpha")
        result = node.process({
            "video_in_a": black_frame,
            "video_in_b": white_frame,
            "opacity": 0.5,
        })
        assert 126 <= result["video_out"].mean() <= 129

    def test_opacity_clamped(self, white_frame, black_frame):
        node = CompositeNode(mode="alpha")
        result = node.process({
            "video_in_a": black_frame,
            "video_in_b": white_frame,
            "opacity": 2.0,  # should clamp to 1.0
        })
        np.testing.assert_array_equal(result["video_out"], white_frame)


class TestCompositeNodeShapeMismatch:
    def test_resize_b_to_match_a(self, white_frame):
        small_b = np.full((10, 15, 3), 128, dtype=np.uint8)
        node = CompositeNode(mode="alpha", opacity=1.0)
        result = node.process({"video_in_a": white_frame, "video_in_b": small_b})
        assert result["video_out"].shape == white_frame.shape


class TestCompositeNodeMask:
    def test_mask_blend(self, white_frame, black_frame):
        # Left half white mask, right half black
        mask = np.zeros((20, 30), dtype=np.uint8)
        mask[:, 15:] = 255
        node = CompositeNode(mode="mask")
        result = node.process({
            "video_in_a": black_frame,
            "video_in_b": white_frame,
            "mask_in": mask,
        })
        out = result["video_out"]
        # Left half should be black (from A), right half white (from B)
        assert out[:, :15, :].mean() < 5
        assert out[:, 15:, :].mean() > 250


class TestCompositeNodeErrors:
    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="Unknown blend mode"):
            CompositeNode(mode="invalid")
