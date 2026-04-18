#!/usr/bin/env python
"""MP3 FX Dashboard — integrated with StreamEngine pipeline. All 40 filters."""
import sys
import os
import socket
import threading
import time as _time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cpp", "build"))

import cv2
import numpy as np
import gradio as gr

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
from ascii_stream_engine.application.pipeline import FilterPipeline
from ascii_stream_engine.adapters.processors.filters import (
    ALL_FILTERS,
    BloomCinematicFilter, ChromaticAberrationFilter, ColorGradingFilter,
    DepthOfFieldFilter, DoubleVisionFilter, FilmGrainFilter,
    GlitchBlockFilter, KineticTypographyFilter, LensFlareFilter,
    MotionBlurFilter, PanelCompositorFilter, RadialBlurFilter, VignetteFilter,
    BloomFilter, BoidsFilter, BrightnessFilter, CRTGlitchFilter,
    DetailBoostFilter, EdgeFilter, EdgeSmoothFilter, GeometricPatternFilter,
    HandFrameFilter, HandSpatialWarpFilter, InvertFilter, KaleidoscopeFilter,
    KuwaharaFilter, MosaicFilter, OpticalFlowParticlesFilter, PhysarumFilter,
    RadialCollapseFilter, SlitScanFilter, StipplingFilter, ToonShadingFilter,
    UVDisplacementFilter,
    CppBrightnessContrastFilter, CppChannelSwapFilter, CppGrayscaleFilter,
    CppInvertFilter, CppPhysarumFilter,
    deserialize_filter,
)
from ascii_stream_engine.presentation.gradio_helpers import load_mp3_presets
from PIL import Image


# ---------------------------------------------------------------------------
# BufferSink — zero-copy, skips PIL when possible
# ---------------------------------------------------------------------------
class BufferSink:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None  # stored as RGB numpy
        self._is_open = False
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = _time.monotonic()
        self._fps_count = 0

    def open(self, config, output_size):
        self._is_open = True

    def write(self, frame):
        image = frame.image if hasattr(frame, "image") else frame
        if isinstance(image, Image.Image):
            # PIL path (from PassthroughRenderer) — convert once
            arr = np.asarray(image)  # zero-copy if possible
            if image.mode != "RGB":
                arr = np.array(image.convert("RGB"))
        elif isinstance(image, np.ndarray):
            arr = image
        else:
            return
        with self._lock:
            self._frame = arr
            self._frame_count += 1
            # FPS calculation
            self._fps_count += 1
            now = _time.monotonic()
            dt = now - self._last_fps_time
            if dt >= 1.0:
                self._fps = self._fps_count / dt
                self._fps_count = 0
                self._last_fps_time = now

    def close(self):
        self._is_open = False
        with self._lock:
            self._frame = None

    def is_open(self):
        return self._is_open

    def get_latest_rgb(self):
        with self._lock:
            return self._frame if self._frame is not None else None

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
# ResizingCameraSource — wraps OpenCVCameraSource with resolution control
# ---------------------------------------------------------------------------
class ResizingCameraSource:
    """Camera source that downscales frames for performance."""

    def __init__(self, camera_index=0, width=640, height=480):
        self._inner = OpenCVCameraSource(camera_index=camera_index)
        self._width = width
        self._height = height

    def set_resolution(self, width, height):
        self._width = width
        self._height = height

    def open(self):
        self._inner.open()
        # Try to set camera resolution directly (faster than resize)
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
preview_sink = PreviewSink(window_name="Spatial-Iteration-Engine — f=fullscreen, ESC=exit")
sink = CompositeOutputSink([buffer_sink, preview_sink])
engine = StreamEngine(
    source=source, renderer=renderer, sink=sink,
    config=config, enable_profiling=True,
)
fp = engine.filter_pipeline


def get_filter(name):
    for f in fp.filters:
        if f.name == name:
            return f
    return None


def ensure_filter(name, cls, **kw):
    f = get_filter(name)
    if f is None:
        f = cls(**kw)
        fp.add(f)
    return f


