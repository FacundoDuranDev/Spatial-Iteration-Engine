---
name: dataflow-graph-architecture
description: Use when designing, proposing, or evaluating dataflow graph architectures for real-time audiovisual processing. Produces node/port schemas, graph execution models, and migration proposals from other architectures.
---

# Dataflow Graph Architecture

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.
> **PURPOSE:** This skill designs dataflow graph architectures for real-time AV systems. It consumes analysis from the hexagonal-architecture-analysis skill and produces migration proposals.

## When to Use This Skill

- Designing a node/graph execution model for real-time media processing
- Proposing migration from linear pipeline or hexagonal to dataflow graph
- Defining node port types, connection rules, and execution semantics
- Evaluating dataflow patterns from TouchDesigner, Max/MSP, Notch, Resolume, VVVV
- Designing feedback loops, branching, merging, and multi-stream processing

## Dataflow Graph — Theory

### Core Concepts

A dataflow graph is a directed graph where:
- **Nodes** are processing units with typed input/output ports
- **Edges** are connections between compatible ports
- **Execution** is driven by data availability (data-driven) or demand (pull-based)
- **Streams** flow through edges: video frames, audio buffers, control signals, analysis data

```
[Camera] ──video──→ [FaceDetect] ──analysis──→ [Mosaic] ──video──→ [Composite] ──video──→ [Output]
                         │                                    ↑
                         └──video──→ [ASCII Render] ──video───┘
```

### The Five Properties of Dataflow Systems

**1. Typed Ports**
Every node has named, typed input and output ports. Types determine what connections are valid.

```
Port Types for AV processing:
- VideoFrame: (H, W, C) uint8 BGR array — the primary visual stream
- AudioBuffer: (samples,) float32 array — audio signal
- AnalysisData: dict with typed keys — perception results
- ControlSignal: float 0-1 — normalized parameter value
- Mask: (H, W) uint8/bool — segmentation or region mask
- Trigger: bool — discrete event (beat detected, gesture recognized)
```

**2. Connection Rules**
- Only compatible types can connect (VideoFrame→VideoFrame, not VideoFrame→AudioBuffer)
- Fan-out: one output port can connect to multiple input ports (broadcast)
- Fan-in: multiple output ports can connect to one input port (requires merge strategy: blend, switch, layer)
- Feedback: output can connect to an upstream input (requires 1-frame delay buffer)

**3. Execution Model**
Two primary models:

| Model | How it Works | Pros | Cons | Used By |
|-------|-------------|------|------|---------|
| **Pull-based** | Output requests data → traverses graph backward → only evaluates needed nodes | Lazy, efficient | Complex scheduling, latency for deep graphs | TouchDesigner |
| **Push-based** | Source produces data → pushes forward through graph → all connected nodes execute | Simple, predictable | Wastes work on unused branches | Max/MSP, most game engines |
| **Hybrid** | Push from sources, but skip branches with no active outputs | Balanced | More complex scheduler | Recommended for SIE |

**4. Feedback & Temporal Access**
Feedback loops are first-class:
- A **Delay node** breaks cycles by buffering N frames
- Any node can declare temporal needs: "I need frame N-1, N-2, ..."
- The graph scheduler detects cycles and inserts implicit delays

**5. Parallel Execution**
Independent branches execute in parallel:
```
[Camera] ──→ [FaceDetect]  }  These run in parallel
         ──→ [HandDetect]  }  (no data dependency between them)
         ──→ [PoseDetect]  }
```
The scheduler builds a dependency DAG and parallelizes independent nodes.

### Reference Architectures

#### TouchDesigner Operator Model

| Family | Data Type | Color | SIE Mapping |
|--------|-----------|-------|-------------|
| **TOP** | 2D textures/images | Purple | VideoFrame, Mask |
| **CHOP** | Numeric channels (signals) | Green | ControlSignal, AudioBuffer |
| **SOP** | 3D geometry | Blue | (future: point clouds) |
| **DAT** | Tables, text, scripts | Purple | AnalysisData, Config |
| **MAT** | Shaders/materials | Yellow | (future: GPU effects) |
| **COMP** | Containers, UI | Gray | Presentation nodes |

Key insight: Each family has its own execution context. TOPs run on GPU, CHOPs on CPU. Cross-family connections require explicit converter nodes.

#### Max/MSP Patching Model

- Pure message-passing: every connection carries typed messages
- Right-to-left, bottom-to-top execution order (deterministic)
- "Hot" vs "cold" inlets: hot inlets trigger computation, cold inlets just store values
- Subpatchers: encapsulate sub-graphs as reusable components

