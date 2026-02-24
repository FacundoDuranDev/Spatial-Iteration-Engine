# Infrastructure Team -- 7-Phase Task Plan

**Team scope:** Cross-cutting concerns in `infrastructure/` and `application/services/`.
**Skill reference:** `.claude/skills/infrastructure-development/SKILL.md`
**Branch:** `feature/infra-*` (one per phase, merged to `develop` via PR)

---

## Constraints (enforced at every phase)

| Constraint | Rule |
|---|---|
| Dependencies | Domain only. Never import from `adapters/`, `application/engine.py`, or `application/pipeline/`. |
| Thread safety | ALL public methods must be thread-safe (use `threading.Lock` or `threading.RLock`). |
| Timing | Use `time.perf_counter()`, NEVER `time.time()` for duration measurement. |
| Memory | Bound all collections (`maxlen`, `max_samples`, trim). No unbounded growth. |
| EventBus callbacks | Must not block. If heavy work is needed, use `publish_async()`. |
| Error handling | Log and continue. Infrastructure NEVER crashes the pipeline. |
| Optional deps | Guard with `try/except ImportError` and `_AVAILABLE` flags. |
| Read-only files | `domain/events.py`, `domain/config.py`, `domain/types.py`, `ports/*` -- never modify. |
| Never touch | `application/engine.py`, `application/pipeline/*`, any adapter file. |

---

## Phase 1: Config Persistence Service

**Goal:** Provide a thread-safe service in `infrastructure/` that serializes and deserializes `EngineConfig` to/from JSON files, with versioning and atomic writes. This supplements the existing `domain/config_loader.py` (which handles YAML/JSON loading and profile management) by adding runtime save/load with schema versioning, diff tracking, and crash-safe atomics.

**Branch:** `feature/infra-config-persistence`

### Deliverables

| # | File | Description |
|---|---|---|
| 1.1 | `python/ascii_stream_engine/infrastructure/config_persistence.py` | `ConfigPersistence` class with `save(config, path)`, `load(path) -> EngineConfig`, `save_atomic(config, path)`, `get_diff(a, b) -> dict`, `get_schema_version() -> str` |
| 1.2 | `python/ascii_stream_engine/tests/test_config_persistence.py` | Unit tests (see acceptance criteria) |
| 1.3 | `python/ascii_stream_engine/infrastructure/__init__.py` | Export `ConfigPersistence` |

### Implementation Details

**`ConfigPersistence`** class:

```python
class ConfigPersistence:
    """Thread-safe config save/load with versioning and atomic writes."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(self, default_path: str = "engine_config.json") -> None: ...
    def save(self, config: EngineConfig, path: Optional[str] = None) -> None: ...
    def save_atomic(self, config: EngineConfig, path: Optional[str] = None) -> None: ...
    def load(self, path: Optional[str] = None) -> EngineConfig: ...
    def exists(self, path: Optional[str] = None) -> bool: ...
    def get_diff(self, config_a: EngineConfig, config_b: EngineConfig) -> Dict[str, Any]: ...
    def get_schema_version(self) -> str: ...
```

- `save_atomic()` writes to a `.tmp` file first, then uses `os.replace()` for crash-safe rename.
- JSON envelope format: `{"schema_version": "1.0.0", "saved_at": <ISO timestamp>, "config": {...}}`.
- `load()` validates `schema_version` and raises `ConfigPersistenceError` on mismatch.
- `get_diff()` returns `{"changed": {key: (old, new)}, "added": {key: val}, "removed": {key: val}}`.
- Thread safety: `threading.Lock` around all file I/O.
- Imports only from `domain.config` (`EngineConfig`, `ConfigValidationError`).

### Acceptance Criteria

- [ ] `save()` writes valid JSON that `load()` round-trips back to an equivalent `EngineConfig`.
- [ ] `save_atomic()` leaves no `.tmp` artifacts on success; does not corrupt existing file on failure.
- [ ] `load()` raises `ConfigPersistenceError` when file is missing, corrupt, or schema version mismatches.
- [ ] `get_diff()` correctly identifies changed, added, and removed keys between two configs.
- [ ] All public methods are thread-safe (verified by concurrent read/write test).
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] JSON output contains `schema_version` and `saved_at` metadata fields.
- [ ] Tests cover: round-trip, atomic write failure recovery, schema mismatch, diff detection, concurrent access.
- [ ] `make lint` and `make format` pass with no changes.

### Estimated effort: 3-4 hours

---

## Phase 2: Plugin Hot-Reload Improvement

