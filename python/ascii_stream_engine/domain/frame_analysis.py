"""Estructuras de análisis de frame para percepción (face, hands, pose). MVP_03."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class FaceAnalysis:
    """Landmarks faciales (normalizados 0–1). MediaPipe: 468 puntos."""
    points: np.ndarray  # (468, 2) o (N, 2)


@dataclass
class HandAnalysis:
    """Landmarks de manos. 21 puntos por mano."""
    left: np.ndarray   # (21, 2)
    right: np.ndarray  # (21, 2)


@dataclass
class PoseAnalysis:
    """Pose corporal. 33 joints."""
    joints: np.ndarray  # (33, 2)
