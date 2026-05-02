"""Sync bridge between WS handlers and the engine.

Phase A: only start/stop/snapshot. Phase B will add filter mutation methods
(toggle, set_param) backed by registry.py.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger("web_dashboard.bridge")


class EngineBridge:
    """Thread-safe wrapper around StreamEngine for the web dashboard.

    All filter mutations go through this object so we have one chokepoint
    for the lock and one source of truth for the snapshot. WS handlers
    (async) call these sync methods directly — they're microsecond ops.

    `start` and `stop` block 500 ms - 2 s opening/releasing the camera, so
    callers MUST wrap them in `loop.run_in_executor(None, ...)`.
    """

    def __init__(self, engine) -> None:
        self._engine = engine
        self._lock = threading.RLock()
        self._listeners: list[Callable[[dict], None]] = []

    @property
    def engine(self):
        return self._engine

    @property
    def running(self) -> bool:
        try:
            return bool(self._engine.is_running)
        except Exception:
            return False

    def start(self) -> None:
        with self._lock:
            try:
                self._engine.start(blocking=False)
            except Exception:
                logger.exception("engine.start failed")

    def stop(self) -> None:
        with self._lock:
            try:
                self._engine.stop()
            except Exception:
                logger.exception("engine.stop failed")

    def snapshot(self) -> dict:
        """Build a state dict matching ws_protocol.md §3.1.

        Phase A: filters dict is empty. Phase B fills it from registry.
        """
        with self._lock:
            running = self.running
            fps = 0.0
            lat_ms = 0.0
            metrics = getattr(self._engine, "_metrics", None)
            if metrics is not None:
                try:
                    fps = float(metrics.get_fps())
                except Exception:
                    fps = 0.0
                try:
                    lat_ms = float(metrics.get_latency_avg()) * 1000.0
                except Exception:
                    lat_ms = 0.0
            return {
                "type": "state",
                "running": running,
                "fps": round(fps, 1),
                "lat_ms": round(lat_ms, 1),
                "filters": {},  # Phase A stub; filled in Phase B
            }

    def add_listener(self, fn: Callable[[dict], None]) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[dict], None]) -> None:
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    def notify(self) -> None:
        snap = self.snapshot()
        for fn in list(self._listeners):
            try:
                fn(snap)
            except Exception:
                logger.exception("listener raised")
