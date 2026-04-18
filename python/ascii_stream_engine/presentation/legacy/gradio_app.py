"""LEGACY Gradio + FastRTC dashboard.

Kept for reference only. This module has its own filter state that is NOT
connected to StreamEngine, so its controls do not affect the real pipeline.
Use ``run_dashboard.py`` at the repo root instead.

If you really need to load it:
    from ascii_stream_engine.presentation.legacy.gradio_app import build_gradio_dashboard
    demo = build_gradio_dashboard()
    demo.launch()
"""

import cv2
import numpy as np

try:
    import gradio as gr
except ImportError:
    raise ImportError(
        "Gradio is required for the dashboard. Install with: pip install gradio>=4.0"
    )

from ...adapters.processors.filters import (
    ALL_FILTERS,
    BloomCinematicFilter,
    ChromaticAberrationFilter,
    ColorGradingFilter,
    DepthOfFieldFilter,
    DoubleVisionFilter,
    FilmGrainFilter,
    GlitchBlockFilter,
    KineticTypographyFilter,
    LensFlareFilter,
    MotionBlurFilter,
    PanelCompositorFilter,
    RadialBlurFilter,
    VignetteFilter,
    deserialize_filter,
)
from ...domain.config import EngineConfig
from ..gradio_helpers import load_mp3_presets, order_mp3_filters


# ---------------------------------------------------------------------------
# Shared filter chain state
# ---------------------------------------------------------------------------
_active_filters = []
_config = EngineConfig()


def _get_filter(name):
    for f in _active_filters:
        if f.name == name:
            return f
    return None


def _toggle(name, cls, enabled, **defaults):
    if enabled:
        existing = _get_filter(name)
        if existing is None:
            _active_filters.append(cls(**defaults))
        else:
            existing.enabled = True
        return f"{name}: ON"
    else:
        f = _get_filter(name)
        if f:
            f.enabled = False
        return f"{name}: OFF"


def _set_param(name, param, value):
    f = _get_filter(name)
    if f:
        attr = f"_{param}"
        if hasattr(f, attr):
            setattr(f, attr, value)


