# Dataflow Graph Migration Proposal

**Date:** 2026-02-28
**Author:** Innovation Team
**Status:** PROPOSAL (ready for review)
**Depends on:** `architecture_audit.md`, `research_touchdesigner.md`, `research_openframeworks.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Node Catalog](#2-node-catalog)
3. [Port Type Specification](#3-port-type-specification)
4. [Graph Examples](#4-graph-examples)
5. [Execution Model](#5-execution-model)
6. [Migration Plan (4 Phases)](#6-migration-plan)
7. [Risk Assessment](#7-risk-assessment)
8. [Concrete Example: Mosaic + ASCII](#8-concrete-example-mosaic--ascii)

---

## 1. Executive Summary

### Why Migrate

The architecture audit (`architecture_audit.md`) identified 7 missing capabilities that cannot be expressed in the current hexagonal architecture, and 3 constraint tensions at pain level 4/5:

- **T3 (Hardcoded pipeline order):** The 6-stage pipeline in `PipelineOrchestrator.process_frame()` is rigid. Any new stage type requires modifying a 210+ line sequential method.
- **T5 (Untyped analysis dict):** The analysis dict carries data between stages as `Optional[dict]` with no schema.
- **T7 (Feedback is a workaround):** `TemporalManager` is injected via `analysis["temporal"]` then popped with `analysis.pop("temporal")` -- a fragile side-channel hack.

The triggering use case: **Mosaic filter + ASCII renderer composition is impossible** in the current linear pipeline. The pipeline processes one frame through one filter chain to one renderer. There is no way to split a frame into two paths (mosaic rendering + ASCII rendering) and composite the results.

### What Changes

The PipelineOrchestrator's hardcoded stage sequence is replaced by a directed acyclic graph (DAG) of processing nodes. Each existing adapter (19 filters, 4 renderers, 8 perception analyzers, 2 sources, 5 outputs) becomes a node in this graph, wrapped without code changes. The graph scheduler executes nodes in topological order, parallelizing independent branches.

### What Stays

- Domain layer (`domain/`) -- untouched
- Infrastructure layer (`infrastructure/`) -- untouched
- All existing adapters -- wrapped as nodes, zero code changes
- EventBus, metrics, profiling, logging -- orthogonal, kept as-is
- Public API (`StreamEngine`) -- preserved via compatibility shim in Phase 0

---

## 2. Node Catalog

### 2.1 Source Nodes

Source nodes have zero required inputs and produce data for downstream consumption.

#### CameraSource

| Property | Value |
|----------|-------|
| **Category** | source |
| **Input ports** | (none) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | OpenCV VideoCapture handle, device index |
| **Latency budget** | 5ms (capture only; OS-level buffering handles camera timing) |
| **Maps from** | `adapters/sources/camera.py` -- `OpenCVCameraSource` |

#### VideoFileSource

| Property | Value |
|----------|-------|
| **Category** | source |
| **Input ports** | (none) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | OpenCV VideoCapture handle, file path, frame position, loop flag |
| **Latency budget** | 3ms (decode from file) |
| **Maps from** | `adapters/sources/video_file.py` -- `VideoFileSource` |

#### AudioSource (new -- Phase 3)

| Property | Value |
|----------|-------|
| **Category** | source |
| **Input ports** | (none) |
| **Output ports** | `audio_out`: AudioBuffer |
| **State** | PyAudio/sounddevice stream handle, sample rate, buffer size |
| **Latency budget** | 2ms (buffer read, non-blocking) |
| **Maps from** | New component (no current equivalent) |

#### OSCReceiver (new -- Phase 3)

| Property | Value |
|----------|-------|
| **Category** | source |
| **Input ports** | (none) |
| **Output ports** | `control_out`: ControlSignal (one per channel, dynamically created) |
| **State** | UDP socket, OSC address map |
| **Latency budget** | <1ms (UDP receive) |
| **Maps from** | New component. Inspired by TD CHOP-to-parameter binding and OF ofxOsc. |

#### MIDIReceiver (new -- Phase 3)

| Property | Value |
|----------|-------|
| **Category** | source |
| **Input ports** | (none) |
| **Output ports** | `control_out`: ControlSignal (one per CC, dynamically created) |
| **State** | MIDI port handle, CC-to-channel map |
| **Latency budget** | <1ms |
| **Maps from** | New component. Inspired by OF ofxMidi and TD MIDI-in CHOP. |

### 2.2 Analyzer Nodes

Analyzers receive a video frame, produce analysis data, and pass through the video frame unchanged. They MUST NOT modify the frame (enforced by read-only VideoFrame semantics on the output).

#### FaceAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData, `mask_out`: Mask (optional) |
| **State** | MediaPipe/ONNX model session, warm-up flag |
| **Latency budget** | 8ms (within 33.3ms total budget, per `LATENCY_BUDGET.md`) |
| **Maps from** | `adapters/perception/face.py` -- `FaceLandmarkAnalyzer` |

**AnalysisData output schema:**
```python
{
    "face": {
        "landmarks": List[Tuple[float, float]],  # 468 points, normalized 0-1
        "bbox": Tuple[float, float, float, float],  # x, y, w, h normalized
        "confidence": float,
    }
}
```

#### HandAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | MediaPipe/ONNX model session |
| **Latency budget** | 6ms |
| **Maps from** | `adapters/perception/hands.py` -- `HandLandmarkAnalyzer` |

#### PoseAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | ONNX model session |
| **Latency budget** | 8ms |
| **Maps from** | `adapters/perception/pose.py` -- `PoseLandmarkAnalyzer` |

#### HandGestureAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required), `hand_analysis_in`: AnalysisData (optional -- from HandAnalyzer) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | Gesture classification model |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/perception/hand_gesture.py` -- `HandGestureAnalyzer` |

#### ObjectDetectionAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | ONNX model session, class filter list |
| **Latency budget** | 10ms |
| **Maps from** | `adapters/perception/object_detection.py` -- `ObjectDetectionAnalyzer` |

#### EmotionAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required), `face_analysis_in`: AnalysisData (optional -- from FaceAnalyzer) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | Emotion classification model |
| **Latency budget** | 4ms |
| **Maps from** | `adapters/perception/emotion.py` -- `EmotionAnalyzer` |

#### PoseSkeletonAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData |
| **State** | Skeleton extraction model |
| **Latency budget** | 6ms |
| **Maps from** | `adapters/perception/pose_skeleton.py` -- `PoseSkeletonAnalyzer` |