#### Notch Real-Time Engine

- Node graph with real-time rendering focus
- Nodes have "exposed parameters" that appear in parent UI
- Built-in performance profiling per node
- Automatic GPU/CPU scheduling based on node type

## Node Design for SIE

### Node Interface

```python
class Node(Protocol):
    """Base node in the dataflow graph."""
    name: str
    node_type: str  # "source", "processor", "analyzer", "renderer", "output", "control"

    def get_input_ports(self) -> List[InputPort]: ...
    def get_output_ports(self) -> List[OutputPort]: ...
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]: ...
    def setup(self) -> None: ...      # Called once on graph build
    def teardown(self) -> None: ...   # Called on graph destroy
```

### Port Interface

```python
@dataclass
class Port:
    name: str
    data_type: PortType          # VideoFrame, AudioBuffer, ControlSignal, etc.
    required: bool = True        # Optional ports don't block execution
    description: str = ""

class InputPort(Port):
    default_value: Any = None    # Used when port is unconnected and not required
    merge_strategy: str = "first"  # "first", "blend", "switch", "layer" for fan-in

class OutputPort(Port):
    pass
```

### Port Types

```python
class PortType(Enum):
    VIDEO_FRAME = "video_frame"        # np.ndarray (H, W, 3) uint8 BGR
    AUDIO_BUFFER = "audio_buffer"      # np.ndarray (samples,) float32
    ANALYSIS_DATA = "analysis_data"    # dict with typed keys
    CONTROL_SIGNAL = "control_signal"  # float 0.0-1.0
    MASK = "mask"                      # np.ndarray (H, W) uint8
    TRIGGER = "trigger"                # bool
    TEXT = "text"                      # str (ASCII lines, metadata)
    RENDER_FRAME = "render_frame"      # RenderFrame (PIL Image + text + metadata)
    CONFIG = "config"                  # dict or EngineConfig
```

### Connection Compatibility Matrix

```
                  → VIDEO  AUDIO  ANALYSIS  CONTROL  MASK  TRIGGER  TEXT  RENDER  CONFIG
VIDEO_FRAME       →   Y      -       -        -       -      -       -      -       -
AUDIO_BUFFER      →   -      Y       -        -       -      -       -      -       -
ANALYSIS_DATA     →   -      -       Y        -       -      -       -      -       -
CONTROL_SIGNAL    →   -      -       -        Y       -      -       -      -       -
MASK              →   -      -       -        -       Y      -       -      -       -
TRIGGER           →   -      -       -        Y       -      Y       -      -       -
TEXT              →   -      -       -        -       -      -       Y      -       -
RENDER_FRAME      →   -      -       -        -       -      -       -      Y       -
CONFIG            →   -      -       -        -       -      -       -      -       Y
```

Note: Converter nodes can bridge types (e.g., VideoFrame→Mask via thresholding, ControlSignal→Config via parameter mapping).

### Node Categories

#### Source Nodes (0 video inputs, 1+ outputs)
- **CameraSource**: outputs VideoFrame
- **VideoFileSource**: outputs VideoFrame
- **AudioSource**: outputs AudioBuffer
- **OSCReceiver**: outputs ControlSignal per channel
- **MIDIReceiver**: outputs ControlSignal per CC

#### Analyzer Nodes (1 video input, 1 video passthrough + analysis outputs)
- **FaceAnalyzer**: in=VideoFrame, out=VideoFrame + AnalysisData + Mask
- **HandAnalyzer**: in=VideoFrame, out=VideoFrame + AnalysisData
- **PoseAnalyzer**: in=VideoFrame, out=VideoFrame + AnalysisData
- **AudioAnalyzer**: in=AudioBuffer, out=AnalysisData (bass/mid/high energy)

Key: Analyzers pass through their video input unchanged. They add analysis as a separate output port.

#### Processor Nodes (1+ inputs, 1+ outputs)
- **MosaicFilter**: in=VideoFrame + optional ControlSignal(block_size), out=VideoFrame
- **ASCIIRender**: in=VideoFrame + optional ControlSignal(grid_size), out=RenderFrame
- **Composite**: in=VideoFrame[] (multiple), out=VideoFrame (blended/layered)
- **Feedback**: in=VideoFrame, out=VideoFrame (delayed by N frames)
- **Delay**: in=Any, out=Same type (buffered N frames)

#### Output Nodes (1+ inputs, 0 outputs)
- **PreviewSink**: in=RenderFrame
- **UDPSink**: in=RenderFrame
- **RecorderSink**: in=RenderFrame
- **OSCSender**: in=AnalysisData

