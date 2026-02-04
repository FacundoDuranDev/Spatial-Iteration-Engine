from contextlib import contextmanager
import threading
from typing import Any, Dict, Iterable, Iterator, List, Optional, Protocol, Tuple

import cv2
import numpy as np

from .config import AsciiStreamConfig


class FrameAnalyzer(Protocol):
    name: str

    def analyze(self, frame: np.ndarray, config: AsciiStreamConfig) -> Any:
        ...


class AnalyzerPipeline:
    def __init__(self, analyzers: Optional[Iterable[FrameAnalyzer]] = None) -> None:
        self._analyzers: List[FrameAnalyzer] = (
            list(analyzers) if analyzers is not None else []
        )
        self._lock = threading.Lock()

    @property
    def analyzers(self) -> List[FrameAnalyzer]:
        return self._analyzers

    def snapshot(self) -> List[FrameAnalyzer]:
        with self._lock:
            return list(self._analyzers)

    def append(self, analyzer: FrameAnalyzer) -> None:
        with self._lock:
            self._analyzers.append(analyzer)

    def extend(self, analyzers: Iterable[FrameAnalyzer]) -> None:
        with self._lock:
            self._analyzers.extend(analyzers)

    def insert(self, index: int, analyzer: FrameAnalyzer) -> None:
        with self._lock:
            self._analyzers.insert(index, analyzer)

    def remove(self, analyzer: FrameAnalyzer) -> None:
        with self._lock:
            self._analyzers.remove(analyzer)

    def pop(self, index: int = -1) -> FrameAnalyzer:
        with self._lock:
            return self._analyzers.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._analyzers.clear()

    def replace(self, analyzers: Iterable[FrameAnalyzer]) -> None:
        with self._lock:
            self._analyzers = list(analyzers)

    def has_any(self) -> bool:
        with self._lock:
            return bool(self._analyzers)

    def run(self, frame: np.ndarray, config: AsciiStreamConfig) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for analyzer in self.snapshot():
            name = getattr(analyzer, "name", analyzer.__class__.__name__)
            results[name] = analyzer.analyze(frame, config)
        return results

    @contextmanager
    def locked(self) -> Iterator[List[FrameAnalyzer]]:
        with self._lock:
            yield self._analyzers


class FaceHaarAnalyzer:
    name = "faces"

    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: Tuple[int, int] = (30, 30),
    ) -> None:
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

    def analyze(
        self, frame: np.ndarray, config: AsciiStreamConfig
    ) -> List[Tuple[int, int, int, int]]:
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
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]


class MediaPipeHandAnalyzer:
    name = "hands"

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise ImportError(
                "Para usar MediaPipe, instala: python -m pip install mediapipe"
            ) from exc

        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def analyze(
        self, frame: np.ndarray, config: AsciiStreamConfig
    ) -> List[List[Dict[str, float]]]:
        if frame.ndim == 2:
            rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)
        if not results.multi_hand_landmarks:
            return []
        h, w = frame.shape[:2]
        hands: List[List[Dict[str, float]]] = []
        for hand_landmarks in results.multi_hand_landmarks:
            points = []
            for lm in hand_landmarks.landmark:
                points.append(
                    {
                        "x": float(lm.x * w),
                        "y": float(lm.y * h),
                        "z": float(lm.z),
                    }
                )
            hands.append(points)
        return hands
