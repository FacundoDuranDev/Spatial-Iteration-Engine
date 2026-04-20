"""Sync bridge between WS handlers and the engine.

Phase B: filter mutation methods (toggle, set_param) backed by registry.py.
WIP filters are refused at the bridge layer (factory is None).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

from . import registry

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
        # Cache the registry list and lookup table at construction time so
        # the snapshot path stays branch-free.
        self._registry = registry.FILTERS
        self._registry_by_id = registry.FILTERS_BY_ID
        # Live filter instances, lazily created on first toggle/set_param.
        # Maps fid -> filter instance (already added to engine.filter_pipeline).
        self._instances: Dict[str, Any] = {}

    @property
    def engine(self):
        return self._engine

    @property
    def running(self) -> bool:
        # "Running" from the UI's POV = preview is live. The engine itself
        # may stay alive even between UI cycles — see start()/stop() docs.
        try:
            if not bool(self._engine.is_running):
                return False
        except Exception:
            return False
        # If the sink supports the _is_open flag (StickyPreviewSink), use
        # it so the UI flips OFFLINE the moment the user taps Detener.
        sink = getattr(self._engine, "_sink", None)
        if sink is not None and hasattr(sink, "_is_open"):
            try:
                return bool(sink._is_open)
            except Exception:
                pass
        return True

    def start(self) -> None:
        """Start (or resume) the preview.

        Cold path (first call): boot the engine — opens the camera and
        creates the cv2 window. Hot path (subsequent toggles): just
        unmute the sink. The engine itself stays running across cycles
        because StreamEngine.start/stop is racy when called in a tight
        loop (Qt namedWindow deadlocks, source.read blocks past
        stop_event, etc.). Keeping the engine warm sidesteps all of it.
        """
        with self._lock:
            try:
                if not self._engine.is_running:
                    self._engine.start(blocking=False)
                # Re-arm the sink even if the engine was already alive.
                sink = getattr(self._engine, "_sink", None)
                if sink is not None and hasattr(sink, "_is_open"):
                    sink._is_open = True
            except Exception:
                logger.exception("bridge.start failed")

    def stop(self) -> None:
        """Pause the preview without tearing the engine down.

        Mutes the sink (write() short-circuits) so the cv2 window
        freezes on the last frame and the FPS reading drops. The camera
        keeps capturing in the background — re-arming via start() is
        instant.
        """
        with self._lock:
            try:
                sink = getattr(self._engine, "_sink", None)
                if sink is not None and hasattr(sink, "_is_open"):
                    sink._is_open = False
            except Exception:
                logger.exception("bridge.stop failed")

    # --- filter mutation -------------------------------------------------

    def _filter_pipeline(self):
        """Return the engine's filter pipeline, or None if not yet wired."""
        return getattr(self._engine, "filter_pipeline", None)

    def _ensure(self, fid: str) -> Optional[Any]:
        """Return the live filter instance for ``fid``, creating it if needed.

        Returns ``None`` if the filter is WIP, unknown, or the engine doesn't
        expose a filter pipeline yet.
        """
        spec = self._registry_by_id.get(fid)
        if spec is None or spec.get("wip") or spec.get("factory") is None:
            return None
        inst = self._instances.get(fid)
        if inst is not None:
            return inst
        pipeline = self._filter_pipeline()
        if pipeline is None:
            logger.warning("ensure(%s): engine has no filter_pipeline yet", fid)
            return None
        try:
            inst = spec["factory"]()
        except Exception:
            logger.exception("ensure(%s): factory failed", fid)
            return None
        # Start disabled — the client must explicitly toggle on.
        try:
            inst.enabled = False
        except Exception:
            pass
        try:
            pipeline.add(inst)
        except Exception:
            logger.exception("ensure(%s): pipeline.add failed", fid)
            return None
        self._instances[fid] = inst
        return inst

    def toggle_filter(self, fid: str, on: bool) -> bool:
        """Enable/disable a filter. Returns True on success."""
        with self._lock:
            inst = self._ensure(fid)
            if inst is None:
                return False
            try:
                inst.enabled = bool(on)
                return True
            except Exception:
                logger.exception("toggle_filter(%s) failed", fid)
                return False

    def set_param(self, fid: str, pid: str, value: Any) -> bool:
        """Apply a param change. Value is assumed pre-clamped by the WS layer.

        Returns True if the apply callback ran without raising.
        """
        with self._lock:
            inst = self._ensure(fid)
            if inst is None:
                return False
            param = registry.find_param(fid, pid)
            if param is None:
                return False
            try:
                param["apply"](inst, value)
                return True
            except Exception:
                logger.exception("set_param(%s.%s)=%r failed", fid, pid, value)
                return False

    # --- snapshot --------------------------------------------------------

    def _filter_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Build the per-filter dict for the state message.

        Live params are read off the instance via the same attribute name
        the apply callback writes to (or the underlying private). For
        un-instantiated or WIP filters we fall back to defaults.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for spec in self._registry:
            fid = spec["id"]
            wip = bool(spec.get("wip"))
            inst = self._instances.get(fid)
            enabled = False
            if inst is not None:
                try:
                    enabled = bool(inst.enabled)
                except Exception:
                    enabled = False
            params: Dict[str, Any] = {}
            if wip or inst is None:
                # Default values until the filter is materialised.
                for p in spec["params"]:
                    params[p["id"]] = p["default"]
            else:
                params = self._read_live_params(fid, inst)
            out[fid] = {"enabled": enabled, "wip": wip, "params": params}
        return out

    def _read_live_params(self, fid: str, inst: Any) -> Dict[str, Any]:
        """Best-effort read of the current live param values from the instance."""
        spec = self._registry_by_id[fid]
        out: Dict[str, Any] = {}
        for p in spec["params"]:
            pid = p["id"]
            out[pid] = self._read_one_param(fid, inst, pid, p["default"])
        return out

    def _read_one_param(self, fid: str, inst: Any, pid: str, fallback: Any) -> Any:
        """Resolve the live value for a single param.

        We hand-map the small set of (fid, pid) pairs to the actual instance
        attribute since the underlying classes expose mixed public/private
        names. Unknown pairs fall back to the registry default.
        """
        try:
            if fid == "temporal_scan":
                if pid == "angle":
                    return float(getattr(inst, "angle_deg", fallback))
                if pid == "buffer":
                    return int(getattr(inst, "max_frames", fallback))
                if pid == "curve":
                    return getattr(inst, "curve", fallback)
            elif fid == "bc_cpp":
                if pid == "brightness":
                    val = getattr(inst, "_brightness_delta", None)
                    return int(val) if val is not None else fallback
                if pid == "contrast":
                    val = getattr(inst, "_contrast_factor", None)
                    return float(val) if val is not None else fallback
            elif fid == "bloom":
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "threshold":
                    return int(getattr(inst, "_threshold", fallback))
                if pid == "audio_react":
                    return float(getattr(inst, "_audio_reactive", fallback))
            elif fid == "chroma":
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
                if pid == "center_x":
                    return float(getattr(inst, "_center_x", fallback))
                if pid == "center_y":
                    return float(getattr(inst, "_center_y", fallback))
                if pid == "radial":
                    return bool(getattr(inst, "_radial", fallback))
            # invert has no params; nothing to read.
        except Exception:
            return fallback
        return fallback

    def snapshot(self) -> dict:
        """Build a state dict matching ws_protocol.md §3.1."""
        with self._lock:
            running = self.running
            fps = 0.0
            lat_ms = 0.0
            # When the UI is "stopped" we want fps/lat to read 0 even
            # though the engine thread keeps spinning. Metrics keep
            # counting; we just hide them.
            if running:
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
                "filters": self._filter_snapshot(),
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