#### SegmentationAnalyzer

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `video_in`: VideoFrame (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `analysis_out`: AnalysisData, `mask_out`: Mask |
| **State** | Segmentation model session |
| **Latency budget** | 10ms |
| **Maps from** | `adapters/perception/segmentation.py` -- `SegmentationAnalyzer` |

#### AudioAnalyzer (new -- Phase 3)

| Property | Value |
|----------|-------|
| **Category** | analyzer |
| **Input ports** | `audio_in`: AudioBuffer (required) |
| **Output ports** | `analysis_out`: AnalysisData |
| **State** | FFT window, onset detection state, BPM estimator |
| **Latency budget** | 2ms |
| **Maps from** | New component. Inspired by TD Audio Spectrum CHOP and OF ofxAudioAnalyzer. |

**AnalysisData output schema:**
```python
{
    "audio": {
        "bass_energy": float,    # 0.0-1.0 (20-250 Hz)
        "mid_energy": float,     # 0.0-1.0 (250-4000 Hz)
        "high_energy": float,    # 0.0-1.0 (4000-20000 Hz)
        "beat_detected": bool,
        "bpm_estimate": float,
        "spectrum": List[float],  # full FFT magnitudes, normalized
    }
}
```

### 2.3 Processor Nodes (Filters)

Processor nodes transform video frames. Each wraps an existing filter adapter.

#### BrightnessFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `brightness`: ControlSignal (optional, default=0.5) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None (stateless) |
| **Latency budget** | 1ms |
| **Maps from** | `adapters/processors/filters/brightness.py` -- `BrightnessFilter` |

#### InvertFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None (stateless) |
| **Latency budget** | <1ms |
| **Maps from** | `adapters/processors/filters/invert.py` -- `InvertFilter` |

#### EdgeFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `threshold`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None (stateless) |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/edges.py` -- `EdgeFilter` |
| **Note** | The node wrapper must ensure output is (H,W,3) BGR, fixing the current grayscale output bug (audit finding). |

#### BoidsFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (optional), `speed`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Particle positions, velocities, trail buffer (stateful -- managed by node instance) |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/processors/filters/boids.py` -- `BoidsFilter` |

#### PhysarumFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Agent positions, trail map, chemoattractant buffer |
| **Latency budget** | 4ms |
| **Maps from** | `adapters/processors/filters/physarum.py` -- `PhysarumFilter` |

#### CRTGlitchFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `intensity`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Scanline state, noise seed, glitch accumulator |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/crt_glitch.py` -- `CRTGlitchFilter` |

#### OpticalFlowParticlesFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Particle positions, previous frame for optical flow computation |
| **Latency budget** | 5ms |
| **Maps from** | `adapters/processors/filters/optical_flow_particles.py` -- `OpticalFlowParticlesFilter` |

#### DetailBoostFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `amount`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None (stateless) |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/detail.py` -- `DetailBoostFilter` |

#### EdgeSmoothFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None (stateless) |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/edge_smooth.py` -- `EdgeSmoothFilter` |

#### StipplingFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `density`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Point distribution cache |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/processors/filters/stippling.py` -- `StipplingFilter` |

#### UVDisplacementFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `amount`: ControlSignal (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Noise seed |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/uv_displacement.py` -- `UVDisplacementFilter` |

#### GeometricPatternFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (optional) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Pattern cache |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/geometric_patterns.py` -- `GeometricPatternFilter` |

#### RadialCollapseFilter

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `center`: ControlSignal (optional, x/y pair) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/processors/filters/radial_collapse.py` -- `RadialCollapseFilter` |

#### C++ Filter Nodes (6 nodes)

The following C++ filters share the same node structure. Each wraps its Python-side adapter which in turn calls into `filters_cpp`:

| Node | Maps from | Latency |
|------|-----------|---------|
| CppBrightnessContrastNode | `cpp_brightness_contrast.py` | <1ms |
| CppChannelSwapNode | `cpp_channel_swap.py` | <1ms |
| CppGrayscaleNode | `cpp_grayscale.py` | <1ms |
| CppInvertNode | `cpp_invert.py` | <1ms |
| CppImageModifierNode | `cpp_modifier.py` | <1ms |
| CppPhysarumNode | `cpp_physarum.py` | 3ms |

All follow the pattern:
- Input ports: `video_in`: VideoFrame, optional ControlSignal ports for parameters
- Output ports: `video_out`: VideoFrame
- State: Varies (CppPhysarum is stateful, others are stateless)

### 2.4 Renderer Nodes

Renderer nodes convert VideoFrame to RenderFrame.

#### AsciiRendererNode

| Property | Value |
|----------|-------|
| **Category** | renderer |
| **Input ports** | `video_in`: VideoFrame, `grid_w`: ControlSignal (optional), `grid_h`: ControlSignal (optional) |
| **Output ports** | `render_out`: RenderFrame |
| **State** | Font handle, character dimensions, cached PIL Image |
| **Latency budget** | 4ms |
| **Maps from** | `adapters/renderers/ascii.py` -- `AsciiRenderer` |

#### PassthroughRendererNode

| Property | Value |
|----------|-------|
| **Category** | renderer |
| **Input ports** | `video_in`: VideoFrame |
| **Output ports** | `render_out`: RenderFrame |
| **State** | None |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/renderers/passthrough_renderer.py` -- `PassthroughRenderer` |

#### LandmarksOverlayRendererNode

| Property | Value |
|----------|-------|
| **Category** | renderer |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (required) |
| **Output ports** | `render_out`: RenderFrame |
| **State** | Inner renderer reference |
| **Latency budget** | 4ms |
| **Maps from** | `adapters/renderers/landmarks_overlay_renderer.py` -- `LandmarksOverlayRenderer` |

#### CppDeformedRendererNode

| Property | Value |
|----------|-------|
| **Category** | renderer |
| **Input ports** | `video_in`: VideoFrame |
| **Output ports** | `render_out`: RenderFrame |
| **State** | render_bridge C++ handle |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/renderers/cpp_renderer.py` -- `CppDeformedRenderer` |

### 2.5 Composition Nodes (new -- Phase 1)

#### CompositeNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_a`: VideoFrame (required), `video_b`: VideoFrame (required), `mask`: Mask (optional), `blend`: ControlSignal (optional, default=0.5) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None |
| **Latency budget** | 1ms |
| **Maps from** | New component. Implements blend modes: alpha, additive, multiply, screen, overlay. |

**Blend modes (set via node parameter, not port):**

| Mode | Formula |
|------|---------|
| alpha | `A * blend + B * (1 - blend)` |
| additive | `min(A + B, 255)` |
| multiply | `A * B / 255` |
| screen | `255 - (255-A) * (255-B) / 255` |
| overlay | per-pixel: `if base < 128: 2*A*B/255 else 255 - 2*(255-A)*(255-B)/255` |
| mask | `A * mask + B * (1 - mask)` (uses mask port) |

#### RenderFrameCompositeNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `render_a`: RenderFrame (required), `render_b`: RenderFrame (required) |
| **Output ports** | `render_out`: RenderFrame |
| **State** | None |
| **Latency budget** | 2ms |
| **Maps from** | New component. Composites two RenderFrames using PIL Image.alpha_composite or paste. |

#### MosaicFilterNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `block_size`: ControlSignal (optional, default=0.1, maps to pixel block size) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | None |
| **Latency budget** | 2ms |
| **Maps from** | New component. Pixelates the frame into blocks of configurable size. |

**Implementation:**
```python
def process(self, inputs):
    frame = inputs["video_in"]
    block = int(inputs.get("block_size", 0.1) * min(frame.shape[:2]))
    block = max(1, block)
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (w // block, h // block), interpolation=cv2.INTER_AREA)
    return {"video_out": cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)}
```

### 2.6 Temporal Nodes (new -- Phase 2)

#### FeedbackNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame |
| **Output ports** | `video_out`: VideoFrame (frame N-1, or black on first frame) |
| **State** | Double-buffered frame: `write_buf` (current frame stored for next), `read_buf` (previous frame output) |
| **Latency budget** | <1ms (buffer swap, no computation) |
| **Maps from** | Replaces `TemporalManager.get_previous_output()`. Inspired by TD Feedback TOP. |

#### DelayNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame (or any port type) |
| **Output ports** | `video_out`: VideoFrame (frame N-delay) |
| **State** | Ring buffer of `delay` frames |
| **Latency budget** | <1ms (ring buffer index update) |
| **Maps from** | Replaces `TemporalManager.get_previous_input(n)`. Used by scheduler to break graph cycles. |

#### FrameAccumulatorNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `decay`: ControlSignal (optional, default=0.95) |
| **Output ports** | `video_out`: VideoFrame |
| **State** | Accumulated float32 buffer |
| **Latency budget** | 2ms |
| **Maps from** | New component. Accumulates frames with exponential decay: `acc = acc * decay + frame * (1 - decay)`. Creates trail/echo effects. |

### 2.7 Output Nodes

Output nodes consume data and write to external sinks.

#### NotebookPreviewSink

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `render_in`: RenderFrame (required) |
| **Output ports** | (none) |
| **State** | IPython display handle |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/outputs/notebook_preview_sink.py` -- `NotebookPreviewSink` |

#### FfmpegUdpSink

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `render_in`: RenderFrame (required) |
| **Output ports** | (none) |
| **State** | FFmpeg subprocess, UDP socket |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/outputs/udp.py` -- `FfmpegUdpOutput` |

#### CompositeOutputSinkNode

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `render_in`: RenderFrame (required) |
| **Output ports** | (none) |
| **State** | List of child output sinks |
| **Latency budget** | 1ms (delegates to children) |
| **Maps from** | `adapters/outputs/composite.py` -- `CompositeOutputSink` |

#### PreviewSinkNode

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `render_in`: RenderFrame (required) |
| **Output ports** | (none) |
| **State** | Display window handle |
| **Latency budget** | 3ms |
| **Maps from** | `adapters/outputs/preview_sink.py` -- `PreviewSink` |

#### AsciiRecorderSinkNode

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `render_in`: RenderFrame (required) |
| **Output ports** | (none) |
| **State** | File handle, frame counter |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/outputs/ascii_recorder.py` -- `AsciiRecorderSink` |

#### AnalysisOutputNode (new -- Phase 1)

| Property | Value |
|----------|-------|
| **Category** | output |
| **Input ports** | `analysis_in`: AnalysisData (required) |
| **Output ports** | (none) |
| **State** | OSC/WebSocket connection |
| **Latency budget** | 1ms |
| **Maps from** | New component. Sends analysis data (face landmarks, hand positions) to external tools via OSC/WebSocket. |

### 2.8 Tracking Nodes

#### ObjectTrackerNode

| Property | Value |
|----------|-------|
| **Category** | processor |
| **Input ports** | `video_in`: VideoFrame, `analysis_in`: AnalysisData (required) |
| **Output ports** | `video_out`: VideoFrame (passthrough), `tracking_out`: AnalysisData (enriched with tracking IDs + trajectories) |
| **State** | Kalman filters per tracked object, trajectory history |
| **Latency budget** | 2ms |
| **Maps from** | `adapters/trackers/` -- `TrackingPipeline` (wraps existing tracking logic) |

### 2.9 Control Nodes (new -- Phase 3)

Control nodes generate and transform ControlSignal values for parameter modulation.

#### LFONode

| Property | Value |
|----------|-------|
| **Category** | control |
| **Input ports** | `rate`: ControlSignal (optional, modulates frequency), `trigger`: Trigger (optional, resets phase) |
| **Output ports** | `signal_out`: ControlSignal |
| **State** | Phase accumulator, waveform type (sine/saw/square/triangle/noise) |
| **Latency budget** | <1ms |
| **Maps from** | New component. Inspired by TD LFO CHOP and OF ofxPDSP oscillators. |

**Parameters (set on node, not via ports):**
- `waveform`: enum (sine, saw, square, triangle, noise)
- `frequency`: float Hz (0.01 - 30.0)
- `amplitude`: float (0.0 - 1.0)
- `offset`: float (0.0 - 1.0)

#### EnvelopeNode

| Property | Value |
|----------|-------|
| **Category** | control |
| **Input ports** | `trigger`: Trigger (required) |
| **Output ports** | `signal_out`: ControlSignal |
| **State** | Current phase (attack/decay/sustain/release), current value |
| **Latency budget** | <1ms |
| **Maps from** | New component. ADSR envelope generator. |

**Parameters:**
- `attack`: float seconds (0.001 - 5.0)
- `decay`: float seconds (0.001 - 5.0)
- `sustain`: float level (0.0 - 1.0)
- `release`: float seconds (0.001 - 10.0)

#### MapNode

| Property | Value |
|----------|-------|
| **Category** | control |
| **Input ports** | `signal_in`: ControlSignal (required) |
| **Output ports** | `signal_out`: ControlSignal |
| **State** | None |
| **Latency budget** | <1ms |
| **Maps from** | New component. Range mapping with optional easing curve. |

**Parameters:**
- `in_min`, `in_max`: input range (default 0.0, 1.0)
- `out_min`, `out_max`: output range (default 0.0, 1.0)
- `curve`: easing function (linear, ease_in, ease_out, ease_in_out, exponential)
- `clamp`: bool (default true)

#### SmoothNode

| Property | Value |
|----------|-------|
| **Category** | control |
| **Input ports** | `signal_in`: ControlSignal (required) |
| **Output ports** | `signal_out`: ControlSignal |
| **State** | Previous smoothed value |
| **Latency budget** | <1ms |
| **Maps from** | New component. Low-pass filter / exponential moving average. Inspired by TD Lag CHOP. |

**Parameters:**
- `lag_up`: float seconds (rise time)
- `lag_down`: float seconds (fall time)

#### AnalysisToControlNode

| Property | Value |
|----------|-------|
| **Category** | control |
| **Input ports** | `analysis_in`: AnalysisData (required) |
| **Output ports** | `signal_out`: ControlSignal |
| **State** | None |
| **Latency budget** | <1ms |
| **Maps from** | New component. Extracts a numeric value from analysis data and outputs as ControlSignal. |

**Parameters:**
- `key_path`: dot-separated path into analysis dict (e.g., `"audio.bass_energy"`, `"face.confidence"`)
- `default`: float (value when key is missing)

### 2.10 Node Summary Table

| # | Node | Category | Phase | New/Wrapped |
|---|------|----------|-------|-------------|
| 1 | CameraSource | source | 0 | wrapped |
| 2 | VideoFileSource | source | 0 | wrapped |
| 3 | AudioSource | source | 3 | new |
| 4 | OSCReceiver | source | 3 | new |
| 5 | MIDIReceiver | source | 3 | new |
| 6 | FaceAnalyzer | analyzer | 0 | wrapped |
| 7 | HandAnalyzer | analyzer | 0 | wrapped |
| 8 | PoseAnalyzer | analyzer | 0 | wrapped |
| 9 | HandGestureAnalyzer | analyzer | 0 | wrapped |
| 10 | ObjectDetectionAnalyzer | analyzer | 0 | wrapped |
| 11 | EmotionAnalyzer | analyzer | 0 | wrapped |
| 12 | PoseSkeletonAnalyzer | analyzer | 0 | wrapped |
| 13 | SegmentationAnalyzer | analyzer | 0 | wrapped |
| 14 | AudioAnalyzer | analyzer | 3 | new |
| 15-34 | All 20 filter nodes | processor | 0 | wrapped |
| 35 | AsciiRendererNode | renderer | 0 | wrapped |
| 36 | PassthroughRendererNode | renderer | 0 | wrapped |
| 37 | LandmarksOverlayRendererNode | renderer | 0 | wrapped |
| 38 | CppDeformedRendererNode | renderer | 0 | wrapped |
| 39 | CompositeNode | processor | 1 | new |
| 40 | RenderFrameCompositeNode | processor | 1 | new |
| 41 | MosaicFilterNode | processor | 1 | new |
| 42 | FeedbackNode | processor | 2 | new |
| 43 | DelayNode | processor | 2 | new |
| 44 | FrameAccumulatorNode | processor | 2 | new |
| 45 | NotebookPreviewSink | output | 0 | wrapped |
| 46 | FfmpegUdpSink | output | 0 | wrapped |
| 47 | CompositeOutputSinkNode | output | 0 | wrapped |
| 48 | PreviewSinkNode | output | 0 | wrapped |
| 49 | AsciiRecorderSinkNode | output | 0 | wrapped |
| 50 | AnalysisOutputNode | output | 1 | new |
| 51 | ObjectTrackerNode | processor | 0 | wrapped |
| 52 | LFONode | control | 3 | new |
| 53 | EnvelopeNode | control | 3 | new |
| 54 | MapNode | control | 3 | new |
| 55 | SmoothNode | control | 3 | new |
| 56 | AnalysisToControlNode | control | 3 | new |

**Phase 0 total:** 38 wrapped nodes (zero adapter code changes)
**Phase 1 total:** +4 new nodes (composition)
**Phase 2 total:** +3 new nodes (temporal/feedback)
**Phase 3 total:** +11 new nodes (control signals, audio)

---

## 3. Port Type Specification

### 3.1 Port Type Enum

```python
class PortType(Enum):
    VIDEO_FRAME = "video_frame"
    AUDIO_BUFFER = "audio_buffer"
    ANALYSIS_DATA = "analysis_data"
    CONTROL_SIGNAL = "control_signal"
    MASK = "mask"
    TRIGGER = "trigger"
    TEXT = "text"
    RENDER_FRAME = "render_frame"
    CONFIG = "config"
```

### 3.2 Data Contracts per Port Type

#### VideoFrame

| Property | Value |
|----------|-------|
| **Python type** | `numpy.ndarray` |
| **Shape** | `(height, width, 3)` |
| **Dtype** | `uint8` |
| **Color space** | BGR (OpenCV convention, per `DESIGN_RULES.md`) |
| **Memory layout** | C-contiguous (`ndarray.flags['C_CONTIGUOUS'] == True`) |
| **Ownership** | Producer owns. Downstream consumers receive read-only views. If a node needs to modify the frame, it must copy first. |

**Validation rule (checked at connection time, not per-frame):**
```python
def validate_video_frame(arr: np.ndarray) -> bool:
    return (arr.ndim == 3 and arr.shape[2] == 3 and
            arr.dtype == np.uint8 and arr.flags['C_CONTIGUOUS'])
```

#### AudioBuffer

| Property | Value |
|----------|-------|
| **Python type** | `numpy.ndarray` |
| **Shape** | `(samples,)` or `(samples, channels)` |
| **Dtype** | `float32` |
| **Range** | -1.0 to 1.0 |
| **Sample rate** | Carried in metadata, not in the array (typically 44100 or 48000) |
| **Ownership** | Producer owns. Consumers receive read-only views. |

#### AnalysisData

| Property | Value |
|----------|-------|
| **Python type** | `dict` |
| **Schema** | Keys are strings identifying the analysis type (`"face"`, `"hands"`, `"pose"`, `"tracking"`, `"audio"`, etc.). Values are dicts or domain dataclass instances (`FaceAnalysis`, `HandAnalysis`, etc.). |
| **Merging** | When multiple AnalysisData ports fan-in to a single input, they are merged with `dict.update()`. Later connections overwrite earlier ones for the same key. This is deterministic because execution order is determined by topological sort. |
| **Ownership** | Read-only. Analysis data must not be mutated by consumers. |

**Fan-in merge strategy:** When an input port receives AnalysisData from multiple connected output ports, the merge happens by dict merge in topological order:
```python
merged = {}
for source in connected_sources_in_topo_order:
    merged.update(source_output)
```

#### ControlSignal

| Property | Value |
|----------|-------|
| **Python type** | `float` |
| **Range** | 0.0 to 1.0 (normalized) |
| **Semantic** | A single continuous parameter value. Updated every frame. |
| **Default** | Each input port declares its own default (used when unconnected). |
| **Interpolation** | When a control signal source updates at a lower rate than the graph framerate, the scheduler linearly interpolates between the last two values. |

#### Mask

| Property | Value |
|----------|-------|
| **Python type** | `numpy.ndarray` |
| **Shape** | `(height, width)` |
| **Dtype** | `uint8` (0-255, where 255 = fully selected) or `bool` |
| **Ownership** | Producer owns, consumers get read-only views. |

#### Trigger

| Property | Value |
|----------|-------|
| **Python type** | `bool` |
| **Semantic** | `True` on the frame the event occurs, `False` otherwise. Edge-triggered (one-shot). |
| **Use cases** | Beat detected, gesture recognized, threshold crossed. |

**Compatibility note:** Trigger is compatible with ControlSignal inputs. `True` maps to `1.0`, `False` maps to `0.0`.

#### Text

| Property | Value |
|----------|-------|
| **Python type** | `str` |
| **Encoding** | UTF-8 |
| **Use cases** | ASCII art lines, metadata strings, OSC addresses. |

#### RenderFrame

| Property | Value |
|----------|-------|
| **Python type** | `domain.types.RenderFrame` (dataclass) |
| **Fields** | `image: PIL.Image.Image`, `text: Optional[str]`, `lines: Optional[List[str]]`, `metadata: Optional[Dict[str, object]]` |
| **Color space** | RGB (PIL convention -- note: different from VideoFrame's BGR) |
| **Ownership** | Producer owns. Consumers must not mutate the PIL Image in-place. |

#### Config

| Property | Value |
|----------|-------|
| **Python type** | `domain.config.EngineConfig` or `dict` |
| **Semantic** | Static configuration that changes infrequently (not every frame). |
| **Update rate** | Config changes are queued and applied between frames, never mid-frame. |

### 3.3 Compatibility Matrix

```
Connection: Output Type -> Input Type

                  VIDEO  AUDIO  ANALYSIS  CONTROL  MASK  TRIGGER  TEXT  RENDER  CONFIG
VIDEO_FRAME    ->  [Y]    .       .        .        .      .       .     .       .
AUDIO_BUFFER   ->   .    [Y]      .        .        .      .       .     .       .
ANALYSIS_DATA  ->   .     .      [Y]       .        .      .       .     .       .
CONTROL_SIGNAL ->   .     .       .       [Y]       .      .       .     .       .
MASK           ->   .     .       .        .       [Y]     .       .     .       .
TRIGGER        ->   .     .       .       [Y]*     .      [Y]      .     .       .
TEXT           ->   .     .       .        .        .      .      [Y]    .       .
RENDER_FRAME   ->   .     .       .        .        .      .       .    [Y]      .
CONFIG         ->   .     .       .        .        .      .       .     .      [Y]

[Y] = compatible    . = incompatible
[Y]* = Trigger->ControlSignal is auto-converted (True->1.0, False->0.0)
```

Cross-type connections require explicit converter nodes. Planned converters:
- `VideoToMask` (threshold-based)
- `MaskToControlSignal` (area fraction)
- `AnalysisToControl` (extract numeric field)

### 3.4 Memory Semantics

| Semantic | When Used | Rule |
|----------|-----------|------|
| **Owned** | Producer creates data | Only one reference. Producer must not use after passing to scheduler. |
| **Shared read-only** | Fan-out (one output -> multiple inputs) | All downstream nodes receive `ndarray.flags.writeable = False` views. Zero-copy. |
| **Copy-on-write** | Node needs to modify shared data | Node calls `frame.copy()` before modification. Node owns the copy. |

**Fan-out zero-copy protocol:**
```python
# Scheduler, after node produces output:
output = node.process(inputs)
video = output["video_out"]
video.flags.writeable = False  # Mark as read-only

# Each downstream node receives the same ndarray view
# If a downstream node needs to modify, it must copy:
def process(self, inputs):
    frame = inputs["video_in"]
    if not frame.flags.writeable:
        frame = frame.copy()  # Copy-on-write
    # Now safe to modify frame
```

**Memory pool (Phase 4 optimization):**
```
Pool Design:
- Pre-allocate N frames of (H, W, 3) uint8 where H, W come from source resolution
- Pool size: 2 * (number of nodes that produce VideoFrame) + temporal buffer depth
- High watermark: 3x base count (grow on demand)
- Low watermark: 1.5x base count (shrink after 60 idle frames)
- Allocation: node requests frame from pool -> gets zeroed buffer or new allocation
- Release: scheduler returns buffer to pool after all consumers have read it
- Reference counting: each buffer tracks number of active readers
```

---

## 4. Graph Examples

### 4.1 Mosaic + ASCII Composition

The original use case that triggered this migration. Currently impossible in the linear pipeline.

```
                                    +------------------+
                                    |  MosaicFilter    |
                                +-->|  block_size=8    |---+
                                |   +------------------+   |
+----------------+   video_out  |                          |  video_a   +------------------+   render_out   +-------------------+
|  CameraSource  |-------------+                           +----------->|  CompositeNode   |-------------->|  AsciiRenderer    |----> render_out
|                |             |                           +----------->|  mode=overlay    |               |  grid=80x40       |
+----------------+             |                          |  video_b   +------------------+               +-------------------+
                               |   +------------------+   |                                                        |
                               +-->|  PassthroughNode |---+                                                        v
                                   |  (identity)      |                                                   +-------------------+
                                   +------------------+                                                   | NotebookPreview   |
                                                                                                          +-------------------+
```

**What this achieves:** The camera frame is split (fan-out). One path pixelates via MosaicFilter. The other passes through unchanged. CompositeNode blends them (mosaic on top of original with alpha). The blended result is rendered as ASCII art and sent to the notebook preview.

**Why this is impossible today:** The `PipelineOrchestrator` processes one frame through one filter chain to one renderer. There is no fan-out from the source and no composition before the renderer.

### 4.2 Audio-Reactive Filter Chain

Audio analysis drives visual filter parameters in real-time.

```
+----------------+                +------------------+     bass_energy    +------------------+
|  AudioSource   |--audio_out--->|  AudioAnalyzer   |---analysis_out--->| AnalysisToControl|--signal_out-+
|  (microphone)  |               |  (FFT + beats)   |                   | key="audio.bass" |             |
+----------------+               +------------------+                   +------------------+             |
                                                                                                         |
                                        +------------------+                                             |
                                        |  SmoothNode      |<---signal_in----+                           |
                                        |  lag_up=0.05     |                 |                           |
                                        |  lag_down=0.3    |             +---+------+                    |
                                        +--------+---------+             | MapNode  |<--signal_in--------+
                                                 |                       | 0-1->0-1 |
                                            signal_out                   | curve=exp|
                                                 |                       +----------+
                                                 v
+----------------+             +------------------+--intensity--+        +------------------+   +-------------------+
|  CameraSource  |--video_out->|  CRTGlitchFilter |             |------->| AsciiRenderer    |-->| NotebookPreview   |
|                |             |  (audio-reactive) |  video_out  |        |                  |   |                   |
+----------------+             +------------------+--------------+        +------------------+   +-------------------+
```

**What this achieves:** Microphone audio is analyzed for bass energy. The bass energy value (0-1) is mapped through an exponential curve and smoothed to prevent jitter. The smoothed signal controls the CRT glitch filter's intensity. When bass hits, the visual distortion increases; when bass fades, the distortion smoothly decays.

**Why this is impossible today:** There is no audio input, no control signal mechanism, and no way for external data to modulate filter parameters per-frame. Filter parameters are static in `EngineConfig`.

### 4.3 Feedback Trail Effect

Frame feedback with transform accumulation creates visual trails.

```
                                    +-------------------+
                              +---->|  FrameAccumulator |
                              |     |  decay=0.92       |---video_out---+
                              |     +-------------------+               |
+----------------+  video_out |                                         |  video_a
|  CameraSource  |-----------+                                         v
|                |            |                               +------------------+    +------------------+    +-------------------+
+----------------+            +------------------------------>| CompositeNode    |--->|  AsciiRenderer   |--->| NotebookPreview   |
                                                  video_b     | mode=additive    |    |                  |    |                   |
                                                              +------------------+    +------------------+    +-------------------+
```

**How feedback works:** The FrameAccumulatorNode maintains an internal buffer. Each frame, it blends the new input with the accumulated buffer using exponential decay (`acc = acc * 0.92 + input * 0.08`). The accumulated result (which contains fading history of previous frames) is composited additively with the live camera feed. The result is motion trails that fade over time.

**Alternative with explicit feedback loop (Phase 2):**

```
+----------------+                +------------------+     +------------------+    +-------------------+
|  CameraSource  |--video_out-+->| CompositeNode    |---->|  AsciiRenderer   |--->| NotebookPreview   |
|                |             |  | mode=alpha 0.3   |     |                  |    |                   |
+----------------+             |  +----+-------------+     +------------------+    +-------------------+
                               |       ^ video_b
                               |       |
                               |  +----+-------------+     +------------------+
                               |  |  FeedbackNode    |<----|  FadeNode        |
                               |  |  (1-frame delay) |     |  level=0.92      |
                               |  +------------------+     +----+-------------+
                               |                                 ^
                               +---------------------------------+
                                              video_in (cycle -- broken by FeedbackNode's 1-frame delay)
```

The scheduler detects the cycle: CompositeNode -> FadeNode -> FeedbackNode -> CompositeNode. The FeedbackNode's 1-frame delay breaks the cycle for topological sort. On frame N, FeedbackNode outputs frame N-1's CompositeNode result (faded).

### 4.4 Multi-Analyzer Fan-Out

Parallel perception with merged results feeding downstream filters.

```
                               +--------------------+
                          +--->|   FaceAnalyzer     |---analysis_out---+
                          |    +--------------------+                  |
                          |                                            |
                          |    +--------------------+                  |    +---------------------+
+----------------+  video |    |   HandAnalyzer     |---analysis_out---+--->| AnalysisData Merge  |---analysis_out
|  CameraSource  |--------+--->|                    |                  |    | (implicit fan-in)   |
|                |  out   |    +--------------------+                  |    +----------+----------+
+----------------+        |                                            |               |
                          |    +--------------------+                  |               v
                          +--->|   PoseAnalyzer     |---analysis_out---+    +---------------------+
                          |    +--------------------+                       |   BoidsFilter       |
                          |                                                 |   (uses face+hands) |
                          |                                                 +----------+----------+
                          +-----video_out (passthrough from any analyzer)              |
                                         |                                             |
                                         v                                        video_out
                          +--------------------+                                       |
                          |   (video merge:    |<--------------------------------------+
                          |    first policy)   |
                          +--------+-----------+
                                   |
                                   v
                          +--------------------+     +-------------------+
                          |  AsciiRenderer     |---->| NotebookPreview   |
                          +--------------------+     +-------------------+
```

**Execution:** The scheduler detects that FaceAnalyzer, HandAnalyzer, and PoseAnalyzer are independent (all read from the same CameraSource output, none depends on another). They execute in parallel (same batch). Their analysis outputs fan-in to BoidsFilter's `analysis_in` port via dict merge. The video passthrough from any analyzer (they all pass through the same frame unchanged) feeds the filter's `video_in`.

**What this achieves:** Three perception models run in parallel, their results are merged, and a single filter uses all three. Today, analyzers run sequentially in `AnalyzerPipeline`, and the merged dict is an untyped bag.

**Performance gain:** If FaceAnalyzer takes 8ms, HandAnalyzer takes 6ms, and PoseAnalyzer takes 8ms, the current sequential pipeline takes 22ms for perception. With parallel execution, it takes max(8, 6, 8) = 8ms -- a 2.75x speedup.

### 4.5 Full Production Setup

Camera + perception + filters + dual render (ASCII + passthrough) + dual output (preview + stream).

```
                                                +--------------------+
                                           +--->|   FaceAnalyzer     |---analysis_out---+
                                           |    +--------------------+                  |
+----------------+   video    +----------+ |                                            |
|  CameraSource  |---------->| Splitter |-+--->+--------------------+                   |
|  (webcam)      |           | (fan-out)| |    |   PoseAnalyzer     |---analysis_out---+|
+----------------+           +----------+ |    +--------------------+                  ||
                                          |                                            ||
                                          |    +--------------------+                  ||
+----------------+   control              +--->|   EdgeFilter       |<-analysis_in------+|
|  OSCReceiver   |--signal-->+                 +--------+-----------+                   |
|  (/glitch/int) |           |                          |video_out                      |
+----------------+           |                          v                               |
                             |                 +--------------------+                   |
                             +---intensity---->|  CRTGlitchFilter   |                   |
                                               +--------+-----------+                   |
                                                        |video_out                      |
                                                        v                               |
                                               +--------------------+                   |
                                               |  BoidsFilter       |<--analysis_in-----+
                                               +--------+-----------+
                                                        |video_out
                                                        |
                                          +-------------+-------------+
                                          |                           |
                                          v                           v
                                 +------------------+       +------------------+
                                 | AsciiRenderer    |       | PassthroughRend  |
                                 | (80x40 grid)     |       | (1280x720)       |
                                 +--------+---------+       +--------+---------+
                                          |render_out                |render_out
                                          v                          v
                                 +------------------+       +------------------+
                                 | NotebookPreview  |       | FfmpegUdpSink    |
                                 | (local display)  |       | (network stream) |
                                 +------------------+       +------------------+
```

**What this achieves:** A full production pipeline where:
1. Camera captures frames
2. Face and Pose analyzers run in parallel
3. Edge, CRT Glitch, and Boids filters run sequentially, each using analysis data
4. CRT Glitch intensity is controlled via OSC from an external device (tablet, phone)
5. The filtered result is rendered BOTH as ASCII art (for local preview) AND as passthrough video (for network streaming via FFmpeg/UDP)
6. Two independent outputs: notebook preview and UDP stream

**Why this is impossible today:** Single renderer, single output sink, no OSC input, no parallel analyzers, no fan-out after filtering.

---

## 5. Execution Model

### 5.1 Hybrid Push-Pull Scheduler

The scheduler uses a **hybrid push-pull** model as recommended by the reference systems analysis:

- **Push from sources:** Source nodes produce frames at their native rate (camera FPS or video file FPS). The scheduler pushes data forward through the graph.
- **Pull via lazy evaluation:** Branches of the graph that have no active output sink are marked dormant and skipped. If a NotebookPreviewSink is disabled, the entire branch leading exclusively to it is not executed.

```
SCHEDULER ALGORITHM (per frame):

1. PREPARATION (once per graph change, cached):
   a. Build adjacency list from all connections
   b. Detect cycles -> insert implicit DelayNode on each back-edge
   c. Topological sort -> ordered node list
   d. Group into parallel batches:
      Batch 0: all source nodes
      Batch 1: nodes whose inputs come only from Batch 0
      Batch N: nodes whose inputs come only from Batches 0..N-1
   e. Mark dormant branches (no active output sink downstream)

2. PER-FRAME EXECUTION:
   a. for each batch (in order):
        for each non-dormant node in batch (parallel if independent):
            collect inputs from upstream connections
            call node.process(inputs)
            store outputs in edge buffers
            if node has ControlSignal inputs with no connection:
                use declared default value
   b. for each FeedbackNode/DelayNode:
        swap read/write buffers (current output becomes next frame's input)
   c. release all edge buffers that have no remaining readers (return to pool)
   d. emit per-node timing to LoopProfiler

3. BETWEEN FRAMES:
   a. Apply queued graph modifications (add/remove node, add/remove connection)
   b. If graph changed: re-run PREPARATION step 1
   c. Check for dormant branch changes
```

### 5.2 Topological Sort with Cycle Detection

```python
def topological_sort_with_cycle_detection(nodes, edges):
    """
    Kahn's algorithm with cycle detection.

    If a cycle is detected, the back-edge is identified and an implicit
    DelayNode is inserted to break it. The sort is then retried.

    Returns:
        sorted_nodes: List[Node] in execution order
        inserted_delays: List[DelayNode] that were added to break cycles
    """
    in_degree = {node: 0 for node in nodes}
    for src, dst in edges:
        in_degree[dst] += 1

    queue = [n for n in nodes if in_degree[n] == 0]
    sorted_nodes = []
    inserted_delays = []

    while queue:
        node = queue.pop(0)
        sorted_nodes.append(node)
        for neighbor in get_downstream(node, edges):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_nodes) != len(nodes):
        # Cycle detected. Find back-edge and insert delay.
        cycle_nodes = [n for n in nodes if in_degree[n] > 0]
        back_edge = find_back_edge(cycle_nodes, edges)
        delay = DelayNode(name=f"_implicit_delay_{len(inserted_delays)}")
        edges = insert_delay_on_edge(back_edge, delay, edges)
        nodes.append(delay)
        inserted_delays.append(delay)
        # Retry sort with delay inserted
        return topological_sort_with_cycle_detection(nodes, edges)

    return sorted_nodes, inserted_delays
```

### 5.3 Parallel Batch Execution

After topological sort, nodes are grouped into execution batches. Nodes within the same batch have no data dependencies on each other and can execute in parallel.

```
BATCH GROUPING:

Given topological order [A, B, C, D, E, F, G]:

If edges are: A->C, A->D, B->D, C->E, D->E, E->F, E->G

Batches:
  Batch 0: [A, B]     -- sources, no dependencies
  Batch 1: [C, D]     -- depend only on Batch 0
  Batch 2: [E]        -- depends on Batch 1
  Batch 3: [F, G]     -- depend only on Batch 2

Execution:
  Batch 0: A and B execute in parallel (ThreadPoolExecutor)
  Batch 1: C and D execute in parallel
  Batch 2: E executes alone
  Batch 3: F and G execute in parallel
```

**Thread pool:** `concurrent.futures.ThreadPoolExecutor(max_workers=cpu_count - 1)`. GIL note: most filter work happens in C++ (OpenCV, numpy) which releases the GIL. Pure Python nodes benefit from I/O parallelism. True CPU parallelism for pure Python nodes would require `ProcessPoolExecutor` but the serialization overhead is too high for per-frame execution.

### 5.4 Memory Pool Design

```
FRAME POOL:

class FramePool:
    """Pre-allocated pool of numpy arrays for VideoFrame buffers."""

    def __init__(self, height: int, width: int, initial_count: int = 16):
        self._shape = (height, width, 3)
        self._dtype = np.uint8
        self._pool: List[np.ndarray] = []
        self._in_use: Set[int] = set()  # ids of buffers currently in use
        self._ref_counts: Dict[int, int] = {}  # id -> reader count
        self._lock = threading.Lock()

        # Pre-allocate
        for _ in range(initial_count):
            buf = np.empty(self._shape, dtype=self._dtype)
            self._pool.append(buf)

    def acquire(self) -> np.ndarray:
        """Get a frame buffer from the pool. Allocates if pool is empty."""
        with self._lock:
            if self._pool:
                buf = self._pool.pop()
            else:
                buf = np.empty(self._shape, dtype=self._dtype)
            self._in_use.add(id(buf))
            self._ref_counts[id(buf)] = 0
            return buf

    def add_reader(self, buf: np.ndarray) -> None:
        """Increment reader count for fan-out."""
        with self._lock:
            self._ref_counts[id(buf)] += 1

    def release_reader(self, buf: np.ndarray) -> None:
        """Decrement reader count. Return to pool when no readers remain."""
        with self._lock:
            bid = id(buf)
            self._ref_counts[bid] -= 1
            if self._ref_counts[bid] <= 0:
                buf.flags.writeable = True  # Reset for reuse
                self._pool.append(buf)
                self._in_use.discard(bid)
                del self._ref_counts[bid]

    def resize(self, height: int, width: int) -> None:
        """Handle resolution change: clear pool, update shape."""
        with self._lock:
            self._shape = (height, width, 3)
            self._pool.clear()
            # In-use buffers will be returned naturally

WATERMARK POLICY:
- High watermark: 3 * base_count -> stop pre-allocating, let pool shrink
- Low watermark: 1.5 * base_count -> pre-allocate to fill
- Shrink trigger: if pool size > high watermark for 60 consecutive frames, discard half
```

### 5.5 Thread Model

```
THREAD ALLOCATION:

1. MAIN THREAD (graph scheduler)
   - Orchestrates frame loop
   - Dispatches batches to worker pool
   - Handles graph modification queue
   - Emits events to EventBus

2. WORKER POOL (ThreadPoolExecutor, size = cpu_count - 1)
   - Executes node.process() calls
   - One task per non-trivial node per batch
   - Trivial nodes (LFO, Map, identity) execute inline on main thread

3. SOURCE THREAD (one per source node)
   - Camera capture runs on dedicated thread (existing pattern in OpenCVCameraSource)
   - Audio capture on dedicated thread (callback-based via sounddevice)
   - Frame delivered to scheduler via thread-safe queue

4. OUTPUT THREADS (one per output sink)
   - Network I/O (UDP streaming) on dedicated thread
   - File I/O (recording) on dedicated thread
   - Notebook display on main thread (IPython requirement)

SYNCHRONIZATION:
- Frame barrier: all nodes in a batch must complete before next batch starts
  Implementation: concurrent.futures.wait(batch_futures, return_when=ALL_COMPLETED)
- Edge buffers: single-producer single-consumer pattern (no lock needed)
- Feedback edges: double-buffered (scheduler swaps atomically between frames)
- Graph modification queue: threading.Queue, drained between frames
- Config updates: copy-on-write EngineConfig, swapped atomically via reference
```

### 5.6 Error Isolation

```
PER-NODE ERROR HANDLING:

try:
    outputs = node.process(inputs)
except Exception as e:
    logger.error(f"Node {node.name} failed: {e}")
    event_bus.emit(NodeErrorEvent(node.name, e))

    # Error recovery strategy per port type:
    outputs = {}
    for port in node.get_output_ports():
        if port.data_type == PortType.VIDEO_FRAME:
            # Pass through input video unchanged
            outputs[port.name] = inputs.get("video_in", black_frame)
        elif port.data_type == PortType.ANALYSIS_DATA:
            outputs[port.name] = {}  # Empty analysis
        elif port.data_type == PortType.CONTROL_SIGNAL:
            outputs[port.name] = port.default_value  # Use default
        elif port.data_type == PortType.RENDER_FRAME:
            outputs[port.name] = error_render_frame  # Red "ERROR" frame
        else:
            outputs[port.name] = None  # Skip

    # Node stays in graph. Will retry next frame.
    # After N consecutive failures, node is auto-disabled with warning.
    node._error_count += 1
    if node._error_count >= MAX_CONSECUTIVE_ERRORS:
        node.enabled = False
        logger.warning(f"Node {node.name} disabled after {MAX_CONSECUTIVE_ERRORS} consecutive errors")

MAX_CONSECUTIVE_ERRORS = 30  # 1 second at 30fps
```

---

## 6. Migration Plan

### Phase 0: Compatibility Layer (No Breaking Changes)

**Goal:** Execute the current linear pipeline as a graph internally. Zero behavioral changes. All 38 existing components wrapped as nodes without code changes. All existing tests pass.

**What changes:**
- New module: `application/graph/` containing `node.py`, `port.py`, `connection.py`, `graph.py`, `scheduler.py`, `node_adapter.py`
- `GraphBuilder` constructs the current linear pipeline as a graph
- `GraphScheduler` executes the graph identically to current `PipelineOrchestrator`
- `StreamEngine` gets a `use_graph=False` flag (default off) for opt-in

**What stays the same:**
- All existing adapters -- zero changes
- `PipelineOrchestrator` -- still exists, still the default
- All public APIs -- unchanged
- All existing tests -- unchanged and passing

**Compatibility guarantees:**
- `StreamEngine` with `use_graph=False` (default): identical to today
- `StreamEngine` with `use_graph=True`: same output frames, same timing (within 1ms)
- All 19 filters, 4 renderers, 8 analyzers, 2 sources, 5 outputs work without modification

**Files to create:**

| File | Purpose |
|------|---------|
| `application/graph/__init__.py` | Package init |
| `application/graph/node.py` | `Node` protocol, `InputPort`, `OutputPort` dataclasses |
| `application/graph/port.py` | `PortType` enum, validation functions |
| `application/graph/connection.py` | `Connection` dataclass (source node+port -> dest node+port) |
| `application/graph/graph.py` | `Graph` class: nodes, connections, add/remove, validate |
| `application/graph/scheduler.py` | `GraphScheduler`: topological sort, batch execution, frame loop |
| `application/graph/node_adapter.py` | `FilterNodeAdapter`, `AnalyzerNodeAdapter`, `RendererNodeAdapter`, `SourceNodeAdapter`, `OutputNodeAdapter` -- wraps existing adapters as nodes |
| `application/graph/graph_builder.py` | `GraphBuilder`: constructs current linear pipeline as graph |

**Files to modify:**

| File | Change |
|------|--------|
| `application/engine.py` | Add `use_graph: bool` parameter, delegate to `GraphScheduler` when True |

**Test strategy:**
1. Create `tests/test_graph_core.py`: unit tests for Node, Port, Connection, Graph
2. Create `tests/test_graph_scheduler.py`: unit tests for topological sort, batch grouping, execution
3. Create `tests/test_graph_adapter.py`: verify each wrapped adapter produces identical output
4. Create `tests/test_graph_parity.py`: integration test that runs the same input through both `PipelineOrchestrator` and `GraphScheduler`, asserts frame-identical output

**Parity test approach:**
```python
def test_graph_parity():
    """Graph scheduler produces identical frames to PipelineOrchestrator."""
    source = DummySource(frames=test_frames)
    renderer = AsciiRenderer()
    sink_a = CaptureSink()
    sink_b = CaptureSink()

    # Run with PipelineOrchestrator
    engine_a = StreamEngine(source, renderer, sink_a, config, use_graph=False)
    engine_a.run(num_frames=10)

    # Run with GraphScheduler
    source.reset()
    engine_b = StreamEngine(source, renderer, sink_b, config, use_graph=True)
    engine_b.run(num_frames=10)

    # Assert identical output
    for frame_a, frame_b in zip(sink_a.captured, sink_b.captured):
        assert frame_a.image == frame_b.image
        assert frame_a.text == frame_b.text
```

**Rollback plan:** Remove `use_graph` flag and `application/graph/` directory. Zero impact on existing code.

**Estimated effort:** 2-3 weeks

---

### Phase 1: Enable Branching and Composition

**Goal:** Allow multiple renderers in parallel, fan-out from any node, and composition of multiple video streams. This is the phase that solves the Mosaic + ASCII use case.

**What changes:**
- New nodes: `CompositeNode`, `RenderFrameCompositeNode`, `MosaicFilterNode`, `AnalysisOutputNode`
- `GraphBuilder` gets new methods: `add_branch()`, `add_composite()`, `fan_out()`
- `GraphScheduler` supports fan-out (read-only sharing) and fan-in (merge strategy)
- New public API: `StreamEngine.build_graph()` for programmatic graph construction

**What stays the same:**
- All Phase 0 wrapped nodes -- no changes
- `PipelineOrchestrator` -- still exists as fallback
- Linear pipeline construction -- still works identically
- Domain, ports, infrastructure layers -- untouched

**Compatibility guarantees:**
- Linear pipeline graphs produce identical results to Phase 0
- New composition features are additive (opt-in)
- Existing `StreamEngine` API unchanged (new methods are additions)

**Files to create:**

| File | Purpose |
|------|---------|
| `adapters/processors/filters/mosaic.py` | `MosaicFilter` adapter (pixelation effect) |
| `application/graph/composite_node.py` | `CompositeNode` with blend modes |
| `application/graph/render_composite_node.py` | `RenderFrameCompositeNode` |

**Files to modify:**

| File | Change |
|------|--------|
| `application/graph/scheduler.py` | Add fan-out (read-only view sharing), fan-in (merge strategy dispatch) |
| `application/graph/graph.py` | Add validation for fan-in merge strategy, connection multiplicity |
| `application/graph/graph_builder.py` | Add `add_branch()`, `add_composite()`, `fan_out()` |
| `application/engine.py` | Add `build_graph()` method returning a `GraphBuilder` |
| `adapters/processors/filters/__init__.py` | Add `MosaicFilter` to exports |
| `presentation/notebook_api.py` | Add `build_mosaic_ascii_panel()` convenience function |

**Test strategy:**
1. `test_composite_node.py`: unit test blend modes with known input/expected output
2. `test_fan_out.py`: verify fan-out produces read-only views, no frame copies
3. `test_fan_in.py`: verify AnalysisData merge produces correct merged dict
4. `test_mosaic_ascii.py`: integration test for the mosaic+ASCII composition graph
5. `test_dual_output.py`: verify two output sinks receive frames independently

**Rollback plan:** Remove new nodes and `GraphBuilder` additions. Phase 0 graph functionality unaffected.

**Estimated effort:** 2 weeks

---

### Phase 2: Enable Feedback and Temporal

**Goal:** Native feedback loops and temporal effects. Replace `TemporalManager` with graph-native constructs.

**What changes:**
- New nodes: `FeedbackNode`, `DelayNode`, `FrameAccumulatorNode`
- Scheduler gains cycle detection with automatic delay insertion
- `TemporalManager` becomes optional (graph-mode uses native feedback)
- `FilterContext` temporal properties delegate to graph edges instead of `TemporalManager` when in graph mode

**What stays the same:**
- All Phase 0/1 nodes and graphs -- no changes
- `TemporalManager` still works for non-graph mode (backward compat)
- All existing filter adapters -- zero changes (they still receive `FilterContext`)
- Domain, ports, infrastructure -- untouched

**Compatibility guarantees:**
- Filters that use `FilterContext.previous_input`, `FilterContext.optical_flow`, etc. still work. In graph mode, the `FilterNodeAdapter` constructs the `FilterContext` from graph edge data instead of from `TemporalManager`.
- `TemporalManager.configure()` is still called for non-graph pipelines.
- Feedback loops are detected and broken automatically. User does not need to manually insert delay nodes (but can, for explicit control).

**Files to create:**

| File | Purpose |
|------|---------|
| `application/graph/feedback_node.py` | `FeedbackNode` with double-buffered frame swap |
| `application/graph/delay_node.py` | `DelayNode` with ring buffer |
| `application/graph/accumulator_node.py` | `FrameAccumulatorNode` with exponential decay |
| `application/graph/cycle_detector.py` | Cycle detection and automatic delay insertion |

**Files to modify:**

| File | Change |
|------|--------|
| `application/graph/scheduler.py` | Add cycle detection before topological sort, buffer swap after frame execution |
| `application/graph/node_adapter.py` | `FilterNodeAdapter` constructs `FilterContext` from graph edges (previous frame via FeedbackNode, optical flow computed on demand) |

**Test strategy:**
1. `test_feedback_node.py`: verify 1-frame delay, double-buffer swap
2. `test_delay_node.py`: verify N-frame ring buffer delay
3. `test_cycle_detection.py`: verify cycles are detected and delays auto-inserted
4. `test_accumulator.py`: verify exponential decay with known inputs
5. `test_temporal_parity.py`: verify that a graph with FeedbackNode produces the same results as the current `TemporalManager` flow for existing stateful filters (boids, physarum, optical_flow_particles)

**Rollback plan:** Remove new temporal nodes. Graph scheduler falls back to Phase 1 (no cycle support). `TemporalManager` remains the temporal mechanism.

**Estimated effort:** 2 weeks

---

### Phase 3: Control Signal Layer

**Goal:** ControlSignal port type enables parameter modulation from audio, OSC, MIDI, LFOs, and perception data.

**What changes:**
- New source nodes: `AudioSource`, `OSCReceiver`, `MIDIReceiver`
- New analyzer node: `AudioAnalyzer`
- New control nodes: `LFONode`, `EnvelopeNode`, `MapNode`, `SmoothNode`, `AnalysisToControlNode`
- Filter node adapters gain ControlSignal input ports for modulatable parameters
- Each filter adapter declares which parameters are modulatable via a class attribute

**What stays the same:**
- All existing filters work identically when ControlSignal ports are unconnected (defaults match current behavior)
- Non-graph pipelines are unaffected
- Domain, ports, infrastructure -- untouched

**Compatibility guarantees:**
- ControlSignal ports have default values. When unconnected, the filter uses its current static parameter from `EngineConfig`. This means all 19 existing filters work identically without any ControlSignal connections.
- New source/control nodes are optional. The graph functions without them.

**Files to create:**

| File | Purpose |
|------|---------|
| `adapters/sources/audio.py` | `AudioSource` using sounddevice |
| `adapters/sources/osc_receiver.py` | `OSCReceiver` using python-osc |
| `adapters/sources/midi_receiver.py` | `MIDIReceiver` using python-rtmidi |
| `adapters/perception/audio_analyzer.py` | `AudioAnalyzer` with FFT + beat detection |
| `application/graph/control_nodes.py` | `LFONode`, `EnvelopeNode`, `MapNode`, `SmoothNode`, `AnalysisToControlNode` |

**Files to modify:**

| File | Change |
|------|--------|
| `application/graph/node_adapter.py` | `FilterNodeAdapter` reads ControlSignal inputs and passes them as parameter overrides to the wrapped filter's `apply()` |
| `application/graph/port.py` | Add Trigger->ControlSignal auto-conversion |

**Modulatable parameter declaration (on existing filter adapters, no code change -- read via introspection):**

```python
# Example: How the adapter discovers modulatable parameters
# The adapter reads these from the filter class if present:
class CRTGlitchFilter(BaseFilter):
    # Existing attribute:
    name = "crt_glitch"

    # New optional class-level attribute (added in Phase 3, not required):
    modulatable_params = {
        "intensity": {"default": 0.5, "range": (0.0, 1.0)},
        "scanline_frequency": {"default": 0.3, "range": (0.0, 1.0)},
    }
```

If `modulatable_params` is not declared, the adapter creates no ControlSignal input ports. Existing filters work as-is. Parameters are opted-in incrementally.

**Test strategy:**
1. `test_lfo_node.py`: verify waveform generation (sine, saw, square, triangle)
2. `test_envelope_node.py`: verify ADSR shape
3. `test_map_node.py`: verify range mapping and easing curves
4. `test_smooth_node.py`: verify lag behavior
5. `test_audio_analyzer.py`: verify FFT output with known sine wave input
6. `test_control_modulation.py`: verify that connecting an LFO to a filter's parameter actually changes the filter output per-frame
7. `test_default_values.py`: verify that unconnected ControlSignal ports produce the declared default

**Rollback plan:** Remove new source/control nodes. Filter adapters without `modulatable_params` are unaffected. Remove ControlSignal auto-conversion.

**Estimated effort:** 3 weeks

---

### Phase 4: Optimization (Lazy Evaluation, Memory Pool, GPU Scheduling)

**Note:** Phase 4 is a performance optimization phase. It does not add new features. It improves the execution model established in Phases 0-3.

**What changes:**
- Lazy evaluation: dormant branches are skipped
- Memory pool: pre-allocated frame buffers replace per-node allocation
- Parallel batch execution: ThreadPoolExecutor for independent nodes within a batch
- Per-node profiling: timing data emitted to `LoopProfiler` per node

**What stays the same:**
- Graph structure, node catalog, port types -- all unchanged
- Behavioral output -- identical to Phase 3 (optimization must not change results)

**Compatibility guarantees:**
- Frame-identical output to Phase 3 for all graphs
- Performance overhead of graph scheduling < 1ms per frame (contract from SKILL.md)

**Files to create:**

| File | Purpose |
|------|---------|
| `application/graph/frame_pool.py` | `FramePool` with watermark-based growth/shrink |
| `application/graph/lazy_evaluator.py` | Dormant branch detection and skip logic |

**Files to modify:**

| File | Change |
|------|--------|
| `application/graph/scheduler.py` | Integrate frame pool, parallel batch execution, lazy evaluation, per-node profiling |

**Test strategy:**
1. `test_frame_pool.py`: unit test allocation, release, resize, watermark behavior
2. `test_lazy_evaluation.py`: verify dormant branches produce no node executions
3. `test_parallel_batches.py`: verify parallel execution produces identical results to sequential
4. `test_scheduling_overhead.py`: benchmark that graph scheduling overhead is < 1ms

**Rollback plan:** Revert to Phase 3 sequential scheduler. Remove pool and lazy evaluation. No API changes.

**Estimated effort:** 2 weeks

---

## 7. Risk Assessment

### 7.1 Performance Regression Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Graph scheduling overhead exceeds 1ms | Low | Medium | Topological sort is cached. Batch dispatch is O(nodes). Benchmark before each phase merge. |
| Fan-out frame copies instead of views | Medium | High | Enforce `flags.writeable = False` on fan-out. Add assertion in debug mode. No copy unless node explicitly calls `.copy()`. |
| ThreadPoolExecutor overhead exceeds parallelism benefit | Medium | Medium | Only parallelize batches with 2+ nodes. Trivial nodes (LFO, Map) run inline. Benchmark pool vs sequential. |
| Memory pool fragmentation on resolution change | Low | Low | Pool clears on resize. In-use buffers are naturally returned. |
| GIL contention with parallel Python nodes | High | Medium | Most work is in C/C++ extensions (OpenCV, numpy) which release GIL. Pure Python control nodes are fast (<1ms). Monitor GIL contention via `sys.getswitchinterval`. |

### 7.2 API Breaking Changes

| Phase | Breaking Change | Affected Code | Mitigation |
|-------|----------------|---------------|------------|
| Phase 0 | None | None | `use_graph=False` default preserves behavior |
| Phase 1 | None | None | New APIs are additions, not replacements |
| Phase 2 | `TemporalManager` injection pattern changes in graph mode | `FilterPipeline.apply()` when `use_graph=True` | `FilterNodeAdapter` handles the translation. Non-graph mode untouched. |
| Phase 3 | Filter adapters may gain `modulatable_params` attribute | Filter classes in `adapters/processors/filters/` | Attribute is optional. Absence means no modulation. Zero code change required on existing filters. |
| Phase 4 | None | None | Pure optimization, no API changes |

### 7.3 Correctness Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cycle detection misses a cycle (infinite loop) | Low | Critical | Kahn's algorithm is provably correct for cycle detection. Add frame-level timeout (2x expected frame time). If frame exceeds timeout, kill and log. |
| Fan-in merge order non-deterministic | Medium | Medium | Merge order is defined by topological sort position. Same graph always produces same merge order. Document explicitly. |
| Feedback node produces stale data after graph reconfiguration | Medium | Low | Clear all feedback/delay buffers on graph change. First frame after reconfiguration may have a black-frame flash. |
| AnalysisData merge overwrites conflicting keys | Low | Medium | Each analyzer uses unique top-level keys ("face", "hands", "pose"). Collision only happens if two analyzers use the same key, which is a graph construction error. Validate at connection time. |
| Node error cascades through graph | Medium | Medium | Error isolation catches per-node exceptions and produces fallback outputs. Downstream nodes receive degraded but valid data. |

### 7.4 Architectural Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Graph engine becomes a "god object" | Medium | High | Keep scheduler generic (no node-type-specific code). All node behavior is in the nodes themselves. Scheduler only knows about ports, connections, and topological order. |
| Migration stalls at Phase 0 (never gets to composition) | Medium | High | Phase 0 is explicitly time-boxed (3 weeks). If it takes longer, scope is reduced (fewer adapter wrappers, graph-parity test for critical path only). |
| Existing tests break during migration | Low | Medium | Phase 0 does not modify any existing file except `engine.py` (which gets an additive parameter). All new code is in `application/graph/`. Existing tests cannot break unless imports fail. |
| Community/team confusion about two execution paths | High | Medium | Document clearly. Deprecate `PipelineOrchestrator` after Phase 2 validation. Remove after Phase 4. Clear migration guide. |

### 7.5 Rollback Strategy (Per Phase)

| Phase | Rollback Action | Time to Rollback | Data Loss |
|-------|----------------|-----------------|-----------|
| Phase 0 | Set `use_graph=False` (already default). Optionally delete `application/graph/`. | 5 minutes | None |
| Phase 1 | Remove new composition nodes. Graph builder reverts to linear-only. Phase 0 graphs still work. | 1 hour | Lose composition capability |
| Phase 2 | Remove temporal nodes. Scheduler falls back to acyclic-only. `TemporalManager` resumes duty. | 1 hour | Lose native feedback |
| Phase 3 | Remove control nodes and new source adapters. Filter adapters lose modulation ports but work identically with defaults. | 2 hours | Lose audio/OSC/MIDI integration |
| Phase 4 | Revert scheduler to Phase 3 sequential execution. Remove pool. | 30 minutes | Lose performance optimizations |

---

## 8. Concrete Example: Mosaic + ASCII

This section designs the specific node graph that solves the original triggering problem: combining a mosaic pixelation effect with ASCII art rendering, where both effects are coordinated.

### 8.1 The Problem

In the current linear pipeline:
1. A filter can pixelate the frame (mosaic effect)
2. The renderer converts the frame to ASCII art
3. But the mosaic block size and ASCII grid size are independent parameters -- there is no way to coordinate them
4. The mosaic effect and the ASCII rendering are sequential, not parallel
5. There is no way to composite a mosaic view alongside or overlaid on the ASCII view

### 8.2 The Solution Graph

```
                                 +-------------------+
                                 |   MosaicFilter    |
                            +--->|   block_size <----+---- block_ctrl (ControlSignal, optional)
                            |    +--------+----------+
                            |             |
                            |         video_out
                            |             |
+----------------+  video   |             v
|  CameraSource  |----------+    +-------------------+
|                |  out     |    |  AsciiRenderer    |
+----------------+          |    |  grid_w <---------+---- grid_w_ctrl (ControlSignal, optional)
                            |    |  grid_h <---------+---- grid_h_ctrl (ControlSignal, optional)
                            |    +--------+----------+
                            |             |
                            |         render_out (RenderFrame: mosaic ASCII)
                            |             |
                            |             v            render_a
                            |    +-------------------+----------+
                            |    | RenderFrameComposite         |---render_out---> NotebookPreview
                            |    +-------------------+----------+
                            |             ^            render_b
                            |             |
                            |    +--------+----------+
                            +--->|  AsciiRenderer    |
                                 |  (clean, no       |
                                 |   mosaic)         |
                                 +-------------------+
```

### 8.3 Node Specifications for This Graph

#### MosaicFilterNode (detailed)

```python
class MosaicFilterNode:
    name = "mosaic_filter"
    node_type = "processor"

    def get_input_ports(self):
        return [
            InputPort(name="video_in", data_type=PortType.VIDEO_FRAME, required=True),
            InputPort(name="block_size", data_type=PortType.CONTROL_SIGNAL,
                      required=False, default_value=0.05,
                      description="Block size as fraction of frame height. 0.01=tiny, 0.2=huge"),
        ]

    def get_output_ports(self):
        return [
            OutputPort(name="video_out", data_type=PortType.VIDEO_FRAME),
        ]

    def process(self, inputs):
        frame = inputs["video_in"]
        block_fraction = inputs.get("block_size", 0.05)

        # Convert fraction to pixel block size
        h, w = frame.shape[:2]
        block_px = max(1, int(block_fraction * h))

        # Pixelate: shrink then enlarge with nearest-neighbor
        small_h, small_w = max(1, h // block_px), max(1, w // block_px)
        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)
        mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

        return {"video_out": mosaic}
```

#### Coordinating block_size and grid_size

The key insight: when the mosaic block size matches the ASCII character cell size, each mosaic block maps to exactly one ASCII character. This produces the cleanest visual result.

**Coordination via shared control signal:**

```
+----------------+
|  LFONode       |--signal_out--+---> MapNode (0-1 -> 0.02-0.15) ---> MosaicFilter.block_size
|  (sine, 0.1Hz) |              |
+----------------+              +---> MapNode (0-1 -> 40-120)     ---> AsciiRenderer.grid_w
                                |
                                +---> MapNode (0-1 -> 20-60)      ---> AsciiRenderer.grid_h
```

When the LFO outputs 0.0: block_size=0.02 (small blocks, fine detail), grid=120x60 (many characters, fine detail).
When the LFO outputs 1.0: block_size=0.15 (large blocks, coarse), grid=40x20 (few characters, coarse).

The mapping ensures they track together. As blocks get bigger, the grid gets coarser, keeping the 1-block-per-character alignment.

**Alternative: direct calculation node (no LFO):**

```python
class MosaicGridCoordinatorNode:
    """Calculates matching mosaic block size from ASCII grid dimensions."""
    name = "mosaic_grid_coordinator"
    node_type = "control"

    def get_input_ports(self):
        return [
            InputPort(name="grid_w", data_type=PortType.CONTROL_SIGNAL, required=True,
                      description="Target ASCII grid width (normalized: 0=20, 1=200)"),
            InputPort(name="frame_width", data_type=PortType.CONTROL_SIGNAL, required=True,
                      description="Source frame width (normalized: 0=320, 1=1920)"),
        ]

    def get_output_ports(self):
        return [
            OutputPort(name="block_size", data_type=PortType.CONTROL_SIGNAL,
                       description="Mosaic block size matched to grid"),
        ]

    def process(self, inputs):
        grid_w_norm = inputs["grid_w"]
        frame_w_norm = inputs["frame_width"]

        # Denormalize
        grid_w = int(20 + grid_w_norm * 180)  # 20 to 200 columns
        frame_w = int(320 + frame_w_norm * 1600)  # 320 to 1920 pixels

        # Block size = frame_width / grid_width (in pixels)
        # Normalize to fraction of frame height (assuming 16:9 aspect)
        frame_h = frame_w * 9 // 16
        block_px = frame_w // grid_w
        block_fraction = block_px / frame_h

        return {"block_size": min(1.0, max(0.0, block_fraction))}
```

### 8.4 Complete Mosaic + ASCII Graph in Code

```python
from ascii_stream_engine.application.graph import Graph, GraphBuilder

def build_mosaic_ascii_graph(config):
    """Build the mosaic + ASCII composition graph."""
    g = GraphBuilder()

    # Sources
    camera = g.add_node("camera", CameraSourceNode(device=0))

    # Mosaic path
    mosaic = g.add_node("mosaic", MosaicFilterNode())
    ascii_mosaic = g.add_node("ascii_mosaic", AsciiRendererNode(font_size=12))

    # Clean path
    ascii_clean = g.add_node("ascii_clean", AsciiRendererNode(font_size=10))

    # Composition
    composite = g.add_node("composite", RenderFrameCompositeNode(mode="alpha", blend=0.6))

    # Output
    preview = g.add_node("preview", NotebookPreviewSinkNode())

    # Connections
    g.connect(camera, "video_out", mosaic, "video_in")      # Camera -> Mosaic
    g.connect(mosaic, "video_out", ascii_mosaic, "video_in") # Mosaic -> ASCII (mosaic path)
    g.connect(camera, "video_out", ascii_clean, "video_in")  # Camera -> ASCII (clean path)
    g.connect(ascii_mosaic, "render_out", composite, "render_a")  # Mosaic ASCII -> Composite A
    g.connect(ascii_clean, "render_out", composite, "render_b")   # Clean ASCII -> Composite B
    g.connect(composite, "render_out", preview, "render_in")      # Composite -> Preview

    # Optional: coordinate block_size with grid via control signal
    lfo = g.add_node("size_lfo", LFONode(waveform="sine", frequency=0.1))
    block_map = g.add_node("block_map", MapNode(out_min=0.02, out_max=0.15))
    grid_map = g.add_node("grid_map", MapNode(out_min=0.2, out_max=0.6))  # Normalized grid_w

    g.connect(lfo, "signal_out", block_map, "signal_in")
    g.connect(block_map, "signal_out", mosaic, "block_size")
    g.connect(lfo, "signal_out", grid_map, "signal_in")
    g.connect(grid_map, "signal_out", ascii_mosaic, "grid_w")

    return g.build()
```

### 8.5 Execution Trace (One Frame)

```
Frame 42:

BATCH 0 (sources):
  camera.process() -> video_out: (480, 640, 3) uint8 BGR
  size_lfo.process() -> signal_out: 0.73 (sine at t=42/30 * 0.1Hz)

BATCH 1 (depend on Batch 0):
  mosaic.process(video_in=camera.video_out, block_size=0.73*0.13+0.02=0.12)
    -> video_out: (480, 640, 3) uint8 BGR (pixelated with 57px blocks)
  ascii_clean.process(video_in=camera.video_out)
    -> render_out: RenderFrame(PIL 640x480, text=ASCII lines)
  block_map.process(signal_in=0.73) -> signal_out: 0.12
  grid_map.process(signal_in=0.73) -> signal_out: 0.49

  [mosaic and ascii_clean run in PARALLEL -- no dependency between them]

BATCH 2 (depend on Batch 1):
  ascii_mosaic.process(video_in=mosaic.video_out, grid_w=0.49)
    -> render_out: RenderFrame(PIL 640x480, text=coarse ASCII)

BATCH 3 (depend on Batch 2):
  composite.process(render_a=ascii_mosaic.render_out, render_b=ascii_clean.render_out)
    -> render_out: RenderFrame(composited PIL image, blended at 60% mosaic / 40% clean)

BATCH 4 (output):
  preview.process(render_in=composite.render_out) -> displays in notebook

Total nodes executed: 8
Parallel nodes: 4 (mosaic + ascii_clean + block_map + grid_map in Batch 1)
Sequential batches: 5
Estimated frame time: ~12ms (well within 33.3ms budget)
```

### 8.6 User-Facing API

For the presentation layer (Jupyter notebooks), the graph is abstracted behind a convenience function:

```python
# In presentation/notebook_api.py:

def build_mosaic_ascii_panel(
    source_type="camera",
    device=0,
    mosaic_block_size=0.05,
    grid_w=80,
    grid_h=40,
    blend=0.5,
    animate_size=False,
    animation_speed=0.1,
):
    """Build a mosaic + ASCII composition panel for Jupyter.

    Args:
        source_type: "camera" or "video" (file path)
        device: Camera device index (if source_type="camera")
        mosaic_block_size: Initial mosaic block size (0.01-0.3)
        grid_w: ASCII grid width in characters
        grid_h: ASCII grid height in characters
        blend: Blend ratio (0=all clean ASCII, 1=all mosaic ASCII)
        animate_size: If True, LFO animates block_size and grid_w
        animation_speed: LFO frequency in Hz (if animate_size=True)

    Returns:
        StreamEngine configured with mosaic+ASCII graph
    """
    graph = build_mosaic_ascii_graph(...)
    engine = StreamEngine(graph=graph)
    return engine
```

---

## Appendix A: Interface Definitions

### Node Protocol

```python
class Node(Protocol):
    """Base interface for all nodes in the dataflow graph."""
    name: str
    node_type: str  # "source", "analyzer", "processor", "renderer", "output", "control"
    enabled: bool

    def get_input_ports(self) -> List[InputPort]: ...
    def get_output_ports(self) -> List[OutputPort]: ...
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]: ...
    def setup(self) -> None: ...
    def teardown(self) -> None: ...
```

### Port Dataclasses

```python
@dataclass
class Port:
    name: str
    data_type: PortType
    required: bool = True
    description: str = ""

@dataclass
class InputPort(Port):
    default_value: Any = None
    merge_strategy: str = "first"  # "first", "blend", "merge_dict", "layer"

@dataclass
class OutputPort(Port):
    pass
```

### Connection Dataclass

```python
@dataclass(frozen=True)
class Connection:
    source_node: str    # node name
    source_port: str    # output port name
    dest_node: str      # node name
    dest_port: str      # input port name
```

### Graph Class

```python
class Graph:
    """Immutable (after build) graph of nodes and connections."""

    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._connections: List[Connection] = []
        self._built: bool = False

    def add_node(self, name: str, node: Node) -> str: ...
    def remove_node(self, name: str) -> None: ...
    def connect(self, src_node: str, src_port: str, dst_node: str, dst_port: str) -> None: ...
    def disconnect(self, src_node: str, src_port: str, dst_node: str, dst_port: str) -> None: ...
    def validate(self) -> List[str]: ...  # Returns list of validation errors
    def build(self) -> 'Graph': ...       # Freezes graph, runs validation

    # Query
    def get_node(self, name: str) -> Node: ...
    def get_connections_from(self, node: str) -> List[Connection]: ...
    def get_connections_to(self, node: str) -> List[Connection]: ...
    def get_source_nodes(self) -> List[Node]: ...
    def get_output_nodes(self) -> List[Node]: ...
```

---

## Appendix B: File Tree After Full Migration

```
python/ascii_stream_engine/
  application/
    graph/                          # NEW -- entire directory
      __init__.py
      node.py                       # Node protocol, InputPort, OutputPort
      port.py                       # PortType enum, validation
      connection.py                 # Connection dataclass
      graph.py                      # Graph class
      graph_builder.py              # GraphBuilder convenience API
      scheduler.py                  # GraphScheduler (topo sort, batch exec)
      node_adapter.py               # Wrappers for existing adapters
      composite_node.py             # CompositeNode, RenderFrameCompositeNode
      feedback_node.py              # FeedbackNode
      delay_node.py                 # DelayNode
      accumulator_node.py           # FrameAccumulatorNode
      control_nodes.py              # LFONode, EnvelopeNode, MapNode, SmoothNode
      analysis_to_control.py        # AnalysisToControlNode
      cycle_detector.py             # Cycle detection + auto delay insertion
      frame_pool.py                 # FramePool memory management
      lazy_evaluator.py             # Dormant branch detection
    engine.py                       # MODIFIED -- adds use_graph param + build_graph()
    orchestration/                  # UNCHANGED (kept for non-graph mode)
    pipeline/                       # UNCHANGED (kept for non-graph mode)
    services/                       # UNCHANGED (TemporalManager kept for compat)
  adapters/
    processors/filters/
      mosaic.py                     # NEW -- MosaicFilter
      (all existing filters)        # UNCHANGED
    sources/
      audio.py                      # NEW -- AudioSource
      osc_receiver.py               # NEW -- OSCReceiver
      midi_receiver.py              # NEW -- MIDIReceiver
      (camera.py, video_file.py)    # UNCHANGED
    perception/
      audio_analyzer.py             # NEW -- AudioAnalyzer
      (all existing analyzers)      # UNCHANGED
    renderers/                      # UNCHANGED
    outputs/                        # UNCHANGED
  domain/                           # UNCHANGED
  ports/                            # UNCHANGED
  infrastructure/                   # UNCHANGED
  presentation/
    notebook_api.py                 # MODIFIED -- adds build_mosaic_ascii_panel(), build_graph()
  tests/
    test_graph_core.py              # NEW
    test_graph_scheduler.py         # NEW
    test_graph_adapter.py           # NEW
    test_graph_parity.py            # NEW
    test_composite_node.py          # NEW
    test_fan_out.py                 # NEW
    test_fan_in.py                  # NEW
    test_mosaic_ascii.py            # NEW
    test_feedback_node.py           # NEW
    test_delay_node.py              # NEW
    test_cycle_detection.py         # NEW
    test_accumulator.py             # NEW
    test_temporal_parity.py         # NEW
    test_control_nodes.py           # NEW
    test_audio_analyzer.py          # NEW
    test_control_modulation.py      # NEW
    test_frame_pool.py              # NEW
    test_lazy_evaluation.py         # NEW
    test_parallel_batches.py        # NEW
    test_scheduling_overhead.py     # NEW
    (all existing test files)       # UNCHANGED
```

---

## Appendix C: Design Checklist Verification

From `SKILL.md` design checklist:

- [x] Every existing adapter can be wrapped as a node without code changes -- Yes: `node_adapter.py` wraps Filter, Analyzer, Renderer, Source, Output
- [x] The current linear pipeline is expressible as a graph -- Yes: `GraphBuilder` constructs identical linear graph
- [x] Feedback loops are handled -- Yes: cycle detection + DelayNode insertion (Phase 2)
- [x] Fan-out works -- Yes: read-only view sharing, zero-copy (Phase 1)
- [x] Fan-in works -- Yes: AnalysisData merge via dict.update, VideoFrame blend modes (Phase 1)
- [x] Control signals can modulate processor parameters -- Yes: ControlSignal ports with defaults (Phase 3)
- [x] Graph can be modified at runtime -- Yes: modification queue applied between frames
- [x] Performance overhead is bounded -- Yes: cached topo sort, benchmark contract < 1ms
- [x] Thread safety is documented -- Yes: Section 5.5 Thread Model
- [x] Error in one node does not crash the graph -- Yes: Section 5.6 Error Isolation
- [x] Dormant branches are skippable -- Yes: lazy evaluation (Phase 4)
- [x] Memory is bounded -- Yes: frame pool with watermarks, ring buffers for temporal

---

## Appendix D: Audit Findings Addressed

| Audit Finding | Addressed By | Phase |
|---------------|-------------|-------|
| V1: FilterPipeline imports from adapters | Graph mode bypasses FilterPipeline entirely. FilterNodeAdapter has no adapter imports. | Phase 0 |
| V3/V4/V5: Adapter imports from application | Graph mode does not use adapter __init__.py re-exports. Nodes are created directly. | Phase 0 |
| V2: ControllerManager imports infrastructure | ControllerManager replaced by OSCReceiver/MIDIReceiver nodes with no infrastructure imports. | Phase 3 |
| T3: Hardcoded pipeline order (pain 4) | Pipeline order determined by graph topology, not hardcoded stages. | Phase 0 |
| T5: Untyped analysis dict (pain 4) | AnalysisData port type with documented schemas. Fan-in merge is explicit. | Phase 0 |
| T7: Feedback workaround (pain 4) | Native FeedbackNode with scheduler-managed double buffers. No dict injection hack. | Phase 2 |
| T2: Filters can't see renderer config (pain 3) | ControlSignal connections allow shared parameters between mosaic filter and ASCII renderer. | Phase 3 |
| T4: No cross-adapter communication (pain 3) | Graph connections are cross-adapter communication. Any node can send data to any other node via edges. | Phase 1 |
| T6: Push-only execution (pain 3) | Lazy evaluation skips dormant branches. | Phase 4 |
| T8: Single stream model (pain 3) | Multiple source nodes, multiple streams flowing through independent branches. | Phase 1 |
| Missing: Graph-based data flow | The entire proposal. | Phase 0-4 |
| Missing: Lazy evaluation | Dormant branch detection. | Phase 4 |
| Missing: Multi-stream | Multiple source nodes, AudioSource alongside CameraSource. | Phase 3 |
| Missing: Back-pressure | Output nodes can signal scheduler to slow down (future extension). | Future |
| Missing: Post-render effects | RenderFrame can be processed by additional nodes after rendering. | Phase 1 |
| Missing: Dynamic reconfiguration | Graph modification queue applied between frames. | Phase 0 |
| Missing: Typed analysis flow | AnalysisData port type with per-analyzer schemas. | Phase 0 |

---

## Revision 1: Post-Review Adjustments

**Date:** 2026-02-28
**Trigger:** External review feedback on the original proposal
**Scope:** 7 adjustments that refine the scheduler, type system, frame model, composition model, back-pressure, C++ integration, and phase plan. No sections above are modified -- this appendix supersedes conflicting details.

---

### R1. Scheduler Phasing (supersedes Section 5.1/5.2 monolithic scheduler)

The original proposal designed the scheduler as a single component that handles DAGs, cycles, and auto-delay from Phase 0. Review feedback: this is too much complexity at once. The scheduler must be phased into three versions:

**Scheduler v1 (Phase 0-1): DAG-only, no cycles**
- Simple topological sort via Kahn's algorithm
- No cycle detection. If a cycle exists, the graph fails validation with a clear error
- No auto-delay insertion
- No implicit DelayNode creation
- Rationale: Phase 0 wraps existing linear pipeline (inherently acyclic). Phase 1 adds fan-out/fan-in (still acyclic). Cycles are not needed until Phase 2.

**Scheduler v2 (Phase 1-2): Explicit DelayNode, no auto-detection**
- Users manually place `DelayNode` instances to break cycles
- The scheduler validates that all cycles are broken by user-placed delays
- If an unbroken cycle is detected, the graph fails validation with an error listing the cycle path and suggesting where to place a DelayNode
- No implicit delay insertion -- the user must be explicit about where temporal boundaries exist
- Rationale: auto-delay insertion hides complexity and can introduce unexpected 1-frame latencies in paths the user did not anticipate

**Scheduler v3 (Phase 3+): Auto-cycle detection + implicit delay insertion**
- Full implementation of the `topological_sort_with_cycle_detection()` function from Section 5.2
- Auto-detects cycles and inserts implicit delays on back-edges
- Logs a warning when implicit delays are inserted, identifying the back-edge
- Users can still place explicit delays (explicit takes priority over implicit)
- Rationale: by Phase 3, users build complex graphs with audio feedback loops where manual delay placement is tedious

**Updated Section 5.2 pseudocode for v1:**
```python
def topological_sort_dag_only(nodes, edges):
    """
    Kahn's algorithm, DAG-only. Raises on cycle.
    Used in scheduler v1 (Phase 0-1).
    """
    in_degree = {node: 0 for node in nodes}
    for src, dst in edges:
        in_degree[dst] += 1

    queue = [n for n in nodes if in_degree[n] == 0]
    sorted_nodes = []

    while queue:
        node = queue.pop(0)
        sorted_nodes.append(node)
        for neighbor in get_downstream(node, edges):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_nodes) != len(nodes):
        cycle_nodes = [n for n in nodes if in_degree[n] > 0]
        raise GraphCycleError(
            f"Cycle detected involving nodes: {[n.name for n in cycle_nodes]}. "
            f"Place a DelayNode on the back-edge to break the cycle, or wait for "
            f"scheduler v3 (Phase 3+) which handles cycles automatically."
        )

    return sorted_nodes
