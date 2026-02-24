# Presentation Team Task Plan

> **Scope:** Jupyter notebook UI panels in `python/ascii_stream_engine/presentation/notebook_api.py`
> **Skill reference:** `.claude/skills/presentation-development/SKILL.md`
> **Branch:** `feature/presentation-panels`
> **Base:** `develop`

---

## Panels to Deliver

| # | Panel | Function Signature |
|---|---|---|
| 1 | Advanced Diagnostics Panel | `build_advanced_diagnostics_panel(engine) -> Dict` |
| 2 | Perception Control Panel | `build_perception_control_panel(engine) -> Dict` |
| 3 | Filter Designer Panel | `build_filter_designer_panel(engine, filters) -> Dict` |
| 4 | Output Manager Panel | `build_output_manager_panel(engine) -> Dict` |
| 5 | Performance Monitor Panel | `build_performance_monitor_panel(engine) -> Dict` |
| 6 | Preset Manager Panel | `build_preset_manager_panel(engine) -> Dict` |

All panels are added to `python/ascii_stream_engine/presentation/notebook_api.py`. Every `build_*` function returns a `Dict` of widgets for programmatic access.

---

## Phase 1: Foundation and Shared Utilities

**Goal:** Establish shared widget helpers, status formatting, and a periodic-refresh mechanism that all six panels will reuse. No new panels yet -- just infrastructure inside `notebook_api.py`.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add shared helper functions (see below) |
| `python/ascii_stream_engine/tests/test_presentation_helpers.py` | Unit tests for helpers |

### Implementation Details

1. **`_status_style(msg, kind)` -- already exists.** Verify it is accessible to all new panel functions. If it is currently nested inside `build_general_control_panel`, refactor it to module level so all `build_*` functions can call it.

2. **`_periodic_refresh(widget_update_fn, interval_ms, stop_event)` helper.** Many panels need timed auto-refresh (profiler graphs, latency numbers, memory stats). Implement a daemon-thread-based updater that:
   - Calls `widget_update_fn()` every `interval_ms` milliseconds.
   - Stops when `stop_event` is set or when the returned `stop()` callable is invoked.
   - Returns a dict `{"thread": Thread, "stop": Callable}`.
   - Catches all exceptions inside the loop (never crash the notebook kernel).

3. **`_safe_engine_call(engine, method_name, *args, default=None)` helper.** Wraps calls to the engine public API so that a missing method or a stopped engine returns `default` instead of raising. This avoids crashes when the engine is `None` or a method does not exist in an older version.

4. **`_make_labeled_section(title, children)` helper.** Returns `widgets.VBox([widgets.HTML(f"<b>{title}</b>"), *children])` with standard padding. Reduces boilerplate in every panel.

5. **Import guard pattern.** Confirm that every new `build_*` function independently guards `import ipywidgets` and `from IPython.display import display` at the top of its body, as required by the skill.

### Acceptance Criteria

- [ ] `_status_style` is a module-level function, not nested.
- [ ] `_periodic_refresh` works in a test with a mock `widget_update_fn` and verifies the function is called approximately the right number of times over 1 second.
- [ ] `_safe_engine_call` returns the default when the engine is `None`, when the method is missing, and when the method raises.
- [ ] `_make_labeled_section` returns a `VBox` (or is tested with an ipywidgets mock).
- [ ] All existing tests still pass (`make test`).

---

## Phase 2: Advanced Diagnostics Panel

