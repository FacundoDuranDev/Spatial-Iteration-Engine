"""Metrics aggregator with time-series windowing.

Collects snapshots from EngineMetrics and LoopProfiler into
time-series windows for dashboard consumption.
"""

import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates metrics from EngineMetrics and LoopProfiler into time-series windows.

    Thread-safe with threading.Lock.
    All timing uses time.perf_counter().
    """

    def __init__(
        self,
        window_size_seconds: float = 10.0,
        max_windows: int = 360,
        sample_interval: float = 1.0,
    ) -> None:
        """Initialize the metrics aggregator.

        Args:
            window_size_seconds: Size of each aggregation window.
            max_windows: Maximum number of windows to store (default 360 = 1h at 10s).
            sample_interval: Minimum interval between snapshots.
        """
        self._window_size_seconds = window_size_seconds
        self._max_windows = max_windows
        self._sample_interval = sample_interval
        self._lock = threading.Lock()

        # Bounded snapshot storage
        self._snapshots: deque = deque(maxlen=max_windows)
        self._last_snapshot_time: Optional[float] = None

    def record_snapshot(self, metrics_summary: Dict, profiler_summary: Dict) -> None:
        """Record a metrics snapshot.

        Args:
            metrics_summary: Output from EngineMetrics.get_summary().
            profiler_summary: Output from LoopProfiler.get_summary_dict().
        """
        now = time.perf_counter()

        with self._lock:
            # Enforce sample interval
            if (
                self._last_snapshot_time is not None
                and (now - self._last_snapshot_time) < self._sample_interval
            ):
                return

            snapshot = {
                "timestamp": now,
                "fps": metrics_summary.get("fps", 0.0),
                "frames_processed": metrics_summary.get("frames_processed", 0),
                "frame_time_ms": metrics_summary.get("latency_avg", 0.0) * 1000.0,
                "total_errors": metrics_summary.get("total_errors", 0),
                "errors": metrics_summary.get("errors_by_component", {}),
                "phases": {},
            }

            # Add per-phase timing from profiler
            for phase, stats in profiler_summary.items():
                snapshot["phases"][phase] = {
                    "avg_ms": stats.get("avg_time", 0.0) * 1000.0,
                    "min_ms": stats.get("min_time", 0.0) * 1000.0,
                    "max_ms": stats.get("max_time", 0.0) * 1000.0,
                    "count": stats.get("count", 0),
                }

            self._snapshots.append(snapshot)
            self._last_snapshot_time = now

    def get_latest(self) -> Optional[Dict]:
        """Get the most recent snapshot.

        Returns:
            Latest snapshot dict or None if no data.
        """
        with self._lock:
            if not self._snapshots:
                return None
            return dict(self._snapshots[-1])

    def get_window(self, seconds: float = 60.0) -> List[Dict]:
        """Get snapshots within a time window.

        Args:
            seconds: Number of seconds of history to return.

        Returns:
            List of snapshot dicts within the window.
        """
        now = time.perf_counter()
        cutoff = now - seconds
        with self._lock:
            return [dict(s) for s in self._snapshots if s["timestamp"] >= cutoff]

    def get_trend(self, metric_key: str, seconds: float = 60.0) -> List[Tuple[float, float]]:
        """Get a time-series of a specific metric.

        Args:
            metric_key: Key to extract from snapshots (e.g., "fps", "frame_time_ms").
            seconds: Number of seconds of history.

        Returns:
            List of (timestamp, value) tuples.
        """
        now = time.perf_counter()
        cutoff = now - seconds
        with self._lock:
            result = []
            for s in self._snapshots:
                if s["timestamp"] < cutoff:
                    continue
                value = s.get(metric_key)
                if value is not None:
                    result.append((s["timestamp"], value))
            return result

    def get_snapshot_count(self) -> int:
        """Get the number of stored snapshots.

        Returns:
            Number of snapshots.
        """
        with self._lock:
            return len(self._snapshots)

    def reset(self) -> None:
        """Reset all stored snapshots."""
        with self._lock:
            self._snapshots.clear()
            self._last_snapshot_time = None