```

---

### R2. Strong Typing for AnalysisData (supersedes Section 3.2 AnalysisData)

The original proposal defines `AnalysisData` as `dict` with informal schema documentation. Review feedback: this is exactly the "untyped analysis dict" problem (audit finding T5) that the migration is supposed to fix. A dict with documentation is still a dict.

**New definition -- frozen dataclass:**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AnalysisData:
    face: Optional[FaceAnalysis] = None
    hands: Optional[HandAnalysis] = None
    pose: Optional[PoseAnalysis] = None
    tracking: Optional[TrackingData] = None
    gesture: Optional[HandGestureAnalysis] = None
    emotion: Optional[EmotionAnalysis] = None
    objects: Optional[ObjectDetectionAnalysis] = None
    segmentation: Optional[SegmentationAnalysis] = None
    timestamp: float = 0.0
    frame_id: int = 0
    source_id: str = ""
```

**Why frozen=True:**
- Immutability makes fan-out zero-copy safe. When one AnalysisData fans out to multiple downstream nodes, no node can mutate it. No ownership issues, no defensive copies.
- Hashable: can be used as dict key or in sets (useful for caching/deduplication).
- Thread-safe: immutable objects need no synchronization.

**Impact on fan-in merge strategy:**
The original Section 3.2 merges via `dict.update()`. With frozen dataclasses, the merge creates a new instance:

