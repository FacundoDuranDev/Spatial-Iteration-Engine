"""Toggle widget — on/off pill that mirrors a boolean into a hidden Gradio
Checkbox. Class markup comes from design/ui_kits/mcp_v2/components.css.
"""

from typing import Tuple

import gradio as gr

from . import register_assets

register_assets(js="toggle.js", css="widgets.css")


def toggle(
    value: bool = False,
    label: str = "",
    elem_id: str = None,
) -> Tuple[gr.HTML, gr.Checkbox]:
    """Create a toggle pill.

    Returns ``(html, checkbox)``. Wire ``checkbox.change`` to your callback.
    The ``label`` is optional and rendered to the left; leave empty to embed
    the pill inside a custom row layout.
    """
    if elem_id is None:
        elem_id = f"sie-toggle-{id(object())}"

    state_class = "sie-on" if value else ""
    label_html = (
        f'<span class="sie-slider-label" style="margin-right:12px">{label}</span>'
        if label else ""
    )
    html = f"""
    <div class="sie-root">
      <div style="display:flex; align-items:center; gap:12px;">
        {label_html}
        <div class="sie-toggle {state_class}" data-widget="toggle"
             data-target="{elem_id}-value"
             id="{elem_id}-root"
             role="switch" aria-checked="{str(value).lower()}">
          <div class="sie-toggle-thumb"></div>
        </div>
      </div>
    </div>
    """

    html_component = gr.HTML(html, elem_id=elem_id)
    checkbox = gr.Checkbox(
        value=value,
        elem_id=f"{elem_id}-value",
        visible=False,
        interactive=True,
    )
    return html_component, checkbox