#### Control Nodes (signal processing)
- **LFO**: out=ControlSignal (sine, saw, square, noise)
- **Envelope**: in=Trigger, out=ControlSignal (attack/decay/sustain/release)
- **Map**: in=ControlSignal, out=ControlSignal (range mapping, curves)
- **Smooth**: in=ControlSignal, out=ControlSignal (low-pass filter, lag)

## Graph Execution Engine

### Scheduler Design

```
1. TOPOLOGY SORT
   - Build adjacency list from connections
   - Detect cycles → insert implicit Delay nodes to break them
   - Topological sort for execution order

2. DEPENDENCY ANALYSIS
   - Group independent nodes into parallel batches
   - Batch N: all nodes whose inputs are satisfied by batches 0..N-1

3. FRAME LOOP
   for each frame:
     a. Source nodes produce data
     b. For each batch (in order):
        - Execute all nodes in batch (parallel if independent)
        - Pass outputs to connected inputs
     c. Output nodes consume data
     d. Feedback/Delay nodes store current output for next frame

4. LAZY EVALUATION (optional)
   - Mark branches with no active output as "dormant"
   - Skip dormant branches entirely
   - Reactivate when output is connected or enabled
```

### Memory Management

```
BUFFER REUSE STRATEGY:
- Maintain a frame pool: pre-allocated (H, W, 3) uint8 arrays
- Nodes request frames from pool, return when done
- Pool grows on demand, shrinks on idle (high/low watermark)
- Read-only outputs: multiple downstream nodes can share same buffer (zero-copy fan-out)
- Writable outputs: node must request a private copy from pool

TEMPORAL BUFFERS:
- Ring buffer per node that declares temporal needs
- Size = max(declared_history) across all downstream consumers
- Managed by scheduler, not by individual nodes
```

### Thread Model

```
THREAD ALLOCATION:
- Main thread: graph scheduling, source capture
- Worker pool: node execution (sized to CPU cores - 1)
- GPU thread: nodes marked as GPU-accelerated
- I/O threads: output sinks (network, disk)

SYNCHRONIZATION:
- Frame barrier: all nodes in a batch must complete before next batch starts
- Per-edge buffers: thread-safe SPSC (single producer, single consumer) queues
- Feedback edges: double-buffered (write current, read previous)
```

## Migration from Hexagonal to Dataflow

### Mapping Strategy

| Hexagonal Component | Dataflow Equivalent | Migration Complexity |
|---------------------|---------------------|---------------------|
| FrameSource adapter | Source Node | Low — wrap existing adapter |
| Analyzer adapter | Analyzer Node (passthrough + analysis output) | Low — add output ports |
| Filter adapter | Processor Node | Low — wrap existing filter |
| FrameRenderer adapter | Processor Node (VideoFrame → RenderFrame) | Medium — new port type |
| OutputSink adapter | Output Node | Low — wrap existing sink |
| FilterPipeline | Graph connections (sequential chain) | Medium — replace with graph edges |
| PipelineOrchestrator | Graph Scheduler | High — replace execution model |
| TemporalManager | Feedback/Delay nodes + scheduler-managed buffers | Medium — native support |
| FilterContext | Input ports on processor nodes | Low — ports replace context |
| EventBus | Side-channel events (kept as-is) | None — orthogonal concern |
| EngineConfig | Config nodes or global config input port | Low |
| PluginManager | Node discovery/registration | Medium — scan for Node subclasses |

### Migration Phases

**Phase 0 — Compatibility Layer (no breaking changes)**
- Define Node, Port, Connection interfaces
- Create NodeAdapter that wraps existing Filter/Analyzer/Renderer adapters as Nodes
- Build GraphBuilder that constructs the current linear pipeline as a graph
- GraphScheduler executes the graph identically to current PipelineOrchestrator
- **Result:** Same behavior, but execution is graph-based internally

**Phase 1 — Enable Branching & Composition**
- Allow multiple renderer nodes in parallel (mosaic + ASCII)
- Add Composite node for merging multiple video streams
- Add fan-out from analyzer nodes (analysis data to multiple consumers)
- **Result:** Mosaic+ASCII composition works natively

**Phase 2 — Enable Feedback & Temporal**
- Add Feedback and Delay nodes
- Scheduler detects cycles and manages temporal buffers
- Remove TemporalManager (replaced by native graph feedback)
- **Result:** Trails, echo, reaction-diffusion work without hacks

