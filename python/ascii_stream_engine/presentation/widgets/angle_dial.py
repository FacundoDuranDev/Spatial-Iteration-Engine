"""Angle dial widget — draggable SVG needle that writes a float into a hidden
Gradio Number component. Use it for any 0-360° parameter (TemporalScan angle,
Kaleidoscope rotation, Radial Blur direction, etc.).
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
    # elem_id must be unique per instance; Gradio uses it for DOM lookups.
    if elem_id is None:
        elem_id = f"angle-dial-{id(object())}"

    svg = f"""
    <div class="sie-angle-dial" data-widget="angle-dial"
         data-target="{elem_id}-value"
         data-min="{min_value}" data-max="{max_value}" data-step="{step}">
      <div class="sie-widget-label">{label}</div>
      <svg viewBox="0 0 120 120" class="sie-dial-svg">
        <circle cx="60" cy="60" r="52" class="sie-dial-ring"/>
        <line x1="60" y1="60" x2="60" y2="12" class="sie-dial-needle"/>
        <circle cx="60" cy="60" r="6" class="sie-dial-hub"/>
        <text x="60" y="112" text-anchor="middle" class="sie-dial-readout">
          {value:.0f}°
        </text>
      </svg>
    </div>
    """

    dial_html = gr.HTML(svg, elem_id=elem_id)
    value_component = gr.Number(
        value=value,
        elem_id=f"{elem_id}-value",
        visible=False,
        precision=2,
        interactive=True,
    )
    return dial_html, value_component
