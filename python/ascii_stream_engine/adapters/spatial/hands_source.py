"""HandsSpatialSource — extracts hand ROIs from hand landmark data."""

from typing import List

import numpy as np

from ...domain.types import ROI


class HandsSpatialSource:
    """Computes bounding boxes from hand landmarks.

    Expects analysis_data["hands"] with "left" and/or "right" keys
    containing (21, 2) float32 landmark arrays (normalized 0-1).
    """

    name: str = "hands"

    def __init__(self, hands: str = "both", padding: float = 0.05) -> None:
        """
        Args:
            hands: "both", "left", or "right"
            padding: Padding around the bounding box (normalized)
        """
        if hands not in ("both", "left", "right"):
            raise ValueError(f"hands must be 'both', 'left', or 'right', got {hands!r}")
        self._hands = hands
        self._padding = padding

    def extract(self, analysis_data: dict) -> List[ROI]:
        hands_data = analysis_data.get("hands", {})
        if not isinstance(hands_data, dict):
            return []

        rois: List[ROI] = []
        sides = []
        if self._hands in ("both", "left"):
            sides.append("left")
        if self._hands in ("both", "right"):
            sides.append("right")

        for side in sides:
            landmarks = hands_data.get(side)
            if landmarks is None:
                continue
            landmarks = np.asarray(landmarks, dtype=np.float32)
            if landmarks.ndim != 2 or landmarks.shape[0] == 0 or landmarks.shape[1] < 2:
                continue
            # Skip all-zero landmarks (not detected)
            if np.all(landmarks[:, :2] == 0):
                continue

            roi = self._bbox_from_landmarks(landmarks[:, :2], side)
            if roi is not None:
                rois.append(roi)
        return rois

    def _bbox_from_landmarks(self, pts: np.ndarray, side: str) -> ROI:
        """Compute padded bounding box from landmark points."""
        x_min = float(np.min(pts[:, 0]))
        x_max = float(np.max(pts[:, 0]))
        y_min = float(np.min(pts[:, 1]))
        y_max = float(np.max(pts[:, 1]))

        x_min = max(0.0, x_min - self._padding)
        y_min = max(0.0, y_min - self._padding)
        x_max = min(1.0, x_max + self._padding)
        y_max = min(1.0, y_max + self._padding)

        w = x_max - x_min
        h = y_max - y_min

        return ROI(
            x=x_min,
            y=y_min,
            w=w,
            h=h,
            confidence=1.0,
            label=f"hand_{side}",
            landmarks=pts,
        )
