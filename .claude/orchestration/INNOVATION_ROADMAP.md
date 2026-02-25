# Innovation Roadmap — 20 Architecture Extension Proposals

> Authored by: Innovation Team
> Status: Draft
> Last Updated: —

## Overview

This document contains 20 prioritized proposals for extending the Spatial-Iteration-Engine,
organized into 3 implementation waves by dependency order and complexity.

**Scoring:**
- **Effort**: S (1-2 days), M (3-5 days), L (6-10 days)
- **Impact**: 1 (nice-to-have) → 5 (transformative)
- **Priority** = Impact / Effort-days (higher = do first)

---

## Wave 1 — Foundation (Days 3-5)

These proposals have minimal dependencies and establish patterns for later waves.

---

### Proposal 1: Optical Flow Particles Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | M (4 days) |
| **Impact** | 5/5 |
| **Dependencies** | None (standalone) |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** TouchDesigner-inspired particle system driven by dense optical flow vectors.
Particles spawn at high-motion areas and are advected by the flow field.

**Technical Approach:**
- Compute dense optical flow (Farneback) between current and previous frame
- Maintain particle buffer (position, velocity, age, color) as structured numpy array
- Advect particles using flow vectors, apply damping and lifetime decay
- Render particles as anti-aliased circles or lines onto frame copy
- **Stateful filter**: requires `reset()`, resolution change handling, bounded particle count

**Analysis Dict Usage:** Optional — can use `analysis["pose"]["joints"]` as particle attractors.

**Output Dict Schema:**
```python
# No new analysis keys (this is a filter, not an analyzer)
# Filter parameters exposed:
#   particle_count: int (max 5000)
#   particle_lifetime: float (seconds)
#   spawn_threshold: float (flow magnitude threshold)
#   damping: float (velocity decay per frame)
#   particle_size: int (pixels)
```

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/optical_flow_particles.py`
- `cpp/src/filters/optical_flow_particles.cpp` (optional, for particle update)
- `python/ascii_stream_engine/tests/test_optical_flow_particles.py`

**Latency Estimate:** 3-8ms Python, 1-3ms C++. May need reduced resolution for flow computation.

**Risks:** Flow computation is expensive (~5ms at 640x480). Mitigation: downsample 2x for flow, full-res for rendering.

---

### Proposal 2: Stippling / Pointillism Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | S (2 days) |
| **Impact** | 4/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Convert frame to a stippled/pointillist rendering using weighted dot placement
based on luminance.

**Technical Approach:**
- Convert to grayscale, compute importance map (inverse luminance)
- Generate dot positions via Poisson disk sampling (precomputed LUT for speed)
- Draw filled circles with radius proportional to local darkness
- Color sampled from original frame at dot center
- **LUT-cached**: Poisson disk positions cached, recomputed only on resolution change

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/stippling.py`
- `python/ascii_stream_engine/tests/test_stippling.py`

**Latency Estimate:** 2-4ms (LUT-cached dot positions, only drawing varies per frame)

---

### Proposal 3: UV Math Displacement Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | M (3 days) |
| **Impact** | 4/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Apply mathematical displacement functions (sin, cos, spiral, vortex) to UV
coordinates using `cv2.remap`.

**Technical Approach:**
- Generate UV mesh grid normalized to [0, 1]
- Apply displacement function: `u' = u + A*sin(v*freq + phase)`, etc.
- Support multiple modes: wave, spiral, vortex, radial, checkerboard warp
- Convert displaced UVs to pixel coords, apply via `cv2.remap`
- **LUT-cached**: remap tables cached, recomputed only when params change (`_params_dirty`)

**Parameters:**
- `mode`: str — displacement function type
- `amplitude`: float — displacement strength
- `frequency`: float — spatial frequency
- `phase`: float — animation phase (can be incremented per frame)
- `interpolation`: str — "linear" or "cubic"

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/uv_displacement.py`
- `python/ascii_stream_engine/tests/test_uv_displacement.py`

**Latency Estimate:** 1-3ms (remap from cached LUT)

---

### Proposal 4: Edge-Aware Smoothing Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | S (1 day) |
| **Impact** | 3/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Bilateral or guided filter that smooths flat regions while preserving edges.
Creates a painterly/cartoon look.

**Technical Approach:**
- Use `cv2.bilateralFilter` or `cv2.edgePreservingFilter`
- Parameters: `sigma_color`, `sigma_space`, `d` (neighborhood diameter)
- Optional edge overlay: detect edges with Canny, overlay as dark lines

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/edge_smooth.py`
- `python/ascii_stream_engine/tests/test_edge_smooth.py`

