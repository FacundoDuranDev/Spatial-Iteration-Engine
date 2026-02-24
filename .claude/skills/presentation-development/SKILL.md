---
name: presentation-development
description: Use when adding, modifying, or debugging Jupyter notebook UI panels, control widgets, diagnostics panels, or example notebooks in presentation/ or examples/
---

# Presentation Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `presentation/__init__.py` | Presentation module init |
| `presentation/notebook_api.py` | Main file — ALL panel functions live here |

### Existing Functions in `notebook_api.py` (extend, don't duplicate):
| Function | Purpose |
|----------|---------|
| `build_control_panel(engine)` | Simple FPS/grid/contrast panel |
| `build_general_control_panel(engine, filters)` | Full 5-tab panel (Red, Motor, Filtros, Vista, IA) |
| `build_diagnostics_panel(engine)` | Devices, latency, benchmark |
| `build_engine_for_notebook(camera_index, config)` | Factory: creates wired engine |

### Example Notebooks:
| File | Purpose |
|------|---------|
| `examples/full_control_panel.ipynb` | Complete demo (reference for new notebooks) |
| `examples/perception_test_bench.ipynb` | Perception testing |
| `examples/system_analysis_and_testing.ipynb` | System diagnostics |

**Pattern:** Copy structure from `build_general_control_panel()` for new panels. Always return Dict of widgets.

## Overview

Develop the Jupyter notebook user interface: control panels, diagnostics, factory functions, and example notebooks. Presentation is the outermost layer — it wires up adapters and engine into interactive widgets for end users.

**Core principle:** Presentation creates and connects components but never implements pipeline logic. It uses `StreamEngine` as a black box, calling only its public API. It delegates all rendering, filtering, and analysis to the existing adapter/engine stack.

## Scope

**Your files:**
- `python/ascii_stream_engine/presentation/notebook_api.py`
- `python/ascii_stream_engine/examples/*.ipynb`

**Read-only (consume, never modify):**
- `application/engine.py` — `StreamEngine` public API
- `application/pipeline/` — `AnalyzerPipeline`, `FilterPipeline`
- `adapters/*` — All adapters (sources, renderers, outputs, filters, perception)
- `domain/config.py` — `EngineConfig`
- `infrastructure/metrics.py` — `EngineMetrics`
- `infrastructure/profiling.py` — `LoopProfiler`

**Never touch:**
- `domain/`, `ports/`, `application/engine.py`, `application/pipeline/`
- Any adapter implementation
- Any infrastructure implementation

## notebook_api.py Functions

| Function | Purpose | Returns |
|---|---|---|
| `build_control_panel(engine)` | Simple config panel (FPS, grid, contrast, brightness, invert, filters) | Dict of widget groups |
| `build_general_control_panel(engine, filters)` | Full tabbed panel (Red, Motor, Filtros, Vista, IA) | Dict of all widgets |
| `build_diagnostics_panel(engine)` | Devices, latency, benchmarking | Dict of diagnostic widgets |
| `build_engine_for_notebook(camera_index, config)` | Factory: creates engine with NotebookPreviewSink + analyzers | `StreamEngine` |

## StreamEngine Public API (Consumed by Presentation)

```python
engine.start(blocking=False)   # Start pipeline in background thread
engine.stop()                  # Stop pipeline
engine.is_running              # bool
engine.get_config()            # EngineConfig snapshot
engine.update_config(**kwargs) # Modify config (stops/restarts if needed)
engine.get_source()            # Current FrameSource
engine.set_renderer(renderer)  # Swap renderer
engine.get_sink()              # Current OutputSink
engine.filters                 # List of active filters
engine.filter_pipeline         # FilterPipeline (has .replace())
engine.analyzer_pipeline       # AnalyzerPipeline (has .set_enabled(), .has_any())
engine.metrics                 # EngineMetrics
engine.get_last_analysis()     # Dict with latest perception results
engine.get_profiling_report()  # String report from LoopProfiler
```

## Widget Architecture (ipywidgets)

