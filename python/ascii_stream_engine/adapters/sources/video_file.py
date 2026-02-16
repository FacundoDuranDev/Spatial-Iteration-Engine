"""Fuente de frames desde un archivo de video (OpenCV)."""

from typing import Optional

import cv2
import numpy as np


class VideoFileSource:
    """FrameSource que lee desde un archivo de video (.mp4, .avi, etc.)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        self.close()
        self._cap = cv2.VideoCapture(self._path)

    def read(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
