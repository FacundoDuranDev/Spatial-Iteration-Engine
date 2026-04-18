#!/usr/bin/env python
"""Mobile-first Spatial-Iteration-Engine dashboard.

Wires the widget kit (angle_dial, slider_row, stepper, toggle) to a real
StreamEngine. Tap Start and the native fullscreen cv2 preview opens on
the PC; every slider / dial / toggle change edits the live FilterPipeline
on the running engine with no reload. No video is streamed to the phone.

Run:
    python run_dashboard_mobile.py
Open:
    http://<lan-ip>:7860   (QR printed on launch)
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time as _time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cpp", "build"))

import cv2
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
    deserialize_filter,
)
from ascii_stream_engine.presentation.gradio_helpers import load_mp3_presets
from ascii_stream_engine.presentation.widgets import (
    angle_dial,
    bundle_css,
    bundle_js,
    slider_row,
    stepper,
    toggle,
)


# ---------------------------------------------------------------------------
# BufferSink — keeps the latest frame + FPS for the dashboard header.
# ---------------------------------------------------------------------------
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

    def get_frame_count(self):
        with self._lock:
            return self._frame_count

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


# ---------------------------------------------------------------------------
# Camera with live resolution switch.
# ---------------------------------------------------------------------------
class ResizingCameraSource:
    def __init__(self, camera_index=0, width=640, height=480):
        self._inner = OpenCVCameraSource(camera_index=camera_index)
        self._width = width
        self._height = height

    def set_resolution(self, width, height):
        self._width = width
        self._height = height

    def open(self):
        self._inner.open()
        if self._inner._cap:
            self._inner._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._inner._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)

    def read(self):
        frame = self._inner.read()
        if frame is None:
            return None
        h, w = frame.shape[:2]
        if w != self._width or h != self._height:
            frame = cv2.resize(frame, (self._width, self._height),
                               interpolation=cv2.INTER_AREA)
        return frame

    def close(self):
        self._inner.close()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
print("Creating StreamEngine...", flush=True)
config = EngineConfig(fps=30, enable_temporal=True, enable_events=True)
source = ResizingCameraSource(camera_index=2, width=640, height=480)
renderer = PassthroughRenderer()
buffer_sink = BufferSink()
preview_sink = PreviewSink(window_name="Spatial-Iteration-Engine — f=fullscreen · ESC=exit")
sink = CompositeOutputSink([buffer_sink, preview_sink])
engine = StreamEngine(
    source=source, renderer=renderer, sink=sink,
    config=config, enable_profiling=False,
)
fp = engine.filter_pipeline


# ---------------------------------------------------------------------------
# Filter helpers — ensure_filter returns the live instance (added once).
# ---------------------------------------------------------------------------
def get_filter(name):
    for f in fp.filters:
        if f.name == name:
            return f
    return None


def ensure_filter(name, cls, **kwargs):
    f = get_filter(name)
    if f is None:
        f = cls(**kwargs)
        fp.add(f)
    return f


def set_enabled(name, cls, on: bool):
    f = ensure_filter(name, cls)
    f.enabled = bool(on)
    return f


# ---------------------------------------------------------------------------
# Banner with LAN URL + QR.
# ---------------------------------------------------------------------------
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
    print("  Spatial-Iteration-Engine — Mobile Control Surface")
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
    else:
        print("  (pip install qrcode to see a scannable QR here)")
    print(f"{bar}\n", flush=True)


# ---------------------------------------------------------------------------
# Presets (reuses the mp3 preset JSON).
# ---------------------------------------------------------------------------
presets = load_mp3_presets()
preset_map = {p["name"]: p for p in presets}
preset_names = list(preset_map.keys())


def apply_preset(name: str) -> str:
    if name == "(none)":
        return "Elegí un preset"
    p = preset_map.get(name)
    if not p:
        return f"'{name}' no encontrado"
    fp.clear()
    for fc in p.get("filter_configs", []):
        try:
            fp.add(deserialize_filter(fc))
        except Exception:
            pass
    return f"'{name}': {len(fp.filters)} filtros"


def clear_filters() -> str:
    fp.clear()
    return "limpio"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
print("Building UI...", flush=True)

extra_css = """
body, .gradio-container { background: #05060b !important; }
.gradio-container { max-width: 440px !important; padding-top: 0 !important; }
.gradio-container .main { gap: 0 !important; }
.sie-stats { font-family: 'JetBrains Mono', monospace; font-size: 13px;
             color: #8891a6; letter-spacing: 0.02em; }
.sie-stats b { color: #00fff2; font-weight: 400; }
"""

head_tags = (
    f"<style>{bundle_css()}</style>\n"
    f"<script>{bundle_js()}</script>"
)


def row_start(title: str) -> gr.HTML:
    return gr.HTML(
        f'<div class="sie-root" style="padding: 0 16px 10px;">'
        f'<div class="sie-row sie-expanded"><div class="sie-row-head">'
        f'<div class="sie-row-name">{title}</div></div>'
        f'<div class="sie-row-body">'
    )


def row_end() -> gr.HTML:
    return gr.HTML("</div></div></div>")


with gr.Blocks(css=extra_css, head=head_tags,
               title="SIE · Mobile Control Surface") as demo:

    # Header: status + live FPS + LAN URL
    header_html = gr.HTML(value='<div class="sie-root" style="padding: 16px 16px 8px;">'
                                '<div style="display:flex; align-items:center; '
                                'justify-content:space-between; gap:12px;">'
                                '<div class="sie-pill sie-pill-stopped" id="sie-status-pill">'
                                '<span class="sie-pill-dot"></span> Stopped</div>'
                                '<div class="sie-stats" id="sie-stats">— FPS</div>'
                                '</div></div>')

    # Master controls (Start / Stop / Reset)
    with gr.Row(elem_id="sie-master-row"):
        start_btn = gr.Button("▶ START", variant="primary", elem_classes=["sie-start-btn"])
        stop_btn = gr.Button("■ STOP", variant="stop", elem_classes=["sie-stop-btn"])

    # ── TemporalScan ──
    row_start("Temporal Scan")
    with gr.Column():
        _, ts_enable = toggle(value=False, label="ENABLE", elem_id="ts-enable")
        _, ts_angle = angle_dial(value=0.0, label="Angle", elem_id="ts-angle")
        _, ts_buffer = stepper(value=30, minimum=2, maximum=60, step=2,
                               elem_id="ts-buffer")
    row_end()

    # ── Brightness / Contrast (C++) ──
    row_start("Brightness / Contrast (C++)")
    with gr.Column():
        _, bc_enable = toggle(value=False, label="ENABLE", elem_id="bc-enable")
        _, bc_brightness = slider_row(value=0, minimum=-100, maximum=100, step=5,
                                      label="Brightness", elem_id="bc-b")
        _, bc_contrast = slider_row(value=1.0, minimum=0.5, maximum=3.0, step=0.1,
                                    label="Contrast", elem_id="bc-c")
    row_end()

    # ── Bloom ──
    row_start("Bloom")
    with gr.Column():
        _, bl_enable = toggle(value=False, label="ENABLE", elem_id="bl-enable")
        _, bl_intensity = slider_row(value=0.6, minimum=0, maximum=1, step=0.05,
                                     label="Intensity", elem_id="bl-i")
        _, bl_threshold = slider_row(value=200, minimum=100, maximum=255, step=5,
                                     label="Threshold", elem_id="bl-t")
    row_end()

    # ── Chromatic Aberration ──
    row_start("Chromatic Aberration")
    with gr.Column():
        _, ca_enable = toggle(value=False, label="ENABLE", elem_id="ca-enable")
        _, ca_strength = slider_row(value=3, minimum=0, maximum=10, step=0.5,
                                    label="Strength", elem_id="ca-s")
    row_end()

    # ── Invert (C++) ──
    row_start("Invert (C++)")
    with gr.Column():
        _, inv_enable = toggle(value=False, label="ENABLE", elem_id="inv-enable")
    row_end()

    # Footer: preset picker + resolution
    gr.HTML('<div class="sie-root" style="padding: 8px 16px 16px;">')
    with gr.Row():
        preset_dd = gr.Dropdown(["(none)"] + preset_names, value="(none)",
                                label="Scene", scale=3)
        load_btn = gr.Button("Load", scale=1, elem_classes=["sie-btn-ghost"])
        clear_btn = gr.Button("Clear", scale=1, elem_classes=["sie-btn-ghost"])
    with gr.Row():
        res_dd = gr.Dropdown(["320x240", "640x480", "800x600", "1280x720"],
                             value="640x480", label="Resolution")
    gr.HTML("</div>")

    # Auto-refresh header stats every second.
    def refresh_stats():
        fps = buffer_sink.get_fps()
        running = engine.is_running
        frames = buffer_sink.get_frame_count()
        n = len([f for f in fp.filters if f.enabled])
        pill = ('<div class="sie-pill sie-pill-running"><span class="sie-pill-dot"></span>'
                ' Running</div>') if running else \
               ('<div class="sie-pill sie-pill-stopped"><span class="sie-pill-dot"></span>'
                ' Stopped</div>')
        stats = f'<span class="sie-stats"><b>{fps:4.1f}</b> FPS · <b>{n}</b> filt · {frames} fr</span>'
        return (
            '<div class="sie-root" style="padding: 16px 16px 8px;">'
            '<div style="display:flex; align-items:center; justify-content:space-between; '
            'gap:12px;">' + pill + stats + '</div></div>'
        )

    stats_timer = gr.Timer(value=1.0)
    stats_timer.tick(refresh_stats, outputs=header_html)

    # ---------- Wiring: widget change → engine filter ----------
    # TemporalScan
    def on_ts_enable(on):
        f = ensure_filter("cpp_temporal_scan", CppTemporalScanFilter)
        f.enabled = bool(on)
        return None

    def on_ts_angle(v):
        f = ensure_filter("cpp_temporal_scan", CppTemporalScanFilter)
        f.angle_deg = float(v or 0.0)
        return None

    def on_ts_buffer(v):
        f = ensure_filter("cpp_temporal_scan", CppTemporalScanFilter)
        f.max_frames = int(v or 30)
        return None

    ts_enable.change(on_ts_enable, inputs=ts_enable, outputs=None)
    ts_angle.change(on_ts_angle, inputs=ts_angle, outputs=None)
    ts_buffer.change(on_ts_buffer, inputs=ts_buffer, outputs=None)

    # Brightness / Contrast (C++)
    def on_bc(en, b, c):
        f = ensure_filter("cpp_brightness_contrast", CppBrightnessContrastFilter)
        f.enabled = bool(en)
        f._brightness_delta = int(b or 0)
        f._contrast_factor = float(c or 1.0)
        return None

    for comp in (bc_enable, bc_brightness, bc_contrast):
        comp.change(on_bc, inputs=[bc_enable, bc_brightness, bc_contrast], outputs=None)

    # Bloom
    def on_bloom(en, i, t):
        f = ensure_filter("bloom", BloomFilter)
        f.enabled = bool(en)
        f._intensity = float(i or 0.0)
        f._threshold = int(t or 200)
        return None

    for comp in (bl_enable, bl_intensity, bl_threshold):
        comp.change(on_bloom, inputs=[bl_enable, bl_intensity, bl_threshold], outputs=None)

    # Chromatic aberration
    def on_ca(en, s):
        f = ensure_filter("chromatic_aberration", ChromaticAberrationFilter)
        f.enabled = bool(en)
        f._strength = float(s or 0.0)
        f._params_dirty = True
        return None

    for comp in (ca_enable, ca_strength):
        comp.change(on_ca, inputs=[ca_enable, ca_strength], outputs=None)

    # Invert
    def on_invert(on):
        f = ensure_filter("cpp_invert", CppInvertFilter)
        f.enabled = bool(on)
        return None

    inv_enable.change(on_invert, inputs=inv_enable, outputs=None)

    # Master Start / Stop
    def on_start():
        if not engine.is_running:
            engine.start()
        return None

    def on_stop():
        if engine.is_running:
            engine.stop()
        return None

    start_btn.click(on_start, outputs=None)
    stop_btn.click(on_stop, outputs=None)

    # Presets + resolution
    load_btn.click(apply_preset, inputs=preset_dd, outputs=None)
    clear_btn.click(clear_filters, outputs=None)

    def on_resolution(res_str):
        w, h = map(int, res_str.split("x"))
        was_running = engine.is_running
        if was_running:
            engine.stop()
        source.set_resolution(w, h)
        if was_running:
            engine.start()
        return None

    res_dd.change(on_resolution, inputs=res_dd, outputs=None)


print_banner(port=7860)
print("Launching...", flush=True)
demo.launch(server_name="0.0.0.0", server_port=7860)