**Goal:** Make the existing `PluginManager` hot-reload faster, more reliable, and dependency-aware. Currently, reload is per-file with simple debounce using `time.time()` (violation). Add dependency ordering, batch reload, and proper timing.

**Branch:** `feature/infra-plugin-hotreload-v2`

### Deliverables

| # | File | Description |
|---|---|---|
| 2.1 | `python/ascii_stream_engine/infrastructure/plugins/plugin_manager.py` | Enhanced `PluginManager` with batch reload, dependency graph, perf_counter timing |
| 2.2 | `python/ascii_stream_engine/infrastructure/plugins/plugin_dependency.py` | New `PluginDependencyResolver` class for topological sort of plugin load order |
| 2.3 | `python/ascii_stream_engine/infrastructure/plugins/plugin_metadata.py` | Add `dependencies: List[str]` field to `PluginMetadata` |
| 2.4 | `python/ascii_stream_engine/tests/test_plugin_hotreload.py` | Tests for batch reload, dependency ordering, debounce timing |

### Implementation Details

**`PluginDependencyResolver`** (new file `plugin_dependency.py`):

```python
class PluginDependencyResolver:
    """Resolves plugin load order using topological sort."""

    def __init__(self) -> None: ...
    def add_plugin(self, name: str, dependencies: List[str]) -> None: ...
    def resolve_order(self) -> List[str]: ...  # Topological sort, raises CyclicDependencyError
    def get_dependents(self, name: str) -> Set[str]: ...  # Plugins that depend on `name`
```

**`PluginManager` changes:**

- Replace `time.time()` in `PluginFileHandler.on_modified()` with `time.perf_counter()`.
- Add batch reload: collect file changes over a configurable window (default 1.0s), then reload all affected plugins in dependency order.
- Add `_dependency_resolver: PluginDependencyResolver` field.
- On reload of plugin X, also reload all plugins that depend on X (via `get_dependents()`).
- Add `reload_stats() -> dict` method returning `{reload_count, avg_reload_time_ms, last_reload_at}`.
- Bound `_pending_reloads` dict with a max size of 100 entries, evicting oldest.

**`PluginMetadata` changes:**

- Add optional `dependencies: List[str] = field(default_factory=list)` field.

### Acceptance Criteria

- [ ] `time.time()` replaced with `time.perf_counter()` in all hot-reload timing paths.
- [ ] Dependency resolver correctly topologically sorts plugins; raises on cycles.
- [ ] Modifying plugin A triggers reload of A and all plugins depending on A, in correct order.
- [ ] Batch window collects multiple file changes before triggering a single reload pass.
- [ ] `_pending_reloads` is bounded (maxlen or manual trim after 100 entries).
- [ ] `reload_stats()` returns accurate timing data using `perf_counter`.
- [ ] All existing `test_plugins.py` tests continue to pass.
- [ ] New tests cover: dependency ordering, cycle detection, cascade reload, batch debounce.
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] `make check` passes.

### Estimated effort: 4-5 hours

---

## Phase 3: Enhanced EventBus

**Goal:** Extend `EventBus` with event filtering, priority-based delivery, bounded event history for replay, and wildcard subscriptions -- without breaking the existing API.

**Branch:** `feature/infra-eventbus-enhanced`

### Deliverables

| # | File | Description |
|---|---|---|
| 3.1 | `python/ascii_stream_engine/infrastructure/event_bus.py` | Enhanced `EventBus` with filtering, priorities, replay, wildcards |
| 3.2 | `python/ascii_stream_engine/infrastructure/event_filter.py` | New `EventFilter` protocol and built-in filters |
| 3.3 | `python/ascii_stream_engine/tests/test_event_bus_enhanced.py` | Tests for all new features |

### Implementation Details

**`EventFilter`** (new file `event_filter.py`):

```python
class EventFilter(Protocol):
    """Protocol for filtering events before delivery."""
    def should_deliver(self, event: BaseEvent, event_type: str) -> bool: ...

class RateLimitFilter:
    """Limits event delivery to N per second per event_type."""
    def __init__(self, max_per_second: float = 10.0) -> None: ...

class DeduplicationFilter:
    """Suppresses duplicate events within a time window."""
    def __init__(self, window_seconds: float = 1.0, max_history: int = 100) -> None: ...
```

**`EventBus` enhancements (backward-compatible additions):**

