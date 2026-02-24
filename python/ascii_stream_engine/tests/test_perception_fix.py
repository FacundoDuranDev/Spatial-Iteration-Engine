"""Tests for fixed perception analyzers (face, hands, pose). No hardware required."""

import numpy as np
import pytest

from ascii_stream_engine.domain.config import EngineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> EngineConfig:
    """Minimal config for analyzer calls."""
    return EngineConfig()


def _synthetic_frame(w: int = 640, h: int = 480) -> np.ndarray:
    """BGR uint8 frame with a white circle (rough face shape) in the center."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Draw a bright oval to give detectors something to find
    import cv2
    cv2.ellipse(frame, (w // 2, h // 2), (80, 100), 0, 0, 360, (200, 180, 160), -1)
    # Draw some features inside the oval
    cv2.circle(frame, (w // 2 - 25, h // 2 - 20), 8, (255, 255, 255), -1)  # left eye
    cv2.circle(frame, (w // 2 + 25, h // 2 - 20), 8, (255, 255, 255), -1)  # right eye
    cv2.ellipse(frame, (w // 2, h // 2 + 30), (20, 8), 0, 0, 360, (100, 100, 200), -1)  # mouth
    return frame


# ---------------------------------------------------------------------------
# Face analyzer tests
# ---------------------------------------------------------------------------

class TestFaceLandmarkAnalyzer:
    def test_import(self):
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        analyzer = FaceLandmarkAnalyzer()
        assert analyzer.name == "face"
        assert analyzer.enabled is True

    def test_none_frame_returns_empty(self):
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        analyzer = FaceLandmarkAnalyzer()
        result = analyzer.analyze(None, _make_config())
        assert result == {}

    def test_disabled_returns_empty(self):
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        analyzer = FaceLandmarkAnalyzer(enabled=False)
        result = analyzer.analyze(_synthetic_frame(), _make_config())
        assert result == {}

    def test_no_crash_on_black_frame(self):
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        analyzer = FaceLandmarkAnalyzer()
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        result = analyzer.analyze(black, _make_config())
        # May or may not detect, but should not crash
        assert isinstance(result, dict)

    def test_detection_output_format(self):
        """If face detected, output should have correct structure."""
        from ascii_stream_engine.adapters.perception.face import (
            FaceLandmarkAnalyzer,
            _FACE_DETECTOR_AVAILABLE,
        )
        if not _FACE_DETECTOR_AVAILABLE:
            pytest.skip("cv2.FaceDetectorYN not available (OpenCV < 4.5.4)")

        import os
        from ascii_stream_engine.adapters.perception.face import _DEFAULT_MODEL_PATH
        if not os.path.isfile(_DEFAULT_MODEL_PATH):
            pytest.skip("face_detection_yunet.onnx not found")

        analyzer = FaceLandmarkAnalyzer()
        frame = _synthetic_frame()
        result = analyzer.analyze(frame, _make_config())

        if result:  # Detection may not fire on synthetic data
            assert "points" in result
            pts = result["points"]
            assert isinstance(pts, np.ndarray)
            assert pts.ndim == 2
            assert pts.shape[1] == 2
            # All coordinates should be in 0-1 range
            assert np.all(pts >= 0.0)
            assert np.all(pts <= 1.0)

            if "faces" in result:
                for face in result["faces"]:
                    assert "bbox" in face
                    assert "confidence" in face
                    assert "points" in face
                    assert len(face["bbox"]) == 4
                    assert face["confidence"] > 0


# ---------------------------------------------------------------------------
# Hands analyzer tests
# ---------------------------------------------------------------------------

class TestHandLandmarkAnalyzer:
    def test_import(self):
        from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
        analyzer = HandLandmarkAnalyzer()
        assert analyzer.name == "hands"
        assert analyzer.enabled is True

    def test_none_frame_returns_empty(self):
        from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
        analyzer = HandLandmarkAnalyzer()
        result = analyzer.analyze(None, _make_config())
        assert result == {}

    def test_disabled_returns_empty(self):
        from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
        analyzer = HandLandmarkAnalyzer(enabled=False)
        result = analyzer.analyze(_synthetic_frame(), _make_config())
        assert result == {}

    def test_graceful_fallback_no_mediapipe(self):
        """If mediapipe is not installed, should return empty dict (not crash)."""
        from ascii_stream_engine.adapters.perception.hands import (
            HandLandmarkAnalyzer,
            _MP_AVAILABLE,
        )
        if _MP_AVAILABLE:
            pytest.skip("mediapipe IS available, can't test fallback")
        analyzer = HandLandmarkAnalyzer()
        result = analyzer.analyze(_synthetic_frame(), _make_config())
        assert result == {}

    @pytest.mark.slow
    def test_mediapipe_output_format(self):
        """If mediapipe available, output should have correct structure."""
        from ascii_stream_engine.adapters.perception.hands import (
            HandLandmarkAnalyzer,
            _MP_AVAILABLE,
        )
        if not _MP_AVAILABLE:
            pytest.skip("mediapipe not installed")

        analyzer = HandLandmarkAnalyzer()
        frame = _synthetic_frame()
        result = analyzer.analyze(frame, _make_config())

        # May or may not detect hands in synthetic frame, but should not crash
        assert isinstance(result, dict)
        if result:
            if "left" in result:
                pts = result["left"]
                assert isinstance(pts, np.ndarray)
                if pts.size > 0:
                    assert pts.ndim == 2
                    assert pts.shape[1] == 2
                    assert np.all(pts >= 0.0)
                    assert np.all(pts <= 1.0)
            if "right" in result:
                pts = result["right"]
                assert isinstance(pts, np.ndarray)
                if pts.size > 0:
                    assert pts.ndim == 2
                    assert pts.shape[1] == 2
                    assert np.all(pts >= 0.0)
                    assert np.all(pts <= 1.0)


# ---------------------------------------------------------------------------
# Pose analyzer tests
# ---------------------------------------------------------------------------

class TestPoseLandmarkAnalyzer:
    def test_import(self):
        from ascii_stream_engine.adapters.perception.pose import PoseLandmarkAnalyzer
        analyzer = PoseLandmarkAnalyzer()
        assert analyzer.name == "pose"
        assert analyzer.enabled is True

    def test_none_frame_returns_empty(self):
        from ascii_stream_engine.adapters.perception.pose import PoseLandmarkAnalyzer
        analyzer = PoseLandmarkAnalyzer()
        result = analyzer.analyze(None, _make_config())
        assert result == {}

    def test_graceful_fallback_no_cpp(self):
        """Without C++ module, should return empty dict."""
        from ascii_stream_engine.adapters.perception.pose import (
            PoseLandmarkAnalyzer,
            _CPP_AVAILABLE,
        )
        if _CPP_AVAILABLE:
            pytest.skip("perception_cpp IS available, can't test fallback")
        analyzer = PoseLandmarkAnalyzer()
        result = analyzer.analyze(_synthetic_frame(), _make_config())
        assert result == {}

    @pytest.mark.slow
    def test_cpp_output_format(self):
        """If C++ module available, output should have correct structure."""
        from ascii_stream_engine.adapters.perception.pose import (
            PoseLandmarkAnalyzer,
            _CPP_AVAILABLE,
        )
        if not _CPP_AVAILABLE:
            pytest.skip("perception_cpp not available")

        analyzer = PoseLandmarkAnalyzer()
        frame = _synthetic_frame()
        result = analyzer.analyze(frame, _make_config())

        assert isinstance(result, dict)
        if result:
            assert "joints" in result
            joints = result["joints"]
            assert isinstance(joints, np.ndarray)
            assert joints.ndim == 2
            assert joints.shape[1] == 2
            # Normalized to 0-1
            assert np.all(joints >= 0.0)
            assert np.all(joints <= 1.0)


# ---------------------------------------------------------------------------
# Coordinate normalization tests
# ---------------------------------------------------------------------------

class TestCoordinateNormalization:
    def test_face_coords_in_range(self):
        """Face points must always be in [0, 1] regardless of frame size."""
        from ascii_stream_engine.adapters.perception.face import (
            FaceLandmarkAnalyzer,
            _FACE_DETECTOR_AVAILABLE,
        )
        if not _FACE_DETECTOR_AVAILABLE:
            pytest.skip("FaceDetectorYN not available")

        import os
        from ascii_stream_engine.adapters.perception.face import _DEFAULT_MODEL_PATH
        if not os.path.isfile(_DEFAULT_MODEL_PATH):
            pytest.skip("face_detection_yunet.onnx not found")

        analyzer = FaceLandmarkAnalyzer()
        for size in [(320, 240), (640, 480), (1280, 720)]:
            frame = _synthetic_frame(w=size[0], h=size[1])
            result = analyzer.analyze(frame, _make_config())
            if result and "points" in result:
                pts = result["points"]
                assert np.all(pts >= 0.0), f"Negative coords at {size}"
                assert np.all(pts <= 1.0), f"Coords > 1.0 at {size}"


# ---------------------------------------------------------------------------
# Perception __init__ tests
# ---------------------------------------------------------------------------

class TestPerceptionInit:
    def test_all_analyzers_importable(self):
        from ascii_stream_engine.adapters.perception import (
            FaceLandmarkAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer,
        )
        assert FaceLandmarkAnalyzer.name == "face"
        assert HandLandmarkAnalyzer.name == "hands"
        assert PoseLandmarkAnalyzer.name == "pose"
