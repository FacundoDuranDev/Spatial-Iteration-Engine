"""Hand landmark analyzer using MediaPipe Hands. MVP_03."""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except ImportError:
    mp = None
    _MP_AVAILABLE = False


class HandLandmarkAnalyzer(BaseAnalyzer):
    """Hand landmarks (21 per hand) using MediaPipe Hands.

    Returns normalized 0-1 coordinates for left and right hands.
    Gracefully returns empty dict if mediapipe is not installed.
    """

    name = "hands"
    enabled = True

    def __init__(
        self,
        enabled: bool = True,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        super().__init__(enabled=enabled)
        self._hands = None
        self._max_num_hands = max_num_hands
        self._min_detection_confidence = min_detection_confidence
        self._min_tracking_confidence = min_tracking_confidence

    def _ensure_hands(self) -> bool:
        if self._hands is not None:
            return True
        if not _MP_AVAILABLE:
            return False
        try:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self._max_num_hands,
                min_detection_confidence=self._min_detection_confidence,
                min_tracking_confidence=self._min_tracking_confidence,
            )
            return True
        except Exception:
            return False

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if frame is None or not self.enabled:
            return {}
        if not self._ensure_hands():
            return {}
        try:
            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            # MediaPipe expects RGB input
            import cv2

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb_frame)

            if not results.multi_hand_landmarks:
                return {}

            left = np.empty((0, 2), dtype=np.float32)
            right = np.empty((0, 2), dtype=np.float32)

            for hand_landmarks, handedness in zip(
                results.multi_hand_landmarks, results.multi_handedness
            ):
                # Extract 21 landmarks, already normalized 0-1
                points = np.array(
                    [[lm.x, lm.y] for lm in hand_landmarks.landmark],
                    dtype=np.float32,
                )
                np.clip(points, 0.0, 1.0, out=points)

                # MediaPipe label is mirrored — "Left" in image is user's right hand
                label = handedness.classification[0].label
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