```python
class EventBus:
    # Existing API unchanged

    # New methods:
    def subscribe_with_priority(
        self, event_type: str, callback: Callable, priority: int = 0
    ) -> None: ...  # Higher priority callbacks execute first

    def subscribe_pattern(
        self, pattern: str, callback: Callable
    ) -> None: ...  # Wildcard: "analysis_*" matches "analysis_complete", "analysis_started"

    def add_filter(self, event_filter: EventFilter) -> None: ...
    def remove_filter(self, event_filter: EventFilter) -> None: ...

    def enable_replay(self, max_events: int = 1000) -> None: ...
    def replay(self, event_type: Optional[str] = None, since: Optional[float] = None) -> List[BaseEvent]: ...
    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[BaseEvent]: ...

    def get_stats(self) -> Dict[str, Any]: ...  # {events_published, events_filtered, subscribers_count, ...}
```

- Priority subscribers stored as sorted list of `(priority, callback)` tuples.
- Pattern matching uses `fnmatch.fnmatchcase()` for wildcard support.
- Replay buffer: `deque(maxlen=max_events)` storing `(event_type, event, timestamp)` tuples.
- Filters run before callback execution; if any filter returns `False`, event is not delivered to that subscriber.
- `get_stats()` tracks `events_published`, `events_filtered`, `events_delivered`, `subscribers_by_type`.
- All new state protected by the existing `self._lock` (RLock).
- Callbacks still execute outside the lock to prevent deadlocks.

### Acceptance Criteria

- [ ] All existing `EventBus` tests pass without modification (backward compatibility).
- [ ] `subscribe_with_priority()`: higher priority callbacks are invoked before lower ones.
- [ ] `subscribe_pattern("analysis_*")` receives events for `"analysis_complete"` and `"analysis_started"` but not `"filter_applied"`.
- [ ] `RateLimitFilter` suppresses events beyond the configured rate.
- [ ] `DeduplicationFilter` suppresses identical events within the time window.
- [ ] Replay buffer is bounded by `max_events`; `replay()` returns events matching criteria.
- [ ] `get_stats()` returns accurate counts.
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] Replay timestamps use `time.perf_counter()`.
- [ ] All collections are bounded (`deque(maxlen=...)` or explicit trim).
- [ ] `make check` passes.

### Estimated effort: 5-6 hours

---

## Phase 4: Performance Dashboard Data Layer

**Goal:** Build the data collection, aggregation, and export layer that provides real-time latency tracking per pipeline phase, budget violation detection, and historical statistics. This is the data backend for a performance dashboard (the presentation layer is Phase 6).

**Branch:** `feature/infra-perf-dashboard-data`

### Deliverables

| # | File | Description |
|---|---|---|
| 4.1 | `python/ascii_stream_engine/infrastructure/performance/budget_tracker.py` | `BudgetTracker` that monitors per-phase latency against the 33.3ms budget from `rules/LATENCY_BUDGET.md` |
| 4.2 | `python/ascii_stream_engine/infrastructure/performance/metrics_aggregator.py` | `MetricsAggregator` that collects time-series data from `EngineMetrics` + `LoopProfiler` with configurable window sizes |
| 4.3 | `python/ascii_stream_engine/infrastructure/performance/metrics_exporter.py` | `MetricsExporter` that formats aggregated data as JSON snapshots for consumption by dashboards or files |
| 4.4 | `python/ascii_stream_engine/infrastructure/performance/__init__.py` | Update exports |
| 4.5 | `python/ascii_stream_engine/tests/test_budget_tracker.py` | Tests for budget violation detection |
| 4.6 | `python/ascii_stream_engine/tests/test_metrics_aggregator.py` | Tests for aggregation and windowing |

### Implementation Details

**`BudgetTracker`** (new file `budget_tracker.py`):

```python
@dataclass
class PhaseBudget:
    name: str
    budget_ms: float
    p95_max_ms: float

class BudgetTracker:
    """Tracks per-phase latency against the frame budget."""

    # Budget constants from rules/LATENCY_BUDGET.md
    FRAME_BUDGET_MS = 33.3
    PHASE_BUDGETS = {
        "capture": PhaseBudget("capture", 2.0, 5.0),
        "analysis": PhaseBudget("analysis", 15.0, 20.0),
        "tracking": PhaseBudget("tracking", 2.0, 3.0),
        "transformation": PhaseBudget("transformation", 2.0, 4.0),
        "filtering": PhaseBudget("filtering", 5.0, 8.0),
        "rendering": PhaseBudget("rendering", 3.0, 5.0),
        "writing": PhaseBudget("writing", 3.0, 5.0),
    }

    def __init__(self, max_history: int = 500) -> None: ...
    def record_phase(self, phase: str, duration_s: float) -> None: ...
    def record_frame(self, total_duration_s: float) -> None: ...
    def get_violations(self, window: int = 100) -> Dict[str, BudgetViolation]: ...
    def get_budget_utilization(self) -> Dict[str, float]: ...  # percentage of budget used per phase
    def get_p95(self, phase: str) -> float: ...  # p95 latency in ms
    def is_over_budget(self) -> bool: ...  # True if total frame exceeds 33.3ms
    def get_degradation_recommendation(self) -> Optional[str]: ...  # Suggest degradation step per LATENCY_BUDGET.md
    def reset(self) -> None: ...
```

