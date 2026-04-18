# Pipeline Extension Rules

How to add new components without breaking the architecture.

---

## 1. Adding a New Filter

**Location:** `python/ascii_stream_engine/adapters/processors/filters/<name>.py`

Requirements:

- Extend `BaseFilter` (from `.base import BaseFilter`)
- Set class attributes: `name` (str), `enabled` (bool = True)
- Implement `apply(self, frame, config, analysis=None) -> np.ndarray`
- Input frame: `np.ndarray` uint8 `(H, W, 3)` C-contiguous BGR
- Output frame: same shape and dtype as input
- If the filter is a no-op (disabled, bad input), return `frame` (not `frame.copy()`)
- If the filter modifies data, copy first: `out = frame.copy(order='C')`

### Temporal declarations

Filters can declare temporal needs via class attributes (default: no needs):

```python
class MyFilter(BaseFilter):
    name = "my_filter"
    required_input_history: int = 0      # previous input frames needed (0 = none)
    needs_previous_output: bool = False  # feedback loop (previous processed frame)
    needs_optical_flow: bool = False     # shared optical flow (auto-derives input_depth >= 1)
    needs_delta_frame: bool = False      # input frame diff (auto-derives input_depth >= 1)
```

Access temporal data via `FilterContext` (passed as `analysis` parameter):
```python
def apply(self, frame, config, analysis=None):
    flow = getattr(analysis, "optical_flow", None)  # shared flow or None
    delta = getattr(analysis, "delta_frame", None)   # frame diff or None
    prev_out = getattr(analysis, "previous_output", None)  # feedback or None
```

The `TemporalManager` service (in `application/services/`) allocates nothing until filters declare needs. Buffer sizes are `max()` of all active filter declarations — no global config knob.

### Stateful filters

Filters that maintain state across frames (feedback, slit scan, particles, reaction-diffusion) MUST:

- Implement `reset(self)` to clear internal state
- Handle shape changes (resolution change mid-stream) by reinitializing buffers
- Never store references to previous frames beyond the declared buffer size
- Document memory usage in the class docstring

### LUT-cached filters

Filters that precompute remap tables or lookup tables (chromatic aberration, kaleidoscope, barrel distortion) MUST:

- Cache the precomputed tables as instance attributes
- Only recompute when parameters change (use a `_params_dirty` flag)
- Never recompute LUTs every frame

### Registration

1. Add to `adapters/processors/filters/__init__.py`
2. Add to `adapters/processors/__init__.py`
3. Add to top-level `__init__.py` `__all__`
4. **Never** modify `FilterPipeline` itself (in `application/`)
5. **Never** modify any port protocol

### C++ filters

- Implement in `cpp/src/filters/<name>.cpp`
- Expose via pybind in `cpp/src/bridge/pybind_filters.cpp`
- Create Python wrapper in `adapters/processors/filters/cpp_<name>.py`
- Follow the ImportError fallback pattern exactly

---

## 2. Adding a New Analyzer

**Location:** `python/ascii_stream_engine/adapters/perception/<name>.py`
or: `python/ascii_stream_engine/adapters/processors/analyzers/<name>.py`

Requirements:

- Extend `BaseAnalyzer`
- Set: `name` (str), `enabled` (bool = True)
- Implement `analyze(self, frame, config) -> dict`
- MUST NOT modify the frame
- Return dict with documented keys (document in the class docstring and in the analysis dict schema)
- On failure, return `{}` (not `None`, not raise)

---

## 3. Adding a New Output Sink

**Location:** `python/ascii_stream_engine/adapters/outputs/<name>.py`

Requirements:

- Implement the `OutputSink` protocol (`ports/outputs.py`)
- Methods: `open()`, `write()`, `close()`, `is_open()`
- `open()` receives `EngineConfig` and `output_size` tuple
- `write()` receives `RenderFrame` (which contains `PIL.Image.Image`)
- `close()` MUST be idempotent (safe to call twice)
- MUST handle its own threading if needed

---

## 4. Adding a New Source

**Location:** `python/ascii_stream_engine/adapters/sources/<name>.py`

Requirements:

