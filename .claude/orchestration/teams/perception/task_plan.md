# Perception Team -- Task Plan

**Team:** Perception
**Branch:** `feature/perception-analyzers`
**Base:** `develop`
**Skill contract:** `.claude/skills/perception-development/SKILL.md`
**Latency budget:** 5ms per analyzer, 15ms all combined (see `rules/LATENCY_BUDGET.md`)

## Goal

Build five new ONNX-based analyzers that extend the perception pipeline:

| # | Analyzer | Key | Description |
|---|----------|-----|-------------|
| 1 | Hand Gesture Classifier | `hand_gesture` | Classify gestures from existing hand landmark geometry |
| 2 | Object Detection | `objects` | YOLOv8-nano ONNX with NMS post-processing |
| 3 | Emotion Detection | `emotion` | Facial expression classification from face region |
| 4 | Body Pose with Skeleton | `pose_skeleton` | Enhanced pose with per-joint confidence scores and skeleton edges |
| 5 | Scene Segmentation | `segmentation` | Background removal mask (per-pixel class) |

All analyzers follow the existing patterns in `adapters/perception/{face,hands,pose}.py` and the 10-step checklist in `rules/AI_MODEL_INTEGRATION_RULES.md`.

---

## Phase 1: Research & Design (Architect)

**Owner:** Architect agent
**Duration:** 1 session
**Depends on:** Nothing

### Tasks

#### 1.1 Survey existing analyzer patterns
- Read and document the structure of the three existing analyzers:
  - `python/ascii_stream_engine/adapters/perception/face.py` (FaceLandmarkAnalyzer)
  - `python/ascii_stream_engine/adapters/perception/hands.py` (HandLandmarkAnalyzer)
  - `python/ascii_stream_engine/adapters/perception/pose.py` (PoseLandmarkAnalyzer)
- Read and document the C++ runner pattern from:
  - `cpp/src/perception/face_landmarks.cpp`
  - `cpp/src/perception/hand_landmarks.cpp`
  - `cpp/src/perception/pose_landmarks.cpp`
  - `cpp/src/perception/onnx_runner.cpp` (shared OnnxRunner with letterbox, NCHW, YOLOv8 post-processing)
- Read and document the pybind bridge pattern from:
  - `cpp/src/bridge/pybind_perception.cpp` (require_3d_uint8, landmarks_to_numpy, gil_scoped_release)
- Document the BaseAnalyzer contract:
  - `python/ascii_stream_engine/adapters/processors/analyzers/base.py`
- Document the domain types:
  - `python/ascii_stream_engine/domain/frame_analysis.py`

**Acceptance criteria:**
- Written summary of every structural element common to all existing analyzers
- List of patterns that MUST be replicated (ImportError guard, `_CPP_AVAILABLE`, normalize to 0-1, `{}` on failure, `name` attribute)

#### 1.2 Design analysis dict schema for each new analyzer
Define the exact dict structure each analyzer will return, following the schema in `rules/PIPELINE_EXTENSION_RULES.md` section 7. The schemas must be:

```python
# Hand Gesture Classifier
analysis["hand_gesture"] = {
    "left_gesture": str,           # gesture class name ("open", "fist", "point", "peace", "thumbs_up", "none")
    "left_confidence": float,      # 0.0-1.0
    "right_gesture": str,          # gesture class name
    "right_confidence": float,     # 0.0-1.0
}

# Object Detection
analysis["objects"] = {
    "detections": [                # list of dicts, one per detected object
        {
            "class_id": int,       # COCO class index
            "class_name": str,     # COCO class label
            "confidence": float,   # 0.0-1.0
            "bbox": np.ndarray,    # (4,) float32 [x1, y1, x2, y2] normalized 0-1
        },
    ],
    "count": int,                  # total number of detections
}

# Emotion Detection
analysis["emotion"] = {
    "expression": str,             # dominant emotion ("neutral", "happy", "sad", "angry", "surprise", "fear", "disgust")
    "confidence": float,           # 0.0-1.0
    "scores": np.ndarray,          # (7,) float32, score per class, sums to ~1.0
}

# Body Pose with Skeleton
analysis["pose_skeleton"] = {
    "joints": np.ndarray,          # (17, 2) float32 normalized 0-1, (x,y) per joint
    "confidences": np.ndarray,     # (17,) float32, per-joint confidence 0-1
    "edges": list,                 # list of (joint_a_idx, joint_b_idx) tuples defining skeleton connectivity
    "visible_mask": np.ndarray,    # (17,) bool, True if confidence > threshold
}

# Scene Segmentation
analysis["segmentation"] = {
    "mask": np.ndarray,            # (H, W) uint8, class index per pixel (0=background, 1=person, ...)
    "person_mask": np.ndarray,     # (H, W) bool, True where person is detected
    "num_classes": int,            # number of segmentation classes
}
```

**Acceptance criteria:**
- Each schema is fully typed with numpy dtypes and shapes
- Schemas are compatible with existing analysis dict merge logic
- No key collisions with existing `face`, `hands`, `pose`, `tracking` keys

#### 1.3 Document ONNX model requirements

For each new analyzer, document:

| Analyzer | Model | Input shape | Input format | Output shape | Output semantics | Expected size | Expected latency | Source |
|----------|-------|-------------|--------------|--------------|------------------|---------------|------------------|--------|
| Hand Gesture | Custom classifier head | N/A (uses hand landmark geometry) | 21 landmarks (42 floats) | (1, num_classes) | gesture probabilities | <1MB | <1ms (pure Python) | N/A |
| Object Detection | YOLOv8n | (1,3,640,640) | NCHW float32 [0,1] RGB | (1,84,8400) | 4 bbox + 80 class scores per detection | ~6MB | ~15-20ms CPU | Ultralytics / HuggingFace |
| Emotion | FER-ONNX or similar | (1,3,48,48) or (1,1,48,48) | NCHW float32 [0,1] | (1,7) | 7 emotion probabilities | ~1-5MB | ~1-3ms CPU | HuggingFace |
| Pose Skeleton | (reuses existing YOLOv8n-pose) | (1,3,640,640) | NCHW float32 [0,1] RGB | (1,56,8400) | 4 bbox + 1 conf + 17*3 kp | 6.48MB | ~15-25ms CPU | Already registered |
| Segmentation | SINet / PP-LiteSeg nano | (1,3,256,256) | NCHW float32 [0,1] RGB | (1,2,256,256) | per-pixel class logits | ~1-5MB | ~3-8ms CPU | HuggingFace / PaddlePaddle |