- All durations stored in a `deque(maxlen=max_history)` per phase.
- `get_degradation_recommendation()` follows the 5-step hierarchy from `rules/LATENCY_BUDGET.md`.
- Thread-safe with `threading.Lock`.
- Uses `time.perf_counter()` for any internal timing.

**`MetricsAggregator`** (new file `metrics_aggregator.py`):

```python
class MetricsAggregator:
    """Aggregates metrics from EngineMetrics and LoopProfiler into time-series windows."""

    def __init__(
        self,
        window_size_seconds: float = 10.0,
        max_windows: int = 360,  # 1 hour at 10s windows
        sample_interval: float = 1.0,
    ) -> None: ...
    def record_snapshot(self, metrics_summary: Dict, profiler_summary: Dict) -> None: ...
    def get_latest(self) -> Optional[Dict]: ...
    def get_window(self, seconds: float = 60.0) -> List[Dict]: ...
    def get_trend(self, metric_key: str, seconds: float = 60.0) -> List[Tuple[float, float]]: ...  # [(timestamp, value), ...]
    def reset(self) -> None: ...
```

- Stores snapshots in `deque(maxlen=max_windows)`.
- Each snapshot: `{"timestamp": float, "fps": float, "frame_time_ms": float, "phases": {...}, "errors": {...}}`.
- Thread-safe with `threading.Lock`.

**`MetricsExporter`** (new file `metrics_exporter.py`):

```python
class MetricsExporter:
    """Exports aggregated metrics as JSON for dashboard consumption."""

    def __init__(self, aggregator: MetricsAggregator, budget_tracker: BudgetTracker) -> None: ...
    def export_snapshot(self) -> str: ...  # JSON string of current state
    def export_to_file(self, path: str) -> None: ...  # Write snapshot to file
    def get_dashboard_payload(self) -> Dict[str, Any]: ...  # Structured dict for HTTP response
```

### Acceptance Criteria

- [ ] `BudgetTracker.record_phase()` correctly flags violations when latency exceeds budget.
- [ ] `get_p95()` returns accurate 95th percentile latency per phase.
- [ ] `get_degradation_recommendation()` returns recommendations in the correct order from `rules/LATENCY_BUDGET.md`.
- [ ] `MetricsAggregator` stores bounded snapshots and retrieves windows by time range.
- [ ] `get_trend()` returns a time-series of `(timestamp, value)` for a given metric key.
- [ ] `MetricsExporter.export_snapshot()` produces valid JSON.
- [ ] All collections bounded: `deque(maxlen=...)` for history, phases, windows.
- [ ] All public methods thread-safe.
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] `make check` passes.

### Estimated effort: 5-6 hours

---

## Phase 5: Distributed Metrics Collection

**Goal:** Allow multiple engine instances to report metrics to a central aggregator over UDP or shared memory, enabling multi-instance monitoring. Designed for the scenario where several `StreamEngine` processes run on the same machine or network.

**Branch:** `feature/infra-distributed-metrics`

### Deliverables

| # | File | Description |
|---|---|---|
| 5.1 | `python/ascii_stream_engine/infrastructure/distributed/metrics_reporter.py` | `MetricsReporter` that periodically sends metric snapshots via UDP |
| 5.2 | `python/ascii_stream_engine/infrastructure/distributed/metrics_collector.py` | `MetricsCollector` that receives and aggregates metrics from multiple reporters |
| 5.3 | `python/ascii_stream_engine/infrastructure/distributed/protocol.py` | Wire protocol definition: JSON-over-UDP message format |
| 5.4 | `python/ascii_stream_engine/infrastructure/distributed/__init__.py` | Package init with exports |
| 5.5 | `python/ascii_stream_engine/tests/test_distributed_metrics.py` | Tests for reporter, collector, protocol |

