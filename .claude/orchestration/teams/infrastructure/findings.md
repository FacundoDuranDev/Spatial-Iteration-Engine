# Infrastructure Team — Findings

## API Contracts

### ConfigPersistence (`infrastructure/config_persistence.py`)

```python
ConfigPersistence(default_path: str = "engine_config.json")
```

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `save` | `(config: EngineConfig, path=None)` | `None` | Non-atomic write. Thread-safe. |
| `save_atomic` | `(config: EngineConfig, path=None)` | `None` | Writes to `.tmp` then `os.replace`. Crash-safe. |
| `load` | `(path=None)` | `EngineConfig` | Validates schema version `"1.0.0"`. |
| `exists` | `(path=None)` | `bool` | Path existence check only. |
| `get_diff` | `(config_a, config_b)` | `dict` | `{changed: {k: (old, new)}, added: {k: v}, removed: {k: v}}` |

JSON envelope: `{schema_version, saved_at (UTC ISO), config: {...}}`. Thread-safe (Lock on all I/O). Raises `ConfigPersistenceError` on failure.

### EventBus (`infrastructure/event_bus.py`)

```python
EventBus()
```

**Subscription:**

| Method | Signature | Notes |
|--------|-----------|-------|
| `subscribe` | `(event_type: str, callback)` | Standard, priority 0. |
| `subscribe_with_priority` | `(event_type, callback, priority=0)` | Higher int = executed first. |
| `subscribe_pattern` | `(pattern: str, callback, priority=0)` | `fnmatch` syntax (e.g. `"analysis_*"`). |
| `unsubscribe` | `(event_type, callback)` | |
| `unsubscribe_pattern` | `(pattern, callback)` | |

**Publishing:**

| Method | Notes |
|--------|-------|
| `publish(event, event_type=None)` | Infers type from class name (CamelCase → snake_case, strips `_event`). |
| `publish_async(event, event_type=None)` | Fires daemon thread. Non-blocking. |

**Filters & Replay:**

| Method | Notes |
|--------|-------|
| `add_filter(event_filter)` / `remove_filter(event_filter)` | Filter protocol: `should_deliver(event, event_type) -> bool`. |
| `enable_replay(max_events=1000)` / `disable_replay()` | Enables/clears replay buffer. |
| `replay(event_type=None, since=None)` | `since` is `perf_counter` timestamp. |
| `get_event_history(event_type=None, limit=100)` | Most recent last. |

**Control:** `enable()` / `disable()` / `is_enabled()` / `clear()` / `get_subscriber_count(event_type=None)` / `get_stats()`.

Thread-safe: `threading.RLock`. Callbacks execute outside the lock.

### Event Filters (`infrastructure/event_filter.py`)

| Class | Constructor | Behavior |
|-------|-------------|----------|
| `RateLimitFilter` | `(max_per_second=10.0, max_tracked_types=100)` | Sliding 1-second window per event type. |
| `DeduplicationFilter` | `(window_seconds=1.0, max_history=100)` | Key: `(event_type, event.source_id)`. |

Both implement `should_deliver(event, event_type) -> bool`.

### EngineMetrics (`infrastructure/metrics.py`)

```python
EngineMetrics()
```

| Method | Returns | Notes |
|--------|---------|-------|
| `start()` | `None` | Resets all state and records start time. |
| `record_frame()` | `None` | Appends to rolling window (last 100 durations). |
| `record_error(component: str)` | `None` | Components: `capture`, `analysis`, `filtering`, `rendering`, `writing`. |
| `get_fps()` | `float` | Average over last 100 frames. |
| `get_frames_processed()` | `int` | |
| `get_errors()` | `Dict[str, int]` | Copy. |
| `get_total_errors()` | `int` | |
| `get_latency_avg/min/max()` | `float` | Seconds. |
| `get_uptime()` | `float` | Seconds since `start()`. |
| `get_summary()` | `dict` | All metrics combined. |

Thread-safe: `threading.Lock`.

### LoopProfiler (`infrastructure/profiling.py`)

```python
LoopProfiler(enabled=True, max_samples=1000)
```

**Phase constants:** `PHASE_CAPTURE`, `PHASE_ANALYSIS`, `PHASE_TRANSFORMATION`, `PHASE_FILTERING`, `PHASE_RENDERING`, `PHASE_WRITING`, `PHASE_TOTAL`.

| Method | Returns | Notes |
|--------|---------|-------|
| `start_frame()` / `end_frame()` | `None` | Wraps entire frame loop. |
| `start_phase(phase)` / `end_phase(phase)` | `None` | LIFO stack, allows nesting. |
| `get_stats(phase=None)` | `Dict[str, PhaseStats]` | Each PhaseStats: `count`, `total_time`, `avg_time`, `min_time`, `max_time`, `std_dev`. |
| `get_summary_dict()` | Nested dict | Same keys as PhaseStats per phase. |
| `get_report()` | `str` | Formatted text with bottleneck analysis. |
| `enabled` (property) | `bool` | Settable. |

Not thread-safe (designed for single-threaded main loop).

### Plugin System (`infrastructure/plugins/`)

**PluginManager** (`plugin_manager.py`):

```python
PluginManager(plugin_paths=None, enable_hot_reload=False, hot_reload_debounce=0.5)
```

