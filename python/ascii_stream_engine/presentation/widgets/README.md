# Custom Gradio widgets

Graphical controls (dials, XY pads, color wheels, curve editors) that go
beyond what Gradio ships out of the box. Built with plain SVG + vanilla
JS so we avoid a Node build step.

## How they fit together

Each widget is a factory function that returns a pair:

1. A visible `gr.HTML` containing the SVG (or canvas) markup.
2. A hidden `gr.Number` (or `gr.JSON`) that holds the current value.

The JS listens for pointer events on the SVG, updates the SVG visually,
then writes the value into the hidden input and dispatches `input`/`change`
events so Gradio's state machine picks it up. From the Python side it
behaves exactly like a `gr.Slider` — you call `.change(callback, ...)`
on the hidden component.

## Using a widget

```python
import gradio as gr
from ascii_stream_engine.presentation.widgets import angle_dial, bundle_js, bundle_css

with gr.Blocks(js=bundle_js(), css=bundle_css()) as demo:
    dial, angle = angle_dial(value=45, label="Scan angle")
    status = gr.Textbox(label="Current angle")

    def on_change(v):
        return f"{v:.1f}°"

    angle.change(on_change, inputs=angle, outputs=status)

demo.launch()
```

## Authoring a new widget

1. Add `presentation/widgets/my_widget.py` with a factory function that
   returns `(gr.HTML, hidden_value_component)`.
2. Drop the JS in `static/my_widget.js` and the CSS (optional) in
   `static/my_widget.css`.
3. Call `register_assets(js="my_widget.js", css="my_widget.css")` at the
   top of `my_widget.py` so the bundler picks them up.
4. Re-export the factory in `__init__.py`.

### JS contract

- Bind every element with your widget class (`.sie-<widget>`).
- Mirror the current value into the hidden input identified by
  `data-target`. Dispatch both `input` and `change` bubble events.
- Observe DOM mutations — Gradio re-renders tabs lazily.
- Respect `touch-action: none` and `pointer-*` events for mobile touch.

## Files in this folder

```
widgets/
├── __init__.py               # bundler + widget re-exports
├── README.md                 # this file
├── angle_dial.py             # POC widget factory
└── static/
    ├── widgets.css           # shared styles
    └── angle_dial.js         # dial logic
```
