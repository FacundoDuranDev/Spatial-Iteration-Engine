from typing import Optional, Tuple

import cv2
import numpy as np


class OpenCVCameraSource:
    def __init__(self, camera_index: int = 0, buffer_size: int = 1) -> None:
        self._camera_index = camera_index
        self._buffer_size = buffer_size
        self._cap: Optional[cv2.VideoCapture] = None

    def set_camera_index(self, camera_index: int) -> None:
        self._camera_index = camera_index

    def open(self) -> None:
        self.close()
        cap = cv2.VideoCapture(self._camera_index)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, self._buffer_size)
        self._cap = cap

    def read(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def read_with_timestamp(self) -> Optional[Tuple[np.ndarray, float]]:
        frame = self.read()
        if frame is None:
            return None
        return frame, cv2.getTickCount() / cv2.getTickFrequency()

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
