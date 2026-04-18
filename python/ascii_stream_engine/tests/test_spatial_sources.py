"""Tests for spatial source adapters."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.spatial import (
    CompoundSpatialSource,
    FaceSpatialSource,
    HandsSpatialSource,
    ManualRegionSource,
    ObjectSpatialSource,
    PoseSpatialSource,
)
from ascii_stream_engine.domain.types import ROI


# --- FaceSpatialSource ---

class TestFaceSpatialSource:
    def test_extract_single_face(self):
        source = FaceSpatialSource()
        data = {"face": {"faces": [{"bbox": [0.1, 0.2, 0.3, 0.4], "confidence": 0.9}]}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].x == pytest.approx(0.1)
        assert rois[0].w == pytest.approx(0.3)
        assert rois[0].confidence == pytest.approx(0.9)
        assert rois[0].label == "face"

    def test_extract_multiple_faces(self):
        source = FaceSpatialSource()
        data = {"face": {"faces": [
            {"bbox": [0.1, 0.1, 0.2, 0.2], "confidence": 0.95},
            {"bbox": [0.5, 0.5, 0.3, 0.3], "confidence": 0.8},
        ]}}
        assert len(source.extract(data)) == 2

    def test_min_confidence_filter(self):
        source = FaceSpatialSource(min_confidence=0.8)
        data = {"face": {"faces": [
            {"bbox": [0.1, 0.1, 0.2, 0.2], "confidence": 0.9},
            {"bbox": [0.5, 0.5, 0.3, 0.3], "confidence": 0.5},
        ]}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].confidence == pytest.approx(0.9)

    def test_empty_data(self):
        source = FaceSpatialSource()
        assert source.extract({}) == []
        assert source.extract({"face": {}}) == []
        assert source.extract({"face": {"faces": []}}) == []

    def test_missing_bbox(self):
        source = FaceSpatialSource()
        data = {"face": {"faces": [{"confidence": 0.9}]}}
        assert source.extract(data) == []


# --- HandsSpatialSource ---

class TestHandsSpatialSource:
    def _hand_landmarks(self, offset_x=0.3, offset_y=0.3):
        pts = np.zeros((21, 2), dtype=np.float32)
        pts[:, 0] = np.linspace(offset_x, offset_x + 0.2, 21)
        pts[:, 1] = np.linspace(offset_y, offset_y + 0.15, 21)
        return pts

    def test_extract_both_hands(self):
        source = HandsSpatialSource(hands="both", padding=0.0)
        data = {"hands": {
            "left": self._hand_landmarks(0.1, 0.1),
            "right": self._hand_landmarks(0.5, 0.5),
        }}
        rois = source.extract(data)
        assert len(rois) == 2

    def test_extract_left_only(self):
        source = HandsSpatialSource(hands="left", padding=0.0)
        data = {"hands": {"left": self._hand_landmarks(), "right": self._hand_landmarks(0.6, 0.6)}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].label == "hand_left"

    def test_extract_right_only(self):
        source = HandsSpatialSource(hands="right", padding=0.0)
        data = {"hands": {"left": self._hand_landmarks(), "right": self._hand_landmarks(0.6, 0.6)}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].label == "hand_right"

    def test_padding(self):
        source_no_pad = HandsSpatialSource(hands="left", padding=0.0)
        source_pad = HandsSpatialSource(hands="left", padding=0.1)
        data = {"hands": {"left": self._hand_landmarks(0.3, 0.3)}}
        roi_np = source_no_pad.extract(data)[0]
        roi_p = source_pad.extract(data)[0]
        assert roi_p.x < roi_np.x
        assert roi_p.w > roi_np.w

    def test_empty_data(self):
        source = HandsSpatialSource()
        assert source.extract({}) == []
        assert source.extract({"hands": {}}) == []

    def test_zero_landmarks_skipped(self):
        source = HandsSpatialSource(hands="left")
        data = {"hands": {"left": np.zeros((21, 2), dtype=np.float32)}}
        assert source.extract(data) == []

    def test_invalid_hands_param(self):
        with pytest.raises(ValueError):
            HandsSpatialSource(hands="middle")

    def test_landmarks_in_roi(self):
        source = HandsSpatialSource(hands="left", padding=0.0)
        lm = self._hand_landmarks(0.3, 0.3)
        data = {"hands": {"left": lm}}
        rois = source.extract(data)
        assert rois[0].landmarks is not None
        assert rois[0].landmarks.shape == (21, 2)


# --- PoseSpatialSource ---

class TestPoseSpatialSource:
    def test_extract_pose(self):
        source = PoseSpatialSource(padding=0.0)
        joints = np.array([
            [0.2, 0.3], [0.4, 0.5], [0.6, 0.7],
        ], dtype=np.float32)
        data = {"pose": {"joints": joints}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].x == pytest.approx(0.2)
        assert rois[0].y == pytest.approx(0.3)
        assert rois[0].w == pytest.approx(0.4)
        assert rois[0].h == pytest.approx(0.4)

    def test_joint_subset(self):
        source = PoseSpatialSource(padding=0.0, joint_subset=[0, 1])
        joints = np.array([
            [0.2, 0.3], [0.4, 0.5], [0.8, 0.9],
        ], dtype=np.float32)
        data = {"pose": {"joints": joints}}
        rois = source.extract(data)
        assert len(rois) == 1
        # Only uses joints 0,1 → bbox (0.2,0.3)→(0.4,0.5)
        assert rois[0].x == pytest.approx(0.2)
        assert rois[0].w == pytest.approx(0.2)

    def test_empty_data(self):
        source = PoseSpatialSource()
        assert source.extract({}) == []
        assert source.extract({"pose": {}}) == []

    def test_all_zero_joints(self):
        source = PoseSpatialSource()
        data = {"pose": {"joints": np.zeros((17, 2), dtype=np.float32)}}
        assert source.extract(data) == []


# --- ObjectSpatialSource ---

class TestObjectSpatialSource:
    def test_extract_detections(self):
        source = ObjectSpatialSource()
        data = {"objects": {"detections": [
            {"bbox": [0.1, 0.2, 0.5, 0.6], "confidence": 0.9, "class_name": "person"},
        ]}}
        rois = source.extract(data)
        assert len(rois) == 1
        # x1,y1,x2,y2 → x,y,w,h
        assert rois[0].x == pytest.approx(0.1)
        assert rois[0].y == pytest.approx(0.2)
        assert rois[0].w == pytest.approx(0.4)
        assert rois[0].h == pytest.approx(0.4)
        assert rois[0].label == "person"

    def test_class_filter(self):
        source = ObjectSpatialSource(class_filter={"cat"})
        data = {"objects": {"detections": [
            {"bbox": [0.1, 0.1, 0.3, 0.3], "confidence": 0.9, "class_name": "person"},
            {"bbox": [0.5, 0.5, 0.7, 0.7], "confidence": 0.8, "class_name": "cat"},
        ]}}
        rois = source.extract(data)
        assert len(rois) == 1
        assert rois[0].label == "cat"

    def test_min_confidence(self):
        source = ObjectSpatialSource(min_confidence=0.7)
        data = {"objects": {"detections": [
            {"bbox": [0.1, 0.1, 0.3, 0.3], "confidence": 0.5, "class_name": "dog"},
        ]}}
        assert source.extract(data) == []

    def test_empty_data(self):
        source = ObjectSpatialSource()
        assert source.extract({}) == []


# --- ManualRegionSource ---

class TestManualRegionSource:
    def test_set_region(self):
        source = ManualRegionSource()
        source.set_region(0.1, 0.2, 0.3, 0.4, label="custom")
        rois = source.extract({})
        assert len(rois) == 1
        assert rois[0].x == pytest.approx(0.1)
        assert rois[0].label == "custom"

    def test_set_regions(self):
        source = ManualRegionSource()
        source.set_regions([
            ROI(x=0.0, y=0.0, w=0.5, h=0.5),
            ROI(x=0.5, y=0.5, w=0.5, h=0.5),
        ])
        assert len(source.extract({})) == 2

    def test_clear(self):
        source = ManualRegionSource()
        source.set_region(0.1, 0.2, 0.3, 0.4)
        source.clear()
        assert source.extract({}) == []

    def test_ignores_analysis_data(self):
        source = ManualRegionSource()
        source.set_region(0.1, 0.2, 0.3, 0.4)
        rois = source.extract({"face": {"faces": [{"bbox": [0, 0, 1, 1]}]}})
        assert len(rois) == 1
        assert rois[0].x == pytest.approx(0.1)


# --- CompoundSpatialSource ---

class TestCompoundSpatialSource:
    def test_combines_sources(self):
        compound = CompoundSpatialSource()
        m1 = ManualRegionSource()
        m1.set_region(0.0, 0.0, 0.5, 0.5)
        m2 = ManualRegionSource()
        m2.set_region(0.5, 0.5, 0.5, 0.5)
        compound.add_source(m1)
        compound.add_source(m2)
        rois = compound.extract({})
        assert len(rois) == 2

    def test_remove_source(self):
        compound = CompoundSpatialSource()
        m1 = ManualRegionSource()
        m1.set_region(0.0, 0.0, 0.5, 0.5)
        compound.add_source(m1)
        assert len(compound.extract({})) == 1
        compound.remove_source(m1)
        assert len(compound.extract({})) == 0

    def test_empty_compound(self):
        compound = CompoundSpatialSource()
        assert compound.extract({}) == []