### Implementation Details

**`protocol.py`** (new file):

```python
@dataclass
class MetricsMessage:
    """Wire format for distributed metrics."""
    version: int = 1
    instance_id: str = ""
    timestamp: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> bytes: ...  # JSON -> UTF-8 bytes, max 65000 bytes
    @classmethod
    def deserialize(cls, data: bytes) -> "MetricsMessage": ...
```

- Message format: `{"v": 1, "id": "<instance_id>", "ts": <perf_counter>, "m": {<metrics_dict>}}`.
- Compact keys to fit within UDP packet size limit.

**`MetricsReporter`** (new file `metrics_reporter.py`):

```python
class MetricsReporter:
    """Sends periodic metric snapshots to a collector via UDP."""

    def __init__(
        self,
        instance_id: str,
        collector_host: str = "127.0.0.1",
        collector_port: int = 9876,
        report_interval: float = 5.0,
        metrics: Optional[EngineMetrics] = None,
        profiler: Optional[LoopProfiler] = None,
    ) -> None: ...
    def start(self) -> None: ...  # Background daemon thread
    def stop(self) -> None: ...
    def report_now(self) -> None: ...  # Immediate one-shot report
    def is_running(self) -> bool: ...
```

- Uses `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)` for non-blocking UDP sends.
- Background thread sleeps with `threading.Event.wait(report_interval)` for clean shutdown.
- Imports `EngineMetrics` from `infrastructure.metrics` and `LoopProfiler` from `infrastructure.profiling` (both in-layer, allowed).

**`MetricsCollector`** (new file `metrics_collector.py`):

```python
class MetricsCollector:
    """Receives and aggregates metrics from multiple engine instances."""

    def __init__(
        self,
        listen_host: str = "0.0.0.0",
        listen_port: int = 9876,
        max_instances: int = 20,
        stale_timeout: float = 30.0,
    ) -> None: ...
    def start(self) -> None: ...  # Background thread listening on UDP
    def stop(self) -> None: ...
    def get_instance_ids(self) -> List[str]: ...
    def get_instance_metrics(self, instance_id: str) -> Optional[Dict]: ...
    def get_aggregate(self) -> Dict[str, Any]: ...  # Aggregate across all instances
    def get_all_instances(self) -> Dict[str, Dict]: ...
    def prune_stale(self) -> int: ...  # Remove instances not reporting for stale_timeout
```

- Per-instance storage: `Dict[str, deque]` with `maxlen=100` snapshots per instance.
- `max_instances` enforced: reject new instances if at capacity.
- `prune_stale()` called automatically every `stale_timeout` seconds.
- UDP receive buffer: 65535 bytes.
- Thread-safe with `threading.Lock`.

### Acceptance Criteria

- [ ] `MetricsReporter` sends valid `MetricsMessage` datagrams at the configured interval.
- [ ] `MetricsCollector` receives and stores metrics from multiple reporters (test with 3+ simulated instances).
- [ ] `get_aggregate()` correctly computes mean FPS, total frames, sum of errors across all instances.
- [ ] `prune_stale()` removes instances that have not reported within `stale_timeout`.
- [ ] `max_instances` limit is enforced; new instances beyond limit are rejected.
- [ ] All per-instance history bounded by `deque(maxlen=100)`.
- [ ] `MetricsMessage.serialize()`/`deserialize()` round-trips correctly.
- [ ] Reporter and collector clean up sockets on `stop()`.
- [ ] All public methods thread-safe.
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] `make check` passes.

### Estimated effort: 6-7 hours

---

## Phase 6: Web Dashboard Server

**Goal:** Provide an HTTP server (stdlib `http.server` only, no Flask/Django dependency) that serves a metrics dashboard endpoint and optionally a live MJPEG preview stream. This is the presentation layer consuming data from Phase 4 (`MetricsAggregator`, `BudgetTracker`, `MetricsExporter`) and Phase 5 (`MetricsCollector`).

**Branch:** `feature/infra-web-dashboard`

### Deliverables

| # | File | Description |
|---|---|---|
| 6.1 | `python/ascii_stream_engine/infrastructure/dashboard/server.py` | `DashboardServer` HTTP server with JSON API endpoints |
| 6.2 | `python/ascii_stream_engine/infrastructure/dashboard/routes.py` | Route handler: `/api/metrics`, `/api/budget`, `/api/instances`, `/api/health` |
| 6.3 | `python/ascii_stream_engine/infrastructure/dashboard/mjpeg_stream.py` | `MJPEGStreamer` for optional live frame preview at `/stream` |
| 6.4 | `python/ascii_stream_engine/infrastructure/dashboard/__init__.py` | Package init with exports |
| 6.5 | `python/ascii_stream_engine/tests/test_dashboard_server.py` | Tests for HTTP endpoints and response format |