| Method | Returns | Notes |
|--------|---------|-------|
| `load_all()` | `int` | Scans configured paths. |
| `load_from_file(path, class_name=None)` | `bool` | |
| `load_from_directory(dir, recursive=False)` | `int` | |
| `get_plugin(name)` | `Optional[Plugin]` | |
| `get_all_plugins(plugin_type=None)` | `List[Plugin]` | |
| `unregister(name)` | `bool` | |
| `start_hot_reload()` / `stop_hot_reload()` | `bool` / `None` | Requires `watchdog`. |

**Plugin Types** (abstract classes in `plugin_interface.py`):
- `FilterPlugin` — `apply(frame, config, analysis=None) -> ndarray`
- `AnalyzerPlugin` — `analyze(frame, config) -> Dict`
- `RendererPlugin` — `render(frame, config, analysis=None) -> RenderFrame` + `output_size(config) -> tuple`
- `TrackerPlugin` — `track(frame, detections, config) -> Dict` + `reset()`

**PluginDependencyResolver** (`plugin_dependency.py`): Kahn's topological sort. `resolve_order() -> List[str]`. Raises `CyclicDependencyError` on cycles.

**PluginMetadata** (`plugin_metadata.py`): Dataclass with `name`, `version`, `plugin_type`, `dependencies`, `capabilities`, `config_schema`, `tags`, etc. Supports JSON serialization (`to_json/from_json`) and file I/O.

### Application Services (`application/services/`)

**TemporalManager** (`temporal_manager.py`):

```python
TemporalManager()
```

| Method | Returns | Notes |
|--------|---------|-------|
| `configure(filters: List)` | `None` | Reads filter attrs: `required_input_history`, `needs_optical_flow`, `needs_delta_frame`, `needs_previous_output`. |
| `begin_frame()` | `None` | Invalidates per-frame caches. Call before `push_input`. |
| `push_input(frame)` | `None` | Ring buffer. Reallocates on resolution change. |
| `push_output(frame)` | `None` | |
| `get_previous_input(n=1)` | `Optional[ndarray]` | Read-only view. |
| `get_previous_output()` | `Optional[ndarray]` | Read-only view. |
| `get_delta()` | `Optional[ndarray]` | Lazy `cv2.absdiff`. Cached per frame. |
| `get_optical_flow()` | `Optional[ndarray]` | Lazy Farneback. Shape `(H, W, 2)` float32. Cached per frame. |

Hot path is not locked (single pipeline thread). `configure()` uses Lock. All returned arrays are `writeable=False`.

**ErrorHandler** (`error_handler.py`):

```python
ErrorHandler(event_bus=None)
```

Convenience methods: `handle_capture_error`, `handle_analysis_error`, `handle_transformation_error`, `handle_filtering_error`, `handle_rendering_error`, `handle_output_error`. Publishes `ErrorEvent` to bus. `get_error_count(error_type=None)` / `get_error_counts()`.

**FrameBuffer** (`frame_buffer.py`):

```python
FrameBuffer(max_size=2)
```

Thread-safe (Lock). `add(frame, timestamp=None)`, `get_latest() -> Optional[Tuple[ndarray, float]]` (pops + clears), `peek_latest()`.

**RetryManager** (`retry_manager.py`):

```python
RetryManager(max_camera_retries=5, camera_retry_delay=1.0, max_udp_retries=3, udp_retry_delay_base=0.1)
```

`reopen_source(source, stop_event=None)` — linear backoff. `write_with_retry(sink, rendered, config, output_size, stop_event=None)` — exponential backoff. `execute_with_retry(operation, max_retries=3, ...)` — generic wrapper.

## Discovered Patterns

1. **Thread safety tiers**: `EventBus`, `ConfigPersistence`, `EngineMetrics`, `FrameBuffer` are individually thread-safe. `LoopProfiler`, plugin subsystem internals, `ErrorHandler`, `RetryManager`, `TemporalManager` hot path are NOT.

2. **Component name vocabulary** is shared across `ErrorHandler`, `EngineMetrics`, and `LoopProfiler`: `capture`, `analysis`, `transformation`, `filtering`, `rendering`, `writing`.

3. **Error handling philosophy**: Loaders/managers catch and log exceptions internally, returning `None`/`False`. `ConfigPersistence` is the exception — it raises `ConfigPersistenceError` explicitly.

4. **EventBus delivery order**: standard subscribers + priority subscribers + pattern subscribers, all sorted descending by priority. Each callback fires at most once per publish (deduplication).

5. **TemporalManager demand-driven allocation**: Buffers are only allocated when at least one filter declares temporal needs via class attributes. No allocation = zero overhead when temporal features are unused.

## Dependencies on Other Teams

- `EngineConfig` from `domain/config.py`
- `BaseEvent` from `domain/events.py`
- `RenderFrame` from `domain/types.py` (used by plugin interfaces)

## Provided to Other Teams

- **EventBus** — publish/subscribe for all domain events
- **ConfigPersistence** — save/load engine config to JSON
- **EngineMetrics** — FPS, latency, error tracking
- **LoopProfiler** — per-phase timing with bottleneck analysis
- **PluginManager** — dynamic plugin loading with hot-reload and dependency resolution
- **TemporalManager** — shared optical flow, delta frames, frame history for filters
- **ErrorHandler** — centralized error handling with EventBus integration
- **FrameBuffer** — thread-safe frame queue for async pipelines
- **RetryManager** — retry strategies for sources and sinks
