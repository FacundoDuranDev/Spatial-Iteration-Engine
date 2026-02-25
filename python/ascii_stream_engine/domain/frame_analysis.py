"""Frame analysis data structures for perception (face, hands, pose, etc.). MVP_03."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class FaceAnalysis:
    """Face landmarks (normalized 0-1). Up to 468 points."""

    points: np.ndarray  # (N, 2) float32


@dataclass
class HandAnalysis:
    """Hand landmarks. 21 points per hand."""

    left: np.ndarray  # (21, 2) float32
    right: np.ndarray  # (21, 2) float32


@dataclass
class PoseAnalysis:
    """Body pose. 17 or 33 joints."""

    joints: np.ndarray  # (N, 2) float32


@dataclass
class HandGestureAnalysis:
    """Gesture classification for each hand."""

    left_gesture: str  # gesture class name
    left_confidence: float  # 0.0-1.0
    right_gesture: str  # gesture class name
    right_confidence: float  # 0.0-1.0


@dataclass
class ObjectDetection:
    """Single detected object."""

    class_id: int
    class_name: str
    confidence: float
    bbox: np.ndarray  # (4,) float32 [x1, y1, x2, y2] normalized 0-1


@dataclass
class ObjectDetectionAnalysis:
    """Object detection results."""

    detections: list  # list of ObjectDetection
    count: int


@dataclass
class EmotionAnalysis:
    """Facial emotion classification."""

    expression: str  # dominant emotion label
    confidence: float  # 0.0-1.0
    scores: np.ndarray  # (7,) float32


@dataclass
class PoseSkeletonAnalysis:
    """Enhanced pose with confidence and skeleton connectivity."""

    joints: np.ndarray  # (17, 2) float32 normalized 0-1
    confidences: np.ndarray  # (17,) float32
    edges: list  # list of (int, int) tuples
    visible_mask: np.ndarray  # (17,) bool


@dataclass
class SegmentationAnalysis:
    """Scene segmentation mask."""

    mask: np.ndarray  # (H, W) uint8, class index per pixel
    person_mask: np.ndarray  # (H, W) bool
    num_classes: int