**Acceptance criteria:**
- Every model has input/output shapes documented
- Every model source is on the `SECURITY_MODEL_DOWNLOAD.md` whitelist
- Models that exceed 5ms budget have documented mitigation (frame skipping)

#### 1.4 Write findings.md

Write the research output to:
``.claude/orchestration/teams/perception/findings.md``

Contents:
- Pattern summary from 1.1
- Complete dict schemas from 1.2
- Model requirements table from 1.3
- Any identified risks or open questions
- Recommendations for model selection

**Deliverables:**
- `.claude/orchestration/teams/perception/findings.md`

---

## Phase 2: Core Python Implementation (Python Implementer)

**Owner:** Python Implementer agent
**Duration:** 2 sessions
**Depends on:** Phase 1 (findings.md must exist)

### Tasks

#### 2.1 Implement HandGestureAnalyzer

**File:** `python/ascii_stream_engine/adapters/perception/hand_gesture.py`

This analyzer does NOT require a separate ONNX model. It classifies gestures from existing hand landmark geometry provided by the `hands` analyzer. The classification logic is pure Python using numpy geometric calculations (finger angles, distances between landmarks).

Implementation:
- Subclass `BaseAnalyzer` with `name = "hand_gesture"`
- `analyze(frame, config)` reads `config` or accepts an optional `analysis` dict parameter to access `analysis["hands"]`
- If hand landmarks are not available (no `hands` key or empty), return `{}`
- Classify gestures using geometric heuristics on 21-point hand landmark topology:
  - **open**: all fingers extended (tip y < pip y for each finger)
  - **fist**: all fingers curled
  - **point**: only index finger extended
  - **peace**: index + middle extended
  - **thumbs_up**: only thumb extended, hand roughly vertical
  - **none**: no confident classification
- Return schema from Phase 1.2 (`left_gesture`, `left_confidence`, `right_gesture`, `right_confidence`)
- Confidence is based on how clearly the geometry matches the gesture template (0.0-1.0)
- Uses `try/except` with `return {}` on any error
- No C++ dependency needed (pure geometry, well under 1ms budget)

**Acceptance criteria:**
- [ ] File exists at the specified path
- [ ] Extends `BaseAnalyzer` with `name = "hand_gesture"`
- [ ] Returns `{}` when no hand landmarks are available
- [ ] Returns valid gesture strings from the defined set
- [ ] Confidence values are 0.0-1.0
- [ ] DOES NOT modify the frame
- [ ] Follows ImportError fallback pattern (even though no C++ dependency, for consistency)
- [ ] Docstring documents the dict schema

#### 2.2 Implement ObjectDetectionAnalyzer

**File:** `python/ascii_stream_engine/adapters/perception/object_detection.py`

Implementation:
- Subclass `BaseAnalyzer` with `name = "objects"`
- `try/except ImportError` for `perception_cpp` at module level
- Call `_perception_cpp.detect_objects(frame)` which returns raw detections from YOLOv8-nano
- Implement NMS (Non-Maximum Suppression) post-processing in Python:
  - IoU threshold: 0.45
  - Confidence threshold: 0.25
  - Max detections: 20
- Normalize bbox coordinates to 0-1 (divide by frame width/height)
- Map class_id to COCO class name using a static `COCO_CLASSES` list (80 classes)
- Return schema from Phase 1.2 (`detections` list + `count`)
- Return `{}` on any failure

**Acceptance criteria:**
- [ ] File exists at the specified path
- [ ] Extends `BaseAnalyzer` with `name = "objects"`
- [ ] ImportError fallback pattern present
- [ ] NMS post-processing implemented correctly
- [ ] All bbox coordinates normalized 0-1
- [ ] `np.clip` applied to all coordinates
- [ ] COCO class mapping is complete (80 classes)
- [ ] Returns `{}` when C++ unavailable, frame is None, or inference fails
- [ ] DOES NOT modify the frame
- [ ] Docstring documents the dict schema

#### 2.3 Implement EmotionAnalyzer

**File:** `python/ascii_stream_engine/adapters/perception/emotion.py`

Implementation:
- Subclass `BaseAnalyzer` with `name = "emotion"`
- `try/except ImportError` for `perception_cpp` at module level
- Call `_perception_cpp.detect_emotion(frame)` which returns raw logits
- Apply softmax in Python to convert logits to probabilities
- Map to emotion labels: `["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]`
- Return the dominant emotion (argmax), its confidence, and the full scores array
- Return schema from Phase 1.2 (`expression`, `confidence`, `scores`)
- Return `{}` on any failure

**Acceptance criteria:**
- [ ] File exists at the specified path
- [ ] Extends `BaseAnalyzer` with `name = "emotion"`
- [ ] ImportError fallback pattern present
- [ ] Softmax applied correctly to raw logits
- [ ] 7 emotion classes mapped correctly
- [ ] Scores sum to approximately 1.0
- [ ] Returns `{}` when C++ unavailable, frame is None, or inference fails
- [ ] DOES NOT modify the frame
- [ ] Docstring documents the dict schema

#### 2.4 Implement PoseSkeletonAnalyzer

**File:** `python/ascii_stream_engine/adapters/perception/pose_skeleton.py`

This analyzer enhances the existing pose analyzer output with confidence scores and skeleton edge connectivity. It reuses the same YOLOv8n-pose model but extracts additional data.

