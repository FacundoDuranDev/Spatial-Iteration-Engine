#!/usr/bin/env python
"""Minimal demo of the custom widget factory — no engine attached.

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
)


def build() -> gr.Blocks:
    with gr.Blocks(js=bundle_js(), css=bundle_css(), title="SIE widget demo") as demo:
        gr.Markdown("# Angle dial widget — POC\nDrag the needle or tap around the ring.")

        with gr.Row():
            with gr.Column(scale=1):
                _, scan_angle = angle_dial(
                    value=0.0, label="Temporal scan angle", elem_id="dial-a"
                )
            with gr.Column(scale=1):
                _, kal_rot = angle_dial(
                    value=45.0, label="Kaleidoscope rotation", elem_id="dial-b"
                )

        readout = gr.Textbox(
            label="Live values",
            value="scan=0.00°   kaleidoscope=45.00°",
            interactive=False,
        )

        def refresh(a, b):
            a = float(a or 0.0)
            b = float(b or 0.0)
            return f"scan={a:.2f}°   kaleidoscope={b:.2f}°"

        scan_angle.change(refresh, inputs=[scan_angle, kal_rot], outputs=readout)
        kal_rot.change(refresh, inputs=[scan_angle, kal_rot], outputs=readout)

    return demo


if __name__ == "__main__":
    build().launch(server_name="0.0.0.0", server_port=7861)