**Latency Estimate:** 2-5ms (bilateral filter is OpenCV-optimized)

---

### Proposal 5: Radial Collapse / Singularity Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | M (3 days) |
| **Impact** | 5/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Warp pixels toward one or more singularity points using radial distortion
in polar coordinates. Can use analysis data for dynamic attractors.

**Technical Approach:**
- Convert pixel coords to polar relative to singularity center
- Apply radial compression: `r' = r * (1 - strength * exp(-r/falloff))`
- Convert back to Cartesian, build remap table
- Multiple singularities: sum displacement vectors
- **LUT-cached** when singularity positions are static
- **Analysis-reactive**: if `analysis["face"]["points"]` exists, use nose tip as attractor

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/radial_collapse.py`
- `python/ascii_stream_engine/tests/test_radial_collapse.py`

**Latency Estimate:** 1-3ms (remap from cached LUT; LUT invalidated when attractor moves)

---

### Proposal 6: Hand Gesture Classifier Analyzer

| Field | Value |
|-------|-------|
| **Domain** | Perception / Analyzer |
| **Effort** | M (4 days) |
| **Impact** | 5/5 |
| **Dependencies** | Existing hand landmark analyzer |
| **Skill** | `.claude/skills/perception-development/SKILL.md` |

**Summary:** Classify hand gestures (open palm, fist, peace, thumbs up, pointing, pinch)
from existing hand landmark geometry without a separate ONNX model.

**Technical Approach:**
- Read `analysis["hands"]["left"]` and `analysis["hands"]["right"]` (21 landmarks each)
- Compute geometric features: finger extension ratios, inter-finger angles, palm spread
- Rule-based classifier (no ML needed for 6-8 gestures)
- Optional: train small MLP on landmark features for more gestures

**Output Dict Schema:**
```python
analysis["gesture"] = {
    "left": {
        "gesture": str,        # "open_palm", "fist", "peace", "thumbs_up", "pointing", "pinch", "unknown"
        "confidence": float,   # 0.0-1.0
        "fingers_extended": List[bool],  # [thumb, index, middle, ring, pinky]
    },
    "right": { ... }  # same structure
}
```

**Files:**
- `python/ascii_stream_engine/adapters/perception/hand_gesture.py`
- `python/ascii_stream_engine/tests/test_hand_gesture.py`

**Latency Estimate:** <1ms (pure geometry computation, no inference)

---

### Proposal 7: Object Detection Analyzer (YOLOv8-nano)

| Field | Value |
|-------|-------|
| **Domain** | Perception / Analyzer |
| **Effort** | L (7 days) |
| **Impact** | 5/5 |
| **Dependencies** | ONNX Runtime |
| **Skill** | `.claude/skills/perception-development/SKILL.md` |

**Summary:** General object detection using YOLOv8-nano ONNX model. Detects 80 COCO
classes with bounding boxes, class labels, and confidence scores.

**Technical Approach:**
- Load YOLOv8n ONNX model (6.2MB, ~15ms CPU inference at 640x640)
- Letterbox resize input to 640x640, normalize to [0,1]
- Run inference via ONNX Runtime (C++ OnnxRunner preferred)
- NMS post-processing: filter by confidence threshold, apply IoU-based NMS
- Normalize bbox coordinates to [0,1]

**Output Dict Schema:**
```python
analysis["objects"] = {
    "detections": [
        {
            "bbox": np.ndarray,    # [x1, y1, x2, y2] normalized 0-1
            "class_id": int,       # COCO class index
            "class_name": str,     # "person", "car", "dog", etc.
            "confidence": float,   # 0.0-1.0
        },
        ...
    ],
    "count": int,                  # total detections
}
```

**Model Registry Entry:**
```yaml
name: yolov8n
format: ONNX
input: [1, 3, 640, 640] float32
output: [1, 84, 8400] float32
size: 6.2MB
latency_cpu: ~15ms
source: ultralytics/yolov8
```

**Files:**
- `python/ascii_stream_engine/adapters/perception/object_detection.py`
- `cpp/src/perception/object_detection_runner.cpp`
- `python/ascii_stream_engine/tests/test_object_detection.py`
- `onnx_models/yolov8n.onnx`

**Latency Estimate:** 12-18ms CPU. Exceeds 5ms single-analyzer budget — must document
degradation strategy (run every 3rd frame, reuse detections).

**Risks:** Model size (6.2MB download), CPU latency above budget. Mitigation: frame skipping,
optional GPU acceleration.

---

### Proposal 8: RTSP Streaming Output

| Field | Value |
|-------|-------|
| **Domain** | Output |
| **Effort** | M (4 days) |
| **Impact** | 4/5 |
| **Dependencies** | ffmpeg installed on system |
| **Skill** | `.claude/skills/output-development/SKILL.md` |

**Summary:** Stream processed frames via RTSP using ffmpeg subprocess. Enables viewing
on VLC, OBS, or any RTSP client.

**Technical Approach:**
- Spawn ffmpeg subprocess: `ffmpeg -f rawvideo -pix_fmt rgb24 -s WxH -r FPS -i pipe:0 -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp rtsp://0.0.0.0:8554/stream`
- Write raw RGB bytes from `RenderFrame.image.tobytes()` to stdin pipe
- Implement proper cleanup: close stdin → wait(timeout=5) → terminate → kill
- OutputCapabilities: STREAMING | MULTI_CLIENT