def process_frame(frame):
    """Process a single frame through the active MP3 filter chain.

    Frame arrives as RGB numpy from WebRTC/Gradio, filters expect BGR.
    """
    if frame is None:
        return None

    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    ordered = order_mp3_filters([f for f in _active_filters if f.enabled])
    for flt in ordered:
        try:
            bgr = flt.apply(bgr, _config)
        except Exception:
            pass

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Main dashboard builder
# ---------------------------------------------------------------------------
def build_gradio_dashboard(title="Spatial-Iteration-Engine // MP3 FX"):
    """Build a Gradio Blocks dashboard with FastRTC WebRTC or basic webcam.

    Tries to use ``fastrtc.WebRTC`` for low-latency WebRTC streaming.
    Falls back to ``gr.Image(sources=['webcam']).stream()`` if fastrtc is
    not installed.

    Returns:
        gr.Blocks — call ``.launch()`` to start.
    """
    try:
        from fastrtc import WebRTC
        _has_webrtc = True
    except ImportError:
        _has_webrtc = False

    presets = load_mp3_presets()
    preset_names = [p["name"] for p in presets]

    with gr.Blocks(title=title, theme=gr.themes.Monochrome()) as demo:
        gr.Markdown(f"# {title}")
        if _has_webrtc:
            gr.Markdown("*WebRTC streaming (low latency)*")
        else:
            gr.Markdown("*HTTP streaming — install `fastrtc` for lower latency*")

        status_box = gr.Textbox(label="Status", value="Ready", interactive=False, visible=True)

        with gr.Row():
            # ===== LEFT: Controls =====
            with gr.Column(scale=2):
                with gr.Tabs():
                    # ---- COLOR GRADING ----
                    with gr.Tab("Color Grading"):
                        cg_en = gr.Checkbox(label="Enable", value=False)
                        cg_sat = gr.Slider(0.0, 2.0, 1.0, step=0.05, label="Saturation")
                        cg_shad = gr.Slider(0.0, 1.0, 0.3, step=0.05, label="Shadow Strength")
                        cg_high = gr.Slider(0.0, 1.0, 0.3, step=0.05, label="Highlight Strength")
                        cg_r = gr.Slider(0.5, 2.0, 1.0, step=0.05, label="Red Gain")
                        cg_g = gr.Slider(0.5, 2.0, 1.0, step=0.05, label="Green Gain")
                        cg_b = gr.Slider(0.5, 2.0, 1.0, step=0.05, label="Blue Gain")

                        cg_en.change(lambda v: _toggle("color_grading", ColorGradingFilter, v), inputs=cg_en, outputs=status_box)
                        cg_sat.change(lambda v: _set_param("color_grading", "saturation", v), inputs=cg_sat)
                        cg_shad.change(lambda v: _set_param("color_grading", "shadow_strength", v), inputs=cg_shad)
                        cg_high.change(lambda v: _set_param("color_grading", "highlight_strength", v), inputs=cg_high)
                        cg_r.change(lambda v: _set_param("color_grading", "gain_r", v), inputs=cg_r)
                        cg_g.change(lambda v: _set_param("color_grading", "gain_g", v), inputs=cg_g)
                        cg_b.change(lambda v: _set_param("color_grading", "gain_b", v), inputs=cg_b)

                    # ---- FILM LOOK ----
                    with gr.Tab("Film Look"):
                        gr.Markdown("#### Film Grain")
                        fg_en = gr.Checkbox(label="Enable", value=False)
                        fg_int = gr.Slider(0.0, 0.5, 0.15, step=0.01, label="Intensity")
                        fg_sz = gr.Slider(1, 4, 1, step=1, label="Grain Size")

                        gr.Markdown("#### Vignette")
                        vig_en = gr.Checkbox(label="Enable", value=False)
                        vig_int = gr.Slider(0.0, 1.0, 0.6, step=0.05, label="Intensity")
                        vig_inner = gr.Slider(0.0, 1.0, 0.4, step=0.05, label="Inner Radius")

                        gr.Markdown("#### Cinematic Bloom")
                        bl_en = gr.Checkbox(label="Enable", value=False)
                        bl_int = gr.Slider(0.0, 2.0, 0.5, step=0.05, label="Intensity")
                        bl_thr = gr.Slider(100, 255, 200, step=5, label="Threshold")
                        bl_ana = gr.Slider(1.0, 5.0, 1.0, step=0.5, label="Anamorphic Ratio")

                        gr.Markdown("#### Lens Flare")
                        lf_en = gr.Checkbox(label="Enable", value=False)
                        lf_int = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="Intensity")
                        lf_str = gr.Slider(0.0, 0.8, 0.3, step=0.05, label="Streak Length")

                        fg_en.change(lambda v: _toggle("film_grain", FilmGrainFilter, v), inputs=fg_en, outputs=status_box)
                        fg_int.change(lambda v: _set_param("film_grain", "intensity", v), inputs=fg_int)
                        fg_sz.change(lambda v: _set_param("film_grain", "grain_size", int(v)), inputs=fg_sz)
                        vig_en.change(lambda v: _toggle("vignette", VignetteFilter, v), inputs=vig_en, outputs=status_box)
                        vig_int.change(lambda v: _set_param("vignette", "intensity", v), inputs=vig_int)
                        vig_inner.change(lambda v: _set_param("vignette", "inner_radius", v), inputs=vig_inner)
                        bl_en.change(lambda v: _toggle("bloom_cinematic", BloomCinematicFilter, v), inputs=bl_en, outputs=status_box)
                        bl_int.change(lambda v: _set_param("bloom_cinematic", "intensity", v), inputs=bl_int)
                        bl_thr.change(lambda v: _set_param("bloom_cinematic", "threshold", int(v)), inputs=bl_thr)
                        bl_ana.change(lambda v: _set_param("bloom_cinematic", "anamorphic_ratio", v), inputs=bl_ana)
                        lf_en.change(lambda v: _set_param("lens_flare", "intensity", v) or _toggle("lens_flare", LensFlareFilter, v), inputs=lf_en, outputs=status_box)
                        lf_int.change(lambda v: _set_param("lens_flare", "intensity", v), inputs=lf_int)
                        lf_str.change(lambda v: _set_param("lens_flare", "streak_length", v), inputs=lf_str)

                    # ---- DISTORTION ----
                    with gr.Tab("Distortion"):
                        gr.Markdown("#### Radial Blur")
                        rb_en = gr.Checkbox(label="Enable", value=False)
                        rb_str = gr.Slider(0.0, 1.0, 0.3, step=0.05, label="Strength")
                        rb_smp = gr.Slider(2, 16, 8, step=1, label="Samples")

                        gr.Markdown("#### Double Vision")
                        dv_en = gr.Checkbox(label="Enable", value=False)
                        dv_off = gr.Slider(0.0, 30.0, 10.0, step=1.0, label="Offset")
                        dv_spd = gr.Slider(0.01, 0.3, 0.05, step=0.01, label="Speed")
                        dv_tmp = gr.Slider(0.0, 0.8, 0.3, step=0.05, label="Temporal Blend")

                        gr.Markdown("#### Motion Blur")
                        mb_en = gr.Checkbox(label="Enable (needs optical flow)", value=False)
                        mb_str = gr.Slider(0.0, 3.0, 1.0, step=0.1, label="Strength")

                        gr.Markdown("#### Depth of Field")
                        dof_en = gr.Checkbox(label="Enable", value=False)
                        dof_fy = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="Focal Y")
                        dof_br = gr.Slider(3, 31, 15, step=2, label="Blur Radius")

                        rb_en.change(lambda v: _toggle("radial_blur", RadialBlurFilter, v), inputs=rb_en, outputs=status_box)
                        rb_str.change(lambda v: _set_param("radial_blur", "strength", v), inputs=rb_str)
                        rb_smp.change(lambda v: _set_param("radial_blur", "samples", int(v)), inputs=rb_smp)
                        dv_en.change(lambda v: _toggle("double_vision", DoubleVisionFilter, v), inputs=dv_en, outputs=status_box)
                        dv_off.change(lambda v: _set_param("double_vision", "offset_x", v), inputs=dv_off)
                        dv_spd.change(lambda v: _set_param("double_vision", "oscillation_speed", v), inputs=dv_spd)
                        dv_tmp.change(lambda v: _set_param("double_vision", "temporal_blend", v), inputs=dv_tmp)
                        mb_en.change(lambda v: _toggle("motion_blur", MotionBlurFilter, v), inputs=mb_en, outputs=status_box)
                        mb_str.change(lambda v: _set_param("motion_blur", "strength", v), inputs=mb_str)
                        dof_en.change(lambda v: _toggle("depth_of_field", DepthOfFieldFilter, v), inputs=dof_en, outputs=status_box)
                        dof_fy.change(lambda v: _set_param("depth_of_field", "focal_y", v), inputs=dof_fy)
                        dof_br.change(lambda v: _set_param("depth_of_field", "blur_radius", int(v)), inputs=dof_br)

                    # ---- GLITCH ----
                    with gr.Tab("Glitch"):
                        gr.Markdown("#### Block Glitch")
                        gb_en = gr.Checkbox(label="Enable", value=False)
                        gb_cor = gr.Slider(0.0, 0.5, 0.05, step=0.01, label="Corruption")
                        gb_rgb = gr.Slider(0, 15, 3, step=1, label="RGB Split")
                        gb_ilc = gr.Checkbox(label="Interlace", value=True)
                        gb_stb = gr.Slider(0, 8, 2, step=1, label="Static Bands")

                        gr.Markdown("#### Chromatic Aberration")
                        ca_en = gr.Checkbox(label="Enable", value=False)
                        ca_str = gr.Slider(0.0, 10.0, 3.0, step=0.5, label="Strength")

                        gb_en.change(lambda v: _toggle("glitch_block", GlitchBlockFilter, v), inputs=gb_en, outputs=status_box)
                        gb_cor.change(lambda v: _set_param("glitch_block", "corruption_rate", v), inputs=gb_cor)
                        gb_rgb.change(lambda v: _set_param("glitch_block", "rgb_split", int(v)), inputs=gb_rgb)
                        gb_ilc.change(lambda v: _set_param("glitch_block", "interlace", v), inputs=gb_ilc)
                        gb_stb.change(lambda v: _set_param("glitch_block", "static_bands", int(v)), inputs=gb_stb)
                        ca_en.change(lambda v: _toggle("chromatic_aberration", ChromaticAberrationFilter, v), inputs=ca_en, outputs=status_box)
                        ca_str.change(lambda v: _set_param("chromatic_aberration", "strength", v), inputs=ca_str)

                    # ---- TYPOGRAPHY ----
                    with gr.Tab("Typography"):
                        kt_en = gr.Checkbox(label="Enable Kinetic Text", value=False)
                        kt_txt = gr.Textbox(value="MAX PAYNE", label="Text")
                        kt_fsz = gr.Slider(16, 120, 48, step=4, label="Font Size")
                        kt_opa = gr.Slider(0.0, 1.0, 0.85, step=0.05, label="Opacity")
                        kt_ani = gr.Dropdown(["scale_in", "fade_in", "hard_cut"], value="scale_in", label="Animation")

                        gr.Markdown("#### Panel Compositor")
                        pc_en = gr.Checkbox(label="Enable", value=False)
                        pc_lay = gr.Dropdown(["2x1", "1x2", "2x2", "3x1"], value="2x1", label="Layout")
                        pc_brd = gr.Slider(1, 10, 3, step=1, label="Border")
                        pc_ang = gr.Slider(-30, 30, 0, step=1, label="Angle")

                        kt_en.change(lambda v: _toggle("kinetic_typography", KineticTypographyFilter, v), inputs=kt_en, outputs=status_box)
                        kt_txt.change(lambda v: _set_param("kinetic_typography", "text", v), inputs=kt_txt)
                        kt_fsz.change(lambda v: _set_param("kinetic_typography", "font_size", int(v)), inputs=kt_fsz)
                        kt_opa.change(lambda v: _set_param("kinetic_typography", "opacity", v), inputs=kt_opa)
                        kt_ani.change(lambda v: _set_param("kinetic_typography", "animation", v), inputs=kt_ani)
                        pc_en.change(lambda v: _toggle("panel_compositor", PanelCompositorFilter, v), inputs=pc_en, outputs=status_box)
                        pc_lay.change(lambda v: _set_param("panel_compositor", "layout", v), inputs=pc_lay)
                        pc_brd.change(lambda v: _set_param("panel_compositor", "border_width", int(v)), inputs=pc_brd)
                        pc_ang.change(lambda v: _set_param("panel_compositor", "angle", float(v)), inputs=pc_ang)

                    # ---- PRESETS ----
                    with gr.Tab("Presets"):
                        gr.Markdown("### Max Payne 3 Presets")
                        preset_dd = gr.Dropdown(
                            choices=preset_names,
                            value=preset_names[0] if preset_names else None,
                            label="Preset",
                        )
                        load_btn = gr.Button("Load", variant="primary")
                        clear_btn = gr.Button("Clear All")

                        def _load_preset(name):
                            _active_filters.clear()
                            for p in load_mp3_presets():
                                if p["name"] == name:
                                    for fc in p.get("filter_configs", []):
                                        try:
                                            _active_filters.append(deserialize_filter(fc))
                                        except (KeyError, TypeError):
                                            pass
                                    return f"Loaded '{name}': {len(_active_filters)} filters"
                            return f"'{name}' not found"

                        def _clear():
                            _active_filters.clear()
                            return "Cleared"

                        load_btn.click(_load_preset, inputs=preset_dd, outputs=status_box)
                        clear_btn.click(_clear, outputs=status_box)

                    # ---- INFO ----
                    with gr.Tab("Info"):
                        n_active = gr.Textbox(label="Active Filters", interactive=False)
                        refresh_btn = gr.Button("Refresh")

                        def _info():
                            active = [f.name for f in _active_filters if f.enabled]
                            return f"{len(active)} active: {', '.join(active) if active else '(none)'}"

                        refresh_btn.click(_info, outputs=n_active)

                        gr.Markdown(f"### {len(ALL_FILTERS)} Registered Filters")
                        fl = "\n".join(f"- `{n}` ({c.__name__})" for n, c in sorted(ALL_FILTERS.items()))
                        gr.Markdown(fl)

            # ===== RIGHT: Video stream =====
            with gr.Column(scale=3):
                if _has_webrtc:
                    gr.Markdown("### WebRTC Stream")
                    webrtc = WebRTC(label="Webcam → MP3 FX", mode="send-receive")
                    webrtc.stream(
                        fn=process_frame,
                        inputs=[webrtc],
                        outputs=[webrtc],
                        time_limit=600,
                    )
                else:
                    gr.Markdown("### Webcam Stream")
                    with gr.Row():
                        webcam = gr.Image(sources=["webcam"], type="numpy", label="Input")
                        output = gr.Image(streaming=True, label="Output")
                    webcam.stream(
                        fn=process_frame,
                        inputs=[webcam],
                        outputs=[output],
                        time_limit=300,
                        stream_every=0.1,
                        concurrency_limit=30,
                    )

    return demo


# Keep backward compat alias.
build_gradio_dashboard_basic = build_gradio_dashboard