- Implement `FrameSource` protocol (`ports/sources.py`)
- Methods: `open()`, `read()`, `close()`
- `read()` returns `Optional[np.ndarray]` -- `None` means no frame available
- Returned array: uint8, `(H, W, 3)`, C-contiguous, **BGR color order**
- `close()` MUST be idempotent

---

## 5. Golden Rule: Never Touch Application Layer

When adding new adapters:

- **NEVER** modify files in `application/` (`engine.py`, `pipeline_orchestrator.py`, etc.)
- **NEVER** modify files in `ports/` (protocol definitions)
- **NEVER** modify files in `domain/` (unless adding a new domain type that does not change existing ones)
- If your feature requires application changes, it is NOT a simple extension; it requires architecture review.

---

## 6. Pipeline Stage Order Is Immutable

The order defined in `DESIGN_RULES.md` section 2:

```
Source -> Perception -> Tracking -> Transformation -> Filters -> Renderer -> Output
```

This order MUST NOT be changed. If you need a stage that does not fit this order, you are inventing a new concept; **stop and ask for architecture review**.

---

## 7. Analysis Dict Schema

Every analyzer MUST document the keys it adds to the analysis dict. Current schema:

```python
analysis = {
    "face": {
        "points": np.ndarray,       # (N, 2) normalized 0-1, face landmarks
    },
    "hands": {
        "left": np.ndarray,          # (21, 2) normalized 0-1, left hand landmarks
        "right": np.ndarray,         # (21, 2) normalized 0-1, right hand landmarks
    },
    "pose": {
        "joints": np.ndarray,        # (17, 2) or (17, 3) normalized 0-1, body keypoints
    },
    "tracking": {
        "objects": list,             # tracked object dicts with id, bbox, class
    },
    # New analyzers add their own top-level key here.
    # Key name MUST match the analyzer's `name` attribute.
}
```

New analyzers MUST:

- Use their `name` attribute as the top-level dict key
- Return numpy arrays with normalized coordinates (0.0-1.0)
- Document their dict structure in this file when adding

---

## 8. Writing Native Graph Nodes

New components can be written as **native graph nodes** instead of adapters. Native nodes work only with `use_graph=True` but offer typed ports, explicit data flow, and lifecycle hooks.

**Location:** `python/ascii_stream_engine/application/graph/nodes/` (base classes) or a custom module

### Choosing a base class

| Base Class | Use Case | Abstract Method |
|------------|----------|-----------------|
| `ProcessorNode` | Frame-modifying filter | `apply_filter(frame, config, analysis)` |
| `AnalyzerNode` | Frame analysis (no modification) | `analyze(frame) -> dict` |
| `RendererNode` | Frame → rendered output | `render(frame, config, analysis)` |
| `TransformNode` | Spatial transformation | `transform(frame) -> frame` |
| `SourceNode` | Frame production | `read_frame()` |
| `OutputNode` | Write rendered output | `write(rendered)` |
| `TrackerNode` | Object tracking | `track(frame, detections, config)` |

### Example: native ProcessorNode

```python
from ascii_stream_engine.application.graph.nodes import ProcessorNode

class MyCustomFilter(ProcessorNode):
    name = "my_custom_filter"
    needs_optical_flow = True       # temporal declarations (optional)
    required_input_history = 2

    def apply_filter(self, frame, config, analysis):
        flow = getattr(analysis, "optical_flow", None)
        # ... process frame ...
        return modified_frame
```

### Rules for native nodes

- **Set `name`** — must be unique within the graph
- **Temporal declarations** — same class attributes as BaseFilter (`required_input_history`, `needs_optical_flow`, `needs_delta_frame`, `needs_previous_output`)
- **AnalyzerNode** — MUST NOT modify the input frame (passthrough enforced)
- **Lifecycle** — override `setup()`, `teardown()`, `reset()` if needed (default: no-op)
- **Port types** — use `PortType` enum values. Custom nodes can override `get_input_ports()` / `get_output_ports()` for non-standard port configurations
- **Registration** — to use with `GraphBuilder.build()`, add to the appropriate `adapter_nodes/` factory module. For standalone graph construction, add directly to a `Graph` instance