**Files:**
- `python/ascii_stream_engine/adapters/outputs/rtsp/rtsp_sink.py` (complete existing)
- `python/ascii_stream_engine/tests/test_rtsp_sink.py`

**Latency Estimate:** 2-3ms (pipe write), encoding is async in ffmpeg process.

---

### Proposal 9: Heatmap Overlay Renderer

| Field | Value |
|-------|-------|
| **Domain** | Renderer |
| **Effort** | S (2 days) |
| **Impact** | 4/5 |
| **Dependencies** | Analysis dict from perception analyzers |
| **Skill** | `.claude/skills/renderer-development/SKILL.md` |

**Summary:** Overlay a color heatmap showing spatial density of detected features
(face landmarks, hand positions, pose joints, object detections).

**Technical Approach:**
- Accumulate detection positions into a float32 density map
- Apply Gaussian blur for smooth gradients
- Apply OpenCV colormap (COLORMAP_JET, COLORMAP_INFERNO, etc.)
- Blend with `cv2.addWeighted` onto the original frame
- Decorator pattern: wraps inner renderer, draws heatmap over its output

**Files:**
- `python/ascii_stream_engine/adapters/renderers/heatmap_renderer.py`
- `python/ascii_stream_engine/tests/test_heatmap_renderer.py`

**Latency Estimate:** 1-2ms (Gaussian blur + blend)

---

### Proposal 10: Config Persistence (JSON Save/Load)

