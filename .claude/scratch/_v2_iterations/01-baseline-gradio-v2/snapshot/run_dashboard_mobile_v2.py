#!/usr/bin/env python
"""Mobile-first Spatial-Iteration-Engine dashboard — v2 layout.

Hub (categories) → category list (filters) → filter detail (params).
All filter params are exposed as live widgets; toggles, sliders, dials
write to the running StreamEngine without a reload. Native cv2 preview
opens on the PC (no video streamed to the phone).

Architecture: pure Gradio visibility for screen switching (one round-
trip per nav, ~100ms over LAN — acceptable). Slider / dial / stepper
drags stay client-side via the existing widget kit.

Run:
    python run_dashboard_mobile_v2.py
Open:
    http://<lan-ip>:7860   (QR printed on launch)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time as _time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cpp", "build"))

import cv2  # noqa: F401  (loaded for camera support side-effects)
import gradio as gr
import numpy as np
from PIL import Image

try:
    import qrcode as _qrcode
except ImportError:
    _qrcode = None

print("Loading engine...", flush=True)
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource
from ascii_stream_engine.adapters.renderers.passthrough_renderer import PassthroughRenderer
from ascii_stream_engine.adapters.outputs.preview_sink import PreviewSink
from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.adapters.processors.filters import (
    BloomFilter,
    ChromaticAberrationFilter,
    CppBrightnessContrastFilter,
    CppInvertFilter,
    CppTemporalScanFilter,
)
from ascii_stream_engine.presentation.widgets import (
    angle_dial,
    bundle_css,
    bundle_js,
    set_theme,
    slider_row,
    stepper,
    toggle,
)

# Force the stage theme (high-contrast, big touch targets, cyan glow).
set_theme("stage")

_STATIC = (
    Path(__file__).parent / "python" / "ascii_stream_engine"
    / "presentation" / "widgets" / "static"
)
V2_CSS = (_STATIC / "v2_layout.css").read_text(encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# BufferSink — keeps the latest frame + FPS for the dashboard header.
# ───────────────────────────────────────────────────────────────────────────
class BufferSink:
    def __init__(self):
        self._lock = threading.Lock()
        self._is_open = False
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = _time.monotonic()
        self._fps_count = 0

    def open(self, config, output_size):
        self._is_open = True

    def write(self, frame):
        image = frame.image if hasattr(frame, "image") else frame
        if not isinstance(image, (Image.Image, np.ndarray)):
            return
        with self._lock:
            self._frame_count += 1
            self._fps_count += 1
            now = _time.monotonic()
            dt = now - self._last_fps_time
            if dt >= 1.0:
                self._fps = self._fps_count / dt
                self._fps_count = 0
                self._last_fps_time = now

    def close(self):
        self._is_open = False

    def is_open(self):
        return self._is_open

    def get_fps(self):
        with self._lock:
            return self._fps

    def get_capabilities(self):
        from ascii_stream_engine.ports.output_capabilities import (
            OutputCapabilities, OutputCapability, OutputQuality,
        )
        return OutputCapabilities(
            capabilities=OutputCapability.STREAMING | OutputCapability.LOW_LATENCY,
            supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM],
            max_clients=1, min_bitrate=None, max_bitrate=None,
            protocol_name="Buffer", metadata={},
        )

    def supports_multiple_clients(self):
        return False


# ───────────────────────────────────────────────────────────────────────────
# Engine
# ───────────────────────────────────────────────────────────────────────────
print("Creating StreamEngine...", flush=True)
config = EngineConfig(
    fps=30, enable_temporal=True, enable_events=True, enable_audio_reactive=True,
)
source = OpenCVCameraSource(camera_index=2)
renderer = PassthroughRenderer()
buffer_sink = BufferSink()
preview_sink = PreviewSink(window_name="Spatial-Iteration-Engine — f=fullscreen · ESC=exit")
sink = CompositeOutputSink([buffer_sink, preview_sink])
engine = StreamEngine(
    source=source, renderer=renderer, sink=sink,
    config=config, enable_profiling=False,
)
fp = engine.filter_pipeline


# ───────────────────────────────────────────────────────────────────────────
# Filter spec — single source of truth driving the UI + the live wiring.
# ───────────────────────────────────────────────────────────────────────────
def _noop(_f, _v):
    """Sentinel for params exposed in the UI but not wired to the filter yet
    (e.g. TemporalScan band_width — needs C++ change to take effect)."""
    return None


FILTERS_SPEC = [
    # ── DISTORT ────────────────────────────────────────────────────────────
    {
        "id": "temporal_scan", "name": "TemporalScan", "cat": "DISTORT",
        "factory": lambda: CppTemporalScanFilter(angle_deg=0.0, max_frames=30),
        "params": [
            {"id": "angle",  "kind": "angle",   "default": 0.0, "label": "Scan angle",
             "apply": lambda f, v: setattr(f, "angle_deg", float(v))},
            {"id": "buffer", "kind": "stepper", "min": 2, "max": 60, "step": 2, "default": 30,
             "label": "Buffer size",
             "apply": lambda f, v: setattr(f, "max_frames", int(v))},
            {"id": "band",   "kind": "slider",  "min": 0.0, "max": 0.5, "step": 0.01, "default": 0.0,
             "label": "Band width (design)",
             "apply": _noop},
            {"id": "curve",  "kind": "select",  "options": ["linear", "ease"], "default": "linear",
             "label": "Curve",
             "apply": lambda f, v: setattr(f, "curve", v)},
        ],
    },
    # ── COLOR ──────────────────────────────────────────────────────────────
    {
        "id": "bc_cpp", "name": "Brightness / Contrast", "cat": "COLOR",
        "factory": lambda: CppBrightnessContrastFilter(brightness=0.0, contrast=1.0),
        "params": [
            {"id": "brightness", "kind": "slider", "min": -100, "max": 100, "step": 5, "default": 0,
             "label": "Brightness",
             "apply": lambda f, v: setattr(f, "brightness", float(v))},
            {"id": "contrast",   "kind": "slider", "min": 0.5, "max": 3.0, "step": 0.1, "default": 1.0,
             "label": "Contrast",
             "apply": lambda f, v: setattr(f, "contrast", float(v))},
        ],
    },
    {
        "id": "bloom", "name": "Bloom · audio-reactive", "cat": "COLOR",
        "factory": lambda: BloomFilter(threshold=200, intensity=0.6, audio_react=1.0),
        "params": [
            {"id": "intensity",   "kind": "slider", "min": 0.0, "max": 1.0, "step": 0.05, "default": 0.6,
             "label": "Intensity",
             "apply": lambda f, v: setattr(f, "intensity", float(v))},
            {"id": "threshold",   "kind": "slider", "min": 100, "max": 255, "step": 5, "default": 200,
             "label": "Threshold",
             "apply": lambda f, v: setattr(f, "threshold", int(v))},
            {"id": "audio_react", "kind": "slider", "min": 0.0, "max": 3.0, "step": 0.1, "default": 1.0,
             "label": "Audio-React (Bass)",
             "apply": lambda f, v: setattr(f, "audio_react", float(v))},
        ],
    },
    # ── GLITCH ─────────────────────────────────────────────────────────────
    {
        "id": "chroma", "name": "Chromatic Aberration", "cat": "GLITCH",
        "factory": lambda: ChromaticAberrationFilter(strength=3.0),
        "params": [
            {"id": "strength", "kind": "slider", "min": 0.0, "max": 10.0, "step": 0.5, "default": 3.0,
             "label": "Strength",
             "apply": lambda f, v: setattr(f, "strength", float(v))},
        ],
    },
    # ── STYLIZE ────────────────────────────────────────────────────────────
    {
        "id": "invert", "name": "Invert (C++)", "cat": "STYLIZE",
        "factory": lambda: CppInvertFilter(),
        "params": [],   # only the enabled toggle
    },
]

CATEGORIES = [
    {"id": "COLOR",   "name": "Color",   "stripe": "linear-gradient(180deg,#e88,#b6371a)"},
    {"id": "STYLIZE", "name": "Stylize", "stripe": "linear-gradient(180deg,#6cb,#2a5d4a)"},
    {"id": "DISTORT", "name": "Distort", "stripe": "linear-gradient(180deg,#b8c,#5a3f7a)"},
    {"id": "GLITCH",  "name": "Glitch",  "stripe": "linear-gradient(180deg,#ec8,#b57f1a)"},
]

FILTERS_BY_ID  = {f["id"]: f for f in FILTERS_SPEC}
FILTERS_BY_CAT = {c["id"]: [f for f in FILTERS_SPEC if f["cat"] == c["id"]] for c in CATEGORIES}


# ───────────────────────────────────────────────────────────────────────────
# Live filter registry — instantiate lazily, push param updates.
# ───────────────────────────────────────────────────────────────────────────
_live_instances = {}      # filter_id -> instance (None until first use)


def _ensure(fid: str):
    spec = FILTERS_BY_ID[fid]
    inst = _live_instances.get(fid)
    if inst is None:
        inst = spec["factory"]()
        inst.enabled = False
        fp.add(inst)
        _live_instances[fid] = inst
    return inst


def set_filter_enabled(fid: str, on: bool) -> None:
    _ensure(fid).enabled = bool(on)


def apply_param(fid: str, pid: str, value) -> None:
    inst = _ensure(fid)
    spec = FILTERS_BY_ID[fid]
    p = next(p for p in spec["params"] if p["id"] == pid)
    try:
        p["apply"](inst, value)
    except Exception as e:
        print(f"[v2] apply_param {fid}.{pid}={value!r} failed: {e}", flush=True)


def cat_active_count(cat_id: str) -> int:
    return sum(
        1 for f in FILTERS_BY_CAT[cat_id]
        if (_live_instances.get(f["id"]) is not None
            and _live_instances[f["id"]].enabled)
    )


# ───────────────────────────────────────────────────────────────────────────
# LAN banner + QR
# ───────────────────────────────────────────────────────────────────────────
def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def print_banner(port: int):
    ip = _lan_ip()
    url = f"http://{ip}:{port}"
    bar = "═" * 64
    print(f"\n{bar}")
    print("  Spatial-Iteration-Engine — Mobile Control Surface (v2)")
    print(f"{bar}")
    print(f"  On this PC:     http://localhost:{port}")
    print(f"  On your phone:  {url}")
    print(f"  Video preview:  native cv2 window (f = fullscreen, ESC)")
    print(bar)
    if _qrcode is not None:
        qr = _qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    print(f"{bar}\n", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# UI
# ───────────────────────────────────────────────────────────────────────────
print("Building UI...", flush=True)

extra_css = V2_CSS + """
/* Load Space Grotesk + Space Mono fonts (fallback handled in tokens). */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
"""

head_tags = (
    f"<style>{bundle_css()}</style>\n"
    f"<script>{bundle_js()}</script>"
)


def build_widget_for(p: dict, fid: str):
    """Create the visible widget + hidden value component for one param."""
    label = p.get("label", p["id"]).title()
    elem_base = f"v2-{fid}-{p['id']}"
    if p["kind"] == "angle":
        return angle_dial(value=p["default"], label=label, elem_id=elem_base)
    if p["kind"] == "slider":
        return slider_row(value=p["default"], minimum=p["min"], maximum=p["max"],
                          step=p["step"], label=label, elem_id=elem_base)
    if p["kind"] == "stepper":
        return stepper(value=p["default"], minimum=p["min"], maximum=p["max"],
                       step=p["step"], elem_id=elem_base)
    if p["kind"] == "select":
        dd = gr.Dropdown(choices=p["options"], value=p["default"], label=label,
                         elem_id=elem_base, interactive=True)
        return dd, dd
    if p["kind"] == "toggle":
        return toggle(value=bool(p["default"]), label=label, elem_id=elem_base)
    raise ValueError(f"unknown kind {p['kind']}")


with gr.Blocks(css=extra_css, head=head_tags,
               title="SIE · Mobile Control Surface (v2)") as demo:

    # State: ("hub" | "cat" | "detail", optional id)
    state = gr.State({"view": "hub", "param": None})

    # ── Header — status pill + KPIs (always visible) ────────────────────
    header = gr.HTML(value=(
        '<div class="siev2-hd"><div class="ttl">SIE · Mobile</div>'
        '<div class="pill" id="siev2-pill">'
        '<span class="dot"></span><span class="lbl">Stopped</span></div></div>'
        '<div class="siev2-kpis">'
        '<span><b id="siev2-kpi-fps">—</b> FPS</span>'
        '<span class="sep">·</span>'
        '<span>filtros <b id="siev2-kpi-fcount">0</b></span>'
        '</div>'
    ))

    # ── Hub group ──────────────────────────────────────────────────────
    with gr.Group(visible=True, elem_id="siev2-hub") as hub_group:
        gr.HTML('<div class="siev2-section-cap">Categorías</div>')
        with gr.Row(elem_classes=["siev2-hubrow"]):
            hub_buttons = {}
            for cat in CATEGORIES:
                n = len(FILTERS_BY_CAT[cat["id"]])
                btn = gr.Button(
                    value=f"{cat['name']}\n{n} filtros",
                    elem_classes=["siev2-cat-btn"],
                )
                hub_buttons[cat["id"]] = btn

    # ── Cat groups (one per category) ──────────────────────────────────
    cat_groups = {}
    cat_back_buttons = {}
    cat_detail_buttons = {}      # (cat_id, filter_id) -> gr.Button
    cat_toggle_components = {}   # filter_id -> hidden checkbox
    for cat in CATEGORIES:
        with gr.Group(visible=False, elem_id=f"siev2-cat-{cat['id']}") as g:
            with gr.Row(elem_classes=["siev2-page-header"]):
                back = gr.Button("‹", elem_classes=["siev2-back-btn"])
                gr.Markdown(f"### {cat['name']}", elem_classes=["siev2-page-title"])
            gr.HTML('<div class="siev2-section-cap">'
                    f'{len(FILTERS_BY_CAT[cat["id"]])} filtros</div>')
            for f in FILTERS_BY_CAT[cat["id"]]:
                with gr.Row(elem_classes=["siev2-row"]):
                    _, en = toggle(value=False, label="",
                                   elem_id=f"v2cat-{f['id']}-en")
                    cat_toggle_components[f["id"]] = en
                    gr.Markdown(f"**{f['name']}**",
                                elem_classes=["siev2-row-name"])
                    open_btn = gr.Button("⤢", elem_classes=["siev2-open-btn"])
                    cat_detail_buttons[(cat["id"], f["id"])] = open_btn
            cat_back_buttons[cat["id"]] = back
        cat_groups[cat["id"]] = g

    # ── Detail groups (one per filter) ─────────────────────────────────
    detail_groups = {}
    detail_back_buttons = {}
    detail_enabled = {}
    detail_param_components = {}   # (filter_id, param_id) -> hidden value comp
    for f in FILTERS_SPEC:
        cat_name = next(c["name"] for c in CATEGORIES if c["id"] == f["cat"])
        with gr.Group(visible=False, elem_id=f"siev2-detail-{f['id']}") as g:
            with gr.Row(elem_classes=["siev2-page-header"]):
                back = gr.Button("‹", elem_classes=["siev2-back-btn"])
                gr.Markdown(f"### {f['name']}",
                            elem_classes=["siev2-page-title"])
            gr.HTML(
                f'<div class="siev2-detail-meta">'
                f'cat <b>{cat_name}</b> · id <b>{f["id"]}</b> · '
                f'{len(f["params"])} params</div>'
            )
            with gr.Column(elem_classes=["siev2-detail-body"]):
                _, en = toggle(value=False, label="ENABLE",
                               elem_id=f"v2det-{f['id']}-en")
                detail_enabled[f["id"]] = en
                for p in f["params"]:
                    _, comp = build_widget_for(p, f["id"])
                    detail_param_components[(f["id"], p["id"])] = comp
            detail_back_buttons[f["id"]] = back
        detail_groups[f["id"]] = g

    # ── Footer with start/stop and live status ─────────────────────────
    with gr.Row(elem_classes=["siev2-footer"]):
        startstop_btn = gr.Button("▶ Iniciar", elem_classes=["siev2-startstop"])
    status_md = gr.Markdown("", elem_classes=["siev2-status"])

    # ── Visibility / nav helpers ───────────────────────────────────────
    visibility_outputs = (
        [hub_group]
        + [cat_groups[c["id"]] for c in CATEGORIES]
        + [detail_groups[f["id"]] for f in FILTERS_SPEC]
    )

    def _visibility(view, param):
        out = [gr.update(visible=(view == "hub"))]
        for c in CATEGORIES:
            out.append(gr.update(visible=(view == "cat" and param == c["id"])))
        for f in FILTERS_SPEC:
            out.append(gr.update(visible=(view == "detail" and param == f["id"])))
        return out

    def _nav(view, param):
        return [{"view": view, "param": param}] + _visibility(view, param)

    nav_outputs = [state] + visibility_outputs

    # Hub buttons -> cat
    for cid, btn in hub_buttons.items():
        btn.click(lambda cid=cid: _nav("cat", cid), inputs=[], outputs=nav_outputs)

    # Cat back -> hub
    for cid, btn in cat_back_buttons.items():
        btn.click(lambda: _nav("hub", None), inputs=[], outputs=nav_outputs)

    # Cat -> detail
    for (cid, fid), btn in cat_detail_buttons.items():
        btn.click(lambda fid=fid: _nav("detail", fid),
                  inputs=[], outputs=nav_outputs)

    # Detail back -> cat (the cat the filter belongs to)
    for fid, btn in detail_back_buttons.items():
        cat_id_for_filter = FILTERS_BY_ID[fid]["cat"]
        btn.click(lambda cid=cat_id_for_filter: _nav("cat", cid),
                  inputs=[], outputs=nav_outputs)

    # Wire enabled toggles (both cat-list and detail) -> engine
    for fid, en in cat_toggle_components.items():
        en.change(lambda v, fid=fid: set_filter_enabled(fid, v),
                  inputs=[en], outputs=[])
    for fid, en in detail_enabled.items():
        en.change(lambda v, fid=fid: set_filter_enabled(fid, v),
                  inputs=[en], outputs=[])

    # Wire params -> engine
    for (fid, pid), comp in detail_param_components.items():
        comp.change(lambda v, fid=fid, pid=pid: apply_param(fid, pid, v),
                    inputs=[comp], outputs=[])

    # Start / stop
    def toggle_run() -> str:
        if engine.is_running:
            engine.stop()
            return "■ STOP · Iniciar"
        else:
            engine.start(blocking=False)
            return "▶ Live · Detener"

    startstop_btn.click(toggle_run, inputs=[], outputs=[startstop_btn])

    # Periodic status refresh — FPS / counts
    def refresh_status():
        running = engine.is_running
        fps = buffer_sink.get_fps()
        n_active = sum(1 for f in FILTERS_SPEC
                       if (_live_instances.get(f["id"]) is not None
                           and _live_instances[f["id"]].enabled))
        per_cat = ", ".join(f"{c['id']}={cat_active_count(c['id'])}" for c in CATEGORIES)
        return (
            f"{'▶ Live' if running else '■ Stopped'} · "
            f"{fps:4.1f} FPS · {n_active} filtros activos ({per_cat})"
        )

    status_timer = gr.Timer(value=1.0, active=True)
    status_timer.tick(refresh_status, inputs=[], outputs=[status_md])


# ─── Launch ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print_banner(port=7860)
    demo.queue().launch(server_name="0.0.0.0", server_port=7860,
                        show_error=True, quiet=False, show_api=False)