```python
def merge_analysis_data(*sources: AnalysisData) -> AnalysisData:
    """Merge multiple AnalysisData into one. Later sources override earlier for non-None fields."""
    merged_kwargs = {}
    for source in sources:
        for field in fields(source):
            value = getattr(source, field.name)
            if value is not None and value != field.default:
                merged_kwargs[field.name] = value
    return AnalysisData(**merged_kwargs)
```

**Impact on existing analyzer adapters:**
The `AnalyzerNodeAdapter` converts the current dict output from each analyzer into the corresponding typed field:

```python
# In AnalyzerNodeAdapter.process():
raw_dict = self._wrapped_analyzer.analyze(frame)
# Map dict keys to AnalysisData fields:
analysis = AnalysisData(
    face=raw_dict.get("face"),
    hands=raw_dict.get("hands"),
    # ... etc
    timestamp=time.perf_counter(),
    frame_id=current_frame_id,
    source_id=source_id,
)
```

Existing analyzer adapters return dicts as before. The adapter layer handles the conversion. Zero code changes to analyzers.

**Impact on downstream consumers (filters):**
Filters currently access analysis via `analysis["face"]`. The `FilterNodeAdapter` must translate:

```python
# In FilterNodeAdapter, when constructing FilterContext:
if analysis_data is not None:
    # Convert frozen dataclass back to dict for FilterContext compatibility
    analysis_dict = {
        k: getattr(analysis_data, k)
        for k in ["face", "hands", "pose", "tracking", "gesture",
                   "emotion", "objects", "segmentation"]
        if getattr(analysis_data, k) is not None
    }
```