| Field | Value |
|-------|-------|
| **Domain** | Infrastructure |
| **Effort** | S (1 day) |
| **Impact** | 3/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/infrastructure-development/SKILL.md` |

**Summary:** Save and load `EngineConfig` to/from JSON files. Enables persisting
user preferences across sessions.

**Technical Approach:**
- `ConfigPersistence.save(config, path)` — serialize EngineConfig to JSON
- `ConfigPersistence.load(path) -> EngineConfig` — deserialize from JSON
- Atomic writes via temp file + `os.replace()`
- Schema versioning (version field in JSON, migration on load)
- Thread-safe (lock around file I/O)

**Files:**
- `python/ascii_stream_engine/infrastructure/config_persistence.py`
- `python/ascii_stream_engine/tests/test_config_persistence.py`

**Latency Estimate:** N/A (not per-frame, called on demand)

---

## Wave 2 — Integration (Days 6-8)

These proposals build on Wave 1 foundations or require cross-team coordination.

---

### Proposal 11: Emotion Detection Analyzer

| Field | Value |
|-------|-------|
| **Domain** | Perception / Analyzer |
| **Effort** | M (4 days) |
| **Impact** | 4/5 |
| **Dependencies** | Existing face analyzer, ONNX Runtime |
| **Skill** | `.claude/skills/perception-development/SKILL.md` |

**Summary:** Classify facial expressions (happy, sad, angry, surprised, neutral, fear,
disgust) from the face region detected by the existing face analyzer.

**Technical Approach:**
- Crop face region using `analysis["face"]["points"]` bounding box
- Resize crop to model input size (48x48 or 64x64 grayscale)
- Run emotion classification ONNX model (small CNN, ~2ms)
- Return top emotion + confidence + full probability distribution

**Output Dict Schema:**
```python
analysis["emotion"] = {
    "dominant": str,          # "happy", "sad", "angry", "surprised", "neutral", "fear", "disgust"
    "confidence": float,      # 0.0-1.0
    "probabilities": {        # full distribution
        "happy": float,
        "sad": float,
        "angry": float,
        "surprised": float,
        "neutral": float,
        "fear": float,
        "disgust": float,
    }
}
```

**Files:**
- `python/ascii_stream_engine/adapters/perception/emotion.py`
- `cpp/src/perception/emotion_runner.cpp`
- `python/ascii_stream_engine/tests/test_emotion.py`
- `onnx_models/emotion_ferplus.onnx`

**Latency Estimate:** 2-4ms (small model + crop overhead)

---

### Proposal 12: Body Pose with Skeleton Overlay Data

| Field | Value |
|-------|-------|
| **Domain** | Perception / Analyzer |
| **Effort** | M (3 days) |
| **Impact** | 4/5 |
| **Dependencies** | Existing pose analyzer |
| **Skill** | `.claude/skills/perception-development/SKILL.md` |

**Summary:** Enhance the existing pose analyzer output with per-joint confidence scores,
skeleton connection definitions, and body part groupings.

**Technical Approach:**
- Extend existing pose output with confidence per joint
- Define skeleton connections as pairs of joint indices
- Group joints by body part (head, torso, left_arm, right_arm, left_leg, right_leg)
- Provide bone lengths for proportional analysis

**Output Dict Schema (extends existing):**
```python
analysis["pose"] = {
    "joints": np.ndarray,           # (17, 2) normalized 0-1 (existing)
    "confidence": np.ndarray,       # (17,) float32 per-joint confidence
    "connections": List[Tuple[int, int]],  # skeleton bone pairs
    "body_parts": {
        "head": List[int],          # joint indices
        "torso": List[int],
        "left_arm": List[int],
        "right_arm": List[int],
        "left_leg": List[int],
        "right_leg": List[int],
    },
    "visible_joints": int,          # count of joints above confidence threshold
}
```

**Files:**
- `python/ascii_stream_engine/adapters/perception/pose_skeleton.py`
- `python/ascii_stream_engine/tests/test_pose_skeleton.py`

**Latency Estimate:** <1ms additional (post-processing existing pose output)

---

### Proposal 13: Physarum Simulation Overlay Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | L (7 days) |
| **Impact** | 5/5 |
| **Dependencies** | C++ implementation required |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Physarum polycephalum (slime mold) simulation overlay. Agents deposit
trails that diffuse and decay, creating organic vein-like patterns that react to the
video content.

**Technical Approach:**
- Agent-based simulation: N agents (10K-50K) with position, heading, sensor params
- Each frame: sense → rotate → move → deposit → diffuse → decay
- Sense: sample trail map at 3 sensor positions (left, center, right)
- Trail map: float32 buffer, Gaussian diffuse + multiplicative decay per frame
- Feed from video: use luminance or edge map as food source
- **C++ mandatory**: Python too slow for 50K agent updates per frame
- Render: blend trail map (colormapped) onto original frame

**Parameters:**
- `agent_count`: int (10000-50000)
- `sensor_angle`: float (radians)
- `sensor_distance`: float (pixels)
- `turn_speed`: float (radians per step)
- `deposit_amount`: float
- `decay_rate`: float (0.95-0.99)
- `diffuse_radius`: int (kernel size)

**Files:**
- `cpp/src/filters/physarum.cpp`
- `cpp/src/bridge/pybind_filters.cpp` (extend)
- `python/ascii_stream_engine/adapters/processors/filters/physarum.py`
- `python/ascii_stream_engine/adapters/processors/filters/cpp_physarum.py`
- `python/ascii_stream_engine/tests/test_physarum.py`

**Latency Estimate:** 5-15ms Python (unusable), 1-3ms C++ with SIMD

---

### Proposal 14: Boids / Flocking Particles Filter

| Field | Value |
|-------|-------|
| **Domain** | Filter |
| **Effort** | M (4 days) |
| **Impact** | 4/5 |
| **Dependencies** | None |
| **Skill** | `.claude/skills/filter-development/SKILL.md` |

**Summary:** Craig Reynolds' Boids algorithm for flocking particle behavior.
Particles exhibit separation, alignment, and cohesion, creating emergent
flocking patterns over the video.

**Technical Approach:**
- N boids (500-2000) with position, velocity
- Three rules: separation (avoid crowding), alignment (match neighbors), cohesion (move toward center)
- Spatial hashing for neighbor lookup (O(N) instead of O(N²))
- Optional: attractors from analysis dict (hand positions, face)
- Render as small triangles or circles with velocity-based color
- **Stateful**: reset(), resolution change handling, bounded boid count

**Files:**
- `python/ascii_stream_engine/adapters/processors/filters/boids.py`
- `cpp/src/filters/boids.cpp` (optional)
- `python/ascii_stream_engine/tests/test_boids.py`

**Latency Estimate:** 2-5ms Python (with spatial hashing), 0.5-1.5ms C++

---

### Proposal 15: WebRTC Peer Output

| Field | Value |
|-------|-------|
| **Domain** | Output |
| **Effort** | L (7 days) |
| **Impact** | 5/5 |
| **Dependencies** | `aiortc` library |
| **Skill** | `.claude/skills/output-development/SKILL.md` |

**Summary:** Stream processed frames via WebRTC for browser-based viewing with
ultra-low latency.

**Technical Approach:**
- Use `aiortc` for WebRTC peer connection
- Simple signaling server (HTTP-based SDP exchange)
- Encode frames as VP8/H264 video track
- Background asyncio event loop for WebRTC
- OutputCapabilities: STREAMING | MULTI_CLIENT

**Files:**
- `python/ascii_stream_engine/adapters/outputs/webrtc/webrtc_sink.py` (complete existing)
- `python/ascii_stream_engine/adapters/outputs/webrtc/signaling_server.py`
- `python/ascii_stream_engine/tests/test_webrtc_sink.py`

**Latency Estimate:** 1-2ms (frame handoff), ~50ms end-to-end with encoding + network.

---

### Proposal 16: OSC Output (for VJ Tools)

| Field | Value |
|-------|-------|
| **Domain** | Output |
| **Effort** | S (2 days) |
| **Impact** | 3/5 |
| **Dependencies** | `python-osc` library |
| **Skill** | `.claude/skills/output-development/SKILL.md` |

**Summary:** Send analysis results as OSC messages over UDP for integration with
VJ tools (TouchDesigner, Resolume, Max/MSP, SuperCollider).

**Technical Approach:**
- Extract analysis data from `RenderFrame.metadata["analysis"]`
- Map to OSC address patterns: `/face/points`, `/hands/left`, `/pose/joints`, `/gesture/left`
- Send via UDP using `python-osc` SimpleUDPClient
- Configurable target host/port, address prefix, send rate
- **Does not transmit video** — only analysis data

**Files:**
- `python/ascii_stream_engine/adapters/outputs/osc/osc_sink.py`
- `python/ascii_stream_engine/tests/test_osc_sink.py`

**Latency Estimate:** <1ms (UDP send, no encoding)

---

### Proposal 17: Plugin Hot-Reload Improvement

| Field | Value |
|-------|-------|
| **Domain** | Infrastructure |
| **Effort** | M (3 days) |
| **Impact** | 3/5 |
| **Dependencies** | Existing PluginManager |
| **Skill** | `.claude/skills/infrastructure-development/SKILL.md` |

**Summary:** Improve the existing plugin hot-reload with faster change detection,
dependency-ordered reloading, and batch reload support.

**Technical Approach:**
- Fix `time.time()` → `time.perf_counter()` in PluginFileHandler
- Add dependency graph for load ordering (topological sort)
- Batch reload: collect changes over a window (100ms), reload all at once
- Cascade reload: if A depends on B, reloading B triggers A reload
- Add reload event to EventBus for notification

**Files:**
- `python/ascii_stream_engine/infrastructure/plugins/plugin_manager.py` (modify)
- `python/ascii_stream_engine/infrastructure/plugins/plugin_dependency.py` (new)
- `python/ascii_stream_engine/tests/test_plugin_reload.py`

**Latency Estimate:** N/A (not per-frame)

---

## Wave 3 — Advanced (Days 9-11)

These proposals are the most complex and depend on foundations from Waves 1-2.

---

### Proposal 18: Scene Segmentation Analyzer (Background Removal)

| Field | Value |
|-------|-------|
| **Domain** | Perception / Analyzer |
| **Effort** | L (7 days) |
| **Impact** | 5/5 |
| **Dependencies** | ONNX Runtime, C++ OnnxRunner |
| **Skill** | `.claude/skills/perception-development/SKILL.md` |

**Summary:** Semantic segmentation producing per-pixel class labels and a binary
person/background mask. Enables background removal, replacement, and selective
filter application.

**Technical Approach:**
- Use lightweight segmentation model (SINet or PP-HumanSeg, ~5MB)
- Input: letterbox resize to 256x256 or 320x320
- Output: per-pixel class probabilities → argmax for class mask
- Binary person mask via threshold on person class probability
- C++ OnnxRunner for inference, Python post-processing

**Output Dict Schema:**
```python
analysis["segmentation"] = {
    "mask": np.ndarray,           # (H, W) uint8, class index per pixel
    "person_mask": np.ndarray,    # (H, W) bool, True where person detected
    "class_names": List[str],     # index-to-name mapping
    "num_classes": int,
    "confidence_map": np.ndarray, # (H, W) float32, max class probability
}
```

**Files:**
- `python/ascii_stream_engine/adapters/perception/segmentation.py`
- `cpp/src/perception/segmentation_runner.cpp`
- `python/ascii_stream_engine/tests/test_segmentation.py`
- `onnx_models/pp_humanseg.onnx`

**Latency Estimate:** 8-15ms CPU. Exceeds 5ms budget — run every 2-3 frames, interpolate mask.

---

### Proposal 19: Optical Flow Visualization Renderer

| Field | Value |
|-------|-------|
| **Domain** | Renderer |
| **Effort** | M (3 days) |
| **Impact** | 4/5 |
| **Dependencies** | None (computes own optical flow) |
| **Skill** | `.claude/skills/renderer-development/SKILL.md` |

**Summary:** Dedicated renderer that visualizes dense optical flow as colored arrows,
streamlines, or HSV-encoded direction maps.

**Technical Approach:**
- Compute Farneback optical flow between consecutive frames
- Multiple visualization modes:
  - **HSV**: hue = direction, saturation = 1, value = magnitude
  - **Arrows**: grid of colored arrows at regular intervals
  - **Streamlines**: traced pathlines through the flow field
- Configurable grid density, arrow scale, color mapping
- Maintains previous grayscale frame (stateful, needs reset)

**Files:**
- `python/ascii_stream_engine/adapters/renderers/optical_flow_renderer.py`
- `python/ascii_stream_engine/tests/test_optical_flow_renderer.py`

**Latency Estimate:** 3-8ms (flow computation dominates). Downsample 2x for flow.

---

### Proposal 20: Web Dashboard (Metrics + Live Preview)

| Field | Value |
|-------|-------|
| **Domain** | Infrastructure |
| **Effort** | L (8 days) |
| **Impact** | 5/5 |
| **Dependencies** | EngineMetrics, LoopProfiler, Config Persistence (Proposal 10) |
| **Skill** | `.claude/skills/infrastructure-development/SKILL.md` |

**Summary:** HTTP-based web dashboard serving real-time metrics, latency budget
visualization, and optional MJPEG live preview stream.

**Technical Approach:**
- stdlib `http.server` (no external dependencies)
- JSON API endpoints:
  - `GET /api/metrics` — current FPS, frame count, errors
  - `GET /api/budget` — per-phase latency vs budget
  - `GET /api/health` — overall system health
  - `GET /api/config` — current engine config
  - `GET /api/metrics/history` — time-series data (bounded buffer)
- MJPEG stream at `/stream` (optional, uses `cv2.imencode`)
- Static HTML dashboard page at `/` with auto-updating charts
- Runs in daemon thread, does not block engine

**Files:**
- `python/ascii_stream_engine/infrastructure/dashboard/server.py`
- `python/ascii_stream_engine/infrastructure/dashboard/handlers.py`
- `python/ascii_stream_engine/infrastructure/dashboard/static/index.html`
- `python/ascii_stream_engine/tests/test_dashboard.py`

**Latency Estimate:** N/A (runs in separate thread, does not affect frame pipeline)

---

## Summary Matrix

| # | Proposal | Domain | Effort | Impact | Wave | Status |
|---|----------|--------|--------|--------|------|--------|
| 1 | Optical Flow Particles | Filter | M | 5 | 1 | Proposed |
| 2 | Stippling / Pointillism | Filter | S | 4 | 1 | Proposed |
| 3 | UV Math Displacement | Filter | M | 4 | 1 | Proposed |
| 4 | Edge-Aware Smoothing | Filter | S | 3 | 1 | Proposed |
| 5 | Radial Collapse / Singularity | Filter | M | 5 | 1 | Proposed |
| 6 | Hand Gesture Classifier | Analyzer | M | 5 | 1 | Proposed |
| 7 | Object Detection (YOLOv8) | Analyzer | L | 5 | 1 | Proposed |
| 8 | RTSP Streaming | Output | M | 4 | 1 | Proposed |
| 9 | Heatmap Overlay | Renderer | S | 4 | 1 | Proposed |
| 10 | Config Persistence | Infra | S | 3 | 1 | Proposed |
| 11 | Emotion Detection | Analyzer | M | 4 | 2 | Proposed |
| 12 | Body Pose + Skeleton | Analyzer | M | 4 | 2 | Proposed |
| 13 | Physarum Simulation | Filter | L | 5 | 2 | Proposed |
| 14 | Boids / Flocking | Filter | M | 4 | 2 | Proposed |
| 15 | WebRTC Peer | Output | L | 5 | 2 | Proposed |
| 16 | OSC Output | Output | S | 3 | 2 | Proposed |
| 17 | Plugin Hot-Reload | Infra | M | 3 | 2 | Proposed |
| 18 | Scene Segmentation | Analyzer | L | 5 | 3 | Proposed |
| 19 | Optical Flow Viz | Renderer | M | 4 | 3 | Proposed |
| 20 | Web Dashboard | Infra | L | 5 | 3 | Proposed |

## Dependency Graph

```
Wave 1 (no dependencies):
  [1] Optical Flow Particles
  [2] Stippling
  [3] UV Displacement
  [4] Edge Smoothing
  [5] Radial Collapse
  [6] Hand Gesture ──── requires existing hand analyzer
  [7] Object Detection
  [8] RTSP Streaming
  [9] Heatmap Overlay ─── requires any analyzer output
  [10] Config Persistence

Wave 2 (builds on Wave 1):
  [11] Emotion ─────────── requires existing face analyzer
  [12] Pose Skeleton ───── requires existing pose analyzer
  [13] Physarum ─────────── requires C++ build infrastructure
  [14] Boids
  [15] WebRTC
  [16] OSC Output ──────── richer with [6] gesture data
  [17] Plugin Hot-Reload

Wave 3 (builds on Waves 1-2):
  [18] Scene Segmentation ── requires C++ OnnxRunner patterns from [7]
  [19] Optical Flow Viz ──── can reuse flow computation from [1]
  [20] Web Dashboard ─────── uses [10] Config Persistence
```

## Effort Summary

| Metric | Value |
|--------|-------|
| Total proposals | 20 |
| Total effort | ~75 developer-days |
| Filters | 7 proposals |
| Analyzers | 5 proposals |
| Outputs | 3 proposals |
| Renderers | 2 proposals |
| Infrastructure | 3 proposals |
| Requires C++ | 4 proposals (7, 13, 18, optional on 1, 14) |
| Requires ONNX models | 4 proposals (7, 11, 18, optional 6) |
| Average impact | 4.2/5 |