Implementation:
- Subclass `BaseAnalyzer` with `name = "pose_skeleton"`
- `try/except ImportError` for `perception_cpp` at module level
- Call `_perception_cpp.detect_pose_with_confidence(frame)` which returns (N, 3) array: x, y, confidence per joint
- Normalize x, y to 0-1 (divide by frame width/height), clip
- Separate into `joints` (N, 2), `confidences` (N,), `visible_mask` (N,) bool
- Define COCO skeleton edges as a static list of (joint_a, joint_b) tuples:
  ```python
  COCO_SKELETON = [
      (0, 1), (0, 2), (1, 3), (2, 4),           # head
      (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),   # arms
      (5, 11), (6, 12), (11, 12),                 # torso
      (11, 13), (13, 15), (12, 14), (14, 16),     # legs
  ]
  ```
- Return schema from Phase 1.2 (`joints`, `confidences`, `edges`, `visible_mask`)
- Return `{}` on any failure

**Acceptance criteria:**
- [ ] File exists at the specified path
- [ ] Extends `BaseAnalyzer` with `name = "pose_skeleton"`
- [ ] ImportError fallback pattern present
- [ ] Joint coordinates normalized 0-1 with `np.clip`
- [ ] Confidences are float32 in 0-1 range
- [ ] `visible_mask` correctly derived from confidence threshold (0.3)
- [ ] Skeleton edges are a static, correct COCO topology
- [ ] Returns `{}` when C++ unavailable, frame is None, or inference fails
- [ ] DOES NOT modify the frame
- [ ] Docstring documents the dict schema

#### 2.5 Implement SceneSegmentationAnalyzer

**File:** `python/ascii_stream_engine/adapters/perception/segmentation.py`

Implementation:
- Subclass `BaseAnalyzer` with `name = "segmentation"`
- `try/except ImportError` for `perception_cpp` at module level
- Call `_perception_cpp.detect_segmentation(frame)` which returns raw logits as flat float array
- Reshape to (num_classes, model_H, model_W)
- Apply argmax along class axis to get per-pixel class index
- Resize mask to original frame dimensions using nearest-neighbor interpolation (cv2.resize with INTER_NEAREST)
- Derive `person_mask` from class index (class 1 = person in typical segmentation models)
- Return schema from Phase 1.2 (`mask`, `person_mask`, `num_classes`)
- Return `{}` on any failure

**Acceptance criteria:**
- [ ] File exists at the specified path
- [ ] Extends `BaseAnalyzer` with `name = "segmentation"`
- [ ] ImportError fallback pattern present
- [ ] Mask resized to original frame dimensions
- [ ] Nearest-neighbor interpolation used (no blurring of class boundaries)
- [ ] `person_mask` is boolean dtype
- [ ] `mask` is uint8 dtype
- [ ] Returns `{}` when C++ unavailable, frame is None, or inference fails
- [ ] DOES NOT modify the frame
- [ ] Docstring documents the dict schema

**Deliverables:**
- `python/ascii_stream_engine/adapters/perception/hand_gesture.py`
- `python/ascii_stream_engine/adapters/perception/object_detection.py`
- `python/ascii_stream_engine/adapters/perception/emotion.py`
- `python/ascii_stream_engine/adapters/perception/pose_skeleton.py`
- `python/ascii_stream_engine/adapters/perception/segmentation.py`

---

## Phase 3: Unit Tests (Test Agent)

**Owner:** Test Agent
**Duration:** 1 session
**Depends on:** Phase 2 (all Python adapters must exist)

### Tasks

#### 3.1 Test each analyzer with synthetic frames

**File:** `python/ascii_stream_engine/tests/test_perception_new.py`

Write tests for all five new analyzers using synthetic (numpy-generated) frames. Each analyzer gets its own test class.

```python
class TestHandGestureAnalyzer(unittest.TestCase):
    def test_returns_empty_when_no_hands(self):
        """HandGestureAnalyzer returns {} when no hand landmarks available."""
    def test_classifies_open_hand(self):
        """Recognizes open hand from synthetic landmark geometry."""
    def test_classifies_fist(self):
        """Recognizes fist from synthetic landmark geometry."""
    def test_returns_valid_gesture_string(self):
        """Gesture string is from the allowed set."""
    def test_confidence_range(self):
        """Confidence is 0.0-1.0."""

class TestObjectDetectionAnalyzer(unittest.TestCase):
    def test_returns_empty_when_no_cpp(self):
        """Returns {} when perception_cpp unavailable."""
    def test_returns_empty_on_none_frame(self):
        """Returns {} when frame is None."""
    def test_bbox_normalized(self):
        """All bbox coordinates are in [0, 1]."""
    def test_nms_reduces_duplicates(self):
        """NMS correctly suppresses overlapping detections."""
    def test_coco_class_mapping(self):
        """class_id maps to correct class_name."""
    def test_max_detections_limit(self):
        """No more than 20 detections returned."""

class TestEmotionAnalyzer(unittest.TestCase):
    def test_returns_empty_when_no_cpp(self):
        """Returns {} when perception_cpp unavailable."""
    def test_softmax_sums_to_one(self):
        """Scores sum to approximately 1.0."""
    def test_dominant_emotion_matches_argmax(self):
        """expression matches the class with highest score."""
    def test_valid_emotion_string(self):
        """expression is from the allowed set of 7 emotions."""

class TestPoseSkeletonAnalyzer(unittest.TestCase):
    def test_returns_empty_when_no_cpp(self):
        """Returns {} when perception_cpp unavailable."""
    def test_joints_normalized(self):
        """Joint coordinates are in [0, 1]."""
    def test_confidences_shape(self):
        """confidences has shape (17,)."""
    def test_visible_mask_dtype(self):
        """visible_mask is bool dtype."""
    def test_skeleton_edges_valid(self):
        """All edge indices are in range [0, 16]."""

class TestSceneSegmentationAnalyzer(unittest.TestCase):
    def test_returns_empty_when_no_cpp(self):
        """Returns {} when perception_cpp unavailable."""
    def test_mask_shape_matches_frame(self):
        """Mask shape matches input frame (H, W)."""
    def test_mask_dtype_uint8(self):
        """mask is uint8."""
    def test_person_mask_dtype_bool(self):
        """person_mask is bool."""
```