This keeps all existing filter code working without changes.

---

### R3. FramePacket Replaces Raw np.ndarray (supersedes Section 3.2 VideoFrame)

The original proposal defines `VideoFrame` as raw `numpy.ndarray`. Review feedback: raw arrays carry no metadata. Multi-camera sync, jitter compensation, and per-node latency tracking all require knowing WHEN and WHERE a frame came from.

**New definition:**

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class FramePacket:
    data: np.ndarray          # (H,W,3) BGR uint8, C-contiguous
    timestamp: float          # time.perf_counter() at capture
    frame_id: int             # monotonic counter per source
    source_id: str            # identifies which source produced this frame
    latency_ms: float = 0.0   # accumulated pipeline latency so far
```

**VideoFrame port type now carries FramePacket instead of np.ndarray.**

**Validation rule (updated from Section 3.2):**
```python
def validate_frame_packet(pkt: FramePacket) -> bool:
    arr = pkt.data
    return (isinstance(pkt, FramePacket) and
            arr.ndim == 3 and arr.shape[2] == 3 and
            arr.dtype == np.uint8 and arr.flags['C_CONTIGUOUS'])
```

**Benefits:**
- **Multi-camera sync:** When two CameraSource nodes produce frames, the scheduler can match frames by timestamp for synchronized processing.
- **Jitter compensation:** Timestamp allows detecting dropped frames and compensating by repeating or interpolating.
- **Latency tracking per-node:** Each node can update `latency_ms += node_execution_time`. The output sink receives the total pipeline latency per frame. This feeds directly into `LoopProfiler`.
- **Source identification:** In multi-source graphs, downstream nodes know which source produced the frame without relying on graph topology inspection.

**Impact on C++ bridge:**
The pybind11 bridge continues to receive raw `np.ndarray` (extracted from `FramePacket.data`). The `FramePacket` wrapper is Python-only and does not cross the C++ boundary. Node adapters unwrap before calling C++ and re-wrap after.

**Impact on existing adapters:**
The `SourceNodeAdapter` wraps the raw ndarray from `source.read()` into a `FramePacket`:

```python
# In SourceNodeAdapter.process():
frame = self._wrapped_source.read()
packet = FramePacket(
    data=frame,
    timestamp=time.perf_counter(),
    frame_id=self._frame_counter,
    source_id=self.name,
)
self._frame_counter += 1
return {"video_out": packet}
```

Downstream node adapters (filters, renderers) extract `packet.data` before calling the wrapped adapter. Zero code changes to existing adapters.

---

### R4. LayoutContext Replaces ControlSignal for Structural Sync (supersedes Section 8.3-8.5 coordination approach)

The original proposal coordinates mosaic block_size with ASCII grid_size via ControlSignal ports and MapNodes (Section 8.3). Review feedback: this overloads ControlSignal with structural negotiation. ControlSignal is a 0-1 float for dynamic modulation (LFOs, audio, MIDI). Structural layout negotiation (grid dimensions, block alignment, output resolution) is a different concern.

**New concept: LayoutContext**

```python
@dataclass
class LayoutContext:
    """Shared structural metadata for composition nodes.

    Declared by a composite/composition node and read by its input branches.
    Enables structural negotiation: "my area is X, my grid is Y, therefore
    block_size = char_size = Z."
    """
    output_width: int           # pixels
    output_height: int          # pixels
    grid_cols: int              # character columns (for ASCII)
    grid_rows: int              # character rows (for ASCII)
    block_width_px: int         # pixel width of one block/cell
    block_height_px: int        # pixel height of one block/cell
    char_width_px: int          # pixel width of one character
    char_height_px: int         # pixel height of one character
