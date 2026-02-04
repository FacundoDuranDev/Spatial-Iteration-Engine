from contextlib import contextmanager
import threading
from typing import Iterable, Iterator, List, Optional, Protocol

import cv2
import numpy as np

from .config import AsciiStreamConfig


class FrameFilter(Protocol):
    def apply(
        self,
        frame: np.ndarray,
        config: AsciiStreamConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        ...


class FilterPipeline:
    def __init__(self, filters: Optional[Iterable[FrameFilter]] = None) -> None:
        self._filters: List[FrameFilter] = list(filters) if filters is not None else []
        self._lock = threading.Lock()

    @property
    def filters(self) -> List[FrameFilter]:
        return self._filters

    def snapshot(self) -> List[FrameFilter]:
        with self._lock:
            return list(self._filters)

    def append(self, filter_obj: FrameFilter) -> None:
        with self._lock:
            self._filters.append(filter_obj)

    def extend(self, filters: Iterable[FrameFilter]) -> None:
        with self._lock:
            self._filters.extend(filters)

    def insert(self, index: int, filter_obj: FrameFilter) -> None:
        with self._lock:
            self._filters.insert(index, filter_obj)

    def remove(self, filter_obj: FrameFilter) -> None:
        with self._lock:
            self._filters.remove(filter_obj)

    def pop(self, index: int = -1) -> FrameFilter:
        with self._lock:
            return self._filters.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._filters.clear()

    def replace(self, filters: Iterable[FrameFilter]) -> None:
        with self._lock:
            self._filters = list(filters)

    @contextmanager
    def locked(self) -> Iterator[List[FrameFilter]]:
        with self._lock:
            yield self._filters


class GrayscaleFilter:
    def apply(
        self,
        frame: np.ndarray,
        config: AsciiStreamConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


class ContrastBrightnessFilter:
    def apply(
        self,
        frame: np.ndarray,
        config: AsciiStreamConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if config.contrast == 1.0 and config.brightness == 0:
            return frame
        return cv2.convertScaleAbs(
            frame, alpha=float(config.contrast), beta=int(config.brightness)
        )


class InvertFilter:
    def apply(
        self,
        frame: np.ndarray,
        config: AsciiStreamConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if not config.invert:
            return frame
        return 255 - frame