**Acceptance criteria:**
- [ ] Test file exists at `python/ascii_stream_engine/tests/test_perception_new.py`
- [ ] At least 5 test methods per analyzer (25+ tests total)
- [ ] All tests pass with `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_perception_new.py -v`
- [ ] Tests that require C++ module are skipped with `@unittest.skipUnless` when module unavailable
- [ ] Tests use synthetic numpy frames, never real camera input
- [ ] Tests use `unittest.mock.patch` to simulate C++ module presence/absence

#### 3.2 Test graceful degradation

Add tests to the same file verifying robustness:

```python
class TestGracefulDegradation(unittest.TestCase):
    def test_all_analyzers_return_empty_on_none_frame(self):
        """Every analyzer returns {} when frame is None."""
    def test_all_analyzers_return_empty_on_wrong_shape(self):
        """Every analyzer returns {} when frame has wrong dimensions."""
    def test_all_analyzers_return_empty_on_wrong_dtype(self):
        """Every analyzer returns {} when frame is float64 instead of uint8."""
    def test_all_analyzers_catch_exceptions(self):
        """No analyzer raises an exception; all return {} on internal error."""
    def test_cpp_import_failure_returns_empty(self):
        """Simulated ImportError yields {} for every analyzer."""
```

**Acceptance criteria:**
- [ ] Degradation tests cover all 5 analyzers
- [ ] No test depends on model files being present
- [ ] No test depends on C++ module being compiled
- [ ] All degradation tests pass

#### 3.3 Test output dict schema compliance

Add schema validation tests:

```python
class TestSchemaCompliance(unittest.TestCase):
    def test_hand_gesture_schema(self):
        """Validate all required keys and types in hand_gesture output."""
    def test_objects_schema(self):
        """Validate all required keys and types in objects output."""
    def test_emotion_schema(self):
        """Validate all required keys and types in emotion output."""
    def test_pose_skeleton_schema(self):
        """Validate all required keys and types in pose_skeleton output."""
    def test_segmentation_schema(self):
        """Validate all required keys and types in segmentation output."""
    def test_no_key_collisions(self):
        """All analyzer names are unique and do not collide with existing keys."""
```

**Acceptance criteria:**
- [ ] Every output dict key is validated for presence and correct type
- [ ] numpy array shapes and dtypes are validated
- [ ] Coordinate ranges validated (0.0 to 1.0 where applicable)
- [ ] Analyzer `name` attributes are unique across all analyzers (old + new)

#### 3.4 Test normalized coordinate ranges

```python
class TestCoordinateNormalization(unittest.TestCase):
    def test_object_bbox_in_unit_range(self):
        """Object detection bbox values are clipped to [0, 1]."""
    def test_pose_joints_in_unit_range(self):
        """Pose skeleton joint coordinates are in [0, 1]."""
    def test_segmentation_mask_indices_valid(self):
        """Segmentation mask values are valid class indices."""
```

**Acceptance criteria:**
- [ ] Tests verify `np.clip` is applied correctly
- [ ] Tests verify no coordinate exceeds 1.0 or goes below 0.0
- [ ] Tests use frames of various sizes (small 64x64, standard 640x480, large 1920x1080)

**Deliverables:**
- `python/ascii_stream_engine/tests/test_perception_new.py`

---

## Phase 4: C++ Implementation (C++ Implementer)

**Owner:** C++ Implementer agent
**Duration:** 2 sessions
**Depends on:** Phase 1 (model requirements), Phase 2 (Python adapters define the expected C++ API)

### Tasks

#### 4.1 OnnxRunner for YOLOv8-nano object detection

**File:** `cpp/src/perception/object_detection.cpp`

Create a new C++ runner following the pattern in `face_landmarks.cpp`:

```cpp
#include "perception/perception_common.hpp"
#include "perception/onnx_runner.hpp"

namespace perception {
namespace {
std::string get_object_detection_model_path() {
    const char* env = std::getenv("ONNX_MODELS_DIR");
    std::string dir = (env && env[0]) ? env : "onnx_models/mediapipe";
    return dir + "/yolov8n.onnx";
}
}  // namespace

std::vector<float> run_object_detection(std::uint8_t* image, int width, int height) {
#ifdef USE_ONNXRUNTIME
    static OnnxRunner runner;
    if (!runner.is_loaded() && !runner.load(get_object_detection_model_path()))
        return {};
    return runner.run(image, width, height);
#else
    (void)image; (void)width; (void)height;
    return {};
#endif
}
}  // namespace perception
```

Additionally, add YOLOv8 detection post-processing to `onnx_runner.cpp` (or a new helper):
- Parse (1, 84, 8400) output: 4 bbox values + 80 class scores per detection
- Transpose to (8400, 84) for easier iteration
- Filter by confidence threshold (0.25)
- Return flat float array: [x1, y1, x2, y2, confidence, class_id, x1, y1, ...] per detection

**Acceptance criteria:**
- [ ] File compiles with `make cpp-build`
- [ ] Static OnnxRunner pattern used (lazy load, singleton)
- [ ] `#ifdef USE_ONNXRUNTIME` guard present
- [ ] Returns `{}` on any failure
- [ ] No heap allocations per frame (uses preallocated buffers)
- [ ] Post-processing produces original-pixel-space coordinates

#### 4.2 OnnxRunner for emotion model inference

**File:** `cpp/src/perception/emotion_detection.cpp`

Create a runner for the emotion classification model:

```cpp
namespace perception {
std::vector<float> run_emotion(std::uint8_t* image, int width, int height);
}
```

The emotion model takes a face crop, so the runner must:
- Use OnnxRunner with the emotion model (small, ~48x48 input)
- Return raw logits as a flat float vector of length 7
- Python adapter handles softmax and label mapping

**Acceptance criteria:**
- [ ] File compiles with `make cpp-build`
- [ ] Static OnnxRunner pattern used
- [ ] Returns 7-element float vector (raw logits) on success
- [ ] Returns `{}` on failure
- [ ] `#ifdef USE_ONNXRUNTIME` guard present

#### 4.3 OnnxRunner for scene segmentation

**File:** `cpp/src/perception/scene_segmentation.cpp`

Create a runner for the segmentation model:

```cpp
namespace perception {
std::vector<float> run_segmentation(std::uint8_t* image, int width, int height);
}
```

