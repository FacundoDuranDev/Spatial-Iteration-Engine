---
name: hexagonal-architecture-analysis
description: Use when analyzing, auditing, or identifying limitations in the current hexagonal architecture. Produces migration-ready component inventories, dependency maps, and architectural debt reports.
---

# Hexagonal Architecture Analysis

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.
> **PURPOSE:** This is an analysis skill, not a development skill. It produces documents, not code.

## When to Use This Skill

- Auditing the current hexagonal architecture for limitations
- Mapping components, ports, adapters, and their real dependencies
- Identifying architectural debt, layer violations, or implicit coupling
- Producing migration inventories for transitioning to another architecture
- Evaluating whether hexagonal constraints help or hurt a specific use case

## Hexagonal Architecture — Theory

### Core Concepts

Hexagonal architecture (Ports & Adapters, Alistair Cockburn 2005) separates an application into:

| Layer | Purpose | Dependency Direction |
|-------|---------|---------------------|
| **Domain** | Pure business logic and data types | Depends on nothing |
| **Ports** | Interfaces/protocols that define how the application talks to the outside | Depends on domain only |
| **Application** | Use cases, orchestration, pipelines | Depends on domain + ports |
| **Adapters** | Concrete implementations of ports (driven and driving) | Depends on ports + domain |
| **Infrastructure** | Cross-cutting concerns (logging, events, metrics) | Depends on domain only |

**The dependency rule:** Dependencies point inward. Adapters → Ports → Domain. Never outward.

### Strengths (When Hexagonal Excels)

1. **Testability** — Ports allow mocking any external dependency
2. **Swappability** — Replace any adapter without touching business logic
3. **Clear boundaries** — Obvious where new code goes
4. **Domain purity** — Business logic has zero external dependencies
5. **Onboarding** — New developers understand where things live

### Weaknesses (When Hexagonal Breaks Down)

1. **Linear pipeline assumption** — Hexagonal models request/response or command patterns well, but NOT graph-based data flow with branching, merging, or feedback
2. **No cross-adapter communication** — Adapters can't talk to each other directly. In AV processing, a filter may need to know about the renderer's grid size
3. **Rigid stage ordering** — Pipeline stages are hardcoded in application layer. Adding a new stage type (e.g., "composite" between filters and renderer) requires modifying orchestration
4. **No multi-stream support** — The architecture models ONE data flow (frame). Real AV processing has parallel streams: video, audio, control signals, analysis data
5. **Push-only execution** — No lazy/pull-based evaluation. Every stage runs even if output isn't needed
6. **Port explosion** — Each new capability needs a new port protocol, leading to interface bloat
7. **Feedback is a hack** — Temporal data (previous frame, optical flow) requires workarounds (TemporalManager) because the architecture doesn't model cyclical data flow

## Analysis Methodology

### Step 1: Component Inventory

Map every concrete component to its hexagonal role:

```
INVENTORY FORMAT:
| Component | Layer | Port | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
```

Check for:
- Adapters importing from application (violation)
- Infrastructure importing from adapters (violation)
- Domain importing anything external (violation)
- Circular dependencies between layers

### Step 2: Data Flow Mapping

Trace every data path through the system:

```
DATA FLOW FORMAT:
Source → [data type, shape] → Stage → [data type, shape] → Stage → ...

Example:
Camera → [BGR frame, (H,W,3)] → FaceAnalyzer → [analysis dict] → BoidsFilter → [BGR frame, (H,W,3)] → AsciiRenderer → [RenderFrame] → UDPSink
```

Identify:
- Where data transforms (type/shape changes)
- Where data is duplicated (unnecessary copies)
- Where data is lost (analysis results not reaching outputs that need them)
- Where data wants to flow backward (feedback) but can't

### Step 3: Constraint Tension Map

For each architectural constraint, identify where it helps vs hurts:

```
TENSION FORMAT:
| Constraint | Helps When | Hurts When | Current Pain Level (1-5) |
```

