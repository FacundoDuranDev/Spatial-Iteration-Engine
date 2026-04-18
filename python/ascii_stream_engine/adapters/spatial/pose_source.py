"""PoseSpatialSource — extracts pose ROIs from joint data."""

from typing import List, Optional, Sequence

import numpy as np

from ...domain.types import ROI


class PoseSpatialSource:
    """Computes bounding box from pose joints.

    Expects analysis_data["pose"]["joints"] as (N, 2) float32 normalized.
    """

    name: str = "pose"

    def __init__(
        self,
        padding: float = 0.05,
        joint_subset: Optional[Sequence[int]] = None,
    ) -> None:
        """
        Args:
            padding: Padding around the bounding box (normalized)
            joint_subset: If provided, only use these joint indices for bbox
        """
        self._padding = padding
        self._joint_subset = list(joint_subset) if joint_subset is not None else None

    def extract(self, analysis_data: dict) -> List[ROI]:
        pose_data = analysis_data.get("pose", {})
        if not isinstance(pose_data, dict):
            return []

        joints = pose_data.get("joints")
        if joints is None:
            return []

        joints = np.asarray(joints, dtype=np.float32)
        if joints.ndim != 2 or joints.shape[0] == 0 or joints.shape[1] < 2:
            return []

        pts = joints[:, :2]

        if self._joint_subset is not None:
            valid = [i for i in self._joint_subset if i < len(pts)]
            if not valid:
                return []
            pts = pts[valid]

        # Skip all-zero joints
        if np.all(pts == 0):
            return []

        # Filter out zero-valued joints (undetected)
        nonzero = np.any(pts != 0, axis=1)
        pts = pts[nonzero]
        if len(pts) == 0:
            return []

        x_min = max(0.0, float(np.min(pts[:, 0])) - self._padding)
        y_min = max(0.0, float(np.min(pts[:, 1])) - self._padding)
        x_max = min(1.0, float(np.max(pts[:, 0])) + self._padding)
        y_max = min(1.0, float(np.max(pts[:, 1])) + self._padding)

        return [
            ROI(
                x=x_min,
                y=y_min,
                w=x_max - x_min,
                h=y_max - y_min,
                confidence=1.0,
                label="pose",
                landmarks=joints[:, :2],
            )
        ]