The segmentation model outputs per-pixel class logits:
- Return raw float array: (num_classes * model_H * model_W) flattened
- Python adapter handles reshape, argmax, and resize to original frame size

**Acceptance criteria:**
- [ ] File compiles with `make cpp-build`
- [ ] Static OnnxRunner pattern used
- [ ] Returns flat float array of logits on success
- [ ] Returns `{}` on failure
- [ ] `#ifdef USE_ONNXRUNTIME` guard present

#### 4.4 OnnxRunner for pose with confidence

**File:** `cpp/src/perception/pose_landmarks.cpp` (modify existing)

Extend the existing pose runner to optionally return confidence scores:

```cpp
namespace perception {
// Existing:
std::vector<float> run_pose(std::uint8_t* image, int width, int height);
// New:
std::vector<float> run_pose_with_confidence(std::uint8_t* image, int width, int height);
}
```

The `run_pose_with_confidence` function returns (x, y, confidence) triplets instead of (x, y) pairs. This requires modifying the YOLOv8 pose post-processing to preserve the per-keypoint confidence values.

**Acceptance criteria:**
- [ ] Existing `run_pose` continues to work unchanged
- [ ] New function returns (N*3) flat array: x, y, conf for each joint
- [ ] Confidence values are preserved from model output (0.0-1.0)
- [ ] Coordinates are in original pixel space (letterbox undone)

#### 4.5 Add pybind11 bindings

**File:** `cpp/src/bridge/pybind_perception.cpp` (modify existing)

Add four new bindings following the existing pattern:

```cpp
m.def("detect_objects", [](py::array_t<std::uint8_t> frame) {
    require_3d_uint8(frame);
    py::buffer_info buf = frame.request();
    int h = static_cast<int>(buf.shape[0]);
    int w = static_cast<int>(buf.shape[1]);
    std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
    std::vector<float> data;
    {
        py::gil_scoped_release release;
        data = perception::run_object_detection(ptr, w, h);
    }
    // Return as 1D float array; Python does NMS and reshape
    return py::array_t<float>({static_cast<py::ssize_t>(data.size())}, data.data());
}, py::arg("frame"), "Detect objects (YOLOv8-nano). Returns flat float32 array.");

m.def("detect_emotion", [](py::array_t<std::uint8_t> frame) { ... });
m.def("detect_segmentation", [](py::array_t<std::uint8_t> frame) { ... });
m.def("detect_pose_with_confidence", [](py::array_t<std::uint8_t> frame) { ... });
```

**Mandatory for each binding:**
- `require_3d_uint8(frame)` validation
- `py::gil_scoped_release` wrapping inference call
- No `py::*` access inside the release block
- Return appropriate numpy array shape

**Acceptance criteria:**
- [ ] All 4 new bindings compile
- [ ] Each binding has `py::gil_scoped_release`
- [ ] Each binding has `require_3d_uint8` validation
- [ ] `perception_cpp` module exposes `detect_objects`, `detect_emotion`, `detect_segmentation`, `detect_pose_with_confidence`
- [ ] Existing `detect_face`, `detect_hands`, `detect_pose` are unchanged

#### 4.6 Update CMakeLists.txt

**File:** `cpp/CMakeLists.txt`

Add the new `.cpp` source files to the `perception_cpp` target:
- `src/perception/object_detection.cpp`
- `src/perception/emotion_detection.cpp`
- `src/perception/scene_segmentation.cpp`

**Acceptance criteria:**
- [ ] `make cpp-build` succeeds with all new files
- [ ] No linker errors
- [ ] `perception_cpp.so` exports all new symbols

#### 4.7 Update perception API header

**File:** `cpp/include/perception/perception_api.hpp` (or equivalent header)

Add function declarations:

```cpp
namespace perception {
std::vector<float> run_object_detection(std::uint8_t* image, int width, int height);
std::vector<float> run_emotion(std::uint8_t* image, int width, int height);
std::vector<float> run_segmentation(std::uint8_t* image, int width, int height);
std::vector<float> run_pose_with_confidence(std::uint8_t* image, int width, int height);
}
```

**Acceptance criteria:**
- [ ] Header compiles without errors
- [ ] All function signatures match their implementations

**Deliverables:**
- `cpp/src/perception/object_detection.cpp`
- `cpp/src/perception/emotion_detection.cpp`
- `cpp/src/perception/scene_segmentation.cpp`
- Modified `cpp/src/perception/pose_landmarks.cpp`
- Modified `cpp/src/bridge/pybind_perception.cpp`
- Modified `cpp/include/perception/perception_api.hpp`
- Modified `cpp/CMakeLists.txt`

---

## Phase 5: Integration Tests (Test Agent + Integration Coordinator)

**Owner:** Test Agent (writes tests), Integration Coordinator (runs full pipeline)
**Duration:** 1 session
**Depends on:** Phase 2, Phase 3, Phase 4

### Tasks

#### 5.1 Test analyzer pipeline with multiple analyzers enabled

**File:** `python/ascii_stream_engine/tests/test_perception_integration.py`

```python
class TestMultiAnalyzerPipeline(unittest.TestCase):
    def test_all_analyzers_run_without_error(self):
        """Enable all 8 analyzers (3 existing + 5 new) and run a frame through."""
    def test_analysis_dict_has_all_keys(self):
        """Combined analysis dict contains keys from all enabled analyzers."""
    def test_disabled_analyzer_produces_no_key(self):
        """Disabled analyzer does not add its key to the analysis dict."""
    def test_pipeline_recovers_from_single_analyzer_failure(self):
        """If one analyzer raises internally, others still produce output."""
```

**Acceptance criteria:**
- [ ] Tests exercise the analyzer pipeline (not just individual analyzers)
- [ ] Tests verify dict merging across all analyzers
- [ ] Tests use mocked C++ module to avoid hardware dependency
- [ ] Pipeline error isolation is verified

#### 5.2 Test analysis dict merging across analyzers