**Goal:** Build `build_advanced_diagnostics_panel(engine)` -- a live profiler dashboard with CPU usage, memory consumption, per-stage timing graphs, and error rates.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_advanced_diagnostics_panel(engine)` |
| `python/ascii_stream_engine/tests/test_presentation_diagnostics.py` | Tests for returned widget dict keys and callback behavior |

### Implementation Details

1. **Profiler stats section.** Read `engine.get_profiling_stats()` (returns `Dict[str, Dict[str, float]]` from `LoopProfiler.get_summary_dict()`). Display per-phase stats in an HTML table with columns: Phase, Avg (ms), Min (ms), Max (ms), Std Dev (ms), Count. Phases to display: `capture`, `analysis`, `transformation`, `filtering`, `rendering`, `writing`, `total_frame`.

2. **Memory section.** Use `import resource; resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` (Linux) to show peak RSS in MB. Also show current process memory via `/proc/self/status` VmRSS parsing (guard with `try/except` for non-Linux). Display as an HTML widget.

3. **CPU usage section.** Use `import os; os.times()` to compute user+sys CPU time. Show CPU utilization as `(delta_user + delta_sys) / delta_wall * 100` between refreshes. Display as a styled HTML bar.

4. **Error breakdown section.** Read `engine.metrics.get_errors()` (returns `Dict[str, int]`). Display a table of component error counts: capture, analysis, filtering, rendering, writing.

5. **Auto-refresh toggle.** Add a `Checkbox(description="Auto-refresh (2s)")` and use `_periodic_refresh` with 2000ms interval. The refresh callback updates all HTML widgets above. When unchecked, stop the refresh thread. Add a manual `Refresh` button as well.

6. **Profiler enable toggle.** Add a `Checkbox(description="Enable profiler")` bound to `engine.profiler.enabled` (the setter on `LoopProfiler`). When toggled, set `engine.profiler.enabled = value`. Display a warning if profiler is disabled (stats will be stale).

### Widget API (returned Dict)

```python
{
    "panel": VBox,
    "profiler_html": HTML,
    "memory_html": HTML,
    "cpu_html": HTML,
    "errors_html": HTML,
    "auto_refresh_cb": Checkbox,
    "profiler_enable_cb": Checkbox,
    "refresh_btn": Button,
    "refresh": Callable,        # manual refresh function
    "stop_refresh": Callable,   # stop auto-refresh
}
```

### Acceptance Criteria

- [ ] `build_advanced_diagnostics_panel(engine=None)` does not crash; shows placeholder text.
- [ ] With a mock engine, `profiler_html` contains an HTML table with all 7 phase names.
- [ ] `auto_refresh_cb` toggling starts/stops the refresh thread.
- [ ] `profiler_enable_cb` toggles `engine.profiler.enabled`.
- [ ] Returned dict contains all keys listed above.
- [ ] No private `_` attribute access on `engine` (only public API).

---

## Phase 3: Perception Control Panel

**Goal:** Build `build_perception_control_panel(engine)` -- per-analyzer configuration, model path display, confidence thresholds, and enabled/disabled toggles with real-time feedback.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_perception_control_panel(engine)` |
| `python/ascii_stream_engine/tests/test_presentation_perception.py` | Tests for widget dict keys and toggle behavior |

### Implementation Details

1. **Analyzer discovery.** Read `engine.analyzer_pipeline.analyzers` to get the list of registered analyzers. For each analyzer, extract: `name` (str), `enabled` (bool), and any configurable attributes. Known analyzers: `FaceLandmarkAnalyzer`, `HandLandmarkAnalyzer`, `PoseLandmarkAnalyzer`.

2. **Per-analyzer control card.** For each analyzer, create a `VBox` card containing:
   - `Checkbox(description=name, value=enabled)` -- toggles `engine.analyzer_pipeline.set_enabled(name, bool)` on `observe`. Follow the existing real-time analyzer toggle pattern (no stop-modify-restart needed for enable/disable).
   - `HTML` status showing last detection result point count (read from `engine.get_last_analysis()[name]` and count points as `_count_points` does).
   - `FloatSlider(description="Confidence", min=0.0, max=1.0, step=0.05, value=0.5)` -- if the analyzer has a `confidence_threshold` or `min_confidence` attribute, bind it. Otherwise display as disabled/informational.

