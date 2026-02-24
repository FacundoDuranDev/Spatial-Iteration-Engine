---
name: infrastructure-development
description: Use when adding, modifying, or debugging cross-cutting infrastructure (EventBus, logging, metrics, profiling, plugins, performance, services) in infrastructure/ or application/services/
---

# Infrastructure Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `infrastructure/__init__.py` | Infrastructure module init |
| `infrastructure/event_bus.py` | EventBus pub/sub (thread-safe, RLock) |
| `infrastructure/logging.py` | StructuredLogger, ConsoleFormatter, JSON |
| `infrastructure/metrics.py` | EngineMetrics (FPS, errors, latency) |
| `infrastructure/profiling.py` | LoopProfiler (per-phase timing) |
| `infrastructure/message_queue.py` | MessageQueue (thread-safe, background) |
| `infrastructure/performance/frame_skipper.py` | Adaptive frame skipping |
| `infrastructure/performance/adaptive_quality.py` | Dynamic resolution scaling |
| `infrastructure/performance/gpu_accelerator.py` | GPU acceleration (optional) |
| `infrastructure/plugins/plugin_manager.py` | PluginManager with hot-reload |
| `infrastructure/plugins/plugin_interface.py` | Plugin base classes |
| `infrastructure/plugins/plugin_loader.py` | Dynamic module loading |
| `infrastructure/plugins/plugin_registry.py` | Thread-safe plugin registry |
| `infrastructure/plugins/plugin_metadata.py` | Plugin metadata dataclass |
| `application/services/frame_buffer.py` | Thread-safe FrameBuffer |
| `application/services/error_handler.py` | ErrorHandler → EventBus |
| `application/services/retry_manager.py` | RetryManager with backoff |

**Pattern:** Follow `event_bus.py` for thread-safe infrastructure, `plugin_manager.py` for file-watching services.

## Overview

Develop cross-cutting infrastructure that supports the pipeline without being part of it. Infrastructure provides event-driven communication, observability (logging, metrics, profiling), performance optimization (frame skipping, adaptive quality), plugin management, and application services (error handling, retry, frame buffering).

**Core principle:** Infrastructure is consumed by application and adapters but never depends on them. It depends only on domain types. It never modifies frames or pipeline behavior directly.

## Scope

**Your files:**
- `python/ascii_stream_engine/infrastructure/event_bus.py`
- `python/ascii_stream_engine/infrastructure/logging.py`
- `python/ascii_stream_engine/infrastructure/metrics.py`
- `python/ascii_stream_engine/infrastructure/profiling.py`
- `python/ascii_stream_engine/infrastructure/message_queue.py`
- `python/ascii_stream_engine/infrastructure/performance/frame_skipper.py`
- `python/ascii_stream_engine/infrastructure/performance/adaptive_quality.py`
- `python/ascii_stream_engine/infrastructure/performance/gpu_accelerator.py`
- `python/ascii_stream_engine/infrastructure/plugins/plugin_interface.py`
- `python/ascii_stream_engine/infrastructure/plugins/plugin_manager.py`
- `python/ascii_stream_engine/infrastructure/plugins/plugin_loader.py`
- `python/ascii_stream_engine/infrastructure/plugins/plugin_registry.py`
- `python/ascii_stream_engine/infrastructure/plugins/plugin_metadata.py`
- `python/ascii_stream_engine/application/services/frame_buffer.py`
- `python/ascii_stream_engine/application/services/error_handler.py`
- `python/ascii_stream_engine/application/services/retry_manager.py`

**Read-only (never modify):**
- `domain/events.py` — `BaseEvent` and all event dataclasses
- `domain/config.py` — `EngineConfig`
- `domain/types.py` — `RenderFrame`
- `ports/*` — All protocol definitions

**Never touch:**
- `application/engine.py`
- `application/pipeline/*`
- Any adapter file

## Module Map