```python
class TestAnalysisDictMerging(unittest.TestCase):
    def test_keys_are_analyzer_names(self):
        """Each top-level key matches an analyzer's name attribute."""
    def test_no_key_overwrites(self):
        """No analyzer overwrites another analyzer's key."""
    def test_empty_results_do_not_pollute_dict(self):
        """Analyzer returning {} does not add empty key to merged dict."""
    def test_order_independence(self):
        """Analysis dict is the same regardless of analyzer execution order."""
```

**Acceptance criteria:**
- [ ] Dict merging logic tested with all analyzer combinations
- [ ] Key uniqueness verified programmatically

#### 5.3 Verify no frame modification

```python
class TestFrameImmutability(unittest.TestCase):
    def test_frame_unchanged_after_all_analyzers(self):
        """Frame data is bit-identical before and after running all analyzers."""
```

Implementation:
- Create a frame, copy it with `frame.copy()`
- Run all analyzers on the original
- Assert `np.array_equal(frame, frame_copy)` is True

**Acceptance criteria:**
- [ ] Frame immutability test covers all 8 analyzers
- [ ] Test uses `np.array_equal` for exact comparison
- [ ] Test runs with a non-trivial frame (not all zeros)

#### 5.4 Test with real model files if available, stubs otherwise

```python
@unittest.skipUnless(os.path.exists("onnx_models/mediapipe/yolov8n.onnx"), "model not available")
class TestWithRealModels(unittest.TestCase):
    def test_object_detection_with_real_model(self):
        """Object detection produces valid output with real YOLOv8n model."""
    def test_segmentation_with_real_model(self):
        """Segmentation produces valid mask with real model."""
```

**Acceptance criteria:**
- [ ] Tests are skipped gracefully when model files are absent
- [ ] Tests validate output shapes and value ranges when models are present
- [ ] Tests do not fail in CI (where models may not be available)

**Deliverables:**
- `python/ascii_stream_engine/tests/test_perception_integration.py`

---

## Phase 6: Performance Validation (Optimizer)

**Owner:** Optimizer agent
**Duration:** 1 session
**Depends on:** Phase 4 (C++ compiled), Phase 5 (integration tests pass)

### Tasks

#### 6.1 Profile each analyzer against 5ms single-analyzer budget

**Method:** Use `time.perf_counter()` in Python, measure 100 frames, report mean/p50/p95/p99.

Profile script location: `python/ascii_stream_engine/tests/bench_perception.py` (not a pytest file, a standalone benchmark script)

```python
"""Perception analyzer latency benchmark."""
import time
import numpy as np

ANALYZERS = [
    ("hand_gesture", HandGestureAnalyzer),
    ("objects", ObjectDetectionAnalyzer),
    ("emotion", EmotionAnalyzer),
    ("pose_skeleton", PoseSkeletonAnalyzer),
    ("segmentation", SceneSegmentationAnalyzer),
]

for name, cls in ANALYZERS:
    analyzer = cls()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        analyzer.analyze(frame, config)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"{name}: mean={np.mean(times):.2f}ms p50={np.median(times):.2f}ms "
          f"p95={np.percentile(times, 95):.2f}ms p99={np.percentile(times, 99):.2f}ms")
```

**Acceptance criteria:**
- [ ] Each analyzer profiled with 100-frame measurement
- [ ] Results documented in `findings.md` update
- [ ] Analyzers exceeding 5ms budget are flagged with mitigation plan

#### 6.2 Profile combined analyzers against 15ms budget

Run all 8 analyzers (3 existing + 5 new) sequentially on the same frame and measure total time.

**Acceptance criteria:**
- [ ] Total combined latency measured
- [ ] If >15ms, document which analyzers to frame-skip
- [ ] Recommended analyzer subsets for different FPS targets documented

#### 6.3 Implement frame-skipping for heavy analyzers

For analyzers that exceed the 5ms budget (expected: ObjectDetectionAnalyzer, PoseSkeletonAnalyzer, possibly SceneSegmentationAnalyzer), implement frame-skipping logic:

**File:** Modify each heavy analyzer to add frame-skipping support.

```python
class ObjectDetectionAnalyzer(BaseAnalyzer):
    name = "objects"
    enabled = True
    _skip_interval = 2          # run every Nth frame
    _frame_count = 0
    _last_result = {}

    def analyze(self, frame, config):
        self._frame_count += 1
        if self._frame_count % self._skip_interval != 0:
            return self._last_result  # reuse previous result
        # ... actual inference ...
        self._last_result = result
        return result
```

**Acceptance criteria:**
- [ ] Frame-skipping only applied to analyzers exceeding 5ms
- [ ] Skip interval is configurable
- [ ] Previous result is cached and returned on skipped frames
- [ ] `_last_result` is `{}` until first real inference
- [ ] HandGestureAnalyzer does NOT have frame-skipping (under 1ms)

#### 6.4 Document latency in MODEL_REGISTRY.md format

**File:** `rules/MODEL_REGISTRY.md` (append new entries)

Add registry entries for each new model:

```markdown
### yolov8n.onnx (YOLOv8-nano Object Detection)

| Field | Value |
|---|---|
| Name | YOLOv8-nano |
| File | `onnx_models/mediapipe/yolov8n.onnx` |
| Source | HuggingFace: Xenova/yolov8n |
| SHA256 | `<measured>` |
| Size | ~6MB |
| Input | `(1, 3, 640, 640)` NCHW float32, normalized 0-1, RGB |
| Output | `(1, 84, 8400)` float32 |
| CPU latency (measured) | `<measured>` |
| Status | APPROVED |
```

**Acceptance criteria:**
- [ ] All new models registered with measured latency
- [ ] SHA256 checksums recorded
- [ ] Input/output shapes documented
- [ ] Status is APPROVED or APPROVED_WITH_FRAME_SKIP

**Deliverables:**
- `python/ascii_stream_engine/tests/bench_perception.py`
- Updated `rules/MODEL_REGISTRY.md`
- Updated `.claude/orchestration/teams/perception/findings.md` (latency section)
- Frame-skipping logic added to heavy analyzers

---

## Phase 7: PR Preparation (Integration Coordinator)

**Owner:** Integration Coordinator agent
**Duration:** 1 session
**Depends on:** Phase 6 (all benchmarks complete, frame-skipping implemented)

### Tasks

