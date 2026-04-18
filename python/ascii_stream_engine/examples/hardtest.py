#!/usr/bin/env python3
"""
hardtest.py — Automated combinatorial integration test for Spatial-Iteration-Engine.

Tests all 91 filter pair combinations (C(14,2)), 3 renderer modes, baseline, and
stress test. Captures frames + full engine state snapshots to disk for review.

Usage (from repo root):
    PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/hardtest.py --camera 2

Output:
    test_captures/hardtest_<timestamp>/
"""

import argparse
import io
import itertools
import json
import logging
import os
import resource
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from ascii_stream_engine.adapters.processors.filters import (
    BoidsFilter,
    BrightnessFilter,
    CppPhysarumFilter,
    CRTGlitchFilter,
    DetailBoostFilter,
    EdgeFilter,
    EdgeSmoothFilter,
    GeometricPatternFilter,
    InvertFilter,
    OpticalFlowParticlesFilter,
    PhysarumFilter,
    RadialCollapseFilter,
    StipplingFilter,
    UVDisplacementFilter,
)
from ascii_stream_engine.adapters.renderers import PassthroughRenderer
from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource

# ---------------------------------------------------------------------------
# Engine imports
# ---------------------------------------------------------------------------
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import AnalyzerPipeline, FilterPipeline
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame

try:
    from ascii_stream_engine.adapters.renderers.ascii import AsciiRenderer
except ImportError:
    AsciiRenderer = None

try:
    from ascii_stream_engine.adapters.renderers.landmarks_overlay_renderer import (
        LandmarksOverlayRenderer,
    )
except ImportError:
    LandmarksOverlayRenderer = None

try:
    from ascii_stream_engine.adapters.perception import (
        FaceLandmarkAnalyzer,
        HandLandmarkAnalyzer,
        PoseLandmarkAnalyzer,
    )

    PERCEPTION_AVAILABLE = True
except ImportError:
    PERCEPTION_AVAILABLE = False

# ---------------------------------------------------------------------------
# Action Logger
# ---------------------------------------------------------------------------