```
infrastructure/
├── event_bus.py           # Central pub/sub (EventBus)
├── logging.py             # StructuredLogger, ConsoleFormatter, StructuredFormatter
├── metrics.py             # EngineMetrics (FPS, errors, latency)
├── profiling.py           # LoopProfiler (per-phase timing)
├── message_queue.py       # Thread-safe MessageQueue with background processing
├── performance/
│   ├── frame_skipper.py   # Adaptive frame skipping
│   ├── adaptive_quality.py # Dynamic quality/resolution scaling
│   └── gpu_accelerator.py # GPU acceleration (optional dep)
└── plugins/
    ├── plugin_interface.py # Plugin, FilterPlugin, AnalyzerPlugin, RendererPlugin, TrackerPlugin
    ├── plugin_manager.py   # PluginManager with hot-reload (watchdog)
    ├── plugin_loader.py    # Dynamic module/file loading
    ├── plugin_registry.py  # Thread-safe name→Plugin registry
    └── plugin_metadata.py  # PluginMetadata dataclass

application/services/
├── frame_buffer.py        # Thread-safe FrameBuffer (deque with timestamps)
├── error_handler.py       # ErrorHandler (centralized, publishes ErrorEvent)
└── retry_manager.py       # RetryManager (source/sink reconnection)
```

## EventBus

Thread-safe pub/sub with type-based subscriptions. Decouples all modules.

```python
from ..infrastructure.event_bus import EventBus

bus = EventBus()
bus.subscribe("analysis_complete", my_callback)
bus.publish(AnalysisCompleteEvent(frame_id="f1", results={}))
bus.publish_async(event)  # Non-blocking (daemon thread)
```

**Key patterns:**
- Callbacks execute outside the lock to prevent deadlocks
- `publish_async()` spawns a daemon thread per call
- Event type is inferred from class name (CamelCase → snake_case, strip "Event")
- `enable()`/`disable()` toggles event delivery without clearing subscriptions

**Adding a new event type:**
1. Add dataclass to `domain/events.py` extending `BaseEvent`
2. Subscribers use the snake_case name (e.g., `FrameCapturedEvent` → `"frame_captured"`)

## LoopProfiler

Measures per-phase timing within the main engine loop.

```python
from ..infrastructure.profiling import LoopProfiler

profiler = LoopProfiler(enabled=True, max_samples=1000)

# In engine loop:
profiler.start_frame()
profiler.start_phase("capture")
# ... capture ...
profiler.end_phase("capture")
profiler.start_phase("analysis")
# ... analyze ...
profiler.end_phase("analysis")
profiler.end_frame()

# Reports:
print(profiler.get_report())
summary = profiler.get_summary_dict()
```

**Registered phases:** `capture`, `analysis`, `transformation`, `filtering`, `rendering`, `writing`, `total_frame`

**When adding a new pipeline stage:** Register it as a constant and add to `phase_order` in `get_report()`.

## EngineMetrics

Thread-safe real-time metrics tracking.

```python
from ..infrastructure.metrics import EngineMetrics

metrics = EngineMetrics()
metrics.start()
metrics.record_frame()       # Each processed frame
metrics.record_error("capture")  # Per-component error counting
fps = metrics.get_fps()
summary = metrics.get_summary()  # All metrics as dict
```

**Provides:** FPS, frames processed, errors by component, latency avg/min/max, uptime.

## StructuredLogger

JSON-structured or colored console logging.

```python
from ..infrastructure.logging import configure_logging, get_logger, log_with_context

configure_logging(level="DEBUG", use_json=False, use_colors=True, log_file="engine.log")
logger = get_logger(__name__)
logger.info("Processing frame")
log_with_context(logger, logging.INFO, "Frame processed", frame_id="f1", latency_ms=12.3)
```

**Two formatters:**
- `ConsoleFormatter`: Colored human-readable (`[TIMESTAMP] LEVEL logger: message`)
- `StructuredFormatter`: JSON with timestamp, level, module, function, line, thread info

## MessageQueue

Thread-safe event queue with optional background processing.

```python
from ..infrastructure.message_queue import MessageQueue

mq = MessageQueue(maxsize=100)
mq.start_processing(handler=my_handler)  # Background thread
mq.put(event)
mq.stop_processing(timeout=5.0)
```

## Performance: FrameSkipper

Adaptive frame skipping when processing is too slow.

```python
from ..infrastructure.performance import FrameSkipper

skipper = FrameSkipper(target_fps=30.0, max_skip=3, skip_threshold=0.8)

# In loop:
if skipper.should_skip(processing_time):
    continue  # Skip this frame
```

