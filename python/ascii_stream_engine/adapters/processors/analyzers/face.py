from typing import List, Optional

import cv2

from .base import BaseAnalyzer


class FaceHaarAnalyzer(BaseAnalyzer):
    name = "faces"

    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: tuple = (30, 30),
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        if cascade_path is None:
            cascade_path = (
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        self._classifier = cv2.CascadeClassifier(cascade_path)
        if self._classifier.empty():
            raise ValueError(f"No se pudo cargar cascade: {cascade_path}")
        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors
        self._min_size = min_size

    def analyze(self, frame, config) -> List[dict]:
        if frame is None:
            return []
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        faces = self._classifier.detectMultiScale(
            gray,
            scaleFactor=self._scale_factor,
            minNeighbors=self._min_neighbors,
            minSize=self._min_size,
        )
        return [
            {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
            for (x, y, w, h) in faces
        ]
