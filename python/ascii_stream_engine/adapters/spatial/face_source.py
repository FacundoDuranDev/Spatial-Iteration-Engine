"""FaceSpatialSource — extracts face ROIs from face analysis data."""

from typing import List

from ...domain.types import ROI


class FaceSpatialSource:
    """Extracts face bounding boxes as ROIs.

    Expects analysis_data["face"]["faces"] to be a list of dicts with
    "bbox" key containing [x, y, w, h] normalized and optional "confidence".
    """

    name: str = "face"

    def __init__(self, min_confidence: float = 0.0) -> None:
        self._min_confidence = min_confidence

    def extract(self, analysis_data: dict) -> List[ROI]:
        face_data = analysis_data.get("face", {})
        if not isinstance(face_data, dict):
            return []

        faces = face_data.get("faces", [])
        if not isinstance(faces, list):
            return []

        rois: List[ROI] = []
        for face in faces:
            if not isinstance(face, dict):
                continue
            bbox = face.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue
            conf = float(face.get("confidence", 1.0))
            if conf < self._min_confidence:
                continue
            face_landmarks = face.get("points", None)
            rois.append(
                ROI(
                    x=float(bbox[0]),
                    y=float(bbox[1]),
                    w=float(bbox[2]),
                    h=float(bbox[3]),
                    confidence=conf,
                    label="face",
                    landmarks=face_landmarks,
                )
            )
        return rois
