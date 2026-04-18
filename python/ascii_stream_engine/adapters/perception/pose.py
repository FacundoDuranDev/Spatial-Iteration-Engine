"""Pose landmark analyzer using MediaPipe Tasks API or C++ perception_cpp. MVP_03."""

import os
from typing import Any, Dict

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions as _MPBaseOptions
    from mediapipe.tasks.python import vision as _mp_vision

    _MP_AVAILABLE = True
except ImportError:
    mp = None
    _mp_vision = None
    _MPBaseOptions = None
    _MP_AVAILABLE = False

try:
    import perception_cpp as _perception_cpp

    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False


def _find_pose_model_path() -> str:
    """Locate pose_landmarker_lite.task from env var or common relative paths."""
    env_dir = os.environ.get("ONNX_MODELS_DIR", "")
    if env_dir:
        p = os.path.join(env_dir, "pose_landmarker_lite.task")
        if os.path.isfile(p):
            return p

    base = os.path.dirname(__file__)
    for depth in range(3, 8):
        candidate = os.path.normpath(
            os.path.join(
                base, *[".."] * depth, "onnx_models", "mediapipe", "pose_landmarker_lite.task"
            )
        )
        if os.path.isfile(candidate):
            return candidate

    cwd_candidate = os.path.join(
        os.getcwd(), "onnx_models", "mediapipe", "pose_landmarker_lite.task"
    )
    if os.path.isfile(cwd_candidate):
        return cwd_candidate

    return os.path.join("onnx_models", "mediapipe", "pose_landmarker_lite.task")


_DEFAULT_POSE_MODEL_PATH = _find_pose_model_path()


class PoseLandmarkAnalyzer(BaseAnalyzer):
    """Pose landmarks (33 joints) using MediaPipe Tasks API or C++ perception_cpp.

    Prefers MediaPipe when available (33 joints with visibility scores).
    Falls back to perception_cpp.detect_pose.
    Returns normalized 0-1 coordinates.
    """

    name = "pose"
    enabled = True

    def __init__(self, enabled: bool = True, model_path: str = "") -> None:
        super().__init__(enabled=enabled)
        self._pose = None
        self._model_path = model_path or _DEFAULT_POSE_MODEL_PATH

    def _ensure_pose(self) -> bool:
        if self._pose is not None:
            return True
        if not _MP_AVAILABLE:
            return False
        if not os.path.isfile(self._model_path):
            return False
        try:
            options = _mp_vision.PoseLandmarkerOptions(
                base_options=_MPBaseOptions(model_asset_path=self._model_path),
                min_pose_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._pose = _mp_vision.PoseLandmarker.create_from_options(options)
            return True
        except Exception:
            return False

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if frame is None or not self.enabled:
            return {}

        # Try MediaPipe first
        if self._ensure_pose():
            return self._analyze_mediapipe(frame)

        # Fallback to C++ perception_cpp
        if _CPP_AVAILABLE:
            return self._analyze_cpp(frame)

        return {}

    def _analyze_mediapipe(self, frame: np.ndarray) -> Dict[str, Any]:
        try:
            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            import cv2

            from ..processors.filters.conversion_cache import get_cached_conversion

            rgb_frame = get_cached_conversion(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self._pose.detect(mp_image)

            if not results.pose_landmarks:
                return {}

            # Use the first detected pose
            landmarks = results.pose_landmarks[0]
            joints = np.array(
                [[lm.x, lm.y] for lm in landmarks],
                dtype=np.float32,
            )
            np.clip(joints, 0.0, 1.0, out=joints)
            return {"joints": joints}
        except Exception:
            return {}

    def _analyze_cpp(self, frame: np.ndarray) -> Dict[str, Any]:
        """Fallback: use perception_cpp.detect_pose."""
        try:
            out = _perception_cpp.detect_pose(frame)
            if out is None or out.size == 0:
                return {}
            h, w = frame.shape[:2]
            if h > 0 and w > 0:
                out = out.astype(np.float32)
                out[:, 0] /= w
                out[:, 1] /= h
                np.clip(out, 0.0, 1.0, out=out)
            return {"joints": out}
        except Exception:
            return {}

    def __del__(self) -> None:
        if self._pose is not None:
            try:
                self._pose.close()
            except Exception:
                pass