The general control panel uses a `Tab` widget with 5 tabs:

```
Tab 0: Red      — network_mode, host, port, apply_net_btn
Tab 1: Motor    — start_btn, stop_btn, camera_index, apply_camera_btn
Tab 2: Filtros  — filter checkboxes (auto-created from available filters), clear_filters_btn
Tab 3: Vista    — FPS, grid, charset, contrast, brightness, render_mode, raw size, buffer, bitrate
Tab 4: IA       — face/hands/pose checkboxes, viz_mode dropdown, apply_ai_btn, detector status
```

**Status bar:** HTML widget showing colored status messages (`_status_style(msg, kind)`).

## Adding a New Control Panel Tab

```python
# Inside build_general_control_panel():

# 1. Create widgets
my_slider = widgets.IntSlider(value=50, min=0, max=100, description="My Param")
my_apply_btn = widgets.Button(description="Apply")

# 2. Create callback
def apply_my_param(_=None):
    was_running = engine.is_running
    if was_running:
        engine.stop()
    engine.update_config(my_param=my_slider.value)
    if was_running:
        engine.start()
    status.value = _status_style("My param applied.", "ok")

my_apply_btn.on_click(apply_my_param)

# 3. Build VBox
my_box = widgets.VBox([
    widgets.HTML("<b>My Section</b>"),
    my_slider,
    my_apply_btn,
])

# 4. Add to tabs
tabs = widgets.Tab(children=[..., my_box])
tabs.set_title(N, "My Tab")

# 5. Add to return dict
return {..., "my_section": {"slider": my_slider, "apply": my_apply_btn}}
```

## Stop-Modify-Restart Pattern

All config changes that affect the pipeline follow this pattern:

```python
def apply_something(_=None):
    was_running = engine.is_running
    if was_running:
        engine.stop()
    # ... modify config/renderer/filters ...
    if was_running:
        engine.start()
    status.value = _status_style("Applied.", "ok")
```

**Why:** Changing config while the pipeline is running can cause race conditions. Always stop first, modify, then restart.

## Renderer Sync Pattern

When render mode or AI overlay changes, sync the renderer:

```python
def _sync_renderer():
    base = AsciiRenderer() if render_mode.value == "ascii" else PassthroughRenderer()
    if LandmarksOverlayRenderer and ai_viz_dd.value == "Overlay landmarks":
        engine.set_renderer(LandmarksOverlayRenderer(inner=base))
    else:
        engine.set_renderer(base)
```

## Filter Application Pattern

Filters are applied immediately on checkbox toggle:

```python
def _apply_filters(_=None):
    selected = [filters[name] for name, cb in filter_checkboxes.items() if cb.value]
    if hasattr(engine, "filter_pipeline"):
        engine.filter_pipeline.replace(selected)
    elif hasattr(engine, "filters"):
        engine.filters[:] = selected
```

## Analyzer Toggle Pattern

Real-time toggling without stop/restart for lightweight changes:

```python
def _on_analyzer_toggle(change):
    if hasattr(engine, "analyzer_pipeline"):
        ap = engine.analyzer_pipeline
        ap.set_enabled("face", face_cb.value)
        ap.set_enabled("hands", hands_cb.value)
        ap.set_enabled("pose", pose_cb.value)

for cb in (face_cb, hands_cb, pose_cb):
    cb.observe(_on_analyzer_toggle, names="value")
```

## build_engine_for_notebook() Factory

Creates a complete engine wired for notebook display:

```python
engine = build_engine_for_notebook(camera_index=0)
# Internally creates:
# - ipywidgets.Image widget (displayed immediately)
# - NotebookPreviewSink(image_widget=widget)
# - OpenCVCameraSource(camera_index)
# - PassthroughRenderer()
# - AnalyzerPipeline([Face, Hands, Pose]) if perception_cpp available
# - FilterPipeline([])
```

## Diagnostics Panel

