# Jupyter Control Panel — UI Kit

Recreation of `build_general_control_panel(engine)` from `python/ascii_stream_engine/presentation/notebook_api.py`. This is the real product surface: an ipywidgets tabbed panel (Red · Motor · Filtros · Vista · IA) rendered inside a Jupyter notebook cell.

Open `index.html` to see the interactive recreation.

## Components
- `ControlPanel.jsx` — the full tabbed shell, status bar, and state
- `NetworkTab.jsx` / `EngineTab.jsx` / `FiltersTab.jsx` / `ViewTab.jsx` / `AITab.jsx`
- `PreviewImage.jsx` — the mock webcam/ASCII preview
- `Widgets.jsx` — mono inputs, sliders, checkboxes, dropdowns, buttons (styled to mimic ipywidgets but on our terminal palette)

## Notes
This is a cosmetic recreation — not functional Python bridges. State is local React state. Copy mirrors the Spanish strings from `notebook_api.py`.
