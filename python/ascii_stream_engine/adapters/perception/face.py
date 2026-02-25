"""Face detection analyzer using OpenCV FaceDetectorYN (YuNet). MVP_03."""

import os
from typing import Any, Dict

import cv2
import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

# Require OpenCV 4.5.4+ for FaceDetectorYN
_CV2_VERSION = tuple(int(x) for x in cv2.__version__.split(".")[:3] if x.isdigit())
_FACE_DETECTOR_AVAILABLE = _CV2_VERSION >= (4, 5, 4) and hasattr(cv2, "FaceDetectorYN")


def _find_model_path() -> str:
    """Locate face_detection_yunet.onnx from env var or common relative paths."""
    env_dir = os.environ.get("ONNX_MODELS_DIR", "")
    if env_dir:
        p = os.path.join(env_dir, "face_detection_yunet.onnx")
        if os.path.isfile(p):
            return p

    # Try relative to this file (package installed in python/ subdir)
    base = os.path.dirname(__file__)
    for depth in range(3, 8):
        candidate = os.path.normpath(
            os.path.join(
                base, *[".."] * depth, "onnx_models", "mediapipe", "face_detection_yunet.onnx"
            )
        )
        if os.path.isfile(candidate):
            return candidate

    # Try relative to cwd
    cwd_candidate = os.path.join(
        os.getcwd(), "onnx_models", "mediapipe", "face_detection_yunet.onnx"
    )
    if os.path.isfile(cwd_candidate):
        return cwd_candidate

    return os.path.join("onnx_models", "mediapipe", "face_detection_yunet.onnx")


_DEFAULT_MODEL_PATH = _find_model_path()


class FaceLandmarkAnalyzer(BaseAnalyzer):
    """Face detection using OpenCV's FaceDetectorYN (YuNet model).

    Returns bounding boxes, confidence, and 5 facial landmarks per face.
    All coordinates normalized to 0-1 range.
    """

    name = "face"
    enabled = True

    def __init__(self, enabled: bool = True, model_path: str = "") -> None:
        super().__init__(enabled=enabled)
        self._detector = None
        self._model_path = model_path or _DEFAULT_MODEL_PATH
        self._input_size = (320, 320)

    def _ensure_detector(self) -> bool:
        if self._detector is not None:
            return True
        if not _FACE_DETECTOR_AVAILABLE:
            return False
        if not os.path.isfile(self._model_path):
            return False
        try:
            self._detector = cv2.FaceDetectorYN.create(
                self._model_path,
                "",
                self._input_size,
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=10,
            )
            return True
        except Exception:
            return False

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if frame is None or not self.enabled:
            return {}
        if not self._ensure_detector():
            return {}
        try:
            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            # FaceDetectorYN accepts BGR directly — set input size to frame size
            self._detector.setInputSize((w, h))
            _, detections = self._detector.detect(frame)

            if detections is None or len(detections) == 0:
                return {}

            faces = []
            all_points = []
            for det in detections:
                # YuNet output (15,): x,y,w,h, lm1_x,lm1_y,...,lm5_x,lm5_y, score
                bx, by, bw, bh = det[0], det[1], det[2], det[3]
                conf = float(det[14])

                # Normalize bbox to 0-1
                bbox = [
                    float(bx / w),
                    float(by / h),
                    float(bw / w),
                    float(bh / h),
                ]

                # Extract 5 facial landmarks at indices 4..13
                landmarks = np.zeros((5, 2), dtype=np.float32)
                for i in range(5):
                    landmarks[i, 0] = float(det[4 + i * 2] / w)
                    landmarks[i, 1] = float(det[4 + i * 2 + 1] / h)

                np.clip(landmarks, 0.0, 1.0, out=landmarks)
                faces.append(
                    {
                        "bbox": bbox,
                        "confidence": conf,
                        "points": landmarks,
                    }
                )
                all_points.append(landmarks)

            if not all_points:
                return {}

            # "points" key: all landmarks concatenated for backwards compatibility
            # with landmarks_overlay_renderer.py
            combined = np.concatenate(all_points, axis=0)
            return {"faces": faces, "points": combined}
        except Exception:
            return {}