3. **Model info section.** For each analyzer, attempt to read `getattr(analyzer, "model_path", None)`. Display the model path if available. Also show whether `perception_cpp` is available using the existing pattern:
   ```python
   try:
       import perception_cpp
       cpp_available = True
   except ImportError:
       cpp_available = False
   ```
   Display a colored status: green if available, amber warning if not.

4. **Visualization mode selector.** Add a `Dropdown` for AI visualization mode that mirrors the existing IA tab's `ai_viz_dd` but also adds an option for "Bounding boxes" (future). When changed, call `_sync_renderer()` pattern:
   - Determine base renderer from engine config `render_mode`.
   - If "Overlay landmarks" is selected and `LandmarksOverlayRenderer` is available, wrap with overlay.
   - Apply via `engine.set_renderer(...)` using stop-modify-restart.

5. **Analysis results display.** An `HTML` widget that shows the last analysis results as formatted text (face: N pts, hands: L/R pts, pose: N joints). Include a `Refresh` button. Optionally auto-refresh using `_periodic_refresh` at 1000ms.

6. **Parallel execution info.** Display whether `AnalyzerPipeline` is using parallel execution (len(active) > 1 triggers `ThreadPoolExecutor`). Informational only.

### Widget API (returned Dict)

```python
{
    "panel": VBox,
    "analyzers": {
        "face": {"enabled_cb": Checkbox, "confidence": FloatSlider, "status_html": HTML},
        "hands": {"enabled_cb": Checkbox, "confidence": FloatSlider, "status_html": HTML},
        "pose": {"enabled_cb": Checkbox, "confidence": FloatSlider, "status_html": HTML},
    },
    "model_info_html": HTML,
    "viz_mode": Dropdown,
    "analysis_html": HTML,
    "refresh_btn": Button,
    "apply_viz_btn": Button,
    "status": HTML,
}
```

### Acceptance Criteria

- [ ] Panel works with `engine` that has no analyzer_pipeline (`has_any()` returns False) -- shows "No perception module" warning.
- [ ] Each analyzer checkbox toggles `set_enabled(name, bool)` in real time.
- [ ] Confidence slider is disabled when the analyzer has no `confidence_threshold` attribute.
- [ ] Visualization mode dropdown triggers renderer sync with stop-modify-restart.
- [ ] `engine.get_last_analysis()` results are displayed as formatted point counts.
- [ ] Returned dict contains all keys listed above.
- [ ] All adapter imports are guarded with `try/except`.

---

## Phase 4: Filter Designer Panel and Output Manager Panel

