from contextlib import contextmanager
import threading
from typing import Dict, Iterable, Iterator, List, Optional

import numpy as np

from .config import EngineConfig


class AnalyzerPipeline:
    def __init__(self, analyzers: Optional[Iterable[object]] = None) -> None:
        self._analyzers: List[object] = list(analyzers) if analyzers else []
        self._lock = threading.Lock()

    @property
    def analyzers(self) -> List[object]:
        return self._analyzers

    def snapshot(self) -> List[object]:
        with self._lock:
            return list(self._analyzers)

    def append(self, analyzer: object) -> None:
        with self._lock:
            self._analyzers.append(analyzer)

    def extend(self, analyzers: Iterable[object]) -> None:
        with self._lock:
            self._analyzers.extend(analyzers)

    def insert(self, index: int, analyzer: object) -> None:
        with self._lock:
            self._analyzers.insert(index, analyzer)

    def remove(self, analyzer: object) -> None:
        with self._lock:
            self._analyzers.remove(analyzer)

    def pop(self, index: int = -1) -> object:
        with self._lock:
            return self._analyzers.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._analyzers.clear()

    def replace(self, analyzers: Iterable[object]) -> None:
        with self._lock:
            self._analyzers = list(analyzers)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        changed = False
        with self._lock:
            for analyzer in self._analyzers:
                analyzer_name = getattr(analyzer, "name", analyzer.__class__.__name__)
                if analyzer_name == name:
                    if hasattr(analyzer, "enabled"):
                        setattr(analyzer, "enabled", enabled)
                        changed = True
        return changed

    def has_any(self) -> bool:
        with self._lock:
            return bool(self._analyzers)

    def run(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, object]:
        results: Dict[str, object] = {}
        for analyzer in self.snapshot():
            if hasattr(analyzer, "enabled") and not getattr(analyzer, "enabled"):
                continue
            name = getattr(analyzer, "name", analyzer.__class__.__name__)
            results[name] = analyzer.analyze(frame, config)
        return results

    @contextmanager
    def locked(self) -> Iterator[List[object]]:
        with self._lock:
            yield self._analyzers


class FilterPipeline:
    def __init__(self, filters: Optional[Iterable[object]] = None) -> None:
        self._filters: List[object] = list(filters) if filters else []
        self._lock = threading.Lock()

    @property
    def filters(self) -> List[object]:
        return self._filters

    def snapshot(self) -> List[object]:
        with self._lock:
            return list(self._filters)

    def append(self, filter_obj: object) -> None:
        with self._lock:
            self._filters.append(filter_obj)

    def extend(self, filters: Iterable[object]) -> None:
        with self._lock:
            self._filters.extend(filters)

    def insert(self, index: int, filter_obj: object) -> None:
        with self._lock:
            self._filters.insert(index, filter_obj)

    def remove(self, filter_obj: object) -> None:
        with self._lock:
            self._filters.remove(filter_obj)

    def pop(self, index: int = -1) -> object:
        with self._lock:
            return self._filters.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._filters.clear()

    def replace(self, filters: Iterable[object]) -> None:
        with self._lock:
            self._filters = list(filters)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        changed = False
        with self._lock:
            for filter_obj in self._filters:
                filter_name = getattr(filter_obj, "name", filter_obj.__class__.__name__)
                if filter_name == name:
                    if hasattr(filter_obj, "enabled"):
                        setattr(filter_obj, "enabled", enabled)
                        changed = True
        return changed

    def apply(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> np.ndarray:
        processed = frame
        for filter_obj in self.snapshot():
            if hasattr(filter_obj, "enabled") and not getattr(filter_obj, "enabled"):
                continue
            processed = filter_obj.apply(processed, config, analysis)
        return processed

    @contextmanager
    def locked(self) -> Iterator[List[object]]:
        with self._lock:
            yield self._filters