Example tensions:
- "Filters can't see renderer config" — hurts mosaic+ASCII coordination
- "Pipeline order is fixed" — hurts compositing, multi-pass effects
- "Adapters can't communicate" — hurts perception→filter parameter modulation

### Step 4: Migration Surface Analysis

Identify which components are:
- **Pure** — Perfectly hexagonal, no migration needed (domain types, simple filters)
- **Strained** — Working but fighting the architecture (TemporalManager, FilterContext)
- **Broken** — Violating hexagonal rules already (if any)
- **Missing** — Capabilities not expressible in hexagonal (feedback loops, branching)

### Step 5: Port/Adapter Coupling Report

For each port, measure:
- How many adapters implement it
- How tightly adapters depend on specific port signatures
- Whether the port interface is stable or frequently modified
- Whether adapters need capabilities not expressible through the port

## SIE-Specific Analysis Points

### Current Layer Map

```
domain/
  config.py         — EngineConfig dataclass
  types.py           — RenderFrame, enums
  events.py          — BaseEvent + event dataclasses

ports/
  sources.py         — FrameSource protocol
  renderers.py       — FrameRenderer protocol
  outputs.py         — OutputSink protocol
  processors.py      — Filter protocol
  analyzers.py       — Analyzer protocol (if exists)

application/
  engine.py          — StreamEngine orchestrator
  pipeline/          — AnalyzerPipeline, FilterPipeline, filter_context, etc.
  orchestration/     — PipelineOrchestrator (enforces stage order)
  services/          — TemporalManager, frame_buffer, error_handler

adapters/
  sources/           — Camera, Video, Network sources
  perception/        — Face, Hand, Pose analyzers
  processors/filters/ — 19 filters
  renderers/         — ASCII, Passthrough, CppDeformed, LandmarksOverlay
  outputs/           — UDP, RTSP, WebRTC, NDI, Preview, Notebook, Recorder

infrastructure/
  event_bus.py, logging.py, metrics.py, profiling.py
  performance/       — FrameSkipper, AdaptiveQuality
  plugins/           — PluginManager, hot-reload

presentation/
  notebook_api.py    — Jupyter control panels
```

### Known Architectural Tensions in SIE

1. **TemporalManager lives in application/services/** — It's infrastructure for temporal data, but placed in application because it needs to interact with the pipeline. This is a layer tension.

2. **FilterContext wraps analysis dict** — Creates a compatibility layer because filters need more than what the port protocol provides (temporal data, typed access). This is port strain.

3. **LandmarksOverlayRenderer wraps another renderer** — Decorator pattern to add perception overlay. This works but doesn't compose well with multiple overlays.

4. **Pipeline stage order hardcoded in orchestrator** — Adding a new stage type (compositing, post-render effects) requires modifying application layer code.

5. **Analysis dict is untyped** — Passed as `Optional[dict]` through the entire pipeline. No compile-time guarantees on keys or values.

## Output Format

Analysis should produce these deliverables:

1. **`component_inventory.md`** — Full inventory table with violation flags
2. **`data_flow_map.md`** — All data paths with transform points
3. **`tension_report.md`** — Constraint tensions with pain levels
4. **`migration_surface.md`** — Pure/strained/broken/missing classification
5. **`recommendations.md`** — Prioritized list of what to migrate first

## Contracts

| Contract | Rule |
|---|---|
| Output | Documents only. This skill NEVER produces code. |
| Scope | Analyze current architecture. Do not design the replacement. |
| Objectivity | Report both strengths and weaknesses honestly. |
| Evidence | Every claim must reference a specific file or code path. |
| No invention | Do not propose new architectural concepts. Report what exists and where it strains. |

## Red Flags

**Stop immediately if you catch yourself:**
- Writing implementation code (this is an analysis skill)
- Proposing a specific replacement architecture (that's the dataflow-graph skill's job)
- Ignoring hexagonal strengths (the analysis must be balanced)
- Making claims without file references
- Assuming all tensions are problems (some are acceptable trade-offs)
- Conflating "doesn't follow hexagonal perfectly" with "is broken"