**Goal:** Build two panels in parallel since they are independent. The Filter Designer provides real-time parameter sliders for each filter. The Output Manager provides multi-sink configuration.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_filter_designer_panel(engine, filters)` and `build_output_manager_panel(engine)` |
| `python/ascii_stream_engine/tests/test_presentation_filters.py` | Tests for Filter Designer |
| `python/ascii_stream_engine/tests/test_presentation_outputs.py` | Tests for Output Manager |

### 4A: Filter Designer Panel

#### Implementation Details

1. **Filter discovery.** Accept an optional `filters: Dict[str, Filter]` argument (same pattern as `build_general_control_panel`). If `None`, auto-discover from available adapters:
   ```python
   filters = {}
   if EdgeFilter: filters["Edges"] = EdgeFilter(60, 120)
   if BrightnessFilter: filters["Brightness/Contrast"] = BrightnessFilter()
   if InvertFilter: filters["Invert"] = InvertFilter()
   if CppInvertFilter: filters["Invert (C++)"] = CppInvertFilter()
   if DetailBoostFilter: filters["Detail Boost"] = DetailBoostFilter()
   # Also: CppBrightnessContrastFilter, CppGrayscaleFilter, CppChannelSwapFilter
   ```

2. **Per-filter parameter card.** For each filter, introspect its attributes to create sliders:
   - `EdgeFilter`: `IntSlider` for `low_threshold` (0-255), `IntSlider` for `high_threshold` (0-255).
   - `BrightnessFilter`: `FloatSlider` for `alpha` (contrast, 0.5-3.0), `IntSlider` for `beta` (brightness, -100 to 100).
   - `DetailBoostFilter`: `FloatSlider` for `strength` (0.0-5.0) if the attribute exists.
   - For C++ filters: display name and enabled checkbox only (parameters are compile-time).
   - Generic fallback: for any filter with numeric attributes, create appropriate sliders.

3. **Real-time parameter application.** When a slider value changes, update the filter object attribute directly (filters are mutable objects in the pipeline). No stop-modify-restart needed for parameter changes -- the next frame will use the new value. Use the `observe` callback pattern.

4. **Filter enable/disable checkboxes.** Each filter gets a `Checkbox(value=False)`. On change, call `_apply_filters()` to rebuild the active filter list via `engine.filter_pipeline.replace(selected)`.

5. **Filter ordering.** Display filters in a `VBox` with their current order. Add "Move Up" / "Move Down" buttons per filter. Reordering calls `engine.filter_pipeline.replace(new_ordered_list)`.

6. **Preview indicator.** An `HTML` widget showing currently active filters and their parameter values as a compact summary.

#### Widget API

```python
{
    "panel": VBox,
    "filter_cards": {
        "Edges": {"enabled_cb": Checkbox, "params": {"low_threshold": IntSlider, "high_threshold": IntSlider}},
        "Brightness/Contrast": {"enabled_cb": Checkbox, "params": {"alpha": FloatSlider, "beta": IntSlider}},
        # ... one entry per discovered filter
    },
    "active_summary_html": HTML,
    "clear_all_btn": Button,
    "status": HTML,
}
```

### 4B: Output Manager Panel

#### Implementation Details

1. **Current sink display.** Read `engine.get_sink()`. Display its type name and whether it is open. If it is a `CompositeOutputSink`, list all child sinks with their types.

2. **Available sink types.** List all available output sink classes with guarded imports:
   - `NotebookPreviewSink` (always available in notebook context)
   - `FfmpegUdpOutput` (requires config: host, port, bitrate, pkt_size)
   - `PreviewSink` (desktop only -- may fail in headless Jupyter)
   - `AsciiFrameRecorder` (requires file path)
   - `FfmpegRtspSink` (optional, guarded import)
   - `WebRTCOutput` (optional, guarded import)

3. **Add sink form.** A `Dropdown` to select sink type, plus type-specific configuration widgets:
   - For `FfmpegUdpOutput`: `Text` for host, `IntText` for port, `Text` for bitrate.
   - For `AsciiFrameRecorder`: `Text` for output file path.
   - For `NotebookPreviewSink`: no config needed (auto-creates image widget).
   - An `Add Sink` button that:
     1. Creates the new sink instance.
     2. If current sink is already a `CompositeOutputSink`, adds via stop-modify-restart pattern: stop engine, call `composite.add_sink(new_sink)`, restart.
     3. If current sink is a single sink, wraps both in a new `CompositeOutputSink` and calls `engine.set_sink(composite)` with stop-modify-restart.

4. **Per-sink controls.** For each sink in the composite (or the single sink):
   - Display type name and open/closed status.
   - A `Remove` button (disabled if it is the last sink). Uses stop-modify-restart: stop engine, remove sink from composite, restart.
   - An `HTML` status indicator (green = open, red = closed).

5. **Sink status refresh.** A `Refresh` button that re-reads sink states and updates the display.

#### Widget API

```python
{
    "panel": VBox,
    "current_sinks_html": HTML,
    "sink_type_dd": Dropdown,
    "sink_config": VBox,           # dynamic config widgets for selected type
    "add_sink_btn": Button,
    "sink_controls": List[Dict],   # per-sink {name_html, remove_btn, status_html}
    "refresh_btn": Button,
    "status": HTML,
}
```

### Acceptance Criteria (Phase 4 combined)

- [ ] Filter Designer: each discovered filter has a card with appropriate sliders.
- [ ] Filter Designer: slider changes update filter attributes immediately (no restart).
- [ ] Filter Designer: enable/disable checkboxes call `engine.filter_pipeline.replace()`.
- [ ] Filter Designer: "Clear all" disables all filters.
- [ ] Output Manager: shows current sink type and status.
- [ ] Output Manager: can add a new sink (wraps in CompositeOutputSink) with stop-modify-restart.
- [ ] Output Manager: can remove a sink from composite (not the last one).
- [ ] Output Manager: all sink class imports are guarded with `try/except`.
- [ ] Both panels return complete widget dicts as specified.
- [ ] No private `_` attribute access on engine.

---

## Phase 5: Performance Monitor Panel

**Goal:** Build `build_performance_monitor_panel(engine)` -- a latency budget visualization panel that shows per-stage timing against the 33.3ms budget, degradation status, and FPS tracking.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_performance_monitor_panel(engine)` |
| `python/ascii_stream_engine/tests/test_presentation_performance.py` | Tests for widget dict keys and budget calculations |

