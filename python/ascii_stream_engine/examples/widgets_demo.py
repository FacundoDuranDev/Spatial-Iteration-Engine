#!/usr/bin/env python
"""Minimal demo of the Spatial-Iteration-Engine widget kit — no engine
attached. Renders the four core widgets (angle dial, slider, stepper,
toggle) inside a phone-sized frame matching ``design/ui_kits/mcp_v2``.

Run: ``python python/ascii_stream_engine/examples/widgets_demo.py``
Then open http://localhost:7861 (or the LAN URL printed in console).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import gradio as gr

from ascii_stream_engine.presentation.widgets import (
    angle_dial,
    bundle_css,
    bundle_js,
    slider_row,
    stepper,
    toggle,
)


def build() -> gr.Blocks:
    extra_css = """
    body, .gradio-container { background: #05060b !important; }
    .gradio-container { max-width: 440px !important; }
    """
    with gr.Blocks(js=bundle_js(), css=bundle_css() + extra_css,
                   title="SIE widget kit") as demo:
        gr.HTML("""
          <div class="sie-root" style="padding: 16px;">
            <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
              <div class="sie-pill sie-pill-running">
                <span class="sie-pill-dot"></span> Running
              </div>
              <span class="sie-num" style="color:#8891a6; font-size:13px;">28.3 FPS</span>
            </div>
            <div class="sie-dial-label" style="opacity:0.6;">Widget kit — live preview</div>
          </div>
        """)

        gr.HTML('<div class="sie-root" style="padding: 0 16px;">'
                '<div class="sie-row sie-expanded"><div class="sie-row-head">'
                '<div class="sie-row-name">Temporal Scan</div></div>'
                '<div class="sie-row-body">')

        with gr.Column():
            _, scan_angle = angle_dial(value=134.0, label="Angle", elem_id="dial-scan")
            _, buffer_n = stepper(value=18, minimum=2, maximum=60, step=1,
                                  elem_id="step-buffer")
            _, blur = slider_row(value=0.65, minimum=0, maximum=1, step=0.01,
                                 label="Blur strength", elem_id="slider-blur")
            _, toggle_enable = toggle(value=True, label="Enable",
                                       elem_id="toggle-enable")

        gr.HTML("</div></div></div>")

        readout = gr.Textbox(
            label="Live values",
            value="angle=134°  buffer=18  blur=0.65  enabled=True",
            interactive=False,
        )

        def refresh(a, b, bl, en):
            return (
                f"angle={float(a or 0):.0f}°  "
                f"buffer={int(b or 0)}  "
                f"blur={float(bl or 0):.2f}  "
                f"enabled={bool(en)}"
            )

        for comp in (scan_angle, buffer_n, blur, toggle_enable):
            comp.change(
                refresh,
                inputs=[scan_angle, buffer_n, blur, toggle_enable],
                outputs=readout,
            )

    return demo


if __name__ == "__main__":
    build().launch(server_name="0.0.0.0", server_port=7861)