def get_stats():
    fps = buffer_sink.get_fps()
    n_filters = len([f for f in fp.filters if f.enabled])
    frames = buffer_sink.get_frame_count()
    return f"{fps:.1f} FPS | {n_filters} filters | {frames} frames"


# ---------------------------------------------------------------------------
# Helper: generic toggle factory to avoid closure bugs
# ---------------------------------------------------------------------------
def make_toggle(filter_name, filter_cls, param_names):
    """Create a toggle callback for a filter with given params."""
    def toggle_fn(*args):
        en = args[0]
        if en:
            f = ensure_filter(filter_name, filter_cls)
            f.enabled = True
            for i, pname in enumerate(param_names):
                val = args[1 + i]
                attr = f"_{pname}"
                if hasattr(f, attr):
                    setattr(f, attr, val)
            return f"{filter_name}: ON"
        else:
            f = get_filter(filter_name)
            if f:
                f.enabled = False
            return f"{filter_name}: OFF"
    return toggle_fn


def wire(toggle_fn, controls, status_box):
    """Wire all controls to a toggle function."""
    for c in controls:
        c.change(toggle_fn, controls, status_box)


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------
presets = load_mp3_presets()
preset_map = {p["name"]: p for p in presets}
preset_names = list(preset_map.keys())

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
print("Building UI...", flush=True)