class ActionLogger:
    """Logs every API call to a file and to the console logger."""

    def __init__(self, log_path: Path, logger: logging.Logger):
        self._file = open(log_path, "w")
        self._logger = logger
        self._phase = "init"

    def set_phase(self, phase_name: str):
        self._phase = phase_name

    def log(self, category: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"{ts} [{self._phase}] {category} {message}"
        self._file.write(line + "\n")
        self._file.flush()
        self._logger.info(line)

    def close(self):
        self._file.close()


# ---------------------------------------------------------------------------
# CaptureSink — thread-safe frame store
# ---------------------------------------------------------------------------


class CaptureSink:
    """OutputSink that stores the last RenderFrame for on-demand capture."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_frame: Optional[RenderFrame] = None
        self._frame_count = 0
        self._is_open = False

    def open(self, config, output_size):
        self._is_open = True
        self._frame_count = 0

    def write(self, frame: RenderFrame):
        with self._lock:
            self._last_frame = frame
            self._frame_count += 1

    def close(self):
        self._is_open = False

    def is_open(self):
        return self._is_open

    def get_capabilities(self):
        return None

    def supports_multiple_clients(self):
        return False

    def save_frame_jpeg(self, path: Path, quality: int = 80) -> Optional[int]:
        """Save last frame as JPEG. Returns file size in bytes, or None if no frame."""
        with self._lock:
            frame = self._last_frame
        if frame is None or frame.image is None:
            return None
        img = frame.image
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        path.write_bytes(data)
        return len(data)

    @property
    def frame_count(self):
        with self._lock:
            return self._frame_count


# ---------------------------------------------------------------------------
# SolidColorSource — fallback when camera unavailable
# ---------------------------------------------------------------------------


class SolidColorSource:
    """Generates animated noise frames when no camera is available."""

    def __init__(self, width=640, height=480):
        self._w = width
        self._h = height
        self._base = np.zeros((height, width, 3), dtype=np.uint8)
        self._base[:] = (30, 30, 80)

    def open(self):
        pass

    def read(self):
        noise = np.random.randint(0, 20, (self._h, self._w, 3), dtype=np.uint8)
        return np.clip(self._base.astype(np.int16) + noise - 10, 0, 255).astype(np.uint8)

    def close(self):
        pass


# ---------------------------------------------------------------------------
# State snapshot — captures everything the dashboard shows
# ---------------------------------------------------------------------------


def _json_safe(obj):
    """Make an object JSON-serializable."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, bytes):
        return f"<bytes {len(obj)}>"
    return str(obj)


def capture_engine_snapshot(engine: StreamEngine, phase_name: str) -> dict:
    """Capture full engine state — everything visible in the dashboard panels."""
    snap: Dict[str, Any] = {
        "phase": phase_name,
        "timestamp": datetime.now().isoformat(),
        "is_running": engine.is_running,
    }

    # Config
    try:
        cfg = engine.get_config()
        snap["config"] = {
            "fps": cfg.fps,
            "render_mode": cfg.render_mode,
            "raw_width": cfg.raw_width,
            "raw_height": cfg.raw_height,
            "grid_w": cfg.grid_w,
            "grid_h": cfg.grid_h,
            "contrast": cfg.contrast,
            "brightness": cfg.brightness,
            "invert": cfg.invert,
            "host": cfg.host,
            "port": cfg.port,
            "bitrate": cfg.bitrate,
            "frame_buffer_size": cfg.frame_buffer_size,
            "enable_events": cfg.enable_events,
            "enable_temporal": cfg.enable_temporal,
            "parallel_workers": cfg.parallel_workers,
            "gpu_enabled": cfg.gpu_enabled,
        }
    except Exception as e:
        snap["config"] = {"error": str(e)}

    # Metrics
    try:
        summary = engine.metrics.get_summary()
        summary["latency_avg_ms"] = summary.get("latency_avg", 0) * 1000
        summary["latency_min_ms"] = summary.get("latency_min", 0) * 1000
        summary["latency_max_ms"] = summary.get("latency_max", 0) * 1000
        snap["metrics"] = summary
    except Exception as e:
        snap["metrics"] = {"error": str(e)}

    # Profiling
    try:
        snap["profiler_enabled"] = engine.profiler.enabled
        snap["profiling"] = engine.get_profiling_stats()
    except Exception as e:
        snap["profiling"] = {"error": str(e)}

    # Filters
    try:
        snap["filters"] = [
            {
                "name": getattr(f, "name", f.__class__.__name__),
                "enabled": getattr(f, "enabled", True),
                "class": f.__class__.__name__,
            }
            for f in engine.filter_pipeline.snapshot()
        ]
    except Exception as e:
        snap["filters"] = {"error": str(e)}

    # Analyzers
    try:
        snap["analyzers"] = [
            {
                "name": getattr(a, "name", a.__class__.__name__),
                "enabled": getattr(a, "enabled", True),
                "class": a.__class__.__name__,
                "model_path": getattr(a, "model_path", None),
            }
            for a in engine.analyzer_pipeline.snapshot()
        ]
    except Exception as e:
        snap["analyzers"] = {"error": str(e)}

    # Last analysis
    try:
        analysis = engine.get_last_analysis()
        snap["last_analysis"] = (
            {k: _summarize_analysis(v) for k, v in analysis.items()} if analysis else {}
        )
    except Exception as e:
        snap["last_analysis"] = {"error": str(e)}

    # Renderer
    try:
        renderer = engine.get_renderer()
        snap["renderer"] = renderer.__class__.__name__
    except Exception:
        snap["renderer"] = "unknown"

    # Event bus
    try:
        bus = engine.get_event_bus()
        snap["event_bus"] = bus.get_stats() if bus is not None else None
    except Exception as e:
        snap["event_bus"] = {"error": str(e)}

    # Temporal manager
    try:
        tm = getattr(engine, "_temporal", None)
        if tm is not None:
            snap["temporal"] = {
                "input_depth": tm.input_depth,
                "needs_output": tm.needs_output,
                "has_allocations": tm.has_allocations,
            }
        else:
            snap["temporal"] = None
    except Exception as e:
        snap["temporal"] = {"error": str(e)}

    # Memory (OS-level)
    try:
        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem = {"peak_rss_mb": round(peak_kb / 1024.0, 1)}
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem["current_rss_kb"] = line.split(":")[1].strip()
                        break
        except FileNotFoundError:
            pass
        snap["memory"] = mem
    except Exception as e:
        snap["memory"] = {"error": str(e)}

    # CPU
    try:
        t = os.times()
        snap["cpu"] = {
            "user_s": round(t.user, 2),
            "sys_s": round(t.system, 2),
            "wall_s": round(time.monotonic(), 2),
        }
    except Exception as e:
        snap["cpu"] = {"error": str(e)}

    return snap


def _summarize_analysis(value) -> Any:
    """Summarize analysis dict values for JSON (reduce numpy arrays to shapes)."""
    if isinstance(value, np.ndarray):
        return {"shape": list(value.shape), "dtype": str(value.dtype)}
    if isinstance(value, dict):
        return {k: _summarize_analysis(v) for k, v in value.items()}
    if isinstance(value, list) and len(value) > 10:
        return {"length": len(value), "sample": value[:3]}
    return value


# ---------------------------------------------------------------------------
# Phase runner
# ---------------------------------------------------------------------------


def run_phase(
    phase_idx: int,
    phase_name: str,
    engine: StreamEngine,
    sink: CaptureSink,
    alog: ActionLogger,
    output_dir: Path,
    setup_fn,
    duration_s: float = 5.0,
    capture_at_s: float = 3.0,
    interrupted: threading.Event = None,
) -> dict:
    """Run a single test phase: setup, wait, capture, snapshot."""
    slug = f"{phase_idx:02d}_{phase_name}"
    alog.set_phase(slug)
    phase_dir = output_dir / slug
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Setup
    setup_fn()

    # Wait for stabilization, then capture
    start = time.monotonic()
    captured = False
    result = {"phase": slug, "frame_captured": False, "frame_size_bytes": 0}

    while (time.monotonic() - start) < duration_s:
        if interrupted and interrupted.is_set():
            break
        elapsed = time.monotonic() - start

        if not captured and elapsed >= capture_at_s:
            # Capture frame
            frame_path = phase_dir / "frame.jpg"
            size = sink.save_frame_jpeg(frame_path, quality=80)
            if size:
                alog.log("CAPTURE", f"frame.jpg ({size // 1024}KB)")
                result["frame_captured"] = True
                result["frame_size_bytes"] = size
            else:
                alog.log("CAPTURE", "FAILED — no frame available")

            # Capture full state snapshot
            snap = capture_engine_snapshot(engine, slug)
            snap_path = phase_dir / "state.json"
            with open(snap_path, "w") as f:
                json.dump(snap, f, indent=2, default=_json_safe)
            alog.log("SNAPSHOT", "state.json")

            result["metrics"] = snap.get("metrics", {})
            result["profiling"] = snap.get("profiling", {})
            result["memory"] = snap.get("memory", {})
            captured = True

        time.sleep(0.05)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Hardtest: combinatorial engine test")
    parser.add_argument("--camera", type=int, default=2, help="Camera index (default: 2)")
    parser.add_argument("--output-dir", default="test_captures", help="Base output directory")
    parser.add_argument("--duration", type=float, default=5.0, help="Seconds per phase")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("hardtest")

    # Output directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"hardtest_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output: {output_dir.resolve()}")

    # Action logger
    alog = ActionLogger(output_dir / "actions.log", logger)

    # ── Test camera ──────────────────────────────────────────────────────
    camera_ok = False
    try:
        test_src = OpenCVCameraSource(args.camera)
        test_src.open()
        test_frame = test_src.read()
        test_src.close()
        camera_ok = test_frame is not None
    except Exception:
        pass

    if camera_ok:
        source = OpenCVCameraSource(args.camera)
        alog.log("INIT", f"Camera {args.camera}: OK")
    else:
        source = SolidColorSource(640, 480)
        alog.log("INIT", f"Camera {args.camera}: UNAVAILABLE — using SolidColorSource")

    # ── Create all filters (once) ────────────────────────────────────────
    ALL_FILTERS = {
        "brightness": BrightnessFilter(),
        "edges": EdgeFilter(),
        "detail": DetailBoostFilter(),
        "invert": InvertFilter(),
        "edge_smooth": EdgeSmoothFilter(),
        "optical_flow": OpticalFlowParticlesFilter(),
        "physarum": PhysarumFilter(),
        "stippling": StipplingFilter(),
        "boids": BoidsFilter(),
        "uv_displacement": UVDisplacementFilter(),
        "crt_glitch": CRTGlitchFilter(),
        "geometric_patterns": GeometricPatternFilter(),
        "radial_collapse": RadialCollapseFilter(),
        "cpp_physarum": CppPhysarumFilter(),
    }
    filter_names = list(ALL_FILTERS.keys())
    alog.log("INIT", f"Filters loaded: {len(ALL_FILTERS)} — {', '.join(filter_names)}")

    # ── Analyzers ────────────────────────────────────────────────────────
    analyzers_list = []
    if PERCEPTION_AVAILABLE:
        analyzers_list = [
            FaceLandmarkAnalyzer(),
            HandLandmarkAnalyzer(),
            PoseLandmarkAnalyzer(),
        ]
        alog.log("INIT", "Perception: face, hands, pose")
    else:
        alog.log("INIT", "Perception: NOT AVAILABLE")

    # ── Build engine ─────────────────────────────────────────────────────
    sink = CaptureSink()
    config = EngineConfig(
        fps=30,
        render_mode="raw",
        raw_width=640,
        raw_height=480,
        frame_buffer_size=0,
        sleep_on_empty=0.001,
        enable_temporal=True,
        enable_events=True,
    )

    engine = StreamEngine(
        source=source,
        renderer=PassthroughRenderer(),
        sink=sink,
        config=config,
        analyzers=AnalyzerPipeline(analyzers_list),
        filters=FilterPipeline([]),
        enable_profiling=True,
    )
    alog.log("INIT", "Engine created (640x480, 30fps, profiling=True, temporal=True, events=True)")

    # ── Renderers ────────────────────────────────────────────────────────
    renderers = {"passthrough": PassthroughRenderer()}
    if AsciiRenderer:
        renderers["ascii"] = AsciiRenderer()
    if LandmarksOverlayRenderer:
        renderers["landmarks"] = LandmarksOverlayRenderer()

    # ── Ctrl+C handler ───────────────────────────────────────────────────
    interrupted = threading.Event()

    def _sighandler(sig, frame):
        logger.warning("Interrupted — finishing current phase...")
        interrupted.set()

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    # ── Start engine ─────────────────────────────────────────────────────
    alog.log("ACTION", "engine.start(blocking=False)")
    engine.start(blocking=False)
    time.sleep(1.5)

    if not engine.is_running:
        logger.error("Engine failed to start. Exiting.")
        alog.close()
        sys.exit(1)

    alog.log("STATUS", f"Engine running. FPS={engine.metrics.get_fps():.1f}")

    # ══════════════════════════════════════════════════════════════════════
    # BUILD PHASE LIST
    # ══════════════════════════════════════════════════════════════════════
    phases: List[Tuple[str, Any]] = []  # (name, setup_fn)

    # Phase 0: Baseline
    def _baseline():
        engine.filter_pipeline.clear()
        engine.set_renderer(renderers["passthrough"])
        alog.log("ACTION", "engine.filter_pipeline.clear()")
        alog.log("ACTION", "engine.set_renderer(PassthroughRenderer)")

    phases.append(("baseline", _baseline))

    # Phases 1-91: All filter pair combinations
    for f1_name, f2_name in itertools.combinations(filter_names, 2):
        f1 = ALL_FILTERS[f1_name]
        f2 = ALL_FILTERS[f2_name]

        def _make_pair_setup(n1, n2, filt1, filt2):
            def _setup():
                engine.filter_pipeline.replace([filt1, filt2])
                engine.set_renderer(renderers["passthrough"])
                alog.log("ACTION", f"engine.filter_pipeline.replace([{n1}, {n2}])")

            return _setup

        phases.append((f"{f1_name}+{f2_name}", _make_pair_setup(f1_name, f2_name, f1, f2)))

    # Renderer phases
    for rname, renderer in renderers.items():

        def _make_renderer_setup(name, r):
            def _setup():
                engine.filter_pipeline.clear()
                engine.set_renderer(r)
                alog.log("ACTION", "engine.filter_pipeline.clear()")
                alog.log("ACTION", f"engine.set_renderer({r.__class__.__name__})")

            return _setup

        phases.append((f"renderer_{rname}", _make_renderer_setup(rname, renderer)))

    # Stress test: all filters
    def _stress():
        engine.filter_pipeline.replace(list(ALL_FILTERS.values()))
        engine.set_renderer(renderers["passthrough"])
        alog.log("ACTION", f"engine.filter_pipeline.replace([ALL {len(ALL_FILTERS)} FILTERS])")

    phases.append(("stress_all_filters", _stress))

    # ══════════════════════════════════════════════════════════════════════
    # RUN PHASES
    # ══════════════════════════════════════════════════════════════════════
    total_phases = len(phases)
    logger.info(
        f"Running {total_phases} phases at {args.duration}s each (~{total_phases * args.duration / 60:.1f} min)"
    )

    results = []
    test_start = time.monotonic()

    for idx, (name, setup_fn) in enumerate(phases):
        if interrupted.is_set():
            logger.warning(f"Interrupted at phase {idx}/{total_phases}")
            break

        logger.info(f"━━━ Phase {idx:02d}/{total_phases}: {name} ━━━")
        try:
            result = run_phase(
                phase_idx=idx,
                phase_name=name,
                engine=engine,
                sink=sink,
                alog=alog,
                output_dir=output_dir,
                setup_fn=setup_fn,
                duration_s=args.duration,
                capture_at_s=args.duration * 0.6,  # capture at 60% of phase
                interrupted=interrupted,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Phase {idx} ({name}) failed: {e}", exc_info=True)
            alog.log("ERROR", f"Phase failed: {e}")

    # ══════════════════════════════════════════════════════════════════════
    # STOP & REPORT
    # ══════════════════════════════════════════════════════════════════════
    alog.log("ACTION", "engine.stop()")
    engine.stop()
    total_elapsed = time.monotonic() - test_start

    # Summary report
    summary = {
        "generated_at": datetime.now().isoformat(),
        "camera_index": args.camera,
        "camera_available": camera_ok,
        "perception_available": PERCEPTION_AVAILABLE,
        "total_phases": total_phases,
        "phases_completed": len(results),
        "total_elapsed_s": round(total_elapsed, 1),
        "phase_duration_s": args.duration,
        "resolution": "640x480",
        "phases": [],
    }

    for r in results:
        fps = r.get("metrics", {}).get("fps", 0)
        lat = r.get("metrics", {}).get("latency_avg_ms", 0)
        errs = r.get("metrics", {}).get("total_errors", 0)
        mem = r.get("memory", {}).get("peak_rss_mb", 0)
        summary["phases"].append(
            {
                "name": r["phase"],
                "frame_captured": r["frame_captured"],
                "frame_size_bytes": r["frame_size_bytes"],
                "fps": round(fps, 1) if fps else 0,
                "latency_avg_ms": round(lat, 1) if lat else 0,
                "total_errors": errs,
                "peak_rss_mb": mem,
            }
        )

    summary_path = output_dir / "summary_report.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=_json_safe)

    alog.log("STATUS", f"Summary written: {summary_path}")
    alog.close()

    # Console summary
    print()
    print("=" * 78)
    print("HARDTEST COMPLETE")
    print("=" * 78)
    print(f"Duration: {total_elapsed:.1f}s | Phases: {len(results)}/{total_phases}")
    print(f"Output:   {output_dir.resolve()}")
    print()
    print(f"{'#':>3} {'Phase':<40} {'FPS':>6} {'Lat ms':>7} {'Errs':>5} {'Frame':>6}")
    print("-" * 78)
    for i, r in enumerate(results):
        fps = r.get("metrics", {}).get("fps", 0)
        lat = r.get("metrics", {}).get("latency_avg_ms", 0)
        errs = r.get("metrics", {}).get("total_errors", 0)
        fsize = r["frame_size_bytes"] // 1024 if r["frame_captured"] else 0
        print(f"{i:>3} {r['phase']:<40} {fps:>6.1f} {lat:>7.1f} {errs:>5} {fsize:>5}KB")
    print("=" * 78)


if __name__ == "__main__":
    main()
