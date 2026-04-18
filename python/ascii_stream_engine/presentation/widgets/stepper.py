"""Stepper — −/+ pair with a monospace numeric readout in the middle. Good
for integer params with a small range (kaleidoscope segments, sample count,
buffer frames, etc.).
"""

from typing import Tuple

import gradio as gr

from . import register_assets

register_assets(js="stepper.js", css="widgets.css")


def stepper(
    value: int = 0,
    minimum: int = 0,
    maximum: int = 10,
    step: int = 1,
    elem_id: str = None,
) -> Tuple[gr.HTML, gr.Number]:
    """Create a −/+ stepper. Returns ``(html, value_component)``."""
    if elem_id is None:
        elem_id = f"sie-stepper-{id(object())}"

    html = f"""
    <div class="sie-root">
      <div class="sie-stepper" data-widget="stepper"
           data-target="{elem_id}-value"
           data-min="{minimum}" data-max="{maximum}" data-step="{step}"
           id="{elem_id}-root">
        <button type="button" class="sie-stepper-btn" data-dir="-1" aria-label="decrement">−</button>
        <span class="sie-stepper-val">{value}</span>
        <button type="button" class="sie-stepper-btn" data-dir="+1" aria-label="increment">+</button>
      </div>
    </div>
    """

    html_component = gr.HTML(html, elem_id=elem_id)
    value_component = gr.Number(
        value=value,
        elem_id=f"{elem_id}-value",
        visible=False,
        precision=0,
        interactive=True,
    )
    return html_component, value_component