### Implementation Details

**`DashboardServer`** (new file `server.py`):

```python
class DashboardServer:
    """Lightweight HTTP dashboard server using stdlib http.server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        metrics_exporter: Optional[MetricsExporter] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        frame_buffer: Optional[FrameBuffer] = None,  # For MJPEG preview
    ) -> None: ...
    def start(self) -> None: ...  # Background daemon thread
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
    def get_url(self) -> str: ...
```

**API Endpoints** (defined in `routes.py`):

| Endpoint | Method | Response | Description |
|---|---|---|---|
| `/api/health` | GET | `{"status": "ok", "uptime": float}` | Health check |
| `/api/metrics` | GET | Full metrics snapshot JSON | Current metrics from `MetricsExporter` |
| `/api/budget` | GET | Budget utilization + violations JSON | From `BudgetTracker` |
| `/api/instances` | GET | All engine instances + aggregate | From `MetricsCollector` |
| `/api/metrics/history?seconds=60` | GET | Time-series array | Historical metrics from `MetricsAggregator` |
| `/stream` | GET | `multipart/x-mixed-replace` MJPEG | Live frame preview (optional) |

**`MJPEGStreamer`** (new file `mjpeg_stream.py`):

```python
class MJPEGStreamer:
    """Generates MJPEG stream from FrameBuffer for live preview."""

    def __init__(
        self,
        frame_buffer: FrameBuffer,
        target_fps: float = 10.0,
        jpeg_quality: int = 50,
        max_width: int = 320,
    ) -> None: ...
    def generate_frames(self) -> Iterator[bytes]: ...  # Yields JPEG frames with multipart boundary
```

- Uses `cv2.imencode()` for JPEG compression (optional dep with `try/except ImportError`).
- Reads from `FrameBuffer.peek_latest()` (non-destructive) to avoid interfering with the pipeline.
- `target_fps` limits stream rate to avoid CPU overhead.
- `max_width` downscales frames before encoding to reduce bandwidth.

**Server implementation:**

- Built on `http.server.HTTPServer` + `http.server.BaseHTTPRequestHandler`.
- Runs in a daemon thread; uses `server.shutdown()` for clean stop.
- All responses include `Access-Control-Allow-Origin: *` for cross-origin access.
- JSON responses use `Content-Type: application/json`.
- Request handling logs errors and returns `500` with JSON error body on failure.

### Acceptance Criteria

- [ ] Server starts on configured `host:port` in a background thread and stops cleanly.
- [ ] `/api/health` returns 200 with status and uptime.
- [ ] `/api/metrics` returns valid JSON containing FPS, frame count, latency, errors.
- [ ] `/api/budget` returns budget utilization percentages and violation list.
- [ ] `/api/instances` returns data for all connected engine instances (or empty list).
- [ ] `/api/metrics/history?seconds=60` returns bounded time-series data.
- [ ] `/stream` returns MJPEG multipart stream (tested with at least frame header verification).
- [ ] Server responds with 404 JSON for unknown routes.
- [ ] All responses include CORS headers.
- [ ] `cv2` is optional: if unavailable, `/stream` returns 503 with explanation.
- [ ] No imports from `adapters/`, `application/engine.py`, or `application/pipeline/`.
- [ ] `make check` passes.
- [ ] Server handles concurrent requests without blocking the engine loop.

### Estimated effort: 6-8 hours

---

## Phase 7: Integration, Documentation, and Hardening

**Goal:** Wire all Phase 1-6 components together, add integration tests that exercise the full stack, harden edge cases, and produce developer documentation. Ensure all new infrastructure is discoverable from the public API.

**Branch:** `feature/infra-integration`

### Deliverables

| # | File | Description |
|---|---|---|
| 7.1 | `python/ascii_stream_engine/infrastructure/__init__.py` | Final public API exports for all new modules |
| 7.2 | `python/ascii_stream_engine/infrastructure/performance/__init__.py` | Export `BudgetTracker`, `MetricsAggregator`, `MetricsExporter` |
| 7.3 | `python/ascii_stream_engine/infrastructure/distributed/__init__.py` | Export `MetricsReporter`, `MetricsCollector` |
| 7.4 | `python/ascii_stream_engine/infrastructure/dashboard/__init__.py` | Export `DashboardServer` |
| 7.5 | `python/ascii_stream_engine/tests/test_infra_integration.py` | Integration tests: full metrics flow from recording to dashboard export |
| 7.6 | `python/ascii_stream_engine/tests/test_infra_thread_safety.py` | Dedicated thread safety stress tests for all new components |
| 7.7 | `CHANGELOG.md` | Update `[Unreleased]` section with all infrastructure features |