#### 7.1 Register all analyzers in __init__.py

**File:** `python/ascii_stream_engine/adapters/perception/__init__.py`

Update exports to include all new analyzers:

```python
"""Perception adapters (face, hands, pose, hand_gesture, objects, emotion, pose_skeleton, segmentation)."""

from .face import FaceLandmarkAnalyzer
from .hands import HandLandmarkAnalyzer
from .pose import PoseLandmarkAnalyzer
from .hand_gesture import HandGestureAnalyzer
from .object_detection import ObjectDetectionAnalyzer
from .emotion import EmotionAnalyzer
from .pose_skeleton import PoseSkeletonAnalyzer
from .segmentation import SceneSegmentationAnalyzer

__all__ = [
    "FaceLandmarkAnalyzer",
    "HandLandmarkAnalyzer",
    "PoseLandmarkAnalyzer",
    "HandGestureAnalyzer",
    "ObjectDetectionAnalyzer",
    "EmotionAnalyzer",
    "PoseSkeletonAnalyzer",
    "SceneSegmentationAnalyzer",
]
```

**Acceptance criteria:**
- [ ] All 8 analyzers are importable from `adapters.perception`
- [ ] `__all__` list is complete and alphabetically or logically ordered
- [ ] `python -c "from ascii_stream_engine.adapters.perception import *"` succeeds

#### 7.2 Update analysis dict schema in PIPELINE_EXTENSION_RULES.md

**File:** `rules/PIPELINE_EXTENSION_RULES.md`

Update section 7 (Analysis Dict Schema) to include all new analyzer schemas:

```python
analysis = {
    "face": { "points": "np.ndarray (N, 2) float32 normalized 0-1" },
    "hands": { "left": "np.ndarray (21, 2)", "right": "np.ndarray (21, 2)" },
    "pose": { "joints": "np.ndarray (17, 2) or (17, 3) normalized 0-1" },
    "tracking": { "objects": "list of tracked object dicts" },
    "hand_gesture": {
        "left_gesture": "str",
        "left_confidence": "float 0-1",
        "right_gesture": "str",
        "right_confidence": "float 0-1",
    },
    "objects": {
        "detections": "list of {class_id, class_name, confidence, bbox}",
        "count": "int",
    },
    "emotion": {
        "expression": "str",
        "confidence": "float 0-1",
        "scores": "np.ndarray (7,) float32",
    },
    "pose_skeleton": {
        "joints": "np.ndarray (17, 2) float32 normalized 0-1",
        "confidences": "np.ndarray (17,) float32",
        "edges": "list of (int, int) tuples",
        "visible_mask": "np.ndarray (17,) bool",
    },
    "segmentation": {
        "mask": "np.ndarray (H, W) uint8",
        "person_mask": "np.ndarray (H, W) bool",
        "num_classes": "int",
    },
}
```

**Acceptance criteria:**
- [ ] All 9 analyzer keys documented (face, hands, pose, tracking + 5 new)
- [ ] Types, shapes, and dtypes specified for every field
- [ ] No key collisions

#### 7.3 Update domain types if needed

**File:** `python/ascii_stream_engine/domain/frame_analysis.py`

Add new dataclasses for the new analyzer outputs:

```python
@dataclass
class HandGestureAnalysis:
    """Gesture classification for each hand."""
    left_gesture: str
    left_confidence: float
    right_gesture: str
    right_confidence: float

@dataclass
class ObjectDetection:
    """Single detected object."""
    class_id: int
    class_name: str
    confidence: float
    bbox: np.ndarray  # (4,) float32 [x1, y1, x2, y2] normalized 0-1

@dataclass
class ObjectDetectionAnalysis:
    """Object detection results."""
    detections: list  # list of ObjectDetection
    count: int

@dataclass
class EmotionAnalysis:
    """Facial emotion classification."""
    expression: str
    confidence: float
    scores: np.ndarray  # (7,) float32

@dataclass
class PoseSkeletonAnalysis:
    """Enhanced pose with confidence and skeleton connectivity."""
    joints: np.ndarray        # (17, 2) float32 normalized 0-1
    confidences: np.ndarray   # (17,) float32
    edges: list               # list of (int, int)
    visible_mask: np.ndarray  # (17,) bool

@dataclass
class SegmentationAnalysis:
    """Scene segmentation mask."""
    mask: np.ndarray          # (H, W) uint8
    person_mask: np.ndarray   # (H, W) bool
    num_classes: int
```

**Acceptance criteria:**
- [ ] Dataclasses match the dict schemas from Phase 1.2
- [ ] Existing dataclasses (FaceAnalysis, HandAnalysis, PoseAnalysis) are NOT modified
- [ ] All fields have type annotations and docstrings

#### 7.4 Update findings.md with final contracts

**File:** `.claude/orchestration/teams/perception/findings.md`

Final update with:
- Confirmed model files and SHA256 hashes
- Measured latency data from Phase 6
- Frame-skipping configuration per analyzer
- Any deviations from the original design
- Known limitations and future improvements

**Acceptance criteria:**
- [ ] All measurements are from actual profiling, not estimates
- [ ] File is complete and self-contained

#### 7.5 Update progress.md with completion status

**File:** `.claude/orchestration/teams/perception/progress.md`

Write completion status for all phases:

```markdown
# Perception Team -- Progress

## Phase Status

| Phase | Status | Blockers | Notes |
|-------|--------|----------|-------|
| 1. Research & Design | COMPLETE | -- | findings.md written |
| 2. Python Implementation | COMPLETE | -- | 5 analyzers implemented |
| 3. Unit Tests | COMPLETE | -- | 25+ tests passing |
| 4. C++ Implementation | COMPLETE | -- | 4 runners + bindings |
| 5. Integration Tests | COMPLETE | -- | Pipeline verified |
| 6. Performance | COMPLETE | -- | Latency documented |
| 7. PR Preparation | COMPLETE | -- | Ready for review |

## Analyzer Status

| Analyzer | Python | C++ | Tests | Perf | Status |
|----------|--------|-----|-------|------|--------|
| HandGesture | done | N/A | done | <1ms | READY |
| ObjectDetection | done | done | done | XXms | READY |
| Emotion | done | done | done | XXms | READY |
| PoseSkeleton | done | done | done | XXms | READY |
| Segmentation | done | done | done | XXms | READY |
```

