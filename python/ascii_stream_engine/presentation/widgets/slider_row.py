"""Slider row — styled single-value slider that writes a float into a hidden
Gradio Number. Visual matches design/ui_kits/mcp_v2 (cyan fill, glowing
handle, monospace value readout on the right).
"""

from typing import Tuple

import gradio as gr

from . import register_assets

register_assets(js="slider_row.js", css="widgets.css")


def slider_row(
    value: float = 0.0,
    minimum: float = 0.0,
    maximum: float = 1.0,
    step: float = 0.01,
    label: str = "VALUE",
    unit: str = "",
    elem_id: str = None,
) -> Tuple[gr.HTML, gr.Number]:
    """Create a styled slider.

    Returns ``(html, value_component)``. Wire ``value_component.change`` to
    your callback. ``unit`` is an optional suffix appended after the numeric
    readout (e.g. ``"px"``, ``"°"``, ``"ms"``).
    """
    if elem_id is None:
        elem_id = f"sie-slider-{id(object())}"

    html = f"""
    <div class="sie-root">
      <div class="sie-slider" data-widget="slider"
           data-target="{elem_id}-value"
           data-min="{minimum}" data-max="{maximum}" data-step="{step}"
           data-unit="{unit}"
           id="{elem_id}-root">
        <div class="sie-slider-top">
          <span class="sie-slider-label">{label}</span>
          <span class="sie-slider-val">{value:g}{unit}</span>
        </div>
        <div class="sie-slider-track">
          <div class="sie-slider-fill" style="width:0%"></div>
          <div class="sie-slider-handle" style="left:0%"></div>
        </div>
      </div>
    </div>
    """

    html_component = gr.HTML(html, elem_id=elem_id)
    value_component = gr.Number(
        value=value,
        elem_id=f"{elem_id}-value",
        visible=False,
        precision=4,
        interactive=True,
    )
    return html_component, value_component
