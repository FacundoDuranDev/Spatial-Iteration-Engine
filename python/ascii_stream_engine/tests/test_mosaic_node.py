"""Tests for MosaicFilterNode — standalone graph node for pixelation."""

import numpy as np
import pytest

from ascii_stream_engine.application.graph.core.port_types import PortType
from ascii_stream_engine.application.graph.nodes.mosaic_node import MosaicFilterNode


@pytest.fixture
def gradient_frame():
    """Frame with a horizontal gradient — easy to detect pixelation."""
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    for x in range(200):
        frame[:, x, :] = int(x * 255 / 199)
    return frame


class TestMosaicFilterNodePorts:
    def test_input_ports(self):
        node = MosaicFilterNode()
        ports = node.get_input_ports()
        names = {p.name: p for p in ports}
        assert "video_in" in names
        assert "block_size" in names
        assert names["video_in"].required is True
        assert names["block_size"].required is False
        assert names["block_size"].data_type == PortType.CONTROL_SIGNAL

    def test_output_ports(self):
        node = MosaicFilterNode()
        ports = node.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "video_out"
        assert ports[0].data_type == PortType.VIDEO_FRAME


class TestMosaicPixelation:
    def test_basic_pixelation(self, gradient_frame):
        node = MosaicFilterNode(default_block_size=0.1)
        result = node.process({"video_in": gradient_frame})
        out = result["video_out"]
        assert out.shape == gradient_frame.shape
        assert out.dtype == np.uint8
        # Pixelated frame should have fewer unique values than the gradient
        unique_original = len(np.unique(gradient_frame[:, :, 0]))
        unique_mosaic = len(np.unique(out[:, :, 0]))
        assert unique_mosaic < unique_original

    def test_control_signal_block_size(self, gradient_frame):
        node = MosaicFilterNode(default_block_size=0.05)
        # Large block size = more pixelation = fewer unique values
        result_large = node.process({"video_in": gradient_frame, "block_size": 0.3})
        result_small = node.process({"video_in": gradient_frame, "block_size": 0.02})
        unique_large = len(np.unique(result_large["video_out"][:, :, 0]))
        unique_small = len(np.unique(result_small["video_out"][:, :, 0]))
        assert unique_large < unique_small

    def test_default_block_size(self, gradient_frame):
        node = MosaicFilterNode()  # default 0.05
        result = node.process({"video_in": gradient_frame})
        assert result["video_out"].shape == gradient_frame.shape

    def test_none_block_size_uses_default(self, gradient_frame):
        node = MosaicFilterNode(default_block_size=0.1)
        result = node.process({"video_in": gradient_frame, "block_size": None})
        assert result["video_out"].shape == gradient_frame.shape

    def test_block_size_clamped_low(self, gradient_frame):
        node = MosaicFilterNode()
        # Should clamp to 0.01, not crash
        result = node.process({"video_in": gradient_frame, "block_size": -1.0})
        assert result["video_out"].shape == gradient_frame.shape

    def test_block_size_clamped_high(self, gradient_frame):
        node = MosaicFilterNode()
        # Should clamp to 0.3, not crash
        result = node.process({"video_in": gradient_frame, "block_size": 10.0})
        assert result["video_out"].shape == gradient_frame.shape


class TestMosaicDifferentSizes:
    def test_small_frame(self):
        frame = np.random.randint(0, 256, (10, 10, 3), dtype=np.uint8)
        node = MosaicFilterNode(default_block_size=0.1)
        result = node.process({"video_in": frame})
        assert result["video_out"].shape == frame.shape

    def test_wide_frame(self):
        frame = np.random.randint(0, 256, (50, 500, 3), dtype=np.uint8)
        node = MosaicFilterNode(default_block_size=0.05)
        result = node.process({"video_in": frame})
        assert result["video_out"].shape == frame.shape

    def test_tall_frame(self):
        frame = np.random.randint(0, 256, (500, 50, 3), dtype=np.uint8)
        node = MosaicFilterNode(default_block_size=0.05)
        result = node.process({"video_in": frame})
        assert result["video_out"].shape == frame.shape