with gr.Blocks(title="Spatial-Iteration-Engine FX") as demo:

    with gr.Sidebar(label="FX Controls", open=True):
        status = gr.Textbox(value="Stopped", label="Status", interactive=False)

        # ── ENGINE ──
        with gr.Accordion("Engine", open=True):
            with gr.Row():
                start_btn = gr.Button("Start", variant="primary", size="sm")
                stop_btn = gr.Button("Stop", variant="stop", size="sm")
            res_dd = gr.Dropdown(
                choices=["320x240", "640x480", "800x600", "1280x720"],
                value="640x480", label="Resolution",
            )
            fps_display = gr.Textbox(value="0 FPS", label="Performance", interactive=False)

            def on_start():
                if not engine.is_running:
                    engine.start()
                    return "Running"
                return "Already running"

            def on_stop():
                if engine.is_running:
                    engine.stop()
                    return "Stopped"
                return "Already stopped"

            def on_resolution(res_str):
                w, h = map(int, res_str.split("x"))
                was_running = engine.is_running
                if was_running:
                    engine.stop()
                source.set_resolution(w, h)
                if was_running:
                    engine.start()
                return f"Resolution: {w}x{h}"

            start_btn.click(on_start, outputs=status)
            stop_btn.click(on_stop, outputs=status)
            res_dd.change(on_resolution, inputs=res_dd, outputs=status)

            # Auto-refresh FPS counter
            fps_timer = gr.Timer(value=1.0)
            fps_timer.tick(get_stats, outputs=fps_display)

        # ── PRESETS ──
        with gr.Accordion("Presets", open=True):
            preset_dd = gr.Dropdown(["(none)"] + preset_names, value="(none)", label="Scene")
            with gr.Row():
                load_btn = gr.Button("Load", variant="primary", size="sm")
                clear_btn = gr.Button("Clear", variant="stop", size="sm")

            def on_load(name):
                if name == "(none)":
                    return "Select a preset"
                p = preset_map.get(name)
                if not p:
                    return f"'{name}' not found"
                fp.clear()
                for fc in p.get("filter_configs", []):
                    try:
                        fp.add(deserialize_filter(fc))
                    except Exception:
                        pass
                return f"'{name}': {len(fp.filters)} filters"

            def on_clear():
                fp.clear()
                return "Cleared"

            load_btn.click(on_load, inputs=preset_dd, outputs=status)
            clear_btn.click(on_clear, outputs=status)

        # ==================================================================
        # MP3 CINEMATIC EFFECTS
        # ==================================================================
        gr.Markdown("### Cinematic (MP3)")

        # ── Color Grading ──
        with gr.Accordion("Color Grading", open=False):
            cg_en = gr.Checkbox(label="Enable", value=False)
            cg_sat = gr.Slider(0, 2, 1, step=0.05, label="Saturation")
            cg_shd = gr.Slider(0, 1, 0.3, step=0.05, label="Shadow Tint")
            cg_hil = gr.Slider(0, 1, 0.3, step=0.05, label="Highlight Tint")
            cg_r = gr.Slider(0.5, 2, 1, step=0.05, label="Red Gain")
            cg_g = gr.Slider(0.5, 2, 1, step=0.05, label="Green Gain")
            cg_b = gr.Slider(0.5, 2, 1, step=0.05, label="Blue Gain")

            def cg_fn(en, sat, shd, hil, r, g, b):
                if en:
                    f = ensure_filter("color_grading", ColorGradingFilter)
                    f.enabled = True
                    f._saturation = sat; f._shadow_strength = shd; f._highlight_strength = hil
                    f._gain_r = r; f._gain_g = g; f._gain_b = b
                    return "color_grading: ON"
                f = get_filter("color_grading"); f and setattr(f, 'enabled', False)
                return "color_grading: OFF"
            wire(cg_fn, [cg_en, cg_sat, cg_shd, cg_hil, cg_r, cg_g, cg_b], status)

        # ── Film Grain ──
        with gr.Accordion("Film Grain", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 0.5, 0.15, step=0.01, label="Intensity"),
                 gr.Slider(1, 4, 1, step=1, label="Size")]
            wire(make_toggle("film_grain", FilmGrainFilter, ["intensity", "grain_size"]), c, status)

        # ── Vignette ──
        with gr.Accordion("Vignette", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.6, step=0.05, label="Intensity"),
                 gr.Slider(0, 1, 0.4, step=0.05, label="Inner Radius")]
            wire(make_toggle("vignette", VignetteFilter, ["intensity", "inner_radius"]), c, status)

        # ── Cinematic Bloom ──
        with gr.Accordion("Cinematic Bloom", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 2, 0.5, step=0.05, label="Intensity"),
                 gr.Slider(100, 255, 200, step=5, label="Threshold"),
                 gr.Slider(1, 5, 1, step=0.5, label="Anamorphic")]
            wire(make_toggle("bloom_cinematic", BloomCinematicFilter,
                             ["intensity", "threshold", "anamorphic_ratio"]), c, status)

        # ── Lens Flare ──
        with gr.Accordion("Lens Flare", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.5, step=0.05, label="Intensity"),
                 gr.Slider(0, 0.8, 0.3, step=0.05, label="Streak")]
            wire(make_toggle("lens_flare", LensFlareFilter, ["intensity", "streak_length"]), c, status)

        # ── Double Vision ──
        with gr.Accordion("Double Vision", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 30, 10, step=1, label="Offset"),
                 gr.Slider(0.01, 0.3, 0.05, step=0.01, label="Speed")]
            wire(make_toggle("double_vision", DoubleVisionFilter,
                             ["offset_x", "oscillation_speed"]), c, status)

        # ── Glitch Block ──
        with gr.Accordion("Glitch Block", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 0.5, 0.05, step=0.01, label="Corruption"),
                 gr.Slider(0, 15, 3, step=1, label="RGB Split")]
            wire(make_toggle("glitch_block", GlitchBlockFilter,
                             ["corruption_rate", "rgb_split"]), c, status)

        # ── Radial Blur ──
        with gr.Accordion("Radial Blur", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.3, step=0.05, label="Strength"),
                 gr.Slider(2, 16, 6, step=1, label="Samples")]
            wire(make_toggle("radial_blur", RadialBlurFilter,
                             ["strength", "samples"]), c, status)

        # ── Depth of Field ──
        with gr.Accordion("Depth of Field", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.5, step=0.05, label="Focal Y"),
                 gr.Slider(3, 31, 15, step=2, label="Blur Radius")]
            wire(make_toggle("depth_of_field", DepthOfFieldFilter,
                             ["focal_y", "blur_radius"]), c, status)

        # ── Motion Blur ──
        with gr.Accordion("Motion Blur", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 3, 1, step=0.1, label="Strength"),
                 gr.Slider(2, 16, 5, step=1, label="Samples")]
            wire(make_toggle("motion_blur", MotionBlurFilter,
                             ["strength", "samples"]), c, status)

        # ── Chromatic Aberration ──
        with gr.Accordion("Chromatic Aberration", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 10, 3, step=0.5, label="Strength")]
            wire(make_toggle("chromatic_aberration", ChromaticAberrationFilter,
                             ["strength"]), c, status)

        # ── Kinetic Typography ──
        with gr.Accordion("Kinetic Typography", open=False):
            kt_en = gr.Checkbox(label="Enable", value=False)
            kt_txt = gr.Textbox(value="MAX PAYNE", label="Text")
            kt_fsz = gr.Slider(16, 120, 48, step=4, label="Font Size")

            def kt_fn(en, txt, fsz):
                if en:
                    f = ensure_filter("kinetic_typography", KineticTypographyFilter)
                    f.enabled = True; f._text = txt; f._font_size = int(fsz)
                    f._text_image = None; f._cached_text_key = None
                    return "text: ON"
                f = get_filter("kinetic_typography"); f and setattr(f, 'enabled', False)
                return "text: OFF"
            wire(kt_fn, [kt_en, kt_txt, kt_fsz], status)

        # ── Panel Compositor ──
        with gr.Accordion("Panel Compositor", open=False):
            pc_en = gr.Checkbox(label="Enable", value=False)
            pc_lay = gr.Dropdown(["2x1", "1x2", "2x2", "3x1"], value="2x1", label="Layout")
            wire(make_toggle("panel_compositor", PanelCompositorFilter, ["layout"]),
                 [pc_en, pc_lay], status)

        # ==================================================================
        # STYLIZATION
        # ==================================================================
        gr.Markdown("### Stylization")

        # ── Toon Shading ──
        with gr.Accordion("Toon Shading", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("toon_shading", ToonShadingFilter, []), c, status)

        # ── Kuwahara (Oil Paint) ──
        with gr.Accordion("Kuwahara (Oil Paint)", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(2, 8, 4, step=1, label="Radius")]
            wire(make_toggle("kuwahara", KuwaharaFilter, ["radius"]), c, status)

        # ── Stippling (Pointillist) ──
        with gr.Accordion("Stippling", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0.1, 1, 0.5, step=0.05, label="Density"),
                 gr.Slider(1, 5, 1, step=1, label="Min Dot"),
                 gr.Slider(2, 10, 4, step=1, label="Max Dot")]
            wire(make_toggle("stippling", StipplingFilter,
                             ["density", "min_dot_size", "max_dot_size"]), c, status)

        # ── Edges (Canny) ──
        with gr.Accordion("Edges (Canny)", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(20, 200, 80, step=10, label="Low Threshold"),
                 gr.Slider(50, 300, 160, step=10, label="High Threshold")]
            wire(make_toggle("edges", EdgeFilter, ["low", "high"]), c, status)

        # ── Mosaic (Pixelate) ──
        with gr.Accordion("Mosaic (Pixelate)", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("mosaic", MosaicFilter, []), c, status)

        # ── Invert ──
        with gr.Accordion("Invert", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("invert", InvertFilter, []), c, status)

        # ==================================================================
        # DISTORTION
        # ==================================================================
        gr.Markdown("### Distortion")

        # ── Kaleidoscope ──
        with gr.Accordion("Kaleidoscope", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(2, 16, 6, step=1, label="Segments"),
                 gr.Slider(0, 6.28, 0, step=0.1, label="Rotation")]
            wire(make_toggle("kaleidoscope", KaleidoscopeFilter,
                             ["segments", "rotation"]), c, status)

        # ── Radial Collapse ──
        with gr.Accordion("Radial Collapse", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.5, step=0.05, label="Strength"),
                 gr.Slider(0, 1, 0.3, step=0.05, label="Falloff"),
                 gr.Dropdown(["collapse", "expand"], value="collapse", label="Mode")]
            wire(make_toggle("radial_collapse", RadialCollapseFilter,
                             ["strength", "falloff", "mode"]), c, status)

        # ── UV Displacement ──
        with gr.Accordion("UV Displacement", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Dropdown(["sin", "cos", "spiral", "noise"], value="sin", label="Function"),
                 gr.Slider(1, 30, 10, step=1, label="Amplitude"),
                 gr.Slider(0.5, 10, 2, step=0.5, label="Frequency")]
            wire(make_toggle("uv_displacement", UVDisplacementFilter,
                             ["function_type", "amplitude", "frequency"]), c, status)

        # ── Slit Scan ──
        with gr.Accordion("Slit Scan", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(5, 60, 30, step=5, label="Buffer Size"),
                 gr.Dropdown(["horizontal", "vertical"], value="horizontal", label="Direction")]
            wire(make_toggle("slit_scan", SlitScanFilter,
                             ["buffer_size", "direction"]), c, status)

        # ==================================================================
        # CRT / RETRO
        # ==================================================================
        gr.Markdown("### CRT / Retro")

        # ── CRT Glitch ──
        with gr.Accordion("CRT Glitch", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 1, 0.3, step=0.05, label="Scanlines"),
                 gr.Slider(0, 1, 0.3, step=0.05, label="Aberration"),
                 gr.Slider(0, 1, 0.1, step=0.05, label="Noise")]
            wire(make_toggle("crt_glitch", CRTGlitchFilter,
                             ["scanline_intensity", "aberration_strength", "noise_amount"]), c, status)

        # ==================================================================
        # PARTICLES / GENERATIVE
        # ==================================================================
        gr.Markdown("### Particles")

        # ── Boids ──
        with gr.Accordion("Boids (Flocking)", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(50, 500, 200, step=50, label="Count"),
                 gr.Slider(1, 10, 4, step=0.5, label="Max Speed")]
            wire(make_toggle("boids", BoidsFilter,
                             ["num_boids", "max_speed"]), c, status)

        # ── Physarum ──
        with gr.Accordion("Physarum (Slime Mold)", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(500, 8000, 4000, step=500, label="Agents"),
                 gr.Slider(0.1, 1, 0.7, step=0.05, label="Opacity")]
            wire(make_toggle("physarum", PhysarumFilter,
                             ["num_agents", "opacity"]), c, status)

        # ── Optical Flow Particles ──
        with gr.Accordion("Optical Flow Particles", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(200, 5000, 2000, step=200, label="Max Particles"),
                 gr.Slider(5, 60, 30, step=5, label="Lifetime")]
            wire(make_toggle("optical_flow_particles", OpticalFlowParticlesFilter,
                             ["max_particles", "particle_lifetime"]), c, status)

        # ==================================================================
        # SPATIAL / HAND-REACTIVE
        # ==================================================================
        gr.Markdown("### Hand-Reactive")

        # ── Geometric Patterns ──
        with gr.Accordion("Geometric Patterns", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Dropdown(["sacred_geometry", "voronoi", "delaunay", "lissajous", "strange_attractor"],
                             value="sacred_geometry", label="Pattern"),
                 gr.Slider(0, 1, 0.4, step=0.05, label="Opacity")]
            wire(make_toggle("geometric_patterns", GeometricPatternFilter,
                             ["pattern_mode", "opacity"]), c, status)

        # ── Hand Frame ──
        with gr.Accordion("Hand Frame", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Dropdown(["invert", "blur", "pixelate", "edge", "tint", "ascii"],
                             value="invert", label="Effect"),
                 gr.Slider(0, 2, 1, step=0.1, label="Strength")]
            wire(make_toggle("hand_frame", HandFrameFilter,
                             ["effect", "effect_strength"]), c, status)

        # ── Hand Spatial Warp ──
        with gr.Accordion("Hand Spatial Warp", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 500, 300, step=50, label="Strength"),
                 gr.Dropdown(["stretch", "compress", "twist"], value="stretch", label="Mode")]
            wire(make_toggle("hand_spatial_warp", HandSpatialWarpFilter,
                             ["strength", "mode"]), c, status)

        # ==================================================================
        # ADJUSTMENTS
        # ==================================================================
        gr.Markdown("### Adjustments")

        # ── Bloom (Basic) ──
        with gr.Accordion("Bloom (Basic)", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(100, 255, 200, step=5, label="Threshold"),
                 gr.Slider(0, 1, 0.6, step=0.05, label="Intensity")]
            wire(make_toggle("bloom", BloomFilter, ["threshold", "intensity"]), c, status)

        # ── Brightness / Contrast ──
        with gr.Accordion("Brightness / Contrast", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("brightness", BrightnessFilter, []), c, status)

        # ── Detail Boost ──
        with gr.Accordion("Detail Boost", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0.5, 5, 2, step=0.5, label="CLAHE Clip"),
                 gr.Slider(0, 1, 0.6, step=0.1, label="Sharpness")]
            wire(make_toggle("detail_boost", DetailBoostFilter,
                             ["clip_limit", "sharpness"]), c, status)

        # ── Edge Smooth ──
        with gr.Accordion("Edge Smooth", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(3, 15, 9, step=2, label="Diameter"),
                 gr.Slider(0, 1, 1, step=0.05, label="Strength")]
            wire(make_toggle("edge_smooth", EdgeSmoothFilter,
                             ["diameter", "strength"]), c, status)

        # ==================================================================
        # C++ ACCELERATED
        # ==================================================================
        gr.Markdown("### C++ Accelerated")

        with gr.Accordion("C++ Invert", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("cpp_invert", CppInvertFilter, []), c, status)

        with gr.Accordion("C++ Grayscale", open=False):
            c = [gr.Checkbox(label="Enable", value=False)]
            wire(make_toggle("cpp_grayscale", CppGrayscaleFilter, []), c, status)

        with gr.Accordion("C++ Brightness/Contrast", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(-100, 100, 0, step=5, label="Brightness"),
                 gr.Slider(0.5, 3, 1, step=0.1, label="Contrast")]
            wire(make_toggle("cpp_brightness_contrast", CppBrightnessContrastFilter,
                             ["brightness_delta", "contrast_factor"]), c, status)

        with gr.Accordion("C++ Channel Swap", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(0, 2, 2, step=1, label="B→Channel"),
                 gr.Slider(0, 2, 1, step=1, label="G→Channel"),
                 gr.Slider(0, 2, 0, step=1, label="R→Channel")]
            wire(make_toggle("cpp_channel_swap", CppChannelSwapFilter,
                             ["dst_for_b", "dst_for_g", "dst_for_r"]), c, status)

        with gr.Accordion("C++ Physarum", open=False):
            c = [gr.Checkbox(label="Enable", value=False),
                 gr.Slider(500, 10000, 4000, step=500, label="Agents"),
                 gr.Slider(0.1, 1, 0.7, step=0.05, label="Opacity")]
            wire(make_toggle("cpp_physarum", CppPhysarumFilter,
                             ["num_agents", "opacity"]), c, status)


def _get_lan_ip():
    """Return the outbound LAN IP without sending packets. Falls back to localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def print_banner(port=7860):
    ip = _get_lan_ip()
    url = f"http://{ip}:{port}"
    bar = "═" * 60
    print(f"\n{bar}\n  Spatial-Iteration-Engine — MP3 FX Dashboard\n{bar}")
    print(f"  Open on this PC:     http://localhost:{port}")
    print(f"  Open on phone (LAN): {url}")
    print(f"  Video preview:       native cv2 window (f = fullscreen, ESC)")
    print(f"{bar}")
    if _qrcode is not None:
        qr = _qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    else:
        print("  (install `qrcode` to see a scannable QR here)")
    print(f"{bar}\n", flush=True)


print(f"Total filters available: {len(ALL_FILTERS)}", flush=True)
print("Click 'Start' to begin.", flush=True)
print_banner(port=7860)
demo.launch(server_name="0.0.0.0", server_port=7860)
