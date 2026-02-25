"""Emotion detection analyzer using C++ perception_cpp. MVP_03.

Classifies facial expression/emotion from the frame. Uses a lightweight
classification model that outputs raw logits for 7 emotion classes.

Output schema:
    analysis["emotion"] = {
        "expression": str,             # dominant emotion label
        "confidence": float,           # 0.0-1.0
        "scores": np.ndarray,          # (7,) float32, score per class, sums to ~1.0
    }

Emotion classes: "neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"
"""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import perception_cpp as _perception_cpp

    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False

# 7 emotion class labels (FER standard order)
EMOTION_LABELS = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Compute softmax probabilities from logits, numerically stable."""
    shifted = logits - np.max(logits)
    exp_vals = np.exp(shifted)
    return exp_vals / np.sum(exp_vals)


class EmotionAnalyzer(BaseAnalyzer):
    """Facial emotion classification via perception_cpp.detect_emotion.

    Delegates inference to C++ OnnxRunner. Applies softmax to raw logits
    and maps to 7 FER emotion labels.

    Output dict keys:
        expression (str): dominant emotion from EMOTION_LABELS
        confidence (float): 0.0-1.0 confidence of top prediction
        scores (np.ndarray): (7,) float32, softmax probabilities
    """

    name = "emotion"
    enabled = True

    # Frame-skipping for heavy analyzers
    _skip_interval = 3
    _frame_count = 0
    _last_result: Dict[str, Any] = {}

    def __init__(self, enabled: bool = True, skip_interval: int = 3) -> None:
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

            raw = _perception_cpp.detect_emotion(frame)
            if raw is None or raw.size == 0:
                self._last_result = {}
                return {}

            logits = raw.flatten().astype(np.float32)

            # Expect exactly 7 logits for 7 emotion classes
            if len(logits) < 7:
                self._last_result = {}
                return {}

            # Use only the first 7 values
            logits = logits[:7]

            # Apply softmax
            scores = _softmax(logits)

            # Get dominant emotion
            idx = int(np.argmax(scores))
            expression = EMOTION_LABELS[idx] if idx < len(EMOTION_LABELS) else "neutral"
            confidence = float(np.clip(scores[idx], 0.0, 1.0))

            result = {
                "expression": expression,
                "confidence": confidence,
                "scores": scores,
            }
            self._last_result = result
            return result
        except Exception:
            return {}