### Implementation Details

1. **Latency budget bar chart (HTML).** Reference `rules/LATENCY_BUDGET.md` for the budget allocations. Render an HTML bar chart where each pipeline stage gets a horizontal bar:
   - Bar width proportional to actual time vs. budget (e.g., if capture took 3ms out of 2ms budget, the bar is 150% and colored red).
   - Colors: green (<80% of budget), amber (80-100%), red (>100%).
   - Stages and budgets (from `LATENCY_BUDGET.md`):
     | Stage | Budget (ms) |
     |---|---|
     | capture | 2.0 |
     | analysis | 15.0 |
     | transformation | 2.0 |
     | filtering | 5.0 |
     | rendering | 3.0 |
     | writing | 3.0 |
     | overhead | 1.3 |
     | **total_frame** | **33.3** |
   - Read actual timings from `engine.get_profiling_stats()`.

2. **FPS gauge.** An `HTML` widget showing:
   - Target FPS (from `engine.get_config().fps`).
   - Actual FPS (from `engine.metrics.get_fps()`).
   - Percentage: `actual / target * 100`.
   - Color coded: green (>90%), amber (70-90%), red (<70%).

3. **Degradation status section.** Display which degradation steps (from `LATENCY_BUDGET.md`) are currently applicable based on timing data:
   - If `total_frame` avg > 33.3ms: suggest "Skip perception on alternating frames".
   - If `analysis` avg > 15ms: suggest "Disable tracking" or "Reduce inference resolution".
   - If `filtering` avg > 5ms: suggest "Disable non-essential filters".
   - If overall still over budget: suggest "Reduce target FPS".
   - Display as a styled list with severity indicators.

4. **Frame time histogram (text-based).** Show a simple ASCII histogram of the last N frame times (from `engine.profiler` stats). Use `Output` widget with monospace text. Buckets: 0-10ms, 10-20ms, 20-33ms, 33-50ms, >50ms. Show count per bucket.

5. **Bottleneck identifier.** Compute which stage consumes the highest percentage of total frame time and highlight it. Read from `engine.get_profiling_stats()` and compute `stage_avg / total_avg * 100` for each stage.

6. **Auto-refresh.** Use `_periodic_refresh` at 1500ms interval. Include start/stop toggle.

### Widget API

```python
{
    "panel": VBox,
    "budget_chart_html": HTML,
    "fps_gauge_html": HTML,
    "degradation_html": HTML,
    "histogram_output": Output,
    "bottleneck_html": HTML,
    "auto_refresh_cb": Checkbox,
    "refresh_btn": Button,
    "refresh": Callable,
    "stop_refresh": Callable,
    "status": HTML,
}
```

