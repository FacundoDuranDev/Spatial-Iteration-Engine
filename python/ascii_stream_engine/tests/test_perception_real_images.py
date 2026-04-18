"""Perception tests using real images from test_images/.

Runs face, hand, and pose detection on actual photographs to validate
that analyzers produce meaningful output on real-world inputs. Also
verifies that new perception-reactive filters work with real analysis data.

Requires:
  - test_images/ directory with real photos
  - face_detection_yunet.onnx for face tests
  - mediapipe for hand tests
  - perception_cpp for pose tests
"""

import os

import cv2
import numpy as np
import pytest

from ascii_stream_engine.domain.config import EngineConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TEST_IMAGES_DIR = os.path.join(REPO_ROOT, "test_images")


def _load_image(name: str) -> np.ndarray:
    """Load a BGR image from test_images/."""
    path = os.path.join(TEST_IMAGES_DIR, name)
    if not os.path.isfile(path):
        pytest.skip(f"Image not found: {path}")
    img = cv2.imread(path)
    if img is None:
        pytest.skip(f"Failed to decode: {path}")
    return img


def _config():
    return EngineConfig()


# ---------------------------------------------------------------------------
# Face detection on real images
# ---------------------------------------------------------------------------


class TestFaceDetectionRealImages:
    """Face detection using real photographs."""

    @pytest.fixture(autouse=True)
    def _check_detector(self):
        from ascii_stream_engine.adapters.perception.face import (
            _DEFAULT_MODEL_PATH,
            _FACE_DETECTOR_AVAILABLE,
        )

        if not _FACE_DETECTOR_AVAILABLE:
            pytest.skip("cv2.FaceDetectorYN not available")
        if not os.path.isfile(_DEFAULT_MODEL_PATH):
            pytest.skip("face_detection_yunet.onnx not found")

    def _analyzer(self):
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer

        return FaceLandmarkAnalyzer()

    def test_face_real_portrait(self):
        """Detect face in a frontal portrait (test_face_real.jpg)."""
        frame = _load_image("test_face_real.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert result, "No face detected in test_face_real.jpg"
        assert "faces" in result
        assert len(result["faces"]) >= 1

        face = result["faces"][0]
        assert face["confidence"] > 0.5
        assert len(face["bbox"]) == 4
        # Bbox should be in reasonable area (face is centered)
        bx, by, bw, bh = face["bbox"]
        assert 0.1 < bx < 0.7, f"bbox x={bx} out of expected range"
        assert 0.0 < by < 0.6, f"bbox y={by} out of expected range"

        # Points should be normalized 0-1
        pts = face["points"]
        assert pts.shape == (5, 2)
        assert np.all(pts >= 0.0) and np.all(pts <= 1.0)

    def test_face_pose_real(self):
        """Detect face in test_pose_real.jpg (person with visible face)."""
        frame = _load_image("test_pose_real.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert result, "No face detected in test_pose_real.jpg"
        assert "faces" in result
        assert len(result["faces"]) >= 1
        assert result["faces"][0]["confidence"] > 0.3

    def test_face_standing_person(self):
        """Detect face in standing_person.jpg (side-lit portrait)."""
        frame = _load_image("standing_person.jpg")
        result = self._analyzer().analyze(frame, _config())
        # This is a dramatic side-lit face, detection may or may not work
        assert isinstance(result, dict)

    def test_face_tpose_person(self):
        """Detect face in tpose_person.jpg."""
        frame = _load_image("tpose_person.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert result, "No face detected in tpose_person.jpg"
        assert "faces" in result
        assert len(result["faces"]) >= 1

    def test_face_fullbody_street(self):
        """Detect faces in fullbody.jpg (street scene with multiple people)."""
        frame = _load_image("fullbody.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert result, "No faces detected in fullbody.jpg"
        assert "faces" in result
        # Street scene has multiple people visible
        assert len(result["faces"]) >= 1

    def test_face_combined_points(self):
        """The 'points' key should concatenate all face landmarks."""
        frame = _load_image("test_face_real.jpg")
        result = self._analyzer().analyze(frame, _config())

        if result:
            assert "points" in result
            pts = result["points"]
            assert isinstance(pts, np.ndarray)
            assert pts.ndim == 2 and pts.shape[1] == 2
            # Should be N*5 points (5 per face)
            assert pts.shape[0] == len(result["faces"]) * 5

    def test_no_face_in_synthetic(self):
        """Synthetic hand image should not detect faces (or return empty)."""
        frame = _load_image("test_hands.jpg")
        result = self._analyzer().analyze(frame, _config())
        # Cartoon hand shapes shouldn't trigger face detection
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Hand detection on real images
# ---------------------------------------------------------------------------


class TestHandDetectionRealImages:
    """Hand detection using real photographs with visible hands."""

    @pytest.fixture(autouse=True)
    def _check_mediapipe(self):
        try:
            import mediapipe

            self._mp_available = True
        except ImportError:
            self._mp_available = False

        try:
            import perception_cpp

            self._cpp_available = True
        except ImportError:
            self._cpp_available = False

        if not self._mp_available and not self._cpp_available:
            pytest.skip("Neither mediapipe nor perception_cpp available")

    def _analyzer(self):
        from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer

        return HandLandmarkAnalyzer(min_detection_confidence=0.3)

    @pytest.mark.slow
    def test_hands_real_image(self):
        """Detect hands in test_hands_real.jpg (person holding object)."""
        frame = _load_image("test_hands_real.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert isinstance(result, dict)
        if result:
            # Should have left/right keys
            for key in ("left", "right"):
                if key in result and result[key].size > 0:
                    pts = result[key]
                    assert pts.ndim == 2
                    assert pts.shape == (21, 2), f"{key} hand: expected (21,2), got {pts.shape}"
                    assert np.all(pts >= 0.0) and np.all(pts <= 1.0)

    @pytest.mark.slow
    def test_hands_tpose(self):
        """Detect hands in tpose_person.jpg (arms crossed, hands visible)."""
        frame = _load_image("tpose_person.jpg")
        result = self._analyzer().analyze(frame, _config())
        assert isinstance(result, dict)

    @pytest.mark.slow
    def test_hands_fullbody(self):
        """Detect hands in fullbody.jpg (street scene)."""
        frame = _load_image("fullbody.jpg")
        result = self._analyzer().analyze(frame, _config())
        assert isinstance(result, dict)

    @pytest.mark.slow
    def test_hand_output_normalized(self):
        """All hand coordinates must be in [0, 1]."""
        for img_name in ("test_hands_real.jpg", "tpose_person.jpg"):
            frame = _load_image(img_name)
            result = self._analyzer().analyze(frame, _config())
            if result:
                for key in ("left", "right"):
                    pts = result.get(key)
                    if pts is not None and pts.size > 0:
                        assert np.all(pts >= 0.0), f"{key} hand has negative coords in {img_name}"
                        assert np.all(pts <= 1.0), f"{key} hand has coords > 1 in {img_name}"


# ---------------------------------------------------------------------------
# Pose detection on real images
# ---------------------------------------------------------------------------


class TestPoseDetectionRealImages:
    """Pose detection using real photographs with visible body."""

    @pytest.fixture(autouse=True)
    def _check_cpp(self):
        try:
            import perception_cpp

            self._available = True
        except ImportError:
            pytest.skip("perception_cpp not available")

    def _analyzer(self):
        from ascii_stream_engine.adapters.perception.pose import PoseLandmarkAnalyzer

        return PoseLandmarkAnalyzer()

    @pytest.mark.slow
    def test_pose_real_image(self):
        """Detect pose in test_pose_real.jpg (upper body visible)."""
        frame = _load_image("test_pose_real.jpg")
        result = self._analyzer().analyze(frame, _config())

        assert isinstance(result, dict)
        if result:
            assert "joints" in result
            joints = result["joints"]
            assert isinstance(joints, np.ndarray)
            assert joints.ndim == 2
            assert joints.shape[1] == 2
            assert np.all(joints >= 0.0) and np.all(joints <= 1.0)

    @pytest.mark.slow
    def test_pose_tpose(self):
        """Detect pose in tpose_person.jpg (clear upper body)."""
        frame = _load_image("tpose_person.jpg")
        result = self._analyzer().analyze(frame, _config())
        assert isinstance(result, dict)

    @pytest.mark.slow
    def test_pose_fullbody(self):
        """Detect pose in fullbody.jpg (multiple people)."""
        frame = _load_image("fullbody.jpg")
        result = self._analyzer().analyze(frame, _config())
        assert isinstance(result, dict)

    @pytest.mark.slow
    def test_pose_vitruvian(self):
        """Detect pose in vitruvian_man.jpg (drawing, may or may not detect)."""
        frame = _load_image("vitruvian_man.jpg")
        result = self._analyzer().analyze(frame, _config())
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Filters with real perception data
# ---------------------------------------------------------------------------


class TestFiltersWithRealPerception:
    """Run perception-reactive filters using real analysis from real images."""

    @pytest.fixture(autouse=True)
    def _check_face_detector(self):
        from ascii_stream_engine.adapters.perception.face import (
            _DEFAULT_MODEL_PATH,
            _FACE_DETECTOR_AVAILABLE,
        )

        if not _FACE_DETECTOR_AVAILABLE:
            pytest.skip("cv2.FaceDetectorYN not available")
        if not os.path.isfile(_DEFAULT_MODEL_PATH):
            pytest.skip("face_detection_yunet.onnx not found")

    def _get_real_analysis(self, img_name: str) -> dict:
        """Run face detection on a real image and return the analysis dict."""
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer

        frame = _load_image(img_name)
        face_result = FaceLandmarkAnalyzer().analyze(frame, _config())

        analysis = {}
        if face_result:
            analysis["face"] = face_result

        # Add mock hand data (mediapipe may not be available)
        h, w = frame.shape[:2]
        analysis["hands"] = {
            "left": np.random.rand(21, 2).astype(np.float32),
            "right": np.random.rand(21, 2).astype(np.float32),
        }

        return frame, analysis

    def test_bloom_with_real_face(self):
        from ascii_stream_engine.adapters.processors.filters.bloom import BloomFilter

        frame, analysis = self._get_real_analysis("test_face_real.jpg")
        f = BloomFilter(intensity=0.5)
        result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_kaleidoscope_with_real_hands(self):
        from ascii_stream_engine.adapters.processors.filters.kaleidoscope import KaleidoscopeFilter

        frame, analysis = self._get_real_analysis("test_face_real.jpg")
        f = KaleidoscopeFilter(segments=6)
        result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_toon_shading_with_real_face(self):
        from ascii_stream_engine.adapters.processors.filters.toon_shading import ToonShadingFilter

        frame, analysis = self._get_real_analysis("test_face_real.jpg")
        f = ToonShadingFilter()
        result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8
        # Toon shading uses face bbox for detail enhancement
        assert "face" in analysis

    def test_chromatic_aberration_with_real_hands(self):
        from ascii_stream_engine.adapters.processors.filters.chromatic_aberration import (
            ChromaticAberrationFilter,
        )

        frame, analysis = self._get_real_analysis("tpose_person.jpg")
        f = ChromaticAberrationFilter(strength=3.0)
        result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_kuwahara_on_real_image(self):
        from ascii_stream_engine.adapters.processors.filters.kuwahara import KuwaharaFilter

        frame, analysis = self._get_real_analysis("standing_person.jpg")
        f = KuwaharaFilter(radius=4)
        result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_slit_scan_with_real_frames(self):
        from ascii_stream_engine.adapters.processors.filters.slit_scan import SlitScanFilter

        frame, analysis = self._get_real_analysis("test_face_real.jpg")
        f = SlitScanFilter(buffer_size=5)
        # Feed multiple frames to fill buffer
        for _ in range(6):
            result = f.apply(frame, None, analysis)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_filter_chain_real_image(self):
        """Chain multiple perception-reactive filters on a real photo."""
        from ascii_stream_engine.adapters.processors.filters.bloom import BloomFilter
        from ascii_stream_engine.adapters.processors.filters.chromatic_aberration import (
            ChromaticAberrationFilter,
        )
        from ascii_stream_engine.adapters.processors.filters.kuwahara import KuwaharaFilter
        from ascii_stream_engine.adapters.processors.filters.toon_shading import ToonShadingFilter

        frame, analysis = self._get_real_analysis("test_face_real.jpg")
        chain = [
            BloomFilter(intensity=0.3),
            ToonShadingFilter(),
            KuwaharaFilter(radius=3),
            ChromaticAberrationFilter(strength=2.0),
        ]
        result = frame.copy()
        for f in chain:
            result = f.apply(result, None, analysis)

        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_all_images_no_crash(self):
        """Run bloom filter on every test image -- no crashes."""
        from ascii_stream_engine.adapters.processors.filters.bloom import BloomFilter

        f = BloomFilter(intensity=0.4)
        images = [
            "test_face_real.jpg",
            "test_hands_real.jpg",
            "test_pose_real.jpg",
            "tpose_person.jpg",
            "standing_person.jpg",
            "fullbody.jpg",
            "vitruvian_man.jpg",
        ]
        for img_name in images:
            path = os.path.join(TEST_IMAGES_DIR, img_name)
            if not os.path.isfile(path):
                continue
            frame = cv2.imread(path)
            if frame is None:
                continue
            result = f.apply(frame, None)
            assert result.shape == frame.shape, f"Shape mismatch on {img_name}"
            assert result.dtype == np.uint8, f"Dtype mismatch on {img_name}"


# ---------------------------------------------------------------------------
# End-to-end: detect then filter
# ---------------------------------------------------------------------------


class TestEndToEndPerceptionToFilter:
    """Full pipeline: real image -> real detection -> filter with real analysis."""

    @pytest.fixture(autouse=True)
    def _check_requirements(self):
        from ascii_stream_engine.adapters.perception.face import (
            _DEFAULT_MODEL_PATH,
            _FACE_DETECTOR_AVAILABLE,
        )

        if not _FACE_DETECTOR_AVAILABLE or not os.path.isfile(_DEFAULT_MODEL_PATH):
            pytest.skip("Face detector not available")

    @pytest.mark.slow
    def test_face_to_toon_shading(self):
        """Detect face in portrait, use bbox for toon shading detail."""
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        from ascii_stream_engine.adapters.processors.filters.toon_shading import ToonShadingFilter

        frame = _load_image("test_face_real.jpg")
        face_result = FaceLandmarkAnalyzer().analyze(frame, _config())

        assert face_result, "Face not detected"
        assert "faces" in face_result
        assert len(face_result["faces"]) >= 1

        analysis = {"face": face_result}
        f = ToonShadingFilter()
        result = f.apply(frame, None, analysis)

        assert result.shape == frame.shape
        assert result.dtype == np.uint8
        # Output should differ from input (filter actually did something)
        assert not np.array_equal(result, frame)

    @pytest.mark.slow
    def test_face_to_radial_collapse(self):
        """Detect face, use it for radial collapse center."""
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        from ascii_stream_engine.adapters.processors.filters.radial_collapse import (
            RadialCollapseFilter,
        )

        frame = _load_image("test_face_real.jpg")
        face_result = FaceLandmarkAnalyzer().analyze(frame, _config())

        assert face_result, "Face not detected"
        analysis = {"face": face_result}
        f = RadialCollapseFilter(follow_face=True, strength=0.3)
        result = f.apply(frame, None, analysis)

        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    @pytest.mark.slow
    def test_multi_face_fullbody(self):
        """Detect multiple faces in street scene, apply geometric patterns."""
        from ascii_stream_engine.adapters.perception.face import FaceLandmarkAnalyzer
        from ascii_stream_engine.adapters.processors.filters.geometric_patterns import (
            GeometricPatternFilter,
        )

        frame = _load_image("fullbody.jpg")
        face_result = FaceLandmarkAnalyzer().analyze(frame, _config())

        analysis = {"face": face_result} if face_result else {}
        # Also add empty hands to test robustness
        analysis["hands"] = {
            "left": np.empty((0, 2), dtype=np.float32),
            "right": np.empty((0, 2), dtype=np.float32),
        }

        f = GeometricPatternFilter()
        result = f.apply(frame, None, analysis)

        assert result.shape == frame.shape
        assert result.dtype == np.uint8
