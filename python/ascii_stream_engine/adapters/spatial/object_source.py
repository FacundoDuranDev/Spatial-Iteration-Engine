"""ObjectSpatialSource — extracts object detection ROIs."""

from typing import List, Optional, Set

from ...domain.types import ROI


class ObjectSpatialSource:
    """Converts object detections to ROIs.

    Expects analysis_data["objects"]["detections"] as list of dicts with
    "bbox" [x1, y1, x2, y2] normalized, "confidence", and "class_name".
    """

    name: str = "objects"

    def __init__(
        self,
        min_confidence: float = 0.0,
        class_filter: Optional[Set[str]] = None,
    ) -> None:
        """
        Args:
            min_confidence: Minimum detection confidence
            class_filter: If provided, only include these class names
        """
        self._min_confidence = min_confidence
        self._class_filter = class_filter

    def extract(self, analysis_data: dict) -> List[ROI]:
        obj_data = analysis_data.get("objects", {})
        if not isinstance(obj_data, dict):
            return []

        detections = obj_data.get("detections", [])
        if not isinstance(detections, list):
            return []

        rois: List[ROI] = []
        for det in detections:
            if not isinstance(det, dict):
                continue
            conf = float(det.get("confidence", 0.0))
            if conf < self._min_confidence:
                continue
            class_name = det.get("class_name", "")
            if self._class_filter is not None and class_name not in self._class_filter:
                continue
            bbox = det.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue
            # Convert [x1, y1, x2, y2] → [x, y, w, h]
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            rois.append(
                ROI(
                    x=x1,
                    y=y1,
                    w=x2 - x1,
                    h=y2 - y1,
                    confidence=conf,
                    label=class_name,
                )
            )
        return rois