```

**How it works:**

1. The `RenderFrameCompositeNode` declares a `LayoutContext` based on its output dimensions and the desired grid.
2. Upstream nodes that support layout awareness read the context to align their parameters.
3. `MosaicFilterNode` reads `layout.block_width_px` to set its block size.
4. `AsciiRendererNode` reads `layout.grid_cols` and `layout.grid_rows` to set its grid.
5. The composite node negotiates: `block_size = char_size = block_width_px`.

**Negotiation flow:**

```
CompositeNode declares:
  output: 640x480
  grid: 80x60 chars
  -> char_width_px = 640/80 = 8px
  -> char_height_px = 480/60 = 8px
  -> block_width_px = 8px (matched to char)
  -> block_height_px = 8px

MosaicFilter reads layout:
  "my block size is 8x8 pixels"

AsciiRenderer reads layout:
  "my grid is 80x60 characters, each 8x8 pixels"

Result: each mosaic block maps to exactly one ASCII character.
```

**Updated ASCII diagram for Mosaic + ASCII with LayoutContext:**

```
+----------------+
| CameraSource   |
+-------+--------+
        | video_out (FramePacket)
        |
        +---------------------------+
        |                           |
        v                           v
+------------------+       +------------------+
| MosaicFilter     |       | AsciiRenderer    |
| block=8px        |       | grid=80x60       |
| (from layout)    |       | (from layout)    |
+--------+---------+       +--------+---------+
         |                          |
         | video_out                | render_out
         |                          |
         v                          |
