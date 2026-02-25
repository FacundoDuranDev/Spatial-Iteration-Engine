"""Hand gesture classifier from hand landmark geometry. No ONNX model required.

Classifies gestures from the 21-point MediaPipe hand landmark topology
using geometric heuristics (finger extension, angles, distances).

Output schema:
    analysis["hand_gesture"] = {
        "left_gesture": str,           # gesture class name
        "left_confidence": float,      # 0.0-1.0
        "right_gesture": str,          # gesture class name
        "right_confidence": float,     # 0.0-1.0
    }

Gesture classes: "open", "fist", "point", "peace", "thumbs_up", "none"
"""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

# Valid gesture labels
GESTURE_LABELS = ("open", "fist", "point", "peace", "thumbs_up", "none")

# MediaPipe hand landmark indices
# 0: wrist
# 1-4: thumb (CMC, MCP, IP, TIP)
# 5-8: index (MCP, PIP, DIP, TIP)
# 9-12: middle (MCP, PIP, DIP, TIP)
# 13-16: ring (MCP, PIP, DIP, TIP)
# 17-20: pinky (MCP, PIP, DIP, TIP)

_FINGER_TIPS = [4, 8, 12, 16, 20]
_FINGER_PIPS = [3, 6, 10, 14, 18]
_FINGER_MCPS = [2, 5, 9, 13, 17]


def _is_finger_extended(landmarks: np.ndarray, tip_idx: int, pip_idx: int) -> bool:
    """Check if a finger is extended by comparing tip and pip y-coordinates.

    For the thumb (tip=4), we use x-distance from wrist instead.
    """
    if tip_idx == 4:
        # Thumb: check if tip is farther from wrist than MCP in x direction
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]
        return abs(thumb_tip[0] - wrist[0]) > abs(thumb_mcp[0] - wrist[0])
    else:
        # Other fingers: tip is above (lower y) pip when extended
        return landmarks[tip_idx][1] < landmarks[pip_idx][1]


def _classify_gesture(landmarks: np.ndarray) -> tuple:
    """Classify a gesture from 21 hand landmarks. Returns (gesture_name, confidence)."""
    if landmarks is None or landmarks.shape[0] < 21 or landmarks.shape[1] < 2:
        return ("none", 0.0)

    # Determine which fingers are extended
    extended = []
    for tip, pip in zip(_FINGER_TIPS, _FINGER_PIPS):
        extended.append(_is_finger_extended(landmarks, tip, pip))

    thumb_ext, index_ext, middle_ext, ring_ext, pinky_ext = extended
    num_extended = sum(extended)

    # Classification by heuristics
    # Open hand: all 5 fingers extended
    if num_extended >= 4 and index_ext and middle_ext and ring_ext:
        return ("open", min(0.6 + num_extended * 0.08, 1.0))

    # Fist: no fingers extended (or only thumb slightly)
    if num_extended == 0 or (num_extended == 1 and thumb_ext):
        return ("fist", 0.7 + (0.15 if num_extended == 0 else 0.0))

    # Point: only index finger extended
    if index_ext and not middle_ext and not ring_ext and not pinky_ext:
        return ("point", 0.8)

    # Peace: index and middle extended, ring and pinky curled
    if index_ext and middle_ext and not ring_ext and not pinky_ext:
        return ("peace", 0.8)

    # Thumbs up: only thumb extended, hand roughly vertical
    if thumb_ext and not index_ext and not middle_ext and not ring_ext and not pinky_ext:
        # Check if thumb points upward (thumb tip y < wrist y)
        if landmarks[4][1] < landmarks[0][1]:
            return ("thumbs_up", 0.75)
        else:
            return ("fist", 0.5)

    return ("none", 0.3)


class HandGestureAnalyzer(BaseAnalyzer):
    """Classify hand gestures from existing hand landmark geometry.

    Consumes output from the 'hands' analyzer (HandLandmarkAnalyzer) to
    classify gestures using geometric heuristics. Does NOT require a separate
    ONNX model. Latency: <1ms.

    Output dict keys:
        left_gesture (str): gesture name from GESTURE_LABELS
        left_confidence (float): 0.0-1.0
        right_gesture (str): gesture name from GESTURE_LABELS
        right_confidence (float): 0.0-1.0
    """

    name = "hand_gesture"
    enabled = True

    def __init__(self, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._last_analysis = None

    def set_analysis(self, analysis: Dict[str, Any]) -> None:
        """Provide the full analysis dict so we can read hand landmarks."""
        self._last_analysis = analysis

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if frame is None or not self.enabled:
            return {}
        try:
            # Get hand landmarks from the analysis dict
            hands_data = {}
            if self._last_analysis and isinstance(self._last_analysis, dict):
                hands_data = self._last_analysis.get("hands", {})

            if not hands_data:
                return {}

            left_gesture = "none"
            left_confidence = 0.0
            right_gesture = "none"
            right_confidence = 0.0

            # Classify left hand
            left_landmarks = hands_data.get("left", None)
            if left_landmarks is not None and isinstance(left_landmarks, np.ndarray):
                if left_landmarks.size > 0 and left_landmarks.shape[0] >= 21:
                    left_gesture, left_confidence = _classify_gesture(left_landmarks)

            # Classify right hand
            right_landmarks = hands_data.get("right", None)
            if right_landmarks is not None and isinstance(right_landmarks, np.ndarray):
                if right_landmarks.size > 0 and right_landmarks.shape[0] >= 21:
                    right_gesture, right_confidence = _classify_gesture(right_landmarks)

            # Only return if at least one hand was classified
            if left_confidence == 0.0 and right_confidence == 0.0:
                return {}

            return {
                "left_gesture": left_gesture,
                "left_confidence": float(np.clip(left_confidence, 0.0, 1.0)),
                "right_gesture": right_gesture,
                "right_confidence": float(np.clip(right_confidence, 0.0, 1.0)),
            }
        except Exception:
            return {}
