# Graph Architecture

**One-sentence rule**: every `StreamEngine` call builds a DAG from the filter / analyzer / tracker / transformation pipelines and runs it through the `GraphScheduler` once per frame — there is no alternative execution path.

This doc is the canonical reference for how the graph is shaped, executed, and extended. It does not duplicate `ARCHITECTURE.md` (what exists), `PIPELINE_EXTENSION_RULES.md` (how to add a new filter), or `PERFORMANCE_RULES.md` (copy / GIL / allocation budgets). Start with those for context.

---

## 1. Mental model

A frame flows through a **directed acyclic graph of nodes**. Each node:

- declares its inputs and outputs as **typed ports** (`VIDEO_FRAME`, `ANALYSIS_DATA`, `RENDER_FRAME`, …).
- is wired to upstream nodes via **connections**.
- implements `process(inputs: dict) -> outputs: dict`.

On every frame:

1. The scheduler asks `graph.get_execution_order()` for a topological sort (Kahn's algorithm, O(V+E)).
2. It walks nodes in that order, resolving each node's inputs from upstream outputs or from the externally-injected frame.
3. It calls `node.process(inputs)` and stores the outputs so downstream nodes can read them.
4. Errors in analyzer / filter / tracker / transform nodes are **non-fatal** — logged, replaced with a passthrough, processing continues. Errors in renderer or output nodes are **fatal** — the frame is dropped and the scheduler returns `(False, err)`.

The graph is rebuilt whenever the underlying `FilterPipeline` / `AnalyzerPipeline` / … are mutated (add/remove/reorder) — tracked via a per-pipeline `version` counter.

File map:

```
application/graph/
├── core/                # BaseNode, Graph, Connection, port_types
├── nodes/               # concrete node types (Source, Analyzer, Processor…)
├── adapter_nodes/       # factory-generated wrappers for existing adapters
├── bridge/              # GraphBuilder + AdapterRegistry
└── scheduler/           # GraphScheduler + NodeContext
```

---

## 2. Node lifecycle

Every node inherits from `core.base_node.BaseNode` and goes through this lifecycle:

```
__init__()            # self._config is None; wiring only, no heavy state
setup()               # called once before the first frame (optional)
  ↓
per-frame loop:
  config = self._config            # scheduler injects before each tick
  inputs = resolve_from_upstream()
  outputs = node.process(inputs)   # your code
  ↓
teardown()            # called once when the scheduler shuts down (optional)
reset()               # called on pipeline mutation — clear any accumulated state
```

Key attributes a node can declare at class level:

| Attribute | Default | Meaning |
|---|---|---|
| `name: str` | `"unnamed"` | Identifies the node in logs, profiler, metrics |
| `enabled: bool` | `True` | If `False`, scheduler skips and passes the input through |
| `required_input_history: int` | `0` | How many previous input frames to keep in the ring buffer (see §7) |
| `needs_previous_output: bool` | `False` | Needs the last frame's output (feedback loops) |
| `needs_optical_flow: bool` | `False` | Needs the shared optical flow field |
| `needs_delta_frame: bool` | `False` | Needs the input-frame diff |

---

## 3. Node types

Built-in, canonical node types in `application/graph/nodes/`:

| Node | Inputs | Outputs | Role |
|---|---|---|---|
| `SourceNode` | — | `video_out` | Entry point. Emits the captured frame. |
| `AnalyzerNode` | `video_in` | `video_out` (passthrough) + `analysis_out` | Reads the frame, returns an analysis dict, does not modify the frame. |
| `TrackerNode` | `video_in`, `analysis_in` | `video_out` (passthrough) + `tracking_out` | Runs after analyzers, consumes their output. |
| `TransformNode` | `video_in` | `video_out` | Warp / resize / projection — returns a new frame. |
| `ProcessorNode` | `video_in`, `analysis_in` (optional) | `video_out` | A filter. Wraps any `BaseFilter` adapter via `adapter_nodes/filter_nodes.py`. |
| `RendererNode` | `video_in`, `analysis_in` (optional) | `render_out` | Converts the processed frame into a `RenderFrame`. |
| `OutputNode` | `render_in` | — | Terminal. Writes to the sink. |

Composite / special nodes:

| Node | Purpose |
|---|---|
| `CompositeNode` | Fan-in — takes N `video_in` ports and blends/selects one output. |
| `SpatialMapNode` / `SpatialSmoothingNode` | Consume perception analysis, emit a derived spatial signal. |
| `AsciiProcessorNode` / `MosaicFilterNode` | Specialised filter nodes that don't fit the generic `ProcessorNode` contract. |
| `RenderFrameCompositeNode` | Merge multiple `RenderFrame`s into one. |

Adapter-generated nodes live in `application/graph/adapter_nodes/`. They are factory-built subclasses of the node types above, one per adapter class in the project. You rarely write these by hand — `GraphBuilder` and `_make_filter_node(...)` produce them for you.

---

## 4. Building a graph

Two paths. Pick based on what you're doing.

### 4a. Automatic — "I just want my filters to run" (99% of cases)

Don't build a graph. Let `StreamEngine` do it. Mutate the pipeline wrappers and the scheduler rebuilds automatically (§6):

```python
from ascii_stream_engine import StreamEngine, FilterPipeline, AnalyzerPipeline
from ascii_stream_engine.adapters.processors.filters import BloomFilter, BrightnessFilter
from ascii_stream_engine.adapters.perception import HandLandmarkAnalyzer

engine = StreamEngine(
    source=camera,
    renderer=renderer,
    sink=sink,
    analyzers=AnalyzerPipeline([HandLandmarkAnalyzer()]),
    filters=FilterPipeline([BrightnessFilter(), BloomFilter()]),
)
engine.start()

# Later, at runtime, from any thread:
engine.filter_pipeline.add(some_other_filter)   # scheduler rebuilds graph on next frame
```

The graph it builds is strictly linear in the canonical stage order:
`source → analyzers (parallel) → tracker → transform → processors (serial) → renderer → output`.

### 4b. Manual — "I need fan-out, composite, branching, or a custom node"

Start from `engine.build_graph()` (which gives you the same DAG as 4a, pre-populated) and extend it:

```python
g = engine.build_graph()

# fan-out: feed the same frame to two renderers
g.fan_out(source_node, [renderer_a, renderer_b])

# composite: mix two processed streams into one
g.add_composite(
    inputs=[branch_a_output, branch_b_output],
    mixer=lambda a, b: 0.5 * a + 0.5 * b,
    name="half_blend",
)

# Custom node
class MyNode(BaseNode):
    name = "my_node"
    def get_input_ports(self):  return [InputPort("video_in", PortType.VIDEO_FRAME)]
    def get_output_ports(self): return [OutputPort("video_out", PortType.VIDEO_FRAME)]
    def process(self, inputs):
        return {"video_out": do_something(inputs["video_in"])}

g.add_node(MyNode())
g.connect(upstream, "video_out", "my_node", "video_in")

errors = g.validate()
assert not errors, errors

# Feed it into a GraphScheduler by hand:
scheduler = GraphScheduler(g, engine._config, temporal_manager=engine._temporal)
engine._orchestrator = scheduler   # or keep running side-by-side for A/B
```

### 4c. From scratch (tests, experiments)

Skip `StreamEngine` entirely:

```python
from ascii_stream_engine.application.graph.bridge.graph_builder import GraphBuilder
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler

g = GraphBuilder.build(
    renderer=my_renderer,
    sink=my_sink,
    analyzers=[MyAnalyzer()],
    filters=FilterPipeline([BrightnessFilter()]),
)
assert g.validate() == []

scheduler = GraphScheduler(g, EngineConfig())
ok, err = scheduler.process_frame(my_frame, timestamp=1.0)
```

This is the pattern every integration test uses.

---

## 5. Runtime mutation

The `*Pipeline` wrappers (`FilterPipeline`, `AnalyzerPipeline`, `TrackingPipeline`, `TransformationPipeline`) each expose a monotonic `version` property that ticks on any structural mutation (`add`, `remove`, `extend`, `insert`, `pop`, `clear`, `replace`).

Inside `StreamEngine._run()`, before each frame tick:

1. Compute `combined = sum(p.version for p in all_pipelines)`.
2. If `combined != self._pipeline_version_snapshot`:
   - Call `self._create_orchestrator()` which rebuilds the graph via `GraphBuilder.build(...)` and wraps it in a new `GraphScheduler`.
   - Update the snapshot.

Consequences:

- It's safe to call `engine.filter_pipeline.add(f)` from any thread, including a Gradio callback. The new filter takes effect on the next frame, not mid-frame.
- Toggling `filter.enabled = False` does **not** bump the version — the same node stays in the graph but becomes a passthrough. This is cheaper than rebuilding.
- Replacing a filter in place (`pipeline.replace([...])`) does bump the version → full rebuild. Use when filter identity changes, not for parameter tweaks.

---

## 6. Error semantics

Two buckets, enforced in the scheduler's per-node try/except:

| Node kind | Behavior on exception |
|---|---|
| `AnalyzerNode`, `TrackerNode`, `TransformNode`, `ProcessorNode`, `CompositeNode`, composite-family | **Non-fatal**: log at `WARNING`, record the error under the node's phase category in `EngineMetrics`, install a passthrough for downstream consumers (video_in→video_out or equivalent), continue with next node. |
| `RendererNode`, `OutputNode` | **Fatal**: log, record error, end profiler frame, return `(False, "Fatal error in <node>: <e>")`. The engine's main loop drops this frame. |

Metric error categories (match `_NODE_PHASE_MAP` in `graph_scheduler.py`):

```
capture · analysis · transformation · filtering · rendering · writing
```

Read with `engine.metrics.get_errors()` — returns a `Dict[str, int]`.

No retry/timeout is applied at the node level. If a node is flaky, fix the node or wrap it yourself; the scheduler does not paper over it.

---

## 7. Temporal & profiling

### Temporal (`application/services/temporal_manager.py`)

`TemporalManager` allocates nothing by default. Nodes / filters declare their needs via class attributes:

```python
class MyFilter(BaseFilter):
    required_input_history = 3     # need last 3 frames
    needs_optical_flow = True      # need Farneback flow
```

`GraphBuilder` and `GraphScheduler` scan those attributes, then configure the manager with `max()` of every active need. The first `ProcessorNode` per frame pushes the input into the ring buffer; every subsequent node reads through `FilterContext` (`application/pipeline/filter_context.py`), which exposes `previous_input`, `previous_output`, `optical_flow`, `delta_frame` lazily (computed on first access, cached for the rest of the frame).

### Profiling (`application/services/loop_profiler.py`)

`LoopProfiler` is off by default. Enable with `StreamEngine(enable_profiling=True)`. Each node's phase transitions are tracked by `_phase_for_node()` in the scheduler, producing per-phase timings available via `engine._profiler.get_stats()`.

For per-node millisecond timings independent of phases: `engine.get_node_timings()` → `Dict[node_name, seconds]`.

---

## 8. Recipes

### 8a. Standard pipeline with 30 filters

Nothing to build. Populate the `FilterPipeline` at engine creation, done.

### 8b. Fan-out — same frame to two renderers

```python
g = engine.build_graph()
g.fan_out(
    source=g.get_node("source"),
    targets=[renderer_ascii_node, renderer_passthrough_node],
)
```

### 8c. A/B composite — split, process two branches, blend

```python
g = engine.build_graph()
branch_a = g.add_processor_chain([BrightnessFilter()])
branch_b = g.add_processor_chain([BloomFilter()])
g.fan_out(source_node, [branch_a.head, branch_b.head])
g.add_composite(
    inputs=[(branch_a.tail, "video_out"), (branch_b.tail, "video_out")],
    mixer="average",
    name="ab_blend",
).connect_to(renderer_node, "video_in")
```

### 8d. Per-ROI pipeline (spatial)

Use `SpatialMapNode` to emit an ROI mask from perception analysis, then wire it into a `CompositeNode` that gates which region gets the heavy filter. See `tests/test_spatial_map_node.py` for a worked example.

### 8e. Inspect the built graph for debugging

```python
g = engine.build_graph()
for node in g.get_execution_order():
    ports_in  = [p.name for p in node.get_input_ports()]
    ports_out = [p.name for p in node.get_output_ports()]
    print(f"{node.name:<30} in={ports_in} out={ports_out}")
```

---

## 9. Relationship to the `*Pipeline` wrappers

The four wrappers — `FilterPipeline`, `AnalyzerPipeline`, `TrackingPipeline`, `TransformationPipeline` — are the **public "bag of items" API** that the dashboard (`run_dashboard.py`), notebooks, and tests use to add/remove/reorder components at runtime.

They are **not** execution engines. They are containers with a `version` counter. `GraphBuilder.build()` reads them and produces the actual DAG.

Do not deprecate them, and do not add execution logic to them. If you need something more expressive than a flat list (fan-out, composite, branching), build a graph directly via §4b.

---

## 10. Non-goals

Explicitly off the table for the graph:

- **Retry / timeout at the node level.** Use application-level retry (e.g. `RetryManager` for the capture loop) or fix the node. The legacy `StageExecutor` advertised this feature but never actually used it.
- **Cross-frame scheduling / backpressure.** One frame in, one frame out. If a node is too slow, the engine main loop drops frames — see `LATENCY_BUDGET.md`.
- **Dynamic reconfiguration of the port graph mid-frame.** Graph mutation is atomic between frames only.
- **Async nodes.** Everything is synchronous in the scheduler thread. Analyzers that want parallelism get it from the scheduler's thread pool for parallel `AnalyzerNode`s only.

---

## 11. Where to look next

- Node source: `python/ascii_stream_engine/application/graph/nodes/`
- Scheduler source: `python/ascii_stream_engine/application/graph/scheduler/graph_scheduler.py`
- Builder source: `python/ascii_stream_engine/application/graph/bridge/graph_builder.py`
- Worked examples: `python/ascii_stream_engine/examples/test_ascii_graph.py`, `tests/test_graph_branching.py`, `tests/test_graph_integration.py`
- Related rules: `ARCHITECTURE.md`, `PIPELINE_EXTENSION_RULES.md`, `PERFORMANCE_RULES.md`, `CPP_VS_PYTHON_RULES.md` (pending), `LATENCY_BUDGET.md`