+------------------+                |
| AsciiRenderer    |                |
| grid=80x60       |                |
| (from layout)    |                |
+--------+---------+                |
         |                          |
         | render_out               |
         |                          |
         v            render_a      v  render_b
+------------------------------------------+
|       RenderFrameCompositeNode           |
|       mode=alpha, blend=0.6             |
|                                          |
|  LayoutContext:                           |
|    output: 640x480                       |
|    grid: 80x60                           |
|    block/char: 8x8 px                   |
+--------------------+---------------------+
                     |
                     | render_out
                     v
              +------------------+
              | NotebookPreview  |
              +------------------+
```

**ControlSignal is now reserved for dynamic modulation only:**

| Concern | Mechanism | Examples |
|---------|-----------|---------|
| Structural negotiation | LayoutContext | Grid dimensions, block sizes, output resolution, aspect ratio |
| Dynamic modulation | ControlSignal (0-1 float) | LFO -> filter intensity, audio bass -> glitch amount, MIDI CC -> brightness |

**Implementation: LayoutContext propagation**

LayoutContext propagates BACKWARDS through the graph (from composite to its inputs) during the PREPARATION phase, not during per-frame execution. It is computed once when the graph is built (or rebuilt after modification).

```python
# In scheduler PREPARATION phase:
def propagate_layout_contexts(graph):
    """Backward propagation: composite nodes push layout to upstream nodes."""
    for node in reversed(topological_order):
        if hasattr(node, 'layout_context') and node.layout_context is not None:
            for conn in graph.get_connections_to(node.name):
                upstream = graph.get_node(conn.source_node)
                if hasattr(upstream, 'receive_layout'):
                    upstream.receive_layout(node.layout_context)
```

---

### R5. Back-Pressure Policy (new -- was listed as "Future" in original Appendix D)

The original proposal listed back-pressure as "Missing: Back-pressure -- future extension" in the audit findings table. Review feedback: back-pressure must be designed now, even if not all strategies are implemented until Phase 4.

**Each output node declares its back-pressure strategy:**

| Strategy | Behavior | Use case |
|----------|----------|----------|
| `DROP_OLDEST` | Discard stale frames from the output buffer when it is full | Preview, UDP streaming (default) |
| `BLOCK_UPSTREAM` | Pause the pipeline until the output node processes its buffer | Recording to file, lossless capture |
| `ADAPTIVE_FPS` | Dynamically reduce the source FPS to match output throughput | Streaming with variable bandwidth |

**Configuration:**

```python
@dataclass
class BackPressurePolicy:
    strategy: str = "DROP_OLDEST"  # "DROP_OLDEST", "BLOCK_UPSTREAM", "ADAPTIVE_FPS"
    buffer_size: int = 3           # max frames in output buffer
    min_fps: float = 10.0          # floor for ADAPTIVE_FPS strategy