**Phase 3 — Control Signal Layer**
- Add ControlSignal port type
- Add LFO, Envelope, Map, Smooth control nodes
- Add AudioSource → AudioAnalyzer → ControlSignal path
- Add OSC/MIDI → ControlSignal path
- Processor nodes accept ControlSignal inputs for parameter modulation
- **Result:** Audio-reactive, MIDI-controlled, LFO-modulated effects

**Phase 4 — Lazy Evaluation & Optimization**
- Implement pull-based evaluation for dormant branches
- Add frame pool for buffer reuse
- Parallel batch execution
- GPU node scheduling
- **Result:** Performance parity or better than current linear pipeline

### What to Keep from Hexagonal

Not everything migrates. Some hexagonal patterns remain valuable:

1. **Domain layer** — Pure data types (EngineConfig, RenderFrame, events) stay as-is
2. **Dependency direction** — Nodes still don't depend on the scheduler/graph engine
3. **Infrastructure** — EventBus, logging, metrics, profiling remain cross-cutting
4. **Testing** — Port-based mocking still works (mock node inputs/outputs)
5. **Plugin system** — Nodes are the new plugins, but discovery mechanism stays

### What to Remove from Hexagonal

1. **Ports layer** — Replaced by port types on nodes. No more separate protocol files.
2. **PipelineOrchestrator** — Replaced by graph scheduler
3. **FilterPipeline** — Replaced by graph connections
4. **TemporalManager** — Replaced by native feedback/delay nodes
5. **FilterContext** — Replaced by typed input ports on nodes
6. **Fixed pipeline stage order** — Replaced by topological sort of graph

## Output Format

Proposals should produce these deliverables:

1. **`node_catalog.md`** — All proposed nodes with port definitions
2. **`graph_examples.md`** — Example graphs for key use cases (mosaic+ASCII, audio-reactive, feedback trails)
3. **`execution_model.md`** — Scheduler design, threading, memory management
4. **`migration_plan.md`** — Phased migration with compatibility guarantees
5. **`port_type_spec.md`** — Complete port type system with compatibility rules
6. **`risk_assessment.md`** — What could go wrong, rollback strategy

## Contracts

| Contract | Rule |
|---|---|
| Output | Design documents and interface specs. Implementation code only for prototypes. |
| Compatibility | Phase 0 must reproduce current behavior exactly. No regressions. |
| Incremental | Each phase must be independently shippable and testable. |
| Performance | Graph overhead must not exceed 1ms per frame vs current pipeline. |
| Existing adapters | All 19 filters, 4 renderers, all outputs must work without modification in Phase 0. |
| No framework dependency | The graph engine must be pure Python (+ optional C++ acceleration). No external graph framework. |

## Design Checklist

When proposing a dataflow graph design, verify:

- [ ] Every existing adapter can be wrapped as a node without code changes
- [ ] The current linear pipeline is expressible as a graph
- [ ] Feedback loops are handled (cycle detection, delay insertion)
- [ ] Fan-out works (one source, multiple consumers)
- [ ] Fan-in works (multiple sources, one consumer with merge strategy)
- [ ] Control signals can modulate processor parameters
- [ ] Graph can be modified at runtime (add/remove nodes and connections)
- [ ] Performance overhead is bounded (graph scheduling < 1ms)
- [ ] Thread safety is documented for all shared state
- [ ] Error in one node doesn't crash the entire graph
- [ ] Dormant branches are skippable (lazy evaluation)
- [ ] Memory is bounded (no unbounded buffer growth)

## Red Flags

**Stop immediately if you catch yourself:**
- Proposing a graph framework dependency (NetworkX, etc.) for the runtime engine
- Designing nodes that depend on specific other nodes (nodes must be independent)
- Ignoring the migration path (jumping straight to Phase 4 without Phase 0)
- Making the graph engine aware of specific node types (it should be generic)
- Designing port types that require frame copies for fan-out (use read-only sharing)
- Forgetting cycle detection (infinite loops will hang the engine)
- Proposing changes that break all existing tests at once
- Over-designing the type system (keep it simple: ~8 port types max)

## Common Mistakes

| Mistake | Fix |
|---|---|
| Nodes store references to other nodes | Nodes only see their input/output data, never other nodes |
| Graph modification during execution | Queue modifications, apply between frames |
| Unbounded feedback buffers | Ring buffers with fixed max depth |
| Fan-out copies frames | Share read-only views, copy only when node needs to modify |
| Control signals sampled once | Control signals update every frame, interpolated if needed |
| GPU and CPU nodes in same batch | Separate scheduling for GPU vs CPU nodes |
| No error isolation | Catch exceptions per-node, skip node, pass through input |
| Graph rebuild every frame | Build once, cache topology sort, rebuild only on connection change |
