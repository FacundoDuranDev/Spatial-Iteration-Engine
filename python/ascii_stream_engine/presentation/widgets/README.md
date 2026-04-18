# Custom Gradio widgets

Graphical controls (dials, sliders, toggles, steppers) styled to match
the mobile control surface designed under `design/ui_kits/mcp_v2/`
(phosphor-cyan on terminal black). Plain SVG + vanilla JS, no Node
build step.

## How they fit together

Each widget is a factory function that returns a pair:

1. A visible `gr.HTML` block containing the SVG / DOM for the widget.
2. A hidden `gr.Number` or `gr.Checkbox` that holds the current value.

The JS listens for pointer / click events, updates the visible DOM, then
writes the value into the hidden input and dispatches `input`/`change`
events. Gradio's reconciliation picks up the change exactly as if you'd
used a native `gr.Slider` / `gr.Checkbox`. From Python you call
`.change(callback, ...)` on the hidden component.

## Using the kit

```python
import gradio as gr
from ascii_stream_engine.presentation.widgets import (
    angle_dial, slider_row, stepper, toggle,
    bundle_js, bundle_css,
)

with gr.Blocks(js=bundle_js(), css=bundle_css()) as demo:
    _, angle   = angle_dial(value=134, label="Angle")
    _, buf     = stepper(value=18, minimum=2, maximum=60, step=1)
    _, blur    = slider_row(value=0.65, minimum=0, maximum=1, step=0.01,
                            label="Blur strength")
    _, enabled = toggle(value=True, label="Enable")

    status = gr.Textbox(label="State")
    def update(a, b, bl, en):
        return f"angle={a:.0f}° buffer={int(b)} blur={bl:.2f} enabled={en}"
    for c in (angle, buf, blur, enabled):
        c.change(update, inputs=[angle, buf, blur, enabled], outputs=status)

demo.launch()
```

Run `python python/ascii_stream_engine/examples/widgets_demo.py` for a
self-contained preview.

## Widgets included

| Widget | Backing component | Good for |
|---|---|---|
| `angle_dial(...)` | `gr.Number` | Any 0–360° param: TemporalScan angle, kaleidoscope rotation, radial direction |
| `slider_row(...)` | `gr.Number` | Float params with a label + unit (e.g. `"°"`, `"px"`, `"ms"`) |
| `stepper(...)` | `gr.Number` | Integer params with a small range (segments, samples, buffer frames) |
| `toggle(...)` | `gr.Checkbox` | Enable/disable toggles (filter active, feature flags) |

All four return `(html_component, value_component)` so you can ignore the
HTML and wire the value component exactly like a stock Gradio control.

## Authoring a new widget

1. Add `presentation/widgets/my_widget.py` with a factory function that
   returns `(gr.HTML, hidden_value_component)`. Scope every piece of
   markup inside a `<div class="sie-root">` wrapper so tokens apply.
2. Drop the JS in `static/my_widget.js` and extend `widgets.css`.
3. Call `register_assets(js="my_widget.js", css="widgets.css")` at the
   top of `my_widget.py` so the bundler picks it up.
4. Re-export the factory from `__init__.py`.

### JS contract

- Bind every element with your widget class (`.sie-<widget>`).
- Mirror the current value into the hidden input identified by
  `data-target`. Dispatch `input` AND `change` bubble events.
- Run an initial sync from the hidden input's current value so state
  persists across page refreshes.
- Observe DOM mutations — Gradio re-renders tabs lazily.
- Use `pointer-*` events + `touch-action: none` for mobile touch.

## Files in this folder

```
widgets/
├── __init__.py               # bundler + widget re-exports
├── README.md                 # this file
├── angle_dial.py             # factory for the 140px rotation dial
├── slider_row.py             # factory for labeled float sliders
├── stepper.py                # factory for −/+ integer stepper
├── toggle.py                 # factory for on/off pill
└── static/
    ├── widgets.css           # shared tokens + component styles
    ├── angle_dial.js
    ├── slider_row.js
    ├── stepper.js
    └── toggle.js
```

## Design lineage

All visual tokens, SVG shapes, and class contracts come from the design
system shipped in `design/` at the repo root. If you need a widget that
isn't covered here, check `design/ui_kits/mcp_v2/components.html` first
— the markup is usually already there; you just need to wire it up in
Python + JS under this folder.