### Acceptance Criteria

- [ ] Budget chart displays all 7 stages with correct budget values from `LATENCY_BUDGET.md`.
- [ ] Bars are color-coded green/amber/red based on actual vs. budget ratio.
- [ ] FPS gauge shows both target and actual FPS with color coding.
- [ ] Degradation suggestions are ordered per the mandatory degradation hierarchy.
- [ ] Panel works when profiler is disabled (shows "Enable profiler for timing data").
- [ ] Panel works when `engine` is `None` (placeholder text).
- [ ] Auto-refresh toggle works correctly.
- [ ] Returned dict contains all keys listed above.

---

## Phase 6: Preset Manager Panel

**Goal:** Build `build_preset_manager_panel(engine)` -- save and load complete pipeline configurations (filter set + parameters, renderer mode, analyzer states) as named presets stored as JSON.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_preset_manager_panel(engine)` |
| `python/ascii_stream_engine/tests/test_presentation_presets.py` | Tests for save/load/delete logic |

### Implementation Details

1. **Preset data structure.** A preset is a JSON-serializable dict:
   ```python
   {
       "name": str,
       "created": str,  # ISO 8601 timestamp
       "config": {       # subset of EngineConfig fields
           "fps": int,
           "grid_w": int,
           "grid_h": int,
           "charset": str,
           "render_mode": str,
           "contrast": float,
           "brightness": int,
           "raw_width": int | None,
           "raw_height": int | None,
       },
       "filters": [str],              # list of active filter names (ordered)
       "analyzers": {                  # analyzer enabled states
           "face": bool,
           "hands": bool,
           "pose": bool,
       },
       "renderer": str,               # "ascii" | "raw" | "overlay_landmarks"
   }
   ```

2. **Preset storage.** Store presets in a JSON file at a configurable path, defaulting to `~/.ascii_stream_engine/presets.json`. Use `pathlib.Path` for cross-platform compatibility. The file contains a JSON array of preset objects. Guard all file I/O with `try/except`.

3. **Save preset.** Widgets: `Text(description="Preset name")` + `Save` button. On click:
   - Read current state from engine public API: `engine.get_config()`, `engine.filter_pipeline.filters`, `engine.analyzer_pipeline.analyzers`.
   - Build the preset dict.
   - Append to presets file (read existing, append, write back).
   - Update the preset list dropdown.
   - Show success status.

4. **Load preset.** Widgets: `Dropdown(options=[preset names])` + `Load` button. On click:
   - Read the selected preset from the JSON file.
   - Apply config via stop-modify-restart: `engine.stop()`, `engine.update_config(**preset["config"])`, apply filters, apply analyzer states, sync renderer, `engine.start()`.
   - For filters: look up filter objects by name from the available filters dict, enable the ones listed in the preset.
   - For analyzers: call `engine.analyzer_pipeline.set_enabled(name, bool)` for each.
   - For renderer: apply via `_sync_renderer` pattern.

5. **Delete preset.** A `Delete` button next to the dropdown. Removes the selected preset from the JSON file and updates the dropdown.

6. **Preset list display.** An `HTML` widget showing all saved presets with name, creation date, and a summary of what they configure (e.g., "30 FPS, ASCII, Edges+Invert, face+hands").

7. **Import/Export.** A `Textarea` widget and `Import JSON` / `Export JSON` buttons. Export serializes the current preset list to JSON text in the textarea. Import parses the textarea content and replaces/merges the preset list.

### Widget API

```python
{
    "panel": VBox,
    "preset_name_input": Text,
    "save_btn": Button,
    "preset_dropdown": Dropdown,
    "load_btn": Button,
    "delete_btn": Button,
    "preset_list_html": HTML,
    "import_export_textarea": Textarea,
    "import_btn": Button,
    "export_btn": Button,
    "status": HTML,
}
```

### Acceptance Criteria

- [ ] Save creates a valid JSON entry with all required fields.
- [ ] Load applies config, filters, analyzers, and renderer using stop-modify-restart.
- [ ] Delete removes the preset and updates the dropdown.
- [ ] Preset file I/O is fully guarded with `try/except` (no crash on missing file, corrupt JSON, permission error).
- [ ] Import/Export round-trips correctly (export then import produces identical presets).
- [ ] Panel works when `engine` is `None` (save is disabled, load shows warning).
- [ ] No private `_` attribute access on engine.
- [ ] Returned dict contains all keys listed above.

---

## Phase 7: Integration, Example Notebook, and Final Validation

**Goal:** Wire all six new panels into the existing notebook workflow, create a comprehensive example notebook, run all tests, and validate the complete panel suite.

### Deliverables

| File | Change |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | Add `build_full_dashboard(engine, filters)` master function |
| `python/ascii_stream_engine/__init__.py` | Export new `build_*` functions in public API |
| `python/ascii_stream_engine/examples/full_dashboard.ipynb` | New example notebook demonstrating all panels |
| `python/ascii_stream_engine/tests/test_presentation_integration.py` | Integration tests for the full dashboard |

### Implementation Details

1. **`build_full_dashboard(engine, filters=None)` function.** Creates a mega-panel with a `Tab` widget containing all panels:
   ```
   Tab 0: Control       (existing build_general_control_panel)
   Tab 1: Diagnostics   (build_advanced_diagnostics_panel)
   Tab 2: Perception    (build_perception_control_panel)
   Tab 3: Filters       (build_filter_designer_panel)
   Tab 4: Outputs       (build_output_manager_panel)
   Tab 5: Performance   (build_performance_monitor_panel)
   Tab 6: Presets       (build_preset_manager_panel)
   ```
   Returns a dict with keys for each sub-panel's widget dict plus the top-level `tabs` widget.

2. **Public API exports.** Add new functions to `python/ascii_stream_engine/__init__.py`:
   ```python
   from .presentation.notebook_api import (
       build_advanced_diagnostics_panel,
       build_perception_control_panel,
       build_filter_designer_panel,
       build_output_manager_panel,
       build_performance_monitor_panel,
       build_preset_manager_panel,
       build_full_dashboard,
   )
   ```
   Guard with `try/except ImportError` as the existing exports do.

3. **Example notebook `full_dashboard.ipynb`.** Four cells:
   - Cell 1: Imports.
   - Cell 2: `engine = build_engine_for_notebook(camera_index=0)` -- displays preview widget.
   - Cell 3: `dashboard = build_full_dashboard(engine)` -- displays the tabbed dashboard.
   - Cell 4: Markdown documentation explaining each tab and how to use it.

4. **Integration tests.** Test that:
   - `build_full_dashboard` returns a dict with all expected top-level keys.
   - Each sub-panel dict is present and contains its expected keys.
   - Creating the dashboard does not raise when engine has no perception module.
   - The dashboard works with `DummySource`, `DummyRenderer`, `DummySink` mocks.

5. **Cross-panel interactions.** Validate that:
   - Changing filters in the Filter Designer reflects in the Preset Manager's "current state" snapshot.
   - Toggling analyzers in the Perception panel reflects in the Performance Monitor's analysis timing.
   - Loading a preset in the Preset Manager updates the Filter Designer checkboxes (may require an `on_preset_loaded` callback or a refresh mechanism).

6. **Cleanup sweep.** Review all six panels for:
   - Consistent use of `_status_style` for status messages.
   - All `build_*` functions have docstrings following existing patterns.
   - All returned dicts have the documented keys.
   - No `engine._private` access anywhere.
   - All daemon threads are stoppable and stopped when the panel provides a `stop_refresh` callable.
   - `make format` and `make lint` pass.

7. **Full test suite run.** Execute `make check` (format + lint + test). Fix any failures.

### Widget API (returned Dict for `build_full_dashboard`)

```python
{
    "tabs": Tab,
    "control": Dict,         # from build_general_control_panel
    "diagnostics": Dict,     # from build_advanced_diagnostics_panel
    "perception": Dict,      # from build_perception_control_panel
    "filters": Dict,         # from build_filter_designer_panel
    "outputs": Dict,         # from build_output_manager_panel
    "performance": Dict,     # from build_performance_monitor_panel
    "presets": Dict,         # from build_preset_manager_panel
}
```

### Acceptance Criteria

- [ ] `build_full_dashboard(engine)` returns a dict with all 8 keys listed above.
- [ ] Each sub-panel's dict contains its documented keys from its respective phase.
- [ ] Example notebook `full_dashboard.ipynb` runs without error with a mock/dummy engine.
- [ ] `make format` passes (Black + isort, line-length 100).
- [ ] `make lint` passes (flake8).
- [ ] `make test` passes -- all existing tests plus all new test files.
- [ ] No references to `engine._` private attributes in any new code.
- [ ] All `build_*` functions are exported in `__init__.py` with import guards.
- [ ] CHANGELOG.md updated under `[Unreleased]` with a `feat(presentation)` entry for each new panel.

---

## Summary Timeline

| Phase | Panels | Key Dependencies |
|---|---|---|
| 1 | (none -- foundation) | None |
| 2 | Advanced Diagnostics | Phase 1 helpers |
| 3 | Perception Control | Phase 1 helpers |
| 4 | Filter Designer + Output Manager | Phase 1 helpers |
| 5 | Performance Monitor | Phase 1 helpers, Phase 2 patterns |
| 6 | Preset Manager | Phase 1 helpers, Phases 3-4 filter/analyzer patterns |
| 7 | Integration + Dashboard + Tests | All previous phases |

Phases 2, 3, and 4 can proceed in parallel after Phase 1 completes. Phase 5 depends lightly on Phase 2 (reuses the profiler display patterns). Phase 6 depends on Phases 3-4 (needs to know the filter/analyzer widget patterns to sync with). Phase 7 is strictly sequential after all others.

---

## Files Modified (Complete List)

| File | Phases |
|---|---|
| `python/ascii_stream_engine/presentation/notebook_api.py` | 1, 2, 3, 4, 5, 6, 7 |
| `python/ascii_stream_engine/__init__.py` | 7 |
| `python/ascii_stream_engine/tests/test_presentation_helpers.py` | 1 (new) |
| `python/ascii_stream_engine/tests/test_presentation_diagnostics.py` | 2 (new) |
| `python/ascii_stream_engine/tests/test_presentation_perception.py` | 3 (new) |
| `python/ascii_stream_engine/tests/test_presentation_filters.py` | 4 (new) |
| `python/ascii_stream_engine/tests/test_presentation_outputs.py` | 4 (new) |
| `python/ascii_stream_engine/tests/test_presentation_performance.py` | 5 (new) |
| `python/ascii_stream_engine/tests/test_presentation_presets.py` | 6 (new) |
| `python/ascii_stream_engine/tests/test_presentation_integration.py` | 7 (new) |
| `python/ascii_stream_engine/examples/full_dashboard.ipynb` | 7 (new) |
| `CHANGELOG.md` | 7 |

## Constraints (from Skill)

- **Never modify:** `domain/`, `ports/`, `application/engine.py`, `application/pipeline/`, any adapter implementation, any infrastructure implementation.
- **Only consume:** `StreamEngine` public API, `EngineMetrics`, `LoopProfiler`, adapter classes (via guarded imports).
- **Every `build_*`:** guards ipywidgets import, returns Dict, uses `_status_style`, follows stop-modify-restart for config changes.
- **Language:** All code comments and variable names in English. UI labels may use the existing bilingual pattern (Spanish labels already present in the codebase).
