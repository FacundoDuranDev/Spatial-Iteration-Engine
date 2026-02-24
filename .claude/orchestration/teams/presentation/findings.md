# Presentation Team -- Findings

## API Contracts

### New Panel Functions (all in `presentation/notebook_api.py`)

| Function | Signature | Returns |
|---|---|---|
| `build_advanced_diagnostics_panel` | `(engine=None) -> Dict` | profiler_html, memory_html, cpu_html, errors_html, auto_refresh_cb, profiler_enable_cb, refresh_btn, refresh, stop_refresh |
| `build_perception_control_panel` | `(engine=None) -> Dict` | analyzers (nested dict per analyzer), model_info_html, viz_mode, analysis_html, refresh_btn, apply_viz_btn, status |
| `build_filter_designer_panel` | `(engine=None, filters=None) -> Dict` | filter_cards (nested dict per filter with enabled_cb + params), active_summary_html, clear_all_btn, status |
| `build_output_manager_panel` | `(engine=None) -> Dict` | current_sinks_html, sink_type_dd, sink_config, add_sink_btn, sink_controls, refresh_btn, status |
| `build_performance_monitor_panel` | `(engine=None) -> Dict` | budget_chart_html, fps_gauge_html, degradation_html, histogram_output, bottleneck_html, auto_refresh_cb, refresh_btn, refresh, stop_refresh, status |
| `build_preset_manager_panel` | `(engine=None, presets_path=None) -> Dict` | preset_name_input, save_btn, preset_dropdown, load_btn, delete_btn, preset_list_html, import_export_textarea, import_btn, export_btn, status |
| `build_full_dashboard` | `(engine=None, filters=None) -> Dict` | tabs, control, diagnostics, perception, filters, outputs, performance, presets |

### Shared Helpers (module-level, private)

| Helper | Purpose |
|---|---|
| `_status_style(msg, kind)` | HTML status message with colored background (ok=green, warn=yellow, info=blue) |
| `_periodic_refresh(fn, interval_ms, stop_event)` | Daemon thread calling fn every interval_ms; returns {thread, stop, stop_event} |
| `_safe_engine_call(engine, method, *args, default)` | Safe engine API call; returns default if engine is None, method missing, or raises |
| `_make_labeled_section(title, children)` | VBox with HTML title and children widgets |

### Preset JSON Schema

```json
{
    "name": "string",
    "created": "ISO 8601 timestamp",
    "config": {
        "fps": "int",
        "grid_w": "int",
        "grid_h": "int",
        "charset": "string",
        "render_mode": "string",
        "contrast": "float",
        "brightness": "int",
        "raw_width": "int|null",
        "raw_height": "int|null"
    },
    "filters": ["string filter names"],
    "analyzers": {"face": "bool", "hands": "bool", "pose": "bool"},
    "renderer": "ascii|raw|overlay_landmarks"
}
```

Default storage: `~/.ascii_stream_engine/presets.json`

## Discovered Patterns

1. **Stop-modify-restart pattern is mandatory** for any config change, renderer swap, or sink modification. Without it, race conditions occur.

2. **Analyzer toggles can be real-time** -- `set_enabled()` is thread-safe and does not require stop-modify-restart.

3. **Filter parameter changes are also real-time** -- setting attributes on mutable filter objects takes effect on the next frame.

4. **Auto-refresh must use daemon threads** with explicit stop mechanisms. The `_periodic_refresh` helper provides this. Always expose a `stop_refresh` callable in the return dict.

5. **`engine.get_profiling_stats()`** returns `Dict[str, Dict[str, float]]` with keys: avg_time, min_time, max_time, std_dev, count. Times are in seconds (multiply by 1000 for ms).

6. **`engine.metrics.get_errors()`** returns `Dict[str, int]` with component names as keys and error counts as values.

7. **All build_* functions must guard ipywidgets import** inside the function body, not at module level (allows importing the module without ipywidgets installed).

8. **`unittest.mock.patch("IPython.display.display")`** is used in `build_full_dashboard` to suppress individual panel display() calls when composing into a master Tab widget.

## Dependencies on Other Teams

- **Engine public API** (application/engine.py): `start`, `stop`, `is_running`, `get_config`, `update_config`, `get_source`, `set_renderer`, `get_sink`, `set_sink`, `filters`, `filter_pipeline`, `analyzer_pipeline`, `metrics`, `get_last_analysis`, `get_profiling_report`, `get_profiling_stats`, `profiler`
- **EngineMetrics** (infrastructure/metrics.py): `get_summary()`, `get_fps()`, `get_errors()`
- **LoopProfiler** (infrastructure/profiling.py): `enabled` property, `get_summary_dict()`
- **Adapter classes** (guarded imports): All renderers, filters, outputs, analyzers

## Provided to Other Teams

- 7 new `build_*` panel functions exported via `__init__.py`
- `build_full_dashboard` as a one-call master UI
- Preset JSON schema for config persistence (no infrastructure dependency -- self-contained file I/O)