**Logic:** If avg processing time > `skip_threshold * frame_time`, skip up to `max_skip` consecutive frames, then force-process one.

## Performance: AdaptiveQuality

Dynamic resolution/quality scaling based on FPS.

```python
from ..infrastructure.performance import AdaptiveQuality

aq = AdaptiveQuality(target_fps=30.0, min_quality=0.5, max_quality=1.0, quality_step=0.1)

# In loop:
aq.update_frame_time(frame_time)
quality = aq.adjust_quality()
target_w, target_h = aq.get_target_resolution(640, 480)
```

**Logic:** If FPS < 90% target → reduce quality. If FPS > 110% target → increase quality. Steps by `quality_step`.

## Plugin System

Dynamic plugin loading with optional hot-reload via `watchdog`.

### Plugin Interface

```python
from ..infrastructure.plugins.plugin_interface import (
    Plugin, FilterPlugin, AnalyzerPlugin, RendererPlugin, TrackerPlugin
)

class MyFilterPlugin(FilterPlugin):
    name = "my_filter"
    version = "1.0.0"
    description = "Does something cool"

    def apply(self, frame, config, analysis=None):
        return frame.copy()
```

**Plugin types:** `FilterPlugin`, `AnalyzerPlugin`, `RendererPlugin`, `TrackerPlugin`

### PluginManager

```python
manager = PluginManager(
    plugin_paths=["./plugins"],
    enable_hot_reload=True,  # Requires watchdog
    hot_reload_debounce=0.5,
)
manager.load_all()
plugin = manager.get_plugin("my_filter")
manager.start_hot_reload()
```

**Hot-reload:** Watches plugin directories for .py file changes (create/modify/delete). Debounced to avoid multiple reloads. Requires `watchdog` package (optional).

## Application Services

### ErrorHandler

Centralized error handling with EventBus integration.

```python
handler = ErrorHandler(event_bus=bus)
handler.handle(error, error_type="capture", module_name="camera")
# Convenience methods:
handler.handle_capture_error(error)
handler.handle_analysis_error(error)
handler.handle_rendering_error(error)
handler.handle_output_error(error)
```

Publishes `ErrorEvent` to EventBus. Tracks error counts per type.

### RetryManager

Source/sink reconnection with exponential backoff.

```python
retry = RetryManager(max_camera_retries=5, max_udp_retries=3)
retry.reopen_source(source, stop_event=stop)
retry.write_with_retry(sink, rendered, config, output_size, stop_event=stop)
success, result, error = retry.execute_with_retry(operation, max_retries=3)
```

**Camera retry:** Linear backoff (`delay * attempt`). **UDP retry:** Exponential backoff (`base * 2^attempt`).

### FrameBuffer

Thread-safe frame buffer for producer/consumer pattern.

```python
buf = FrameBuffer(max_size=2)
buf.add(frame, timestamp=time.time())
latest = buf.get_latest()   # Pops latest, clears rest
peeked = buf.peek_latest()  # Non-destructive read
```

## Domain Events Reference

Events live in `domain/events.py`. All extend `BaseEvent` (timestamp, source_id, metadata).

| Event | Key Fields | Published When |
|---|---|---|
| `FrameCapturedEvent` | frame, frame_id | Frame read from source |
| `AnalysisCompleteEvent` | frame_id, results, analysis_time | All analyzers finish |
| `FilterAppliedEvent` | frame_id, filter_name, filter_time | Filter applied |
| `RenderCompleteEvent` | frame_id, render_time, output_size | Rendering done |
| `FrameWrittenEvent` | frame_id, write_time | Output written |
| `TrackingEvent` | frame_id, trajectories, tracked_objects | Tracking updated |
| `SensorEvent` | sensor_name, sensor_data, sensor_type | External sensor data |
| `ControlEvent` | controller_name, command, params | MIDI/OSC command |
| `ConfigChangeEvent` | changed_params, old_values | Config modified |
| `ErrorEvent` | error_type, error_message, module_name | Error in any module |

## Thread Safety Rules

All infrastructure components are thread-safe:
- `EventBus`: `threading.RLock` for subscriber list, callbacks execute outside lock
- `EngineMetrics`: `threading.Lock` for all counters
- `FrameBuffer`: `threading.Lock` for deque access
- `MessageQueue`: `queue.Queue` (inherently thread-safe) + background thread
- `PluginManager`: `threading.Lock` for hot-reload operations
- `StructuredLogger`: Class-level `threading.Lock` for configuration

