"""Hand landmark analyzer using MediaPipe Tasks API or C++ perception_cpp. MVP_03."""

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


def _find_hand_model_path() -> str:
    """Locate hand_landmarker.task from env var or common relative paths."""
    env_dir = os.environ.get("ONNX_MODELS_DIR", "")
    if env_dir:
        p = os.path.join(env_dir, "hand_landmarker.task")
        if os.path.isfile(p):
            return p

    base = os.path.dirname(__file__)
    for depth in range(3, 8):
        candidate = os.path.normpath(
            os.path.join(
                base, *[".."] * depth, "onnx_models", "mediapipe", "hand_landmarker.task"
            )
        )
        if os.path.isfile(candidate):
            return candidate

    cwd_candidate = os.path.join(
        os.getcwd(), "onnx_models", "mediapipe", "hand_landmarker.task"
    )
    if os.path.isfile(cwd_candidate):
        return cwd_candidate

    return os.path.join("onnx_models", "mediapipe", "hand_landmarker.task")


_DEFAULT_HAND_MODEL_PATH = _find_hand_model_path()


class HandLandmarkAnalyzer(BaseAnalyzer):
    """Hand landmarks (21 per hand) using MediaPipe Tasks API or C++ perception_cpp.

    Prefers MediaPipe when available (supports left/right hand distinction).
    Falls back to perception_cpp.detect_hands (single hand, no left/right).
    Returns normalized 0-1 coordinates.
    """

    name = "hands"
    enabled = True

    def __init__(
        self,
        enabled: bool = True,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str = "",
    ) -> None:
        super().__init__(enabled=enabled)
        self._hands = None
        self._max_num_hands = max_num_hands
        self._min_detection_confidence = min_detection_confidence
        self._min_tracking_confidence = min_tracking_confidence
        self._model_path = model_path or _DEFAULT_HAND_MODEL_PATH

    def _ensure_hands(self) -> bool:
        if self._hands is not None:
            return True
        if not _MP_AVAILABLE:
            return False
        if not os.path.isfile(self._model_path):
            return False
        try:
            options = _mp_vision.HandLandmarkerOptions(
                base_options=_MPBaseOptions(model_asset_path=self._model_path),
                num_hands=self._max_num_hands,
                min_hand_detection_confidence=self._min_detection_confidence,
                min_hand_presence_confidence=self._min_detection_confidence,
                min_tracking_confidence=self._min_tracking_confidence,
            )
            self._hands = _mp_vision.HandLandmarker.create_from_options(options)
            return True
        except Exception:
            return False

    def _analyze_cpp(self, frame: np.ndarray) -> Dict[str, Any]:
        """Fallback: use perception_cpp.detect_hands when mediapipe unavailable."""
        try:
            out = _perception_cpp.detect_hands(frame)
            if out is None or out.size == 0:
                return {}
            h, w = frame.shape[:2]
            if h > 0 and w > 0:
                out = out.astype(np.float32)
                out[:, 0] /= w
                out[:, 1] /= h
                np.clip(out, 0.0, 1.0, out=out)
            return {"left": np.empty((0, 2), dtype=np.float32), "right": out}
        except Exception:
            return {}

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if frame is None or not self.enabled:
            return {}

        # Try MediaPipe first (supports left/right distinction)
        if self._ensure_hands():
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
            results = self._hands.detect(mp_image)

            if not results.hand_landmarks:
                return {}

            left = np.empty((0, 2), dtype=np.float32)
            right = np.empty((0, 2), dtype=np.float32)

            for hand_landmarks, handedness in zip(
                results.hand_landmarks, results.handedness
            ):
                points = np.array(
                    [[lm.x, lm.y] for lm in hand_landmarks],
                    dtype=np.float32,
                )
                np.clip(points, 0.0, 1.0, out=points)

                # MediaPipe mirrors: "Left" in result = viewer's left = subject's right
                label = handedness[0].category_name
                if label == "Left":
                    right = points
                else:
                    left = points

            return {"left": left, "right": right}
        except Exception:
            return {}

    def __del__(self) -> None:
        if self._hands is not None:
            try:
                self._hands.close()
            except Exception:
                pass
