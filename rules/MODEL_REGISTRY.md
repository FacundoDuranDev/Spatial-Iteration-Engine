# Model Registry

Central registry of all AI models used in the pipeline.
Every model MUST be registered here before use.

See `SECURITY_MODEL_DOWNLOAD.md` for verification procedures.

---

## Registered Models

### pose_landmark.onnx (YOLOv8n-pose)

| Field | Value |
|---|---|
| Name | YOLOv8n-pose |
| File | `onnx_models/mediapipe/pose_landmark.onnx` |
| Source | HuggingFace: Xenova/yolov8n-pose |
| SHA256 | `e16e5f4abb3e67ee77877e8be3823b099463c9504c060008490cc1fd519a1cbb` |
| Size | 6.48 MB |
| Input | `(1, 3, 640, 640)` NCHW float32, normalized 0-1, RGB |
| Output | `(1, 56, 8400)` float32 -- 8400 detections, 56 values per detection (4 bbox + 1 conf + 51 keypoints) |
| Post-processing | YOLOv8 NMS + keypoint extraction (implemented in `onnx_runner.cpp`) |
| Keypoints | 17 COCO keypoints (x, y, confidence) |
| CPU latency (measured) | ~15-25ms at 640x640 input (1 thread) |
| Status | APPROVED, working |

### face_landmark.onnx (DETR face detection)

| Field | Value |
|---|---|
| Name | DETR face detection |
| File | `onnx_models/mediapipe/face_landmark.onnx` |
| Source | HuggingFace: iuliancmarcu/detr-face-detection-onnx |
| SHA256 | `d20f797c161bbdb040a9cd4ee088cfae292a81212a095b003b10962b5a3da218` |
| Size | 159.01 MB |
| Input | Needs investigation -- model may not match expected NCHW contract |
| Output | Needs investigation |
| CPU latency (measured) | Not verified (model may be incompatible with current runner) |
| Status | APPROVED for storage, NOT WORKING in pipeline |
| Notes | DETR model may require different preprocessing than the generic OnnxRunner provides. Need to verify input tensor name, shape, and normalization. Consider replacing with a lighter face detection model. |

### hand_landmark (MediaPipe)

| Field | Value |
|---|---|
| Name | MediaPipe hand landmarks |
| File | `onnx_models/mediapipe/tflite/hand/` |
| Source | MediaPipe official |
| Format | TFLite (NOT ONNX) |
| Status | NOT WORKING -- needs TFLite-to-ONNX conversion |
| Notes | The downloaded file is a TFLite ZIP archive, not an ONNX model. Requires conversion via `tf2onnx` or replacement with an ONNX-native hand detection model. |

---

## Model Requirements for New Models

Before adding a new model, verify:

1. Format is ONNX (convert if necessary)
2. Input is `(1, 3, H, W)` NCHW float32 normalized 0-1
3. File size < 50MB preferred (< 200MB maximum)
4. CPU inference < 20ms at target resolution
5. Source is in the `SECURITY_MODEL_DOWNLOAD.md` whitelist
6. SHA256 checksum is recorded
7. Input/output shapes are documented

---

## Candidate Models (Not Yet Integrated)

Models identified during research for future integration:

| Model | Task | Size | Expected Latency | Source |
|---|---|---|---|---|
| MoveNet SinglePose Lightning | Pose (17kp) | ~3MB | ~8-12ms CPU | TensorFlow Hub -> ONNX |
| MediaPipe BlazePose | Pose (33kp) | ~6MB | ~10-15ms CPU | MediaPipe -> ONNX |
| YOLOv8n-face | Face detection | ~6MB | ~15-20ms CPU | Ultralytics |
| BlazeFace | Face detection | ~0.5MB | ~3-5ms CPU | MediaPipe -> ONNX |
| HandLite | Hand landmarks | ~3MB | ~8-12ms CPU | Needs research |
