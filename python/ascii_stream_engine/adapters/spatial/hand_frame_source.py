"""HandFrameSpatialSource — extracts a single ROI spanning both hands (thumb+index frame)."""

from typing import List

import numpy as np

from ...domain.types import ROI


class HandFrameSpatialSource:
    """Computes the bounding rectangle formed by index tips and thumb tips across both hands.

    Uses landmarks 4 (thumb tip) and 8 (index tip) from each hand to define
    4 corners. Returns a single ROI enclosing the region between both hands.

    Expects analysis_data["hands"] with "left" AND "right" keys containing
    (21, 2) float32 landmark arrays (normalized 0-1).
    """

    name: str = "hand_frame"

    THUMB_TIP = 4
    INDEX_TIP = 8

    def __init__(self, padding: float = 0.0, min_size: float = 0.02) -> None:
        self._padding = padding
        self._min_size = min_size

    def extract(self, analysis_data: dict) -> List[ROI]:
        hands_data = analysis_data.get("hands", {})
        if not isinstance(hands_data, dict):
            return []

        left = hands_data.get("left")
        right = hands_data.get("right")

        if left is None or right is None:
            return []

        left = np.asarray(left, dtype=np.float32)
        right = np.asarray(right, dtype=np.float32)

        min_len = max(self.THUMB_TIP, self.INDEX_TIP) + 1
        if left.ndim != 2 or left.shape[0] < min_len:
            return []
        if right.ndim != 2 or right.shape[0] < min_len:
            return []

        # 4 corner points: index tips + thumb tips
        corners = np.array([
            left[self.INDEX_TIP, :2],
            right[self.INDEX_TIP, :2],
            left[self.THUMB_TIP, :2],
            right[self.THUMB_TIP, :2],
        ], dtype=np.float32)

        x_min = float(np.min(corners[:, 0]))
        x_max = float(np.max(corners[:, 0]))
        y_min = float(np.min(corners[:, 1]))
        y_max = float(np.max(corners[:, 1]))

        w = x_max - x_min
        h = y_max - y_min

        if w < self._min_size and h < self._min_size:
            return []

        # Apply padding
        x_min = max(0.0, x_min - self._padding)
        y_min = max(0.0, y_min - self._padding)
        x_max = min(1.0, x_max + self._padding)
        y_max = min(1.0, y_max + self._padding)

        return [ROI(
            x=x_min,
            y=y_min,
            w=x_max - x_min,
            h=y_max - y_min,
            confidence=1.0,
            label="hand_frame",
            landmarks=corners,
        )]