### Integration Tests (`test_infra_integration.py`)

The following end-to-end scenarios must be tested:

1. **Config round-trip:** Create `EngineConfig` -> `ConfigPersistence.save_atomic()` -> `ConfigPersistence.load()` -> verify equality.
2. **Metrics pipeline:** `EngineMetrics.record_frame()` (50 frames) -> `MetricsAggregator.record_snapshot()` -> `MetricsExporter.export_snapshot()` -> verify JSON structure.
3. **Budget detection:** `BudgetTracker.record_phase("analysis", 0.025)` (25ms, over 15ms budget) -> verify `get_violations()` flags analysis, `get_degradation_recommendation()` returns first step.
4. **EventBus enhanced flow:** Subscribe with priority + filter -> publish events -> verify delivery order and filtering.
5. **Distributed round-trip:** `MetricsReporter` -> UDP -> `MetricsCollector` -> `get_instance_metrics()` -> verify data integrity (loopback test on `127.0.0.1`).
6. **Dashboard endpoint:** Start `DashboardServer` -> HTTP GET `/api/metrics` -> verify 200 + JSON body -> stop server.

### Thread Safety Stress Tests (`test_infra_thread_safety.py`)

For each new component, spawn 10 threads performing concurrent operations for 2 seconds:

- `ConfigPersistence`: 5 writers + 5 readers on the same file.
- `EventBus`: 5 publishers + 5 subscribers with filters enabled.
- `BudgetTracker`: 10 threads calling `record_phase()` concurrently.
- `MetricsAggregator`: 5 threads recording snapshots + 5 threads reading windows.
- `MetricsCollector`: Simulated 10 instances sending concurrent UDP datagrams.

All tests must complete without deadlocks (timeout: 10s), without exceptions, and without data corruption.

### Hardening Checklist

- [ ] Audit every new file: no `time.time()` for durations (grep verification).
- [ ] Audit every new file: no unbounded collections (grep for `list()`, `dict()` without maxlen).
- [ ] Audit every new file: no imports from forbidden modules.
- [ ] Audit every new file: all public methods have docstrings.
- [ ] Add graceful shutdown for all background threads (dashboard server, metrics reporter, metrics collector).
- [ ] Verify `__del__` methods do not raise on double-close.
- [ ] Add `py.typed` marker if not already present (for mypy compatibility).
- [ ] Run `make format && make lint && make test` -- all green.

### CHANGELOG Entry

```markdown
## [Unreleased]

### Added
- Config persistence with atomic writes and schema versioning (`infrastructure/config_persistence.py`)
- Plugin dependency resolution and batch hot-reload (`infrastructure/plugins/plugin_dependency.py`)
- Enhanced EventBus with priority subscriptions, wildcard patterns, event filtering, and replay (`infrastructure/event_bus.py`, `infrastructure/event_filter.py`)
- Performance budget tracker with per-phase violation detection and degradation recommendations (`infrastructure/performance/budget_tracker.py`)
- Metrics aggregator with time-series windowing and JSON export (`infrastructure/performance/metrics_aggregator.py`, `infrastructure/performance/metrics_exporter.py`)
- Distributed metrics collection via UDP for multi-instance monitoring (`infrastructure/distributed/`)
- Lightweight HTTP dashboard server with JSON API and optional MJPEG preview (`infrastructure/dashboard/`)

### Fixed
- Plugin hot-reload timing now uses `time.perf_counter()` instead of `time.time()`
```

### Acceptance Criteria

- [ ] All 6 integration test scenarios pass.
- [ ] All thread safety stress tests pass within 10s timeout.
- [ ] `grep -rn "time.time()" python/ascii_stream_engine/infrastructure/` returns zero matches (excluding import lines).
- [ ] `grep -rn "from.*adapters" python/ascii_stream_engine/infrastructure/` returns zero matches.
- [ ] `grep -rn "from.*application.engine" python/ascii_stream_engine/infrastructure/` returns zero matches.
- [ ] `grep -rn "from.*application.pipeline" python/ascii_stream_engine/infrastructure/` returns zero matches.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] `make check` passes (format + lint + all tests).
- [ ] All new modules importable from `python/ascii_stream_engine/infrastructure/__init__.py`.
- [ ] No regressions in existing test suite (all 15 existing test files pass).