**Acceptance criteria:**
- [ ] All phases marked with accurate status
- [ ] All analyzers have measured latency
- [ ] Any remaining issues documented

#### 7.6 Run full test suite

Execute the complete test suite to ensure no regressions:

```bash
PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/ -v
```

**Acceptance criteria:**
- [ ] All existing tests continue to pass
- [ ] All new tests pass
- [ ] No warnings about import failures (except expected C++ module skips)

#### 7.7 Format and lint

```bash
make format && make lint
```

**Acceptance criteria:**
- [ ] Black formatting passes
- [ ] isort passes
- [ ] flake8 passes with no new violations

#### 7.8 Create PR to develop

Create a pull request from `feature/perception-analyzers` to `develop`:

```bash
gh pr create \
  --base develop \
  --title "feat(perception): add 5 new ONNX-based analyzers" \
  --body "..."
```

PR body should include:
- Summary of all 5 new analyzers with their dict schemas
- Latency measurements
- List of new files
- List of modified files
- Test coverage summary
- Any known limitations

**Acceptance criteria:**
- [ ] PR is created against `develop` branch
- [ ] PR title follows conventional commit format
- [ ] PR body includes latency data and test summary
- [ ] All CI checks pass
- [ ] No merge conflicts

**Deliverables:**
- Modified `python/ascii_stream_engine/adapters/perception/__init__.py`
- Modified `rules/PIPELINE_EXTENSION_RULES.md`
- Modified `python/ascii_stream_engine/domain/frame_analysis.py`
- Updated `.claude/orchestration/teams/perception/findings.md`
- Created `.claude/orchestration/teams/perception/progress.md`
- PR URL

---

## File Inventory

### New files created by this plan

| File | Phase | Owner |
|------|-------|-------|
| `.claude/orchestration/teams/perception/findings.md` | 1 | Architect |
| `python/ascii_stream_engine/adapters/perception/hand_gesture.py` | 2 | Python Implementer |
| `python/ascii_stream_engine/adapters/perception/object_detection.py` | 2 | Python Implementer |
| `python/ascii_stream_engine/adapters/perception/emotion.py` | 2 | Python Implementer |
| `python/ascii_stream_engine/adapters/perception/pose_skeleton.py` | 2 | Python Implementer |
| `python/ascii_stream_engine/adapters/perception/segmentation.py` | 2 | Python Implementer |
| `python/ascii_stream_engine/tests/test_perception_new.py` | 3 | Test Agent |
| `cpp/src/perception/object_detection.cpp` | 4 | C++ Implementer |
| `cpp/src/perception/emotion_detection.cpp` | 4 | C++ Implementer |
| `cpp/src/perception/scene_segmentation.cpp` | 4 | C++ Implementer |
| `python/ascii_stream_engine/tests/test_perception_integration.py` | 5 | Test Agent |
| `python/ascii_stream_engine/tests/bench_perception.py` | 6 | Optimizer |
| `.claude/orchestration/teams/perception/progress.md` | 7 | Integration Coordinator |

### Existing files modified by this plan

| File | Phase | Change |
|------|-------|--------|
| `cpp/src/perception/pose_landmarks.cpp` | 4 | Add `run_pose_with_confidence` |
| `cpp/src/bridge/pybind_perception.cpp` | 4 | Add 4 new bindings |
| `cpp/include/perception/perception_api.hpp` | 4 | Add 4 function declarations |
| `cpp/CMakeLists.txt` | 4 | Add 3 new source files |
| `python/ascii_stream_engine/adapters/perception/__init__.py` | 7 | Add 5 new exports |
| `python/ascii_stream_engine/domain/frame_analysis.py` | 7 | Add 6 new dataclasses |
| `rules/PIPELINE_EXTENSION_RULES.md` | 7 | Extend analysis dict schema |
| `rules/MODEL_REGISTRY.md` | 6 | Add 3-4 new model entries |
| `.claude/orchestration/teams/perception/findings.md` | 1, 6, 7 | Progressive updates |

### Read-only files (never modify)

| File | Reason |
|------|--------|
| `python/ascii_stream_engine/ports/processors.py` | Port protocol definition |
| `python/ascii_stream_engine/application/engine.py` | Application layer |
| `python/ascii_stream_engine/application/pipeline/analyzer_pipeline.py` | Pipeline orchestrator |
| `python/ascii_stream_engine/application/pipeline/filter_pipeline.py` | Filter orchestrator |

---

## Dependency Graph

```
Phase 1 (Research)
    |
    v
Phase 2 (Python) --------+
    |                     |
    v                     v
Phase 3 (Unit Tests)   Phase 4 (C++)
    |                     |
    +----------+----------+
               |
               v
         Phase 5 (Integration)
               |
               v
         Phase 6 (Performance)
               |
               v
         Phase 7 (PR)
```

Phases 2 and 4 can run in parallel after Phase 1 completes.
Phases 3 and 4 can run in parallel.
Phase 5 requires both Phase 3 and Phase 4 to be complete.
Phases 6 and 7 are strictly sequential.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| YOLOv8-nano exceeds 5ms budget | HIGH | MEDIUM | Frame-skipping (Phase 6.3). Already documented for existing pose model at ~15-25ms. |
| Emotion model incompatible with OnnxRunner | MEDIUM | LOW | OnnxRunner handles standard NCHW models. If model needs special preprocessing, add adapter logic in Python. |
| Segmentation model too large (>200MB) | LOW | HIGH | Use nano/lite variant. SINet is ~1MB. |
| Hand gesture heuristics unreliable | MEDIUM | LOW | Pure geometry approach is a starting point. Can be replaced with ML classifier later. |
| C++ build fails on CI | LOW | HIGH | `#ifdef USE_ONNXRUNTIME` ensures stub compilation without ONNX Runtime. |
| Multiple analyzers exceed 15ms combined | HIGH | MEDIUM | Frame-skipping + analyzer subset recommendations (Phase 6.2). |
