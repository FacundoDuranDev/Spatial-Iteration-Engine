"""Angle dial widget — draggable SVG needle that writes a float into a hidden
Gradio Number component. SVG shape matches design/ui_kits/mcp_v2 — tick
marks, phosphor-cyan arc, pointer, center puck, glowing knob handle. Used
for any 0-360° parameter (TemporalScan angle, Kaleidoscope rotation,
Radial Blur direction, etc.).
"""

from typing import Tuple

import gradio as gr

from . import register_assets

register_assets(js="angle_dial.js", css="widgets.css")


def angle_dial(
    value: float = 0.0,
    label: str = "Angle",
    min_value: float = 0.0,
    max_value: float = 360.0,
    step: float = 1.0,
    elem_id: str = None,
) -> Tuple[gr.HTML, gr.Number]:
    """Create an angle dial.

    Returns ``(dial_html, value_component)``. Wire ``value_component.change``
    to your filter callback exactly as you would for a ``gr.Slider``.
    """
    if elem_id is None:
        elem_id = f"sie-angle-dial-{id(object())}"

    html = f"""
    <div class="sie-root">
      <div class="sie-angle-dial" data-widget="angle-dial"
           data-target="{elem_id}-value"
           data-min="{min_value}" data-max="{max_value}" data-step="{step}"
           id="{elem_id}-dial">
        <div class="sie-dial-label">{label}</div>
        <div class="sie-dial-ring"></div>
        <div class="sie-dial-readout">{value:.0f}°</div>
      </div>
    </div>
    """

    dial_html = gr.HTML(html, elem_id=elem_id)
    # Kept in DOM (not visible=False) so the JS can read/write its <input>.
    # Visually hidden via the sie-hidden-host CSS class.
    value_component = gr.Number(
        value=value,
        elem_id=f"{elem_id}-value",
        elem_classes=["sie-hidden-host"],
        precision=2,
        interactive=True,
        show_label=False,
    )
    return dial_html, value_component
