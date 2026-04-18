"""Tests for SpatialMapNode — mask generation, control signals, video passthrough."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.spatial import (
    FaceSpatialSource,
    HandsSpatialSource,
    ManualRegionSource,
)
from ascii_stream_engine.application.graph.core.port_types import PortType
from ascii_stream_engine.application.graph.nodes.spatial_map_node import SpatialMapNode
from ascii_stream_engine.domain.types import ROI


@pytest.fixture
def frame():
    return np.full((100, 200, 3), 128, dtype=np.uint8)


@pytest.fixture
def manual_source():
    src = ManualRegionSource()
    src.set_region(0.25, 0.25, 0.5, 0.5)
    return src


class TestSpatialMapNodePorts:
    def test_input_ports(self):
        node = SpatialMapNode()
        ports = {p.name: p for p in node.get_input_ports()}
        assert "video_in" in ports
        assert "analysis_in" in ports
        assert "region_in" in ports
        assert ports["video_in"].data_type == PortType.VIDEO_FRAME
        assert ports["analysis_in"].data_type == PortType.ANALYSIS_DATA
        assert ports["region_in"].required is False

    def test_output_ports(self):
        node = SpatialMapNode()
        ports = {p.name: p for p in node.get_output_ports()}
        assert "video_out" in ports
        assert "mask_out" in ports
        assert "control_out" in ports
        assert "roi_video_out" in ports
        assert ports["mask_out"].data_type == PortType.MASK
        assert ports["control_out"].data_type == PortType.CONTROL_SIGNAL


class TestSpatialMapNodeMask:
    def test_mask_shape(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source)
        result = node.process({"video_in": frame, "analysis_in": {}})
        mask = result["mask_out"]
        assert mask.shape == (100, 200)
        assert mask.dtype == np.uint8

    def test_mask_roi_region(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source)
        result = node.process({"video_in": frame, "analysis_in": {}})
        mask = result["mask_out"]
        # ROI covers center quarter
        assert mask[50, 100] == 255  # inside ROI
        assert mask[0, 0] == 0  # outside ROI

    def test_mask_no_source(self, frame):
        node = SpatialMapNode()
        result = node.process({"video_in": frame, "analysis_in": {}})
        mask = result["mask_out"]
        assert mask.sum() == 0  # all black

    def test_mask_blur(self, frame, manual_source):
        node_no_blur = SpatialMapNode(source=manual_source, blur_mask=False)
        node_blur = SpatialMapNode(source=manual_source, blur_mask=True, blur_radius=21)
        r1 = node_no_blur.process({"video_in": frame, "analysis_in": {}})
        r2 = node_blur.process({"video_in": frame, "analysis_in": {}})
        # Blurred mask has intermediate values at edges
        unique_no_blur = np.unique(r1["mask_out"])
        unique_blur = np.unique(r2["mask_out"])
        assert len(unique_blur) > len(unique_no_blur)


class TestSpatialMapNodeControl:
    def test_control_detected(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source)
        result = node.process({"video_in": frame, "analysis_in": {}})
        ctrl = result["control_out"]
        assert ctrl["detected"] is True
        assert ctrl["center_x"] == pytest.approx(0.5)
        assert ctrl["center_y"] == pytest.approx(0.5)
        assert ctrl["width"] == pytest.approx(0.5)
        assert ctrl["height"] == pytest.approx(0.5)
        assert ctrl["area"] == pytest.approx(0.25)
        assert ctrl["confidence"] == pytest.approx(1.0)

    def test_control_not_detected(self, frame):
        node = SpatialMapNode()
        result = node.process({"video_in": frame, "analysis_in": {}})
        ctrl = result["control_out"]
        assert ctrl["detected"] is False
        assert ctrl["area"] == pytest.approx(0.0)
        assert ctrl["confidence"] == pytest.approx(0.0)


class TestSpatialMapNodeVideo:
    def test_video_passthrough(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source)
        result = node.process({"video_in": frame, "analysis_in": {}})
        np.testing.assert_array_equal(result["video_out"], frame)

    def test_crop_disabled(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source, produce_crop=False)
        result = node.process({"video_in": frame, "analysis_in": {}})
        # Without crop, roi_video_out is passthrough
        np.testing.assert_array_equal(result["roi_video_out"], frame)

    def test_crop_enabled(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source, produce_crop=True)
        result = node.process({"video_in": frame, "analysis_in": {}})
        crop = result["roi_video_out"]
        # Crop is resized back to original dimensions
        assert crop.shape == frame.shape


class TestSpatialMapNodeSetSource:
    def test_set_source_runtime(self, frame):
        node = SpatialMapNode()
        result1 = node.process({"video_in": frame, "analysis_in": {}})
        assert result1["control_out"]["detected"] is False

        manual = ManualRegionSource()
        manual.set_region(0.1, 0.1, 0.3, 0.3)
        node.set_source(manual)
        result2 = node.process({"video_in": frame, "analysis_in": {}})
        assert result2["control_out"]["detected"] is True

    def test_source_property(self):
        src = ManualRegionSource()
        node = SpatialMapNode(source=src)
        assert node.source is src


class TestSpatialMapNodeRegionOverride:
    def test_region_in_override(self, frame, manual_source):
        node = SpatialMapNode(source=manual_source)
        override = {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}
        result = node.process({"video_in": frame, "analysis_in": {}, "region_in": override})
        ctrl = result["control_out"]
        assert ctrl["detected"] is True
        assert ctrl["width"] == pytest.approx(0.1)

    def test_invalid_region_override_ignored(self, frame):
        node = SpatialMapNode()
        override = {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
        result = node.process({"video_in": frame, "analysis_in": {}, "region_in": override})
        assert result["control_out"]["detected"] is False


class TestSpatialMapNodeROIIndex:
    def test_roi_index(self, frame):
        source = FaceSpatialSource()
        node = SpatialMapNode(source=source, roi_index=1)
        data = {"face": {"faces": [
            {"bbox": [0.0, 0.0, 0.2, 0.2], "confidence": 0.9},
            {"bbox": [0.5, 0.5, 0.3, 0.3], "confidence": 0.8},
        ]}}
        result = node.process({"video_in": frame, "analysis_in": data})
        ctrl = result["control_out"]
        assert ctrl["detected"] is True
        assert ctrl["center_x"] == pytest.approx(0.65)

    def test_roi_index_out_of_range(self, frame):
        source = FaceSpatialSource()
        node = SpatialMapNode(source=source, roi_index=5)
        data = {"face": {"faces": [{"bbox": [0.1, 0.1, 0.2, 0.2], "confidence": 0.9}]}}
        result = node.process({"video_in": frame, "analysis_in": data})
        assert result["control_out"]["detected"] is False