Three sections:
1. **Devices:** `/dev/video*`, OpenCV indices, group membership, backend info
2. **Latency:** FPS, frames processed, latency avg/min/max, uptime, errors (from `engine.metrics`)
3. **Benchmark:** Run N seconds, collect profiling report, display results

## Example Notebooks

| Notebook | Purpose |
|---|---|
| `full_control_panel.ipynb` | Complete demo: engine + all panels |
| `perception_test_bench.ipynb` | Test perception models (face, hands, pose) |
| `system_analysis_and_testing.ipynb` | System diagnostics and benchmarking |

**Notebook pattern:**
```python
# Cell 1: Setup
from ascii_stream_engine.presentation.notebook_api import (
    build_engine_for_notebook,
    build_general_control_panel,
    build_diagnostics_panel,
)

# Cell 2: Create engine (displays preview widget)
engine = build_engine_for_notebook(camera_index=0)

# Cell 3: Control panel
panel = build_general_control_panel(engine)

# Cell 4 (optional): Diagnostics
diag = build_diagnostics_panel(engine)
```

## Dependencies

Presentation depends on `ipywidgets` and `IPython.display`. Both are optional:

```python
try:
    import ipywidgets as widgets
    from IPython.display import display
except ImportError as exc:
    raise ImportError(
        "Instala ipywidgets e ipython: pip install ipywidgets ipython"
    ) from exc
```

**Always guard imports** at the top of each function that uses widgets.

## Contracts

| Contract | Rule |
|---|---|
| Engine interaction | Only via public API (start, stop, update_config, set_renderer, etc.) |
| Config changes | Stop-modify-restart pattern for safe updates |
| Dependencies | ipywidgets + IPython required (raise ImportError with install hint) |
| Widget return | Every `build_*` function returns Dict of widgets for programmatic access |
| Status feedback | Use `_status_style(msg, kind)` for consistent styling |
| Optional adapters | Guard all adapter imports with try/except |
| No pipeline logic | Never implement filters, renderers, or analyzers in presentation |

## Testing

```python
def test_build_engine_for_notebook():
    """Factory creates a valid engine."""
    # Requires ipywidgets mock or skip
    engine = build_engine_for_notebook(camera_index=0)
    assert hasattr(engine, "start")
    assert hasattr(engine, "stop")

def test_build_general_control_panel():
    """Panel returns widget dict with expected keys."""
    engine = build_engine_for_notebook(0)
    panel = build_general_control_panel(engine)
    assert "tabs" in panel
    assert "network" in panel
    assert "engine" in panel
    assert "filters" in panel
    assert "ascii" in panel
    assert "ia" in panel

def test_build_diagnostics_panel():
    """Diagnostics panel returns expected widgets."""
    diag = build_diagnostics_panel()
    assert "devices_html" in diag
    assert "refresh_btn" in diag
```

## Red Flags

**Stop immediately if you catch yourself:**
- Implementing filter/renderer/analyzer logic inside presentation
- Modifying `StreamEngine`, `FilterPipeline`, or `AnalyzerPipeline`
- Directly accessing engine internals (private `_` attributes)
- Forgetting the stop-modify-restart pattern for config changes
- Missing ipywidgets/IPython import guard
- Creating widgets that don't get returned in the dict (unreachable programmatically)
- Leaving `engine.start()` called without a way to stop
- Hardcoding adapter classes without try/except fallback

## Common Mistakes

| Mistake | Fix |
|---|---|
| Config race condition | Stop engine before modifying, restart after |
| Widget not shown | Call `display(widget)` inside the function |
| Checkbox state out of sync | Read actual state from engine at init time (`_analyzer_enabled()`) |
| Filter applied but no visual change | Check render_mode; ASCII may mask filter effects |
| Missing import guard | Every `build_*` function must guard ipywidgets import |
| Diagnostics crash without engine | Handle `engine is None` gracefully in all callbacks |
| Benchmark blocks notebook | Run benchmark in daemon thread, update output async |
| Detector status stale | Provide refresh button; don't auto-poll (saves resources) |