**Pattern:** Acquire lock, copy data, release lock, process outside lock.

## Contracts

| Contract | Rule |
|---|---|
| Dependencies | Domain only. Never import from adapters, application/engine, or pipeline. |
| Thread safety | ALL public methods must be thread-safe |
| Timing | Use `time.perf_counter()`, NEVER `time.time()` for durations |
| Error handling | Log and continue. Infrastructure NEVER crashes the pipeline. |
| Optional deps | `watchdog` for hot-reload, GPU libs for accelerator. Use try/except ImportError. |
| Event bus callbacks | Must not block. If heavy, use `publish_async()`. |
| Memory | Bound all collections (`maxlen`, `max_samples`, trim). No unbounded growth. |

## Testing

```python
def test_event_bus_pubsub():
    """Events reach subscribers."""
    bus = EventBus()
    received = []
    bus.subscribe("test", lambda e: received.append(e))
    event = BaseEvent()
    bus.publish(event, "test")
    assert len(received) == 1

def test_event_bus_disabled():
    """Disabled bus doesn't deliver events."""
    bus = EventBus()
    received = []
    bus.subscribe("test", lambda e: received.append(e))
    bus.disable()
    bus.publish(BaseEvent(), "test")
    assert len(received) == 0

def test_profiler_phases():
    """Profiler records phase timings."""
    p = LoopProfiler(enabled=True)
    p.start_frame()
    p.start_phase("capture")
    time.sleep(0.001)
    p.end_phase("capture")
    p.end_frame()
    stats = p.get_stats("capture")
    assert "capture" in stats
    assert stats["capture"].count == 1

def test_metrics_fps():
    """Metrics correctly compute FPS."""
    m = EngineMetrics()
    m.start()
    for _ in range(10):
        time.sleep(0.01)
        m.record_frame()
    fps = m.get_fps()
    assert 50 < fps < 150  # ~100 FPS at 10ms per frame

def test_frame_skipper_no_skip_initially():
    """FrameSkipper doesn't skip first frames."""
    fs = FrameSkipper(target_fps=30.0)
    assert not fs.should_skip(0.01)
    assert not fs.should_skip(0.01)

def test_error_handler_publishes():
    """ErrorHandler publishes to EventBus."""
    bus = EventBus()
    received = []
    bus.subscribe("error", lambda e: received.append(e))
    handler = ErrorHandler(event_bus=bus)
    handler.handle(Exception("test"), "capture", "camera")
    assert len(received) == 1

def test_frame_buffer_thread_safe():
    """FrameBuffer handles concurrent access."""
    buf = FrameBuffer(max_size=2)
    buf.add(np.zeros((100, 100, 3), dtype=np.uint8))
    result = buf.get_latest()
    assert result is not None
    assert buf.is_empty()
```

## Red Flags

**Stop immediately if you catch yourself:**
- Importing from `adapters/` or `application/engine.py`
- Modifying `application/pipeline/` files
- Using `time.time()` for duration measurement (use `time.perf_counter()`)
- Creating unbounded collections (always use `maxlen` or trim)
- Blocking inside EventBus lock during callback execution
- Making infrastructure depend on specific adapter implementations
- Storing frame numpy references beyond their intended scope
- Missing thread safety (lock) on shared mutable state

## Common Mistakes

| Mistake | Fix |
|---|---|
| Deadlock in EventBus callback | Copy subscriber list under lock, execute callbacks outside lock |
| Unbounded metrics history | Use `maxlen` on deque or trim after N samples |
| `time.time()` for profiling | `time.perf_counter()` for accurate monotonic timing |
| Hot-reload crashes pipeline | Debounce, catch all exceptions in reload path |
| Error handler raises | Always wrap in try/except, log and continue |
| Plugin not found after reload | Update file→plugin mapping after successful reload |
| Frame buffer memory leak | Use `deque(maxlen=N)`, `get_latest()` clears old frames |
| Missing `watchdog` import guard | Use try/except ImportError with `WATCHDOG_AVAILABLE` flag |
