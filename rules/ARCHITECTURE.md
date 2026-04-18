# 1. Qué es este proyecto
# System Architecture (Authoritative)

This file defines what exists in the system.
If something is not listed here, it does not exist.
All agents must obey this architecture.

Este proyecto es un motor de procesamiento audiovisual en tiempo real que permite construir pipelines de análisis, transformación y renderizado de streams (cámaras, video, red, archivos) usando una arquitectura modular y extensible, combinando Python y C++.

# 2. Qué problema resuelve

- Orquestar flujos de video complejos en tiempo real
- Permitir filtros de alto rendimiento en C++
- Permitir análisis semántico en Python
- Emitir resultados en múltiples formatos (ASCII, NDI, RTSP, notebooks, etc.)
- Facilitar experimentación visual y perceptual

# 3. Módulos que existen

## Núcleo (canónico)
- python/ascii_stream_engine
  - domain (tipos, eventos, config)
  - application (engine, pipeline, orquestación)
    - application/graph (graph-based execution model, opt-in via `use_graph=True`)
      - graph/core (BaseNode, Graph, Connection, PortType, InputPort, OutputPort)
      - graph/nodes (ProcessorNode, AnalyzerNode, RendererNode, SourceNode, OutputNode, TrackerNode, TransformNode)
      - graph/adapter_nodes (factory-generated node wrappers for existing adapters)
      - graph/scheduler (GraphScheduler — topological execution, same API as PipelineOrchestrator)
      - graph/bridge (GraphBuilder — converts pipeline objects to Graph; adapter_registry)
  - infrastructure (event bus, logging, plugins)
  - ports (interfaces de sensores, filtros, outputs)
  - adapters (implementaciones concretas)
  - presentation (API notebooks)

## Backend de alto rendimiento
- cpp/src/filters (implementaciones reales)
- cpp/src/bridge (pybind11)

## Datos y modelos
- data/
- onnx_models/

## Ejecución
- run_preview.sh
- run_basic_stream.sh

# 4. Flujo de datos

Sensor / Source
   ↓
Pipeline
   ↓
Filters (Python o C++)
   ↓
Analyzers (perception, tracking)
   ↓
Renderers / Outputs (ASCII, RTSP, NDI, notebooks)

# 5. Qué NO existe todavía

- Un frontend visual dedicado
- Un editor gráfico de pipelines
- Persistencia de proyectos
- UI de control fuera de notebooks
- Parallel/batch execution in GraphScheduler (future phase)
- Audio/control signal port types in graph (future phase)

# 6. Núcleo del sistema

El núcleo es el motor de pipeline en python/ascii_stream_engine/application que orquesta flujos de frames entre módulos desacoplados mediante puertos, eventos y adaptadores.

## 7. Graph Execution Model (`application/graph/`)

Opt-in alternative execution model: `StreamEngine(use_graph=True)`. The default `PipelineOrchestrator` remains unchanged.

### Core (`graph/core/`)
- **PortType** enum: `VIDEO_FRAME`, `ANALYSIS_DATA`, `RENDER_FRAME`, `TRACKING_DATA`, `CONTROL_SIGNAL`, `MASK`, `CONFIG`
- **InputPort / OutputPort**: frozen dataclasses with type-safe `accepts()` validation
- **BaseNode** ABC: abstract `process(inputs) -> outputs`, with temporal declarations (`needs_optical_flow`, `required_input_history`, etc.) and lifecycle hooks (`setup`, `teardown`, `reset`)
- **Connection**: frozen dataclass linking source_node.output_port → target_node.input_port with type validation
- **Graph**: DAG container with `add_node()`, `connect()`, `validate()`, `get_execution_order()` (Kahn's algorithm), DFS cycle detection

### Node Types (`graph/nodes/`)
| Class | Inputs | Outputs |
|-------|--------|---------|
| SourceNode | (none) | video_out |
| AnalyzerNode | video_in | video_out (passthrough), analysis_out |
| TrackerNode | video_in, analysis_in | video_out (passthrough), tracking_out |
| TransformNode | video_in | video_out |
| ProcessorNode | video_in, analysis_in (opt) | video_out |
| RendererNode | video_in, analysis_in (opt) | render_out |
| OutputNode | render_in | (none) |

### Adapter Nodes (`graph/adapter_nodes/`)
Factory-generated `ProcessorNode`/`AnalyzerNode`/etc. subclasses that wrap existing adapters. Each copies temporal declarations from the adapter class and delegates `process()` to the adapter's native method (`apply`, `analyze`, etc.).

### Scheduler (`graph/scheduler/`)
**GraphScheduler** executes nodes in topological order. Same `process_frame(frame, timestamp) -> (bool, error_msg)` API as `PipelineOrchestrator`. Features:
- FilterContext injection for ProcessorNodes (temporal access)
- TemporalManager integration (configured from node declarations)
- Error isolation: processor/analyzer failures are non-fatal (passthrough), renderer/output failures are fatal
- Disabled node passthrough by matching port types

### Bridge (`graph/bridge/`)
- **GraphBuilder.build()**: converts StreamEngine's pipeline objects (FilterPipeline, AnalyzerPipeline, etc.) into a Graph
- **AnalysisMergeNode**: merges parallel analyzer outputs into a single analysis dict
- **AdapterRegistry**: maps adapter class names to node classes with MRO-based lookup

## 8. Temporal Infrastructure

### TemporalManager (`application/services/temporal_manager.py`)
Demand-driven temporal state service. Allocates nothing until filters declare needs via class attributes. Buffer sizes derived from `max()` of all active filter declarations.

Three temporal patterns:
- **Input ring buffer**: Previous input frames (for optical flow, delta frame). Depth = max(required_input_history) + 1 across active filters.
- **Output buffer**: Single previous processed frame (for feedback/accumulation effects).
- **Own state**: Filters like Physarum maintain their own internal state (trail_map) — not managed by TemporalManager.

Lazy computation: optical flow and delta frame computed on first access per frame, cached.

### FilterContext (`application/pipeline/filter_context.py`)
Dict-compatible wrapper providing lazy access to temporal + analysis data. Backwards compatible with existing `analysis.get("key")` patterns. Adds temporal properties: `previous_input`, `previous_output`, `optical_flow`, `delta_frame`.

### Temporal Declarations (`adapters/processors/filters/base.py`)
Class attributes on BaseFilter:
- `required_input_history: int = 0` — how many previous input frames needed
- `needs_previous_output: bool = False` — needs feedback loop
- `needs_optical_flow: bool = False` — needs shared optical flow
- `needs_delta_frame: bool = False` — needs input frame diff
