import os
import sys
from typing import Optional, Tuple

import cv2
import numpy as np


def _silence_stderr(f):
    """Decorador que redirige fd 2 a /dev/null durante la ejecución (silencia OpenCV C++)."""
    def _run(*args, **kwargs):
        stderr_fd = sys.stderr.fileno()
        save_fd = os.dup(stderr_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stderr_fd)
            return f(*args, **kwargs)
        finally:
            os.dup2(save_fd, stderr_fd)
            os.close(devnull)
            os.close(save_fd)
    return _run


class OpenCVCameraSource:
    def __init__(self, camera_index: int = 0, buffer_size: int = 1) -> None:
        self._camera_index = camera_index
        self._buffer_size = buffer_size
        self._cap: Optional[cv2.VideoCapture] = None

    def set_camera_index(self, camera_index: int) -> None:
        self._camera_index = camera_index

    def open(self) -> None:
        self.close()
        self._open_impl()

    @_silence_stderr
    def _open_impl(self) -> None:
        if sys.platform == "linux":
            cap = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self._camera_index)
        else:
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
