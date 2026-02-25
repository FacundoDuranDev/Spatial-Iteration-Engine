"""Enhanced pose analyzer with per-joint confidence and skeleton edges. MVP_03.

Extends the existing pose detection with confidence scores per keypoint and
COCO skeleton edge definitions. Reuses the same YOLOv8n-pose model via
perception_cpp.detect_pose_with_confidence.

Output schema:
    analysis["pose_skeleton"] = {
        "joints": np.ndarray,          # (17, 2) float32 normalized 0-1, (x, y) per joint
        "confidences": np.ndarray,     # (17,) float32 per-joint confidence 0-1
        "edges": list,                 # list of (int, int) tuples for skeleton connections
        "visible_mask": np.ndarray,    # (17,) bool, True if confidence > threshold
    }
"""

from typing import Any, Dict, List, Tuple

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import perception_cpp as _perception_cpp

    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False

# COCO skeleton edges (17 keypoints)
# 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
# 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
# 9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
# 13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle
COCO_SKELETON: List[Tuple[int, int]] = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),  # head
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),  # arms
    (5, 11),
    (6, 12),
    (11, 12),  # torso
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),  # legs
]

_NUM_KEYPOINTS = 17
_CONFIDENCE_THRESHOLD = 0.3


class PoseSkeletonAnalyzer(BaseAnalyzer):
    """Enhanced pose with per-joint confidence and skeleton connectivity.

    Delegates to perception_cpp.detect_pose_with_confidence which returns
    (x, y, confidence) triplets for each of 17 COCO keypoints. Normalizes
    coordinates to 0-1 and provides skeleton edge definitions.

    Output dict keys:
        joints (np.ndarray): (17, 2) float32 normalized 0-1
        confidences (np.ndarray): (17,) float32 per-joint confidence
        edges (list): list of (int, int) tuples for skeleton connections
        visible_mask (np.ndarray): (17,) bool, True if confidence > 0.3
    """

    name = "pose_skeleton"
    enabled = True

    # Frame-skipping for heavy analyzers (shares model with pose)
    _skip_interval = 2
    _frame_count = 0
    _last_result: Dict[str, Any] = {}

    def __init__(self, enabled: bool = True, skip_interval: int = 2) -> None:
        super().__init__(enabled=enabled)
        self._skip_interval = max(1, skip_interval)
        self._frame_count = 0
        self._last_result = {}

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None or not self.enabled:
            return {}
        try:
            # Frame skipping
            self._frame_count += 1
            if self._skip_interval > 1 and self._frame_count % self._skip_interval != 0:
                return self._last_result

            raw = _perception_cpp.detect_pose_with_confidence(frame)
            if raw is None or raw.size == 0:
                self._last_result = {}
                return {}

            # C++ returns flat array of (x, y, confidence) triplets
            raw_flat = raw.flatten()
            if raw_flat.size < _NUM_KEYPOINTS * 3:
                self._last_result = {}
                return {}

            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            # Reshape to (N, 3): x, y, confidence
            triplets = raw_flat[: _NUM_KEYPOINTS * 3].reshape(_NUM_KEYPOINTS, 3)

            # Separate joints and confidences
            joints = np.zeros((_NUM_KEYPOINTS, 2), dtype=np.float32)
            confidences = np.zeros(_NUM_KEYPOINTS, dtype=np.float32)

            # Normalize pixel coordinates to 0-1
            joints[:, 0] = triplets[:, 0] / w
            joints[:, 1] = triplets[:, 1] / h
            np.clip(joints, 0.0, 1.0, out=joints)

            confidences[:] = triplets[:, 2]
            np.clip(confidences, 0.0, 1.0, out=confidences)

            # Visible mask: joints above confidence threshold
            visible_mask = confidences > _CONFIDENCE_THRESHOLD

            result = {
                "joints": joints,
                "confidences": confidences,
                "edges": list(COCO_SKELETON),
                "visible_mask": visible_mask,
            }
            self._last_result = result
            return result
        except Exception:
            return {}
