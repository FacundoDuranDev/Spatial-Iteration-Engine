"""Tests for ROI dataclass — center, area, to_pixel_rect, clamping, defaults."""

import numpy as np
import pytest

from ascii_stream_engine.domain.types import ROI


class TestROIProperties:
    def test_center(self):
        roi = ROI(x=0.2, y=0.3, w=0.4, h=0.2)
        cx, cy = roi.center
        assert cx == pytest.approx(0.4)
        assert cy == pytest.approx(0.4)

    def test_center_origin(self):
        roi = ROI(x=0.0, y=0.0, w=1.0, h=1.0)
        cx, cy = roi.center
        assert cx == pytest.approx(0.5)
        assert cy == pytest.approx(0.5)

    def test_area(self):
        roi = ROI(x=0.0, y=0.0, w=0.5, h=0.5)
        assert roi.area == pytest.approx(0.25)

    def test_area_zero(self):
        roi = ROI(x=0.5, y=0.5, w=0.0, h=0.0)
        assert roi.area == pytest.approx(0.0)


class TestROIPixelRect:
    def test_basic_conversion(self):
        roi = ROI(x=0.25, y=0.25, w=0.5, h=0.5)
        x1, y1, x2, y2 = roi.to_pixel_rect(100, 200)
        assert x1 == 50
        assert y1 == 25
        assert x2 == 150
        assert y2 == 75

    def test_clamp_negative(self):
        roi = ROI(x=-0.1, y=-0.2, w=0.5, h=0.5)
        x1, y1, x2, y2 = roi.to_pixel_rect(100, 100)
        assert x1 == 0
        assert y1 == 0

    def test_clamp_overflow(self):
        roi = ROI(x=0.8, y=0.8, w=0.5, h=0.5)
        x1, y1, x2, y2 = roi.to_pixel_rect(100, 100)
        assert x2 == 100
        assert y2 == 100

    def test_full_frame(self):
        roi = ROI(x=0.0, y=0.0, w=1.0, h=1.0)
        x1, y1, x2, y2 = roi.to_pixel_rect(480, 640)
        assert (x1, y1, x2, y2) == (0, 0, 640, 480)


class TestROIDefaults:
    def test_default_confidence(self):
        roi = ROI(x=0, y=0, w=1, h=1)
        assert roi.confidence == 1.0

    def test_default_label(self):
        roi = ROI(x=0, y=0, w=1, h=1)
        assert roi.label == ""

    def test_default_landmarks(self):
        roi = ROI(x=0, y=0, w=1, h=1)
        assert roi.landmarks is None


class TestROILandmarks:
    def test_landmarks_stored(self):
        lm = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        roi = ROI(x=0, y=0, w=1, h=1, landmarks=lm)
        np.testing.assert_array_equal(roi.landmarks, lm)
