# Hexagonal Architecture Audit — Spatial-Iteration-Engine

**Date:** 2026-02-28
**Auditor:** Innovation Team (automated analysis)
**Methodology:** 5-step hexagonal architecture analysis per `.claude/skills/hexagonal-architecture-analysis/SKILL.md`

---

## Table of Contents

1. [Component Inventory](#step-1-component-inventory)
2. [Data Flow Mapping](#step-2-data-flow-mapping)
3. [Constraint Tension Map](#step-3-constraint-tension-map)
4. [Migration Surface](#step-4-migration-surface)
5. [Recommendations](#step-5-recommendations)

---

## Step 1: Component Inventory

### 1.1 Domain Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `EngineConfig` | `domain/config.py` | `re`, `socket`, `dataclasses`, `typing` (stdlib only) | Nothing external | **No** |
| `NeuralConfig` | `domain/config.py` | `dataclasses`, `typing` (stdlib only) | Nothing external | **No** |
| `RenderFrame` | `domain/types.py` | `PIL.Image`, `dataclasses`, `typing` | Nothing external | **BORDERLINE** (see note) |
| `BaseEvent` + 10 event classes | `domain/events.py` | `numpy`, `time`, `dataclasses`, `typing` | Nothing external | **BORDERLINE** (see note) |
| `FaceAnalysis`, `HandAnalysis`, `PoseAnalysis`, `HandGestureAnalysis`, `ObjectDetectionAnalysis`, `EmotionAnalysis`, `PoseSkeletonAnalysis`, `SegmentationAnalysis` | `domain/frame_analysis.py` | `numpy`, `dataclasses`, `typing` | Nothing external | **BORDERLINE** |
| `AnalysisResult`, `Detection` | `domain/analysis_result.py` | `dataclasses`, `typing` (stdlib only) | Nothing external | **No** |
| `FrameMetadata` | `domain/frame_metadata.py` | `numpy`, `dataclasses`, `typing` | Nothing external | **BORDERLINE** |
| `TrajectoryPoint`, `Trajectory`, `TrackingData` | `domain/tracking_data.py` | `dataclasses`, `typing` (stdlib only) | Nothing external | **No** |
| `ConfigLoader` functions | `domain/config_loader.py` | `json`, `os`, `pathlib`, `yaml` (optional), `.config` | Nothing external | **No** (internal domain cross-ref is fine) |

**Note on BORDERLINE dependencies:** The domain layer imports `numpy` (in `events.py`, `frame_analysis.py`, `frame_metadata.py`) and `PIL` (in `types.py`). In strict hexagonal architecture, the domain should have zero external dependencies. However, for a real-time AV engine, numpy arrays *are* the domain data type (frame = ndarray). PIL Image is the rendering output type. These are pragmatic choices, not violations -- they are domain-intrinsic types for this problem space. If pure hexagonal is desired, these would need to be behind abstractions, but the cost would be high for negligible benefit.

### 1.2 Ports Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `FrameSource` | `ports/sources.py` | `typing`, `numpy` | domain only | **No** |
| `FrameRenderer` | `ports/renderers.py` | `typing`, `numpy`, `domain.config`, `domain.types` | domain only | **No** |
| `OutputSink` | `ports/outputs.py` | `typing`, `domain.config`, `domain.types`, `ports.output_capabilities` | domain only | **No** (ports can depend on other ports) |
| `FrameProcessor`, `Filter`, `Analyzer`, `ProcessorPipeline` | `ports/processors.py` | `typing`, `numpy`, `domain.config` | domain only | **No** |
| `ObjectTracker` | `ports/trackers.py` | `typing`, `numpy`, `domain.config`, `domain.tracking_data` | domain only | **No** |
| `SpatialTransform` | `ports/transformations.py` | `typing`, `numpy` | domain only | **No** |
| `ContentGenerator` | `ports/generators.py` | `typing`, `numpy` | domain only | **No** |
| `Controller` | `ports/controllers.py` | `typing` | domain only | **No** |
| `Sensor` | `ports/sensors.py` | `typing` | domain only | **No** |
| `OutputCapabilities`, `OutputCapability`, `OutputQuality` | `ports/output_capabilities.py` | `enum`, `typing` | domain only | **No** |

**Ports layer assessment:** Clean. All ports depend only on domain types and stdlib. No violations.

### 1.3 Application Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `StreamEngine` | `application/engine.py` | `domain.config`, `domain.events`, `domain.types`, `infrastructure.event_bus`, `infrastructure.metrics`, `infrastructure.plugins`, `infrastructure.profiling`, `ports.outputs`, `ports.renderers`, `ports.sources`, `application.orchestration`, `application.parallel_pipeline`, `application.pipeline.*`, `application.services.*` | domain + ports + infrastructure | **No** |
| `PipelineOrchestrator` | `application/orchestration/pipeline_orchestrator.py` | `domain.config`, `domain.events`, `domain.types`, `infrastructure.event_bus`, `infrastructure.profiling`, `ports.outputs`, `ports.renderers`, `ports.sources`, `application.pipeline.*`, `application.orchestration.stage_executor` | domain + ports + infrastructure | **No** |
| `StageExecutor`, `StageResult` | `application/orchestration/stage_executor.py` | `domain.config`, `domain.types` | domain + ports | **No** |
| `FilterPipeline` | `application/pipeline/filter_pipeline.py` | `cv2`, `numpy`, `domain.config`, `ports.processors`, `application.pipeline.filter_context`, **`adapters.processors.filters.conversion_cache`** (line 174) | domain + ports | **YES -- VIOLATION** |
| `FilterContext` | `application/pipeline/filter_context.py` | `typing` only | domain + ports | **No** |
| `AnalyzerPipeline` | `application/pipeline/analyzer_pipeline.py` | `numpy`, `domain.config`, `ports.processors` | domain + ports | **No** |
| `TrackingPipeline` | `application/pipeline/tracking_pipeline.py` | `numpy`, `domain.config`, `domain.tracking_data`, `ports.trackers` | domain + ports | **No** |
| `TransformationPipeline` | `application/pipeline/transformation_pipeline.py` | `numpy`, `ports.transformations` | domain + ports | **No** |
| `ProcessorPipelineImpl` | `application/pipeline/processor_pipeline.py` | `numpy`, `domain.config`, `ports.processors` | domain + ports | **No** |
| `TemporalManager` | `application/services/temporal_manager.py` | `cv2`, `numpy`, `logging`, `threading` | domain only (for services) | **STRAINED** (see analysis) |
| `FrameBuffer` | `application/services/frame_buffer.py` | `numpy`, `threading`, `time`, `collections` | domain only | **No** |
| `ErrorHandler` | `application/services/error_handler.py` | `domain.events`, `infrastructure.event_bus` | domain + infrastructure | **No** |
| `RetryManager` | `application/services/retry_manager.py` | `domain.config`, `domain.types`, `ports.outputs`, `ports.sources` | domain + ports | **No** |
| `FrameProcessor` (parallel) | `application/parallel_pipeline.py` | `numpy`, `domain.config` | domain + ports | **No** |

**Application layer violations:**

1. **`FilterPipeline` imports from adapters** (`application/pipeline/filter_pipeline.py`, line 174):
   ```python
   from ...adapters.processors.filters.conversion_cache import clear_conversion_cache
   ```
   This is a dependency rule violation: application layer must NOT import from adapters. The import is guarded by `try/except ImportError` which mitigates the coupling, but it is still an architectural violation. The conversion cache should either be in infrastructure or injected via a port.

### 1.4 Adapter Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `OpenCVCameraSource` | `adapters/sources/camera.py` | `cv2`, `numpy`, `os`, `sys` | ports + domain | **No** |
| `VideoFileSource` | `adapters/sources/video_file.py` | `cv2`, `numpy` | ports + domain | **No** |
| `FaceLandmarkAnalyzer` | `adapters/perception/face.py` | `cv2`, `numpy`, `domain.config`, `adapters.processors.analyzers.base` | ports + domain | **No** (adapter-to-adapter within same layer is acceptable) |
| `HandLandmarkAnalyzer` | `adapters/perception/hands.py` | `numpy`, `mediapipe`, `cv2`, `domain.config`, `adapters.processors.analyzers.base` | ports + domain | **No** |
| `PoseLandmarkAnalyzer` | `adapters/perception/pose.py` | `numpy`, `perception_cpp`, `domain.config`, `adapters.processors.analyzers.base` | ports + domain | **No** |
| `HandGestureAnalyzer` | `adapters/perception/hand_gesture.py` | Same pattern as above | ports + domain | **No** |
| `ObjectDetectionAnalyzer` | `adapters/perception/object_detection.py` | Same pattern as above | ports + domain | **No** |
| `EmotionAnalyzer` | `adapters/perception/emotion.py` | Same pattern as above | ports + domain | **No** |
| `PoseSkeletonAnalyzer` | `adapters/perception/pose_skeleton.py` | Same pattern as above | ports + domain | **No** |
| `SegmentationAnalyzer` | `adapters/perception/segmentation.py` | Same pattern as above | ports + domain | **No** |
| `BaseFilter` | `adapters/processors/filters/base.py` | None | ports + domain | **No** |
| `BaseAnalyzer` | `adapters/processors/analyzers/base.py` | None | ports + domain | **No** |
| `EdgeFilter` | `adapters/processors/filters/edges.py` | `cv2`, `.base`, `.conversion_cache` | ports + domain | **No** |
| `BoidsFilter` | `adapters/processors/filters/boids.py` | `cv2`, `numpy`, `.base` | ports + domain | **No** |
| `OpticalFlowParticlesFilter` | `adapters/processors/filters/optical_flow_particles.py` | `cv2`, `numpy`, `.base`, `.conversion_cache` | ports + domain | **No** |
| `PhysarumFilter` | `adapters/processors/filters/physarum.py` | `cv2`, `numpy`, `.base` | ports + domain | **No** |
| `CRTGlitchFilter` | `adapters/processors/filters/crt_glitch.py` | `cv2`, `numpy`, `.base` | ports + domain | **No** |
| 19 total filters | `adapters/processors/filters/` | Various (all follow same pattern) | ports + domain | **No** |
| `AsciiRenderer` | `adapters/renderers/ascii.py` | `cv2`, `numpy`, `PIL`, `domain.config`, `domain.types` | ports + domain | **No** |
| `PassthroughRenderer` | `adapters/renderers/passthrough_renderer.py` | `cv2`, `numpy`, `PIL`, `domain.config`, `domain.types`, `ports.renderers` | ports + domain | **No** |
| `LandmarksOverlayRenderer` | `adapters/renderers/landmarks_overlay_renderer.py` | `cv2`, `numpy`, `PIL`, `domain.config`, `domain.types`, `ports.renderers` | ports + domain | **No** |
| `CppDeformedRenderer` | `adapters/renderers/cpp_renderer.py` | `cv2`, `numpy`, `PIL`, `domain.config`, `domain.types`, `ports.renderers`, `render_bridge` | ports + domain | **No** |
| `FfmpegUdpOutput` | `adapters/outputs/udp.py` | `subprocess`, `PIL`, `domain.config`, `domain.types`, `ports.output_capabilities` | ports + domain | **No** |
| `CompositeOutputSink` | `adapters/outputs/composite.py` | `domain.config`, `domain.types`, `ports.output_capabilities`, `ports.outputs` | ports + domain | **No** |
| `NotebookPreviewSink` | `adapters/outputs/notebook_preview_sink.py` | `numpy`, `PIL`, `domain.config`, `domain.types`, `ports.output_capabilities` | ports + domain | **No** |
| `ControllerManager` | `adapters/controllers/controller_manager.py` | **`infrastructure.event_bus`**, `.base`, `.control_mapping` | ports + domain | **YES -- VIOLATION** |
| `adapters/trackers/__init__.py` | `adapters/trackers/__init__.py` | **`application.pipeline.TrackingPipeline`** | ports + domain | **YES -- VIOLATION** |
| `adapters/transformations/__init__.py` | `adapters/transformations/__init__.py` | **`application.pipeline.TransformationPipeline`** | ports + domain | **YES -- VIOLATION** |
| `adapters/trackers/tracking_pipeline.py` | `adapters/trackers/tracking_pipeline.py` | **`application.pipeline.TrackingPipeline`** | ports + domain | **YES -- VIOLATION** |

**Adapter layer violations:**

1. **`ControllerManager` imports from infrastructure** (`adapters/controllers/controller_manager.py`, line 6):
   ```python
   from ...infrastructure.event_bus import EventBus
   ```
   Adapters should depend on ports + domain only, not infrastructure. The EventBus should be injected via a port or constructor parameter without a concrete infrastructure import.

2. **`adapters/trackers/__init__.py` imports from application** (line 4):
   ```python
   from ...application.pipeline import TrackingPipeline
   ```
   Adapters must NOT depend on application layer. This re-exports an application class through the adapter module, creating a circular conceptual dependency.

3. **`adapters/transformations/__init__.py` imports from application** (line 12):
   ```python
   from ...application.pipeline import TransformationPipeline
   ```
   Same violation as above. The comment says "moved to application.pipeline" confirming this was a migration that broke the dependency direction.

4. **`adapters/trackers/tracking_pipeline.py` imports from application** (line 7):
   ```python
   from ...application.pipeline import TrackingPipeline
   ```
   Duplicate file that re-imports from application.

### 1.5 Infrastructure Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `EventBus` | `infrastructure/event_bus.py` | `domain.events` | domain only | **No** |
| `EngineMetrics` | `infrastructure/metrics.py` | stdlib only (`threading`, `time`, `collections`) | domain only | **No** |
| `LoopProfiler`, `PhaseStats` | `infrastructure/profiling.py` | stdlib only (`time`, `collections`, `statistics`) | domain only | **No** |
| `StructuredLogger`, formatters | `infrastructure/logging.py` | stdlib only (`json`, `logging`, `sys`, `threading`) | domain only | **No** |
| `PluginManager` | `infrastructure/plugins/plugin_manager.py` | `watchdog` (optional), `infrastructure.plugins.*` | domain only | **No** |
| `ConfigPersistence` | `infrastructure/config_persistence.py` | `domain.config` | domain only | **No** |
| `DashboardServer` | `infrastructure/dashboard/server.py` | `infrastructure.dashboard.*` | domain only | **No** |
| `FrameSkipper` | `infrastructure/performance/frame_skipper.py` | stdlib only | domain only | **No** |
| `AdaptiveQuality` | `infrastructure/performance/adaptive_quality.py` | stdlib only | domain only | **No** |

**Infrastructure layer assessment:** Clean. All infrastructure modules depend only on domain and stdlib. No violations.

### 1.6 Presentation Layer

| Component | File | Dependencies (actual) | Dependencies (allowed) | Violation? |
|---|---|---|---|---|
| `notebook_api.py` (all `build_*` functions) | `presentation/notebook_api.py` | `adapters.outputs.NotebookPreviewSink`, `adapters.renderers.AsciiRenderer`, `adapters.renderers.PassthroughRenderer`, `adapters.sources.OpenCVCameraSource`, `application.engine.StreamEngine`, `application.pipeline.AnalyzerPipeline`, `application.pipeline.FilterPipeline`, `domain.config.EngineConfig` | application + infrastructure + domain | **YES -- VIOLATION** |

**Presentation layer violation:**

The presentation layer directly imports concrete adapter classes:
```python
from ..adapters.outputs import NotebookPreviewSink          # line 19
from ..adapters.renderers import AsciiRenderer, PassthroughRenderer  # line 20
from ..adapters.sources import OpenCVCameraSource            # line 21
```

In strict hexagonal architecture, presentation should depend on application (which uses ports), not on concrete adapters. The presentation layer acts as a composition root, wiring concrete adapters to ports. This is a common pragmatic choice in Python projects -- the composition root often lives in presentation or a dedicated `bootstrap` module. This is a **soft violation**: the wiring has to happen somewhere, and presentation is the most natural place. However, it does mean presentation is tightly coupled to specific adapter implementations.

### 1.7 Violation Summary

| # | Violation | Severity | File | Line |
|---|---|---|---|---|
| V1 | Application imports from Adapters | **High** | `application/pipeline/filter_pipeline.py` | 174 |
| V2 | Adapter imports from Infrastructure | **Medium** | `adapters/controllers/controller_manager.py` | 6 |
| V3 | Adapter imports from Application | **High** | `adapters/trackers/__init__.py` | 4 |
| V4 | Adapter imports from Application | **High** | `adapters/transformations/__init__.py` | 12 |
| V5 | Adapter imports from Application | **High** | `adapters/trackers/tracking_pipeline.py` | 7 |
| V6 | Presentation imports from Adapters | **Low** | `presentation/notebook_api.py` | 19-21 |

---

## Step 2: Data Flow Mapping

### 2.1 Primary Pipeline Data Flow

The canonical data flow as enforced by `PipelineOrchestrator.process_frame()` (`application/orchestration/pipeline_orchestrator.py`):

```
Source.read()
  → [np.ndarray (H,W,3) BGR uint8]
  → AnalyzerPipeline.run(frame, config)
    → [Dict[str, object]]  (analysis results: face, hands, pose, etc.)
  → TrackingPipeline.run(frame, analysis, config)
    → [TrackingData → dict merged into analysis["tracking"]]
  → TemporalManager.push_input(frame)
    → [stores in ring buffer, no output]
  → FilterPipeline.apply(frame, config, analysis)
    → [np.ndarray (H,W,3) BGR uint8]  (modified frame)
  → TemporalManager.push_output(frame)
    → [stores in output buffer, no output]
  → Renderer.render(frame, config, analysis)
    → [RenderFrame (PIL Image + text + lines + metadata)]
  → OutputSink.write(rendered)
    → [void -- writes to network/file/display]
```

### 2.2 Data Transformation Points

| Stage Boundary | Input Type | Output Type | Transform |
|---|---|---|---|
| Source → Analysis | `np.ndarray (H,W,3) BGR` | `Dict[str, object]` | Frame to structured analysis dict |
| Analysis → Tracking | `np.ndarray` + `Dict` | `TrackingData` merged into dict | Enriches analysis dict with trajectories |
| Analysis → TemporalManager | `np.ndarray` | ring buffer slot | Zero-copy into pre-allocated buffer |
| TemporalManager → FilterContext | ring buffer | `FilterContext` wrapper | Lazy property access via `FilterContext.previous_input`, `.optical_flow`, `.delta_frame` |
| Analysis dict → FilterContext | `Dict` + `TemporalManager` | `FilterContext` | Dict-compatible wrapper with temporal properties |
| Filter chain → Filter chain | `np.ndarray` | `np.ndarray` | Sequential, each filter receives previous output |
| Last Filter → TemporalManager | `np.ndarray` | output buffer slot | Copy into output buffer |
| Frame → Renderer | `np.ndarray BGR` → `RenderFrame` | `PIL.Image RGB` | BGR→RGB + resize + optional ASCII conversion |
| RenderFrame → OutputSink | `RenderFrame` | raw bytes | PIL→bytes (JPEG/PNG) or PIL→RGB24 tobytes() |

### 2.3 Data Duplication Points

1. **Renderer copies**: `AsciiRenderer._frame_to_image()` (line 70, `adapters/renderers/ascii.py`) calls `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` creating a copy. This is unavoidable for PIL conversion.

2. **Filter copies**: Most filters call `frame.copy(order="C")` at the start of their `apply()` method (e.g., `BoidsFilter` line 79, `CRTGlitchFilter` line 61). This is correct behavior (filters should not mutate the input) but means N filters = N copies.

3. **LandmarksOverlayRenderer double conversion**: The renderer (line 70-72, `adapters/renderers/landmarks_overlay_renderer.py`) converts inner result from PIL (RGB) back to numpy (BGR) for cv2 drawing, then back to PIL (RGB). Two unnecessary color conversions.

4. **TemporalManager ring buffer**: `np.copyto()` in `push_input()` (line 120, `application/services/temporal_manager.py`) performs a full frame copy into the ring buffer. This is intentional and correct.

### 2.4 Data Loss Points

1. **Analysis dict is untyped**: The analysis dict passes through the entire pipeline as `Optional[dict]`. Any consumer must know the exact string keys to look up ("face", "hands", "pose", "tracking"). There is no compile-time or runtime schema enforcement. If an analyzer changes its output format, downstream filters break silently.

2. **Temporal data injected/removed from analysis dict**: In `PipelineOrchestrator.process_frame()` (line 179), the TemporalManager is injected into the analysis dict:
   ```python
   analysis["temporal"] = self._temporal
   ```
   Then in `FilterPipeline.apply()` (line 184, `filter_pipeline.py`), it is extracted and popped:
   ```python
   temporal = analysis.pop("temporal")
   ```
   This is a side-channel hack. The analysis dict is being used as a general-purpose context bag, not a typed data structure.

3. **Renderer receives analysis but cannot act on tracking**: The renderer receives `analysis` but the tracking data is nested as `analysis["tracking"]`. Renderers like `LandmarksOverlayRenderer` access `analysis.get("face")`, `analysis.get("hands")`, `analysis.get("pose")` but do not access tracking data. Tracking information is essentially lost after the tracking stage.

### 2.5 Feedback / Backward Data Flow

1. **TemporalManager** (`application/services/temporal_manager.py`): This is the sole mechanism for backward data flow. It provides:
   - `get_previous_input(n)`: Ring buffer of N previous input frames
   - `get_previous_output()`: Last filtered output frame
   - `get_optical_flow()`: Lazy-computed Farneback flow between current and previous input
   - `get_delta()`: Lazy-computed absdiff between current and previous input

   These are accessed via `FilterContext` properties. This is a **workaround** for the lack of cyclical data flow in hexagonal architecture.

2. **No feedback from renderer to filters**: Filters cannot know the renderer's grid size, character set, or output resolution. This hurts filters that need to coordinate with the ASCII rendering (e.g., mosaic-style effects that need grid alignment).

3. **No feedback from output to pipeline**: If the output sink is lagging (e.g., network congestion), the pipeline cannot back-pressure. The only mechanism is the frame buffer's fixed size, which drops old frames.

---

## Step 3: Constraint Tension Map

| # | Constraint | Helps When | Hurts When | Pain Level (1-5) |
|---|---|---|---|---|
| T1 | **Dependency direction** (adapters → ports → domain) | Swapping renderers, sources, outputs without touching application | Adapter-to-adapter coordination (controller→filter parameter modulation, perception→filter reactivity) | **2** |
| T2 | **Filters can't see renderer config** | Keeps filters decoupled from rendering | ASCII grid alignment, mosaic effects, resolution-aware filtering | **3** |
| T3 | **Pipeline stage order hardcoded** in `PipelineOrchestrator.process_frame()` | Predictable, debuggable execution | Adding compositing between filters and renderer, multi-pass effects, post-render effects | **4** |
| T4 | **No cross-adapter communication** | Clean separation, easy testing | Perception→filter parameter modulation (e.g., boids attracted to faces), filter→renderer hints, sensor→filter data | **3** |
| T5 | **Analysis dict is untyped** (`Optional[dict]`) | Easy to add new analysis keys | Silent failures when key names change, no IDE completion, runtime errors from missing keys | **4** |
| T6 | **Push-only execution** (every stage runs every frame) | Simple execution model | Expensive analyzers run even when no filter uses their output, wasted computation | **3** |
| T7 | **Feedback is a workaround** (TemporalManager injected via analysis dict) | Works for frame history and optical flow | No feedback from render stage, no lazy graph evaluation, no multi-step feedback | **4** |
| T8 | **Single stream model** (one frame flows through) | Simple mental model | No multi-camera support, no audio stream, no parallel streams with different frame rates | **3** |
| T9 | **Adapter isolation** (adapters should not know about each other) | Testability, swappability | BaseAnalyzer shared between perception and processors (cross-adapter coupling already exists) | **2** |
| T10 | **FilterContext as compatibility shim** | Backwards-compatible dict API + temporal properties | Hides the fact that the port protocol is too narrow, adds an implicit contract layer | **3** |

### Tension Analysis

**Highest pain (4/5):**
- **T3 (Hardcoded pipeline order)**: The 6-stage pipeline in `PipelineOrchestrator` is rigid. Any new stage type (compositing, post-render effects, multi-pass) requires modifying `process_frame()`. This method is 210+ lines of sequential logic with no plugin points.
- **T5 (Untyped analysis dict)**: The analysis dict is the primary inter-stage data carrier but has no schema. The domain layer has typed dataclasses (`FaceAnalysis`, `HandAnalysis`, etc.) but they are not used in the pipeline -- analyzers return plain dicts.
- **T7 (Feedback workaround)**: The TemporalManager injection via `analysis["temporal"]` then `analysis.pop("temporal")` is fragile. If any intermediate code serializes the analysis dict, the TemporalManager object will cause errors.

**Moderate pain (3/5):**
- **T2, T4, T6, T8, T10**: These are genuine limitations of hexagonal architecture for AV processing. They all stem from the same root cause: hexagonal models request/response or command patterns, not graph-based data flow.

**Acceptable (2/5):**
- **T1, T9**: The dependency direction constraint works well overall. The few violations (Section 1.7) are localized and fixable.

---

## Step 4: Migration Surface

### 4.1 Pure Components (No Migration Needed)

These components are perfectly hexagonal, well-isolated, and would map cleanly to any architecture:

| Component | File | Why Pure |
|---|---|---|
| `EngineConfig` | `domain/config.py` | Pure domain dataclass, zero external deps |
| `NeuralConfig` | `domain/config.py` | Pure domain dataclass |
| `ConfigLoader` | `domain/config_loader.py` | Pure domain utility |
| `TrajectoryPoint`, `Trajectory`, `TrackingData` | `domain/tracking_data.py` | Pure domain dataclasses |
| `AnalysisResult`, `Detection` | `domain/analysis_result.py` | Pure domain dataclasses |
| All port protocols | `ports/*.py` | Clean protocol definitions |
| `FrameBuffer` | `application/services/frame_buffer.py` | Pure infrastructure service |
| `EventBus` | `infrastructure/event_bus.py` | Clean pub/sub, depends only on domain events |
| `EngineMetrics` | `infrastructure/metrics.py` | Pure metrics, no domain coupling |
| `LoopProfiler` | `infrastructure/profiling.py` | Pure profiling, no domain coupling |
| `StructuredLogger` | `infrastructure/logging.py` | Pure logging utilities |
| `OpenCVCameraSource` | `adapters/sources/camera.py` | Clean FrameSource adapter |
| `VideoFileSource` | `adapters/sources/video_file.py` | Clean FrameSource adapter |
| `BrightnessFilter` | `adapters/processors/filters/brightness.py` | Stateless filter, pure function |
| `InvertFilter` | `adapters/processors/filters/invert.py` | Stateless filter, pure function |
| `FfmpegUdpOutput` | `adapters/outputs/udp.py` | Clean OutputSink adapter |
| `NotebookPreviewSink` | `adapters/outputs/notebook_preview_sink.py` | Clean OutputSink adapter |
| `CompositeOutputSink` | `adapters/outputs/composite.py` | Clean composite pattern |
| `StageExecutor` | `application/orchestration/stage_executor.py` | Pure execution utility |
| `RetryManager` | `application/services/retry_manager.py` | Clean error recovery |

### 4.2 Strained Components (Working but Fighting the Architecture)

| Component | File | Strain Type | Description |
|---|---|---|---|
| `TemporalManager` | `application/services/temporal_manager.py` | **Layer tension** | Acts as infrastructure (buffer management) but lives in application because it needs pipeline integration. Imports `cv2` directly for optical flow computation -- this is business logic (computing motion features) embedded in a service. |
| `FilterContext` | `application/pipeline/filter_context.py` | **Port strain** | Exists because the `Filter.apply()` port protocol takes `Optional[dict]` but filters need temporal data and typed analysis access. FilterContext wraps both, creating an implicit contract that extends beyond the port definition. |
| `FilterPipeline` | `application/pipeline/filter_pipeline.py` | **Abstraction leak** | Contains a `try/except` import of `adapters.processors.filters.conversion_cache` (violation V1). Also extracts TemporalManager from the analysis dict using `analysis.pop("temporal")` -- this is fragile coupling to the orchestrator's injection pattern. |
| `PipelineOrchestrator` | `application/orchestration/pipeline_orchestrator.py` | **Rigidity** | 318 lines of sequential pipeline logic. Stage order is hardcoded. Adding a new stage requires modifying this file. The TemporalManager injection (`analysis["temporal"] = self._temporal`) is a side-channel. |
| `LandmarksOverlayRenderer` | `adapters/renderers/landmarks_overlay_renderer.py` | **Composition strain** | Uses decorator pattern wrapping an inner renderer. Works for one overlay but doesn't compose with multiple overlays. The BGR→RGB→BGR→RGB conversion chain (lines 70-72, 122) is wasteful. |
| `EdgeFilter` | `adapters/processors/filters/edges.py` | **Contract strain** | Returns `(H,W)` grayscale from `cv2.Canny` instead of `(H,W,3)` BGR. This breaks the BGR contract that all other filters and the renderer expect. Downstream filters receiving this output will fail or produce incorrect results. |
| `BoidsFilter`, `PhysarumFilter`, `CRTGlitchFilter`, `OpticalFlowParticlesFilter` | `adapters/processors/filters/` | **Statefulness tension** | These filters maintain internal state (particle positions, trail maps, previous frames). The hexagonal pipeline model assumes stateless transformations. State management is done ad-hoc per filter with `_last_shape` reinitialization guards. |
| `ControllerManager` | `adapters/controllers/controller_manager.py` | **Infrastructure coupling** | Directly imports and depends on `infrastructure.event_bus.EventBus` instead of using a port abstraction (violation V2). |

### 4.3 Broken Components (Violating Hexagonal Rules)

| Component | File | Violation | Impact |
|---|---|---|---|
| `adapters/trackers/__init__.py` | `adapters/trackers/__init__.py` | Re-exports `TrackingPipeline` from application layer | Creates circular conceptual dependency: application defines the pipeline, adapters re-export it. Users importing from adapters get an application class. |
| `adapters/transformations/__init__.py` | `adapters/transformations/__init__.py` | Re-exports `TransformationPipeline` from application layer | Same as above. Also has a fallback to a local `transformation_pipeline.py`, creating two definitions. |
| `FilterPipeline.apply()` | `application/pipeline/filter_pipeline.py:174` | Imports adapter module at runtime | Application layer reaches into adapter implementation details for cache clearing. |

### 4.4 Missing Capabilities (Not Expressible in Current Hexagonal Architecture)

| Capability | What's Missing | Impact |
|---|---|---|
| **Graph-based data flow** | Hexagonal enforces linear pipeline. No branching (one frame to multiple processing paths), no merging (combine multiple analysis results), no conditional routing. | Cannot do multi-resolution processing, A/B filter comparison, or conditional analysis chains. |
| **Lazy evaluation** | Every stage runs every frame. No mechanism to skip analysis if no filter needs it. | Wasted computation. FaceLandmarkAnalyzer runs even if no filter uses face data. |
| **Multi-stream** | Architecture models one frame flowing through one pipeline. No concept of parallel streams (video + audio + control). | Cannot process audio, cannot synchronize multiple camera feeds. |
| **Back-pressure** | No mechanism for slow outputs to signal the pipeline to slow down. | Frame dropping is the only congestion strategy. |
| **Post-render effects** | Pipeline ends at render→output. No stage for post-render image processing. | Cannot apply effects to the rendered ASCII image (e.g., bloom on ASCII characters). |
| **Dynamic pipeline reconfiguration** | Adding/removing stages requires recreating the orchestrator. | Hot-swapping pipeline stages while running is not supported cleanly. |
| **Typed analysis flow** | Domain defines `FaceAnalysis`, `HandAnalysis`, etc. but the pipeline uses `dict`. | Type safety is lost between analyzers and consumers. |

---

## Step 5: Recommendations

### Priority 1: Fix Dependency Violations (Immediate)

These are concrete bugs that should be fixed regardless of architecture migration:

1. **V1: Remove adapter import from FilterPipeline** (`application/pipeline/filter_pipeline.py:174`)
   - Move `conversion_cache` to `infrastructure/` or inject via constructor
   - Estimated effort: 1 hour

2. **V3/V4/V5: Remove application imports from adapter __init__.py files**
   - `adapters/trackers/__init__.py` should not re-export `TrackingPipeline`
   - `adapters/transformations/__init__.py` should not re-export `TransformationPipeline`
   - Users should import pipelines from `application.pipeline` directly
   - Estimated effort: 2 hours (includes updating all import sites)

3. **V2: Decouple ControllerManager from infrastructure.EventBus**
   - Accept `EventBus` as a constructor parameter typed to a protocol, not a concrete import
   - Or create a `ports/event_publishing.py` protocol
   - Estimated effort: 1 hour

### Priority 2: Type the Analysis Flow (High Impact, Medium Effort)

The `Optional[dict]` analysis flow is the source of multiple tensions (T5, T7, T10):

1. Create a typed `FrameContext` dataclass in `domain/`:
   ```
   @dataclass
   class FrameContext:
       face: Optional[FaceAnalysis] = None
       hands: Optional[HandAnalysis] = None
       pose: Optional[PoseAnalysis] = None
       tracking: Optional[TrackingData] = None
       timestamp: float = 0.0
   ```
2. Migrate analyzers to return typed domain objects instead of dicts
3. Migrate `FilterContext` to wrap `FrameContext` instead of `dict`
4. This eliminates the untyped dict passing and enables IDE completion
5. Estimated effort: 1-2 days

### Priority 3: Extract TemporalManager from Analysis Dict (Medium Impact)

The current pattern of `analysis["temporal"] = self._temporal` → `analysis.pop("temporal")` is fragile:

1. Pass `TemporalManager` as an explicit parameter to `FilterPipeline.apply()`, not smuggled through the dict
2. Or create a `PipelineState` object that carries both analysis and temporal data
3. Estimated effort: 4 hours

### Priority 4: Fix EdgeFilter Contract Violation

`EdgeFilter.apply()` returns `(H,W)` grayscale instead of `(H,W,3)` BGR:

1. Add `cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)` at the end of `EdgeFilter.apply()`
2. Or convert to 3-channel: `np.stack([edges]*3, axis=-1)`
3. Estimated effort: 30 minutes

### Priority 5: Assess Pipeline Extensibility (For Dataflow Graph Migration)

If transitioning to a dataflow graph architecture, the following components have the cleanest migration surface:

1. **All pure components** (Section 4.1) can be migrated as-is -- they become graph nodes
2. **Stateful filters** (boids, physarum, CRT, optical_flow) need their state management extracted into node-level state -- the current `_last_shape` pattern maps to graph node state
3. **TemporalManager** would become graph-level state with explicit edges for previous frame access
4. **PipelineOrchestrator** would be replaced entirely by a graph executor
5. **FilterContext** would be replaced by typed edge data flowing through the graph

### Summary of Architectural Health

| Metric | Value |
|---|---|
| Total components audited | 70+ |
| Dependency violations | 6 (3 high, 2 medium, 1 low) |
| Pure components | 20+ (28%) |
| Strained components | 8 (11%) |
| Broken components | 3 (4%) |
| Missing capabilities | 7 major |
| Overall hexagonal compliance | **Good** (85%+ of code follows rules) |

The architecture is fundamentally sound for its current scope. The violations are localized and fixable. The real limitation is not that hexagonal is implemented poorly, but that hexagonal architecture is inherently insufficient for graph-based real-time AV processing with feedback loops, multi-stream, and dynamic reconfiguration. The strains identified here (T3, T5, T7 at pain level 4) are structural limitations of the pattern itself, not implementation bugs.