### Estimated effort: 4-5 hours

---

## Phase Dependency Graph

```
Phase 1 (Config Persistence)     -- independent, start immediately
Phase 2 (Plugin Hot-Reload)      -- independent, start immediately
Phase 3 (Enhanced EventBus)      -- independent, start immediately
Phase 4 (Perf Dashboard Data)    -- independent, start immediately
Phase 5 (Distributed Metrics)    -- depends on Phase 4 (uses MetricsAggregator types)
Phase 6 (Web Dashboard)          -- depends on Phase 4 + Phase 5
Phase 7 (Integration)            -- depends on ALL previous phases
```

Phases 1-4 can be developed in parallel. Phase 5 requires Phase 4's types. Phase 6 requires Phase 4 and Phase 5. Phase 7 is the final integration pass.

---

## Total Estimated Effort

| Phase | Hours |
|---|---|
| 1. Config Persistence | 3-4 |
| 2. Plugin Hot-Reload | 4-5 |
| 3. Enhanced EventBus | 5-6 |
| 4. Perf Dashboard Data | 5-6 |
| 5. Distributed Metrics | 6-7 |
| 6. Web Dashboard | 6-8 |
| 7. Integration | 4-5 |
| **Total** | **33-41** |

---

## File Index (all new and modified files)

### New Files

| File | Phase |
|---|---|
| `python/ascii_stream_engine/infrastructure/config_persistence.py` | 1 |
| `python/ascii_stream_engine/tests/test_config_persistence.py` | 1 |
| `python/ascii_stream_engine/infrastructure/plugins/plugin_dependency.py` | 2 |
| `python/ascii_stream_engine/tests/test_plugin_hotreload.py` | 2 |
| `python/ascii_stream_engine/infrastructure/event_filter.py` | 3 |
| `python/ascii_stream_engine/tests/test_event_bus_enhanced.py` | 3 |
| `python/ascii_stream_engine/infrastructure/performance/budget_tracker.py` | 4 |
| `python/ascii_stream_engine/infrastructure/performance/metrics_aggregator.py` | 4 |
| `python/ascii_stream_engine/infrastructure/performance/metrics_exporter.py` | 4 |
| `python/ascii_stream_engine/tests/test_budget_tracker.py` | 4 |
| `python/ascii_stream_engine/tests/test_metrics_aggregator.py` | 4 |
| `python/ascii_stream_engine/infrastructure/distributed/__init__.py` | 5 |
| `python/ascii_stream_engine/infrastructure/distributed/protocol.py` | 5 |
| `python/ascii_stream_engine/infrastructure/distributed/metrics_reporter.py` | 5 |
| `python/ascii_stream_engine/infrastructure/distributed/metrics_collector.py` | 5 |
| `python/ascii_stream_engine/tests/test_distributed_metrics.py` | 5 |
| `python/ascii_stream_engine/infrastructure/dashboard/__init__.py` | 6 |
| `python/ascii_stream_engine/infrastructure/dashboard/server.py` | 6 |
| `python/ascii_stream_engine/infrastructure/dashboard/routes.py` | 6 |
| `python/ascii_stream_engine/infrastructure/dashboard/mjpeg_stream.py` | 6 |
| `python/ascii_stream_engine/tests/test_dashboard_server.py` | 6 |
| `python/ascii_stream_engine/tests/test_infra_integration.py` | 7 |
| `python/ascii_stream_engine/tests/test_infra_thread_safety.py` | 7 |

### Modified Files

| File | Phase | Change |
|---|---|---|
| `python/ascii_stream_engine/infrastructure/__init__.py` | 1, 7 | Add exports |
| `python/ascii_stream_engine/infrastructure/plugins/plugin_manager.py` | 2 | Batch reload, dependency ordering, perf_counter fix |
| `python/ascii_stream_engine/infrastructure/plugins/plugin_metadata.py` | 2 | Add `dependencies` field |
| `python/ascii_stream_engine/infrastructure/event_bus.py` | 3 | Priority, wildcards, replay, filters, stats |
| `python/ascii_stream_engine/infrastructure/performance/__init__.py` | 4, 7 | Add exports |
| `CHANGELOG.md` | 7 | Add `[Unreleased]` entries |
