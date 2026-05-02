"""Sync bridge between WS handlers and the engine.

Phase B: filter mutation methods (toggle, set_param) backed by registry.py.
WIP filters are refused at the bridge layer (factory is None).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import registry

logger = logging.getLogger("web_dashboard.bridge")

# Persistencia de mappings — mismo directorio que `presets.json` del notebook
# (ver `presentation/notebook_api.py:2355`). Schema versionado v1.
MODULATIONS_FILE = Path.home() / ".ascii_stream_engine" / "modulations.json"
MODULATIONS_SCHEMA_VERSION = 1


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

        # Modulation: SignalBus + MediaPipeSignalSource + ModulationEngine.
        # Sin mappings activos no consume nada (tick es no-op). El bridge
        # es dueño del lifecycle porque acá viven los chokepoints (set_param)
        # y la persistencia futura (Fase 3).
        from ....application.modulation import (
            MediaPipeSignalSource,
            ModulationEngine,
            SignalBus,
        )

        self._signal_bus = SignalBus()
        self._signal_sources = [MediaPipeSignalSource()]
        self._mod_engine = ModulationEngine(self._signal_bus)
        try:
            engine.attach_modulation(
                self._mod_engine,
                self._signal_bus,
                self._signal_sources,
                self.set_param,
            )
        except Exception:
            logger.exception("attach_modulation failed; continuing without it")

        # Auto-load mappings persistidos. Si el archivo no existe (primera
        # run) o está corrupto, arrancamos vacío sin tirar — el usuario
        # vuelve a crearlos desde la UI.
        self._load_modulations()

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

    # --- tracking control ----------------------------------------------

    def _find_overlay_renderer(self):
        """Walk the renderer chain looking for an OverlayCapable adapter.

        Usamos `isinstance(r, OverlayCapable)` en vez de comparar
        `__class__.__name__` — el bridge no debería conocer la clase
        concreta. Cualquier renderer que cumpla el Protocol funciona.
        """
        from ....ports.overlay_capable import OverlayCapable

        r = getattr(self._engine, "get_renderer", lambda: None)()
        seen = set()
        while r is not None and id(r) not in seen:
            seen.add(id(r))
            if isinstance(r, OverlayCapable):
                return r
            r = getattr(r, "inner", None)
        return None

    def toggle_analyzer(self, name: str, on: bool) -> bool:
        """Habilita/deshabilita un analyzer por nombre (face / hands / pose / ...).

        Returns True si el analyzer existe y se modificó. La AnalyzerPipeline
        ya expone `set_enabled(name, enabled)` y respeta el flag en `run()`,
        así que un analyzer deshabilitado no consume CPU.
        """
        with self._lock:
            pipeline = getattr(self._engine, "analyzer_pipeline", None)
            if pipeline is None:
                return False
            try:
                return bool(pipeline.set_enabled(name, bool(on)))
            except Exception:
                logger.exception("toggle_analyzer(%s) failed", name)
                return False

    def toggle_overlay(self, on: bool) -> bool:
        """Muestra/oculta los landmarks dibujados en el preview.

        El analyzer puede seguir corriendo (sigue alimentando filtros y el
        ModulationEngine futuro) — esto controla SOLO el dibujo encima del
        frame. Devuelve False si el renderer activo no es overlay-capable.
        """
        with self._lock:
            overlay = self._find_overlay_renderer()
            if overlay is None:
                return False
            try:
                overlay.overlay_enabled = bool(on)
                return True
            except Exception:
                logger.exception("toggle_overlay failed")
                return False

    def _tracking_state(self) -> Dict[str, Any]:
        """Snapshot del estado de tracking — para UI mobile y debugging.

        Counts vienen del último analysis cacheado por el engine; pueden
        quedar en 0 si MediaPipe no detectó nada o si el analyzer está off.
        """
        face_enabled = False
        hands_enabled = False
        pipeline = getattr(self._engine, "analyzer_pipeline", None)
        if pipeline is not None:
            try:
                for a in pipeline.snapshot():
                    nm = getattr(a, "name", a.__class__.__name__)
                    if nm == "face":
                        face_enabled = bool(getattr(a, "enabled", True))
                    elif nm == "hands":
                        hands_enabled = bool(getattr(a, "enabled", True))
            except Exception:
                pass
        overlay = self._find_overlay_renderer()
        overlay_enabled = bool(getattr(overlay, "overlay_enabled", False)) if overlay else False
        face_count = 0
        hands_count = 0
        try:
            getter = getattr(self._engine, "get_last_analysis", None)
            last = getter() if callable(getter) else {}
            face = last.get("face") or {}
            if isinstance(face, dict):
                faces = face.get("faces") or []
                face_count = len(faces) if isinstance(faces, list) else 0
            hands = last.get("hands") or {}
            if isinstance(hands, dict):
                left = hands.get("left")
                right = hands.get("right")
                if left is not None and getattr(left, "size", 0) > 0:
                    hands_count += 1
                if right is not None and getattr(right, "size", 0) > 0:
                    hands_count += 1
        except Exception:
            pass
        return {
            "face_enabled": face_enabled,
            "hands_enabled": hands_enabled,
            "overlay_enabled": overlay_enabled,
            "overlay_available": overlay is not None,
            "face_count": face_count,
            "hands_count": hands_count,
        }

    # --- modulation ----------------------------------------------------

    def list_signals(self) -> List[str]:
        """Catálogo estático de señales disponibles para mapear.

        Estático = no depende de si MediaPipe detectó algo. Lo construimos
        agregando lo que cada SignalSource registrada declara.
        """
        out: List[str] = []
        for src in self._signal_sources:
            try:
                out.extend(src.declared_signals())
            except Exception:
                logger.exception("signal source declared_signals failed")
        # Mantener orden estable, sin duplicados (preserva el orden de
        # primera aparición — útil para la UI).
        seen = set()
        unique: List[str] = []
        for s in out:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique

    def list_modulations(self) -> List[Dict[str, Any]]:
        """Snapshot serializable de los mappings actuales — para snapshot/UI."""
        with self._lock:
            return [m.to_dict() for m in self._mod_engine.list()]

    def add_modulation(self, payload: Dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
        """Crea un mapping. Devuelve (idx, None) ok o (None, error_msg).

        Persiste a disco antes de devolver — si el save falla, el mapping
        sí queda activo en memoria pero loggeamos warn (no rollback). El
        UX es: "el mapping te funciona ya, pero al reiniciar capaz se
        pierde". Mejor que rechazar el feature por un IOError.
        """
        from ....application.modulation import Modulation, curves
        from .protocol import validate_modulation_payload

        valid_signals = frozenset(self.list_signals())
        valid_curves = frozenset(curves.CURVE_NAMES)
        normalized, err = validate_modulation_payload(
            payload, valid_signals, registry, valid_curves
        )
        if err is not None:
            return None, err
        with self._lock:
            try:
                m = Modulation(**normalized)
                idx = self._mod_engine.add(m)
            except Exception as e:
                logger.exception("add_modulation: build/insert failed")
                return None, f"internal: {e}"
            self._save_modulations_quiet()
        return idx, None

    def remove_modulation(self, idx: int) -> bool:
        with self._lock:
            ok = self._mod_engine.remove(int(idx))
            if ok:
                self._save_modulations_quiet()
            return ok

    def clear_modulations(self) -> int:
        with self._lock:
            n = self._mod_engine.clear()
            if n > 0:
                self._save_modulations_quiet()
            return n

    # --- persistencia (atomic write + tolerant load) -------------------

    def _save_modulations_quiet(self) -> None:
        """Persiste a disco. Falla silenciosa con log warn — no rollback."""
        try:
            self._save_modulations()
        except Exception:
            logger.exception("save modulations failed (in-memory state intact)")

    def _save_modulations(self) -> None:
        MODULATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": MODULATIONS_SCHEMA_VERSION,
            "mappings": self.list_modulations(),
        }
        # Atomic: write to tmp same dir, then rename. POSIX rename es atómico.
        tmp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=str(MODULATIONS_FILE.parent),
            prefix=".modulations.", suffix=".tmp",
            delete=False,
        )
        try:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, str(MODULATIONS_FILE))
        except Exception:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            raise

    def _load_modulations(self) -> None:
        """Lee mappings persistidos al boot. Tolerante a archivo ausente / corrupto."""
        if not MODULATIONS_FILE.is_file():
            return
        try:
            with MODULATIONS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.exception("load modulations: parse failed; starting empty")
            return
        version = data.get("version") if isinstance(data, dict) else None
        if version != MODULATIONS_SCHEMA_VERSION:
            logger.warning(
                "modulations.json schema v=%s, expected v=%s — ignoring",
                version, MODULATIONS_SCHEMA_VERSION,
            )
            return
        from ....application.modulation import Modulation
        loaded = 0
        for entry in data.get("mappings", []) or []:
            try:
                m = Modulation.from_dict(entry)
                self._mod_engine.add(m)
                loaded += 1
            except Exception:
                logger.exception("load modulations: skipping bad entry %r", entry)
        if loaded:
            logger.info("modulations: loaded %d mapping(s) from disk", loaded)

    def clear_filters(self) -> int:
        """Disable every currently-enabled filter instance. Returns count cleared."""
        with self._lock:
            n = 0
            for fid, inst in self._instances.items():
                try:
                    if bool(inst.enabled):
                        inst.enabled = False
                        n += 1
                except Exception:
                    logger.exception("clear_filters: %s failed", fid)
            return n

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
        # Set de (fid, pid) bajo modulación activa — usado para marcar el
        # snapshot. La UI lo usa para deshabilitar el slider y mostrar
        # badge "🔗 modulado por X" (evita "fight" con el server tick).
        try:
            modulated = self._mod_engine.modulated_params()
        except Exception:
            modulated = set()
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
            modulated_pids: List[str] = []
            if wip or inst is None:
                for p in spec["params"]:
                    params[p["id"]] = p["default"]
            else:
                params = self._read_live_params(fid, inst)
            for p in spec["params"]:
                if (fid, p["id"]) in modulated:
                    modulated_pids.append(p["id"])
            entry: Dict[str, Any] = {"enabled": enabled, "wip": wip, "params": params}
            if modulated_pids:
                entry["modulated_params"] = modulated_pids
            out[fid] = entry
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
                if pid == "bands":
                    return int(getattr(inst, "bands", fallback))
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
            elif fid == "hand_frame":
                if pid == "effect":
                    return getattr(inst, "_effect", fallback)
                if pid == "strength":
                    return float(getattr(inst, "_effect_strength", fallback))
                if pid == "border":
                    return int(getattr(inst, "_border_thickness", fallback))
                if pid == "hold":
                    return int(getattr(inst, "_hold_frames", fallback))
            elif fid == "hand_warp":
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
                if pid == "falloff":
                    return float(getattr(inst, "_falloff", fallback))
                if pid == "mode":
                    return getattr(inst, "_mode", fallback)
                if pid == "smoothing":
                    return float(getattr(inst, "_smoothing", fallback))
            elif fid == "kaleidoscope":
                if pid == "segments":
                    return int(getattr(inst, "_segments", fallback))
                if pid == "rotation":
                    rad = float(getattr(inst, "_rotation", 0.0))
                    return rad * 180.0 / 3.14159265
                if pid == "center_x":
                    return float(getattr(inst, "_center_x", fallback))
                if pid == "center_y":
                    return float(getattr(inst, "_center_y", fallback))
            elif fid == "radial_collapse":
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
                if pid == "falloff":
                    return float(getattr(inst, "_falloff", fallback))
                if pid == "mode":
                    return getattr(inst, "_mode", fallback)
                if pid == "center_x":
                    return float(getattr(inst, "_center_x", fallback))
            elif fid == "uv_displacement":
                if pid == "function":
                    return getattr(inst, "_function_type", fallback)
                if pid == "amplitude":
                    return float(getattr(inst, "_amplitude", fallback))
                if pid == "frequency":
                    return float(getattr(inst, "_frequency", fallback))
                if pid == "phase_speed":
                    return float(getattr(inst, "_phase_speed", fallback))
            elif fid == "bloom_cinematic":
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "threshold":
                    return int(getattr(inst, "_threshold", fallback))
                if pid == "anamorphic":
                    return float(getattr(inst, "_anamorphic_ratio", fallback))
                if pid == "light_leak":
                    return float(getattr(inst, "_light_leak", fallback))
            elif fid == "color_grading":
                if pid == "saturation":
                    return float(getattr(inst, "_saturation", fallback))
                if pid == "shadow_strength":
                    return float(getattr(inst, "_shadow_strength", fallback))
                if pid == "highlight_strength":
                    return float(getattr(inst, "_highlight_strength", fallback))
                if pid == "gain_r":
                    return float(getattr(inst, "_gain_r", fallback))
            elif fid == "infrared":
                if pid == "colormap":
                    return getattr(inst, "_colormap_name", fallback)
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "contrast":
                    return float(getattr(inst, "_contrast", fallback))
            elif fid == "lens_flare":
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "threshold":
                    return int(getattr(inst, "_threshold", fallback))
                if pid == "streak_length":
                    return float(getattr(inst, "_streak_length", fallback))
                if pid == "ghost_count":
                    return int(getattr(inst, "_ghost_count", fallback))
            elif fid == "vignette":
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "inner_radius":
                    return float(getattr(inst, "_inner_radius", fallback))
                if pid == "outer_radius":
                    return float(getattr(inst, "_outer_radius", fallback))
            elif fid == "chromatic_trails":
                if pid == "r_delay":
                    return int(getattr(inst, "_r_delay", fallback))
                if pid == "g_delay":
                    return int(getattr(inst, "_g_delay", fallback))
                if pid == "b_delay":
                    return int(getattr(inst, "_b_delay", fallback))
            elif fid == "crt_glitch":
                if pid == "scanlines":
                    return float(getattr(inst, "_scanline_intensity", fallback))
                if pid == "aberration":
                    return float(getattr(inst, "_aberration_strength", fallback))
                if pid == "noise":
                    return float(getattr(inst, "_noise_amount", fallback))
                if pid == "tear":
                    return float(getattr(inst, "_tear_probability", fallback))
            elif fid == "double_vision":
                if pid == "offset_x":
                    return float(getattr(inst, "_offset_x", fallback))
                if pid == "offset_y":
                    return float(getattr(inst, "_offset_y", fallback))
                if pid == "ghost_alpha":
                    return float(getattr(inst, "_ghost_alpha", fallback))
                if pid == "copies":
                    return int(getattr(inst, "_copies", fallback))
            elif fid == "glitch_block":
                if pid == "block_size":
                    return int(getattr(inst, "_block_size", fallback))
                if pid == "corruption":
                    return float(getattr(inst, "_corruption_rate", fallback))
                if pid == "rgb_split":
                    return int(getattr(inst, "_rgb_split", fallback))
                if pid == "static_bands":
                    return int(getattr(inst, "_static_bands", fallback))
            elif fid == "motion_blur":
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
                if pid == "samples":
                    return int(getattr(inst, "_samples", fallback))
                if pid == "scale":
                    return float(getattr(inst, "_scale", fallback))
                if pid == "quality":
                    return float(getattr(inst, "_quality", fallback))
            elif fid == "radial_blur":
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
                if pid == "samples":
                    return int(getattr(inst, "_samples", fallback))
                if pid == "falloff":
                    return float(getattr(inst, "_falloff", fallback))
                if pid == "center_x":
                    return float(getattr(inst, "_center_x", fallback))
            elif fid == "ascii":
                if pid == "font_size":
                    val = getattr(inst, "_font_size_pending", None)
                    if val is not None:
                        return int(val)
                    return int(getattr(inst, "_char_h", fallback))
            elif fid == "boids":
                if pid == "num_boids":
                    return int(getattr(inst, "_num_boids", fallback))
                if pid == "max_speed":
                    return float(getattr(inst, "_max_speed", fallback))
                if pid == "separation_radius":
                    return float(getattr(inst, "_separation_radius", fallback))
            elif fid == "cpp_physarum":
                if pid == "num_agents":
                    return int(getattr(inst, "_num_agents", fallback))
                if pid == "sensor_angle":
                    return float(getattr(inst, "_sensor_angle", fallback))
                if pid == "deposit_amount":
                    return float(getattr(inst, "_deposit_amount", fallback))
                if pid == "opacity":
                    return float(getattr(inst, "_opacity", fallback))
            elif fid == "depth_of_field":
                if pid == "focal_y":
                    return float(getattr(inst, "_focal_y", fallback))
                if pid == "focal_range":
                    return float(getattr(inst, "_focal_range", fallback))
                if pid == "blur_radius":
                    return int(getattr(inst, "_blur_radius", fallback))
                if pid == "use_segmentation":
                    return bool(getattr(inst, "_use_segmentation", fallback))
            elif fid == "detail_boost":
                if pid == "clip_limit":
                    return float(getattr(inst, "_clip_limit", fallback))
                if pid == "sharpness":
                    return float(getattr(inst, "_sharpness", fallback))
            elif fid == "edges":
                if pid == "low":
                    return int(getattr(inst, "_low", fallback))
                if pid == "high":
                    return int(getattr(inst, "_high", fallback))
            elif fid == "edge_smooth":
                if pid == "diameter":
                    return int(getattr(inst, "_diameter", fallback))
                if pid == "sigma_color":
                    return float(getattr(inst, "_sigma_color", fallback))
                if pid == "sigma_space":
                    return float(getattr(inst, "_sigma_space", fallback))
                if pid == "strength":
                    return float(getattr(inst, "_strength", fallback))
            elif fid == "film_grain":
                if pid == "intensity":
                    return float(getattr(inst, "_intensity", fallback))
                if pid == "grain_size":
                    return int(getattr(inst, "_grain_size", fallback))
                if pid == "color_variation":
                    return float(getattr(inst, "_color_variation", fallback))
            elif fid == "geometric_patterns":
                if pid == "pattern_mode":
                    return str(getattr(inst, "_pattern_mode", fallback))
                if pid == "opacity":
                    return float(getattr(inst, "_opacity", fallback))
                if pid == "scale":
                    return float(getattr(inst, "_scale", fallback))
                if pid == "animate":
                    return bool(getattr(inst, "_animate", fallback))
            elif fid == "kinetic_typography":
                if pid == "font_size":
                    return int(getattr(inst, "_font_size", fallback))
                if pid == "animation":
                    return str(getattr(inst, "_animation", fallback))
                if pid == "duration_frames":
                    return int(getattr(inst, "_duration_frames", fallback))
                if pid == "opacity":
                    return float(getattr(inst, "_opacity", fallback))
            elif fid == "kuwahara":
                if pid == "radius":
                    return int(getattr(inst, "_radius", fallback))
            elif fid == "optical_flow_particles":
                if pid == "max_particles":
                    return int(getattr(inst, "_max_particles", fallback))
                if pid == "particle_lifetime":
                    return int(getattr(inst, "_particle_lifetime", fallback))
                if pid == "spawn_threshold":
                    return float(getattr(inst, "_spawn_threshold", fallback))
                if pid == "color_mode":
                    return str(getattr(inst, "_color_mode", fallback))
            elif fid == "panel_compositor":
                if pid == "layout":
                    return str(getattr(inst, "_layout", fallback))
            elif fid == "physarum":
                if pid == "num_agents":
                    return int(getattr(inst, "_num_agents", fallback))
                if pid == "sensor_angle":
                    return float(getattr(inst, "_sensor_angle", fallback))
                if pid == "deposit_amount":
                    return float(getattr(inst, "_deposit_amount", fallback))
                if pid == "opacity":
                    return float(getattr(inst, "_opacity", fallback))
            elif fid == "stippling":
                if pid == "density":
                    return float(getattr(inst, "_density", fallback))
                if pid == "min_dot_size":
                    return int(getattr(inst, "_min_dot_size", fallback))
                if pid == "max_dot_size":
                    return int(getattr(inst, "_max_dot_size", fallback))
                if pid == "invert_size":
                    return bool(getattr(inst, "_invert_size", fallback))
            # invert / mosaic / channel_swap_cpp / brightness_cfg / invert_py /
            # grayscale_cpp / toon_shading have no live params; nothing to read.
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
                "tracking": self._tracking_state(),
                "modulations": self.list_modulations(),
                "signals": self.list_signals(),
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