```

**How each strategy works:**

**DROP_OLDEST (default):**
```
Source produces at 30 FPS. Output can only consume at 20 FPS.
Output buffer: [frame_28, frame_29, frame_30] (size=3)
Frame 31 arrives -> drop frame_28, buffer becomes [frame_29, frame_30, frame_31]
Result: output displays latest frames, drops 10 FPS worth of frames.
Preview sees smooth motion but at reduced sample rate.
```

**BLOCK_UPSTREAM:**
```
Source produces at 30 FPS. Output writes to disk at 20 FPS.
Output buffer: [frame_28, frame_29, frame_30] (size=3, FULL)
Frame 31 arrives -> scheduler blocks. Source.read() is not called.
Output processes frame_28 -> buffer has space -> scheduler resumes.
Result: all frames are written to disk. Pipeline runs at output speed (20 FPS).
No frame loss.
```

**ADAPTIVE_FPS:**
```
Source produces at 30 FPS. Network bandwidth drops, output can do 15 FPS.
Scheduler measures output throughput: 15 FPS average over last 30 frames.
Scheduler signals source: "reduce to 18 FPS" (output_fps * 1.2 headroom).
Source adjusts capture interval.
If bandwidth recovers: scheduler ramps source back up toward 30 FPS.
Floor: never below min_fps (default 10).
```

**Output node declaration:**

```python
class FfmpegUdpSinkNode:
    back_pressure = BackPressurePolicy(
        strategy="DROP_OLDEST",
        buffer_size=2,
    )

class AsciiRecorderSinkNode:
    back_pressure = BackPressurePolicy(
        strategy="BLOCK_UPSTREAM",
        buffer_size=5,
    )
```

**Multiple outputs with conflicting strategies:**
When a graph has multiple output sinks with different strategies, the most conservative strategy wins for shared upstream nodes. If one output says `BLOCK_UPSTREAM` and another says `DROP_OLDEST`, the scheduler blocks for the blocking output and drops for the dropping output (independent buffers per output).

---

### R6. C++ Scheduler as Fourth Module (supersedes Phase 4 scope)

The original proposal keeps the scheduler in pure Python with `ThreadPoolExecutor`. Review feedback: the GIL fundamentally limits parallelism for the scheduler itself (dispatch, buffer management, refcounting). The scheduler should be a C++ compiled module.

**New module: `graph_scheduler.so`**

```
cpp/build/
  ├── filters_cpp.so          # existing
  ├── perception_cpp.so        # existing
  ├── render_bridge.so         # existing
  └── graph_scheduler.so       # NEW (Phase 4)
```

**What moves to C++:**
- Topological sort and batch grouping
- Frame pool with reference counting
- Batch dispatch loop (calls back into Python for node.process())
- Buffer lifecycle management (acquire, add_reader, release_reader)

**What stays in Python:**
- Graph construction and validation (GraphBuilder, Graph)
- Node implementations (all node.process() methods)
- LayoutContext propagation
- Graph modification queue

**pybind11 interface:**

```cpp
// graph_scheduler.cpp
namespace py = pybind11;

class CppGraphScheduler {
public:
    void set_topology(const std::vector<int>& sorted_node_ids,
                      const std::vector<std::pair<int,int>>& edges);

    void execute_frame(py::dict node_callbacks);
    // node_callbacks: {node_id: python callable}
    // For each node in topo order:
    //   1. Collect inputs from edge buffers (C++ side)
    //   2. py::gil_scoped_acquire -> call Python node.process(inputs)
    //   3. py::gil_scoped_release -> store outputs in edge buffers (C++ side)
    //   4. Update refcounts, release consumed buffers to pool

    py::array_t<uint8_t> acquire_frame(int height, int width);
    void release_frame(py::array_t<uint8_t>& frame);
    void add_reader(py::array_t<uint8_t>& frame);
};

PYBIND11_MODULE(graph_scheduler, m) {
    py::class_<CppGraphScheduler>(m, "CppGraphScheduler")
        .def(py::init<>())
        .def("set_topology", &CppGraphScheduler::set_topology)
        .def("execute_frame", &CppGraphScheduler::execute_frame)
        .def("acquire_frame", &CppGraphScheduler::acquire_frame)
        .def("release_frame", &CppGraphScheduler::release_frame)
        .def("add_reader", &CppGraphScheduler::add_reader);
}
```

**GIL management pattern:**

```cpp
void CppGraphScheduler::execute_frame(py::dict node_callbacks) {
    for (int node_id : sorted_nodes_) {
        // Collect inputs from C++ edge buffers (no GIL needed)
        auto inputs = collect_inputs(node_id);

        // Call Python node.process() -- needs GIL
        py::object callback = node_callbacks[py::int_(node_id)];
        py::dict outputs;
        {
            py::gil_scoped_acquire acquire;
            outputs = callback(inputs);
        }

        // Store outputs in C++ edge buffers, update refcounts (no GIL)
        store_outputs(node_id, outputs);
    }
}
```

**Benefits:**
- True parallelism for buffer management (no GIL contention for acquire/release/refcount)
- Memory pool with C++ refcounting avoids Python object overhead
- `py::gil_scoped_release` during C++ node execution (for C++ filter nodes that do not call back into Python)
- Frame pool ownership tracking in C++ (deterministic deallocation, no GC pauses)

**Python fallback:**
The existing Python `GraphScheduler` remains as fallback for environments without C++ compilation. The pattern matches existing C++ module fallback convention:

```python
try:
    from graph_scheduler import CppGraphScheduler
    _use_cpp_scheduler = True
except ImportError:
    _use_cpp_scheduler = False
    # Fall back to pure Python scheduler
```

**CMake addition:**

```cmake
# In cpp/CMakeLists.txt, add alongside existing modules:
pybind11_add_module(graph_scheduler
    src/graph_scheduler.cpp
    src/frame_pool.cpp
    src/topo_sort.cpp
)
target_compile_features(graph_scheduler PRIVATE cxx_std_17)
```

---

### R7. Revised Phase Plan (supersedes Section 6)

The original 5-phase plan (0-4) is restructured to incorporate the scheduler phasing, FramePacket, LayoutContext, back-pressure, and C++ scheduler adjustments.

```
Phase 0 (2-3 weeks): DAG Compatibility Layer
  - Scheduler v1 (DAG only, no cycles, Kahn's algorithm)
  - FramePacket replaces raw np.ndarray for VideoFrame port type
  - AnalysisData as frozen dataclass (strong typing from day one)
  - All 38 existing adapters wrapped as nodes (zero adapter code changes)
  - Snapshot tests: graph output == PipelineOrchestrator output (frame-identical)
  - Performance comparison: graph overhead < 1ms vs linear pipeline
  - use_graph=False default flag in StreamEngine
  - Deliverables:
    - application/graph/ module (node, port, connection, graph, scheduler v1,
      node_adapter, graph_builder)
    - FramePacket, AnalysisData dataclass in domain/types.py
    - test_graph_core, test_graph_scheduler, test_graph_adapter, test_graph_parity

Phase 1 (2 weeks): Branching + Composition + Explicit Delay
  - CompositeNode + RenderFrameCompositeNode
  - LayoutContext for structural negotiation (replaces ControlSignal for grid/block sync)
  - Fan-out from any node (read-only view sharing, zero-copy)
  - Fan-in for AnalysisData (frozen dataclass merge)
  - Manual DelayNode placement (scheduler v2: validates cycles are broken by user delays)
  - Solves the mosaic + ASCII triggering use case
  - Deliverables:
    - CompositeNode, RenderFrameCompositeNode, MosaicFilterNode
    - LayoutContext dataclass and backward propagation
    - DelayNode (user-placed, not auto-inserted)
    - Scheduler v2 (cycle validation, not auto-detection)
    - test_composite_node, test_fan_out, test_fan_in, test_mosaic_ascii,
      test_layout_context

Phase 2 (2 weeks): Auto-Cycle Detection + Feedback Native
  - Scheduler v3 with auto-cycle detection and implicit delay insertion
  - FeedbackNode with double-buffered frame swap
  - FrameAccumulatorNode with exponential decay
  - FeedbackNode replaces TemporalManager for graph-mode pipelines
  - TemporalManager deprecated (still works for use_graph=False)
  - Deliverables:
    - Scheduler v3 (topological_sort_with_cycle_detection)
    - FeedbackNode, FrameAccumulatorNode, cycle_detector module
    - test_feedback_node, test_cycle_detection, test_accumulator,
      test_temporal_parity

Phase 3 (3 weeks): Control Signals + Audio
  - ControlSignal port type (for dynamic modulation only, NOT structural negotiation)
  - AudioSource -> AudioAnalyzer -> ControlSignal pipeline
  - OSCReceiver, MIDIReceiver source nodes
  - LFO, Envelope, Map, Smooth, AnalysisToControl control nodes
  - Filter modulatable_params opt-in mechanism
  - Deliverables:
    - audio.py, osc_receiver.py, midi_receiver.py source adapters
    - audio_analyzer.py perception adapter
    - control_nodes.py (LFO, Envelope, Map, Smooth, AnalysisToControl)
    - test_lfo_node, test_envelope_node, test_map_node, test_smooth_node,
      test_audio_analyzer, test_control_modulation

Phase 4 (2 weeks): C++ Scheduler + Optimization
  - graph_scheduler.so compiled module (fourth C++ module)
  - Frame pool with C++ refcounting (deterministic, no GC)
  - Parallel batch execution without GIL (py::gil_scoped_release for C++ nodes)
  - Back-pressure policies (DROP_OLDEST, BLOCK_UPSTREAM, ADAPTIVE_FPS)
  - Lazy evaluation of dormant branches
  - Python fallback scheduler for environments without C++ compilation
  - Deliverables:
    - cpp/src/graph_scheduler.cpp, frame_pool.cpp, topo_sort.cpp
    - BackPressurePolicy dataclass
    - Python fallback maintained
    - test_frame_pool, test_lazy_evaluation, test_parallel_batches,
      test_scheduling_overhead, test_back_pressure
```

**Total estimated timeline:** 11-12 weeks (unchanged from original, but scope is better distributed).

**Key differences from original phase plan:**
1. FramePacket and typed AnalysisData move to Phase 0 (was implicit/unplanned)
2. LayoutContext is Phase 1 (was not in original; ControlSignal was overloaded)
3. Scheduler is explicitly phased v1/v2/v3 across Phases 0/1-2/3+
4. Back-pressure moves from "Future" to Phase 4
5. C++ scheduler is Phase 4 (was vaguely "optimization")
6. DelayNode is available in Phase 1 (user-placed) instead of Phase 2 only

---

### R8. Systems to Study Before Implementation

Before beginning Phase 0 implementation, the team should study these systems for proven patterns:

**GStreamer (industrial AV pipeline standard)**
- **Pads and caps negotiation:** How upstream and downstream elements agree on format (resolution, framerate, colorspace). Directly relevant to LayoutContext design.
- **Back-pressure:** GStreamer uses a pull-based model where downstream elements request data. The `gst_pad_push()` / `GST_FLOW_OK` / `GST_FLOW_FLUSHING` pattern is the gold standard for back-pressure in AV.
- **Plugin system:** How elements are discovered, instantiated, and connected. The `GstElementFactory` pattern is relevant to our node registry.
- **Key source:** GStreamer Plugin Writer's Guide, especially chapters on pads, scheduling, and state management.

**MediaPipe (Google's graph-based perception framework)**
- **Timestamped packets:** MediaPipe's `Packet` type carries timestamp + data, directly analogous to our `FramePacket`. Study their `Timestamp` class and how it handles monotonicity guarantees.
- **Multi-stream synchronization:** How `ImmediateInputStreamHandler` vs `SyncSetInputStreamHandler` handle streams at different rates. Relevant for audio+video sync.
- **GPU scheduling:** MediaPipe's `GpuBuffer` and `GlCalculator` patterns for GPU-accelerated nodes. Relevant for future GPU filter support.
- **Calculator (node) lifecycle:** `Open()`, `Process()`, `Close()` maps to our `setup()`, `process()`, `teardown()`.
- **Key source:** MediaPipe Framework documentation, `mediapipe/framework/calculator_graph.cc`.

**Apache Beam (distributed processing, conceptual)**
- **Windowing:** How Beam groups events into time windows. Relevant for multi-camera sync where frames from different sources arrive at different times.
- **Watermarks:** The concept of "all data up to time T has arrived" is relevant for determining when all analyzers have completed for a given frame.
- **Event-time vs processing-time:** Beam's distinction is directly applicable: `FramePacket.timestamp` is event-time (when captured), wall clock during processing is processing-time. Matters for latency measurement and jitter detection.
- **Key source:** "Streaming Systems" by Akidau, Chernyak, Lax (O'Reilly), chapters 1-3.

---

### R9. Updated Appendix D: Audit Findings Addressed (additions)

| Audit Finding | Addressed By | Phase |
|---------------|-------------|-------|
| T5: Untyped analysis dict (pain 4) | **Revised:** Frozen `AnalysisData` dataclass with typed Optional fields. Not just "documented dict" but actual static types. | Phase 0 (moved earlier) |
| Missing: Back-pressure | **Revised:** Three configurable strategies (DROP_OLDEST, BLOCK_UPSTREAM, ADAPTIVE_FPS) per output node. | Phase 4 (was "Future") |
| Missing: Multi-camera sync | FramePacket.timestamp enables frame matching across sources. | Phase 0 (via FramePacket) |
| Missing: Per-node latency tracking | FramePacket.latency_ms accumulates through pipeline. | Phase 0 (via FramePacket) |
| Missing: Structural negotiation | LayoutContext replaces ControlSignal abuse for grid/block coordination. | Phase 1 |
| Missing: GIL-free scheduling | C++ graph_scheduler.so with py::gil_scoped_release. | Phase 4 |
