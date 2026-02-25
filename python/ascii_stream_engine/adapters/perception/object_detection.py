"""Object detection analyzer using YOLOv8-nano via C++ perception_cpp. MVP_03.

Detects objects in the frame and returns bounding boxes, class labels,
and confidence scores. Uses NMS post-processing in Python.

Output schema:
    analysis["objects"] = {
        "detections": [
            {
                "class_id": int,       # COCO class index (0-79)
                "class_name": str,     # COCO class label
                "confidence": float,   # 0.0-1.0
                "bbox": np.ndarray,    # (4,) float32 [x1, y1, x2, y2] normalized 0-1
            },
        ],
        "count": int,                  # total number of detections
    }
"""

from typing import Any, Dict, List

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import perception_cpp as _perception_cpp

    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False

# COCO 80 class labels
COCO_CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]

# NMS parameters
_CONF_THRESHOLD = 0.25
_IOU_THRESHOLD = 0.45
_MAX_DETECTIONS = 20


def _compute_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    """Compute IoU between two boxes in [x1, y1, x2, y2] format."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter

    if union <= 0.0:
        return 0.0
    return inter / union


def _nms(detections: List[Dict[str, Any]], iou_threshold: float) -> List[Dict[str, Any]]:
    """Apply Non-Maximum Suppression to a list of detections."""
    if not detections:
        return []

    # Sort by confidence descending
    detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    keep = []

    while detections:
        best = detections.pop(0)
        keep.append(best)
        detections = [
            d for d in detections if _compute_iou(best["bbox"], d["bbox"]) < iou_threshold
        ]

    return keep


class ObjectDetectionAnalyzer(BaseAnalyzer):
    """Object detection using YOLOv8-nano via perception_cpp.detect_objects.

    Delegates inference to C++ OnnxRunner and performs NMS in Python.
    Returns bounding boxes normalized to 0-1, class labels from COCO,
    and confidence scores.

    Output dict keys:
        detections (list): list of detection dicts with class_id, class_name,
            confidence, bbox
        count (int): total number of detections
    """

    name = "objects"
    enabled = True

    # Frame-skipping for heavy analyzers
    _skip_interval = 2
    _frame_count = 0
    _last_result: Dict[str, Any] = {}

    def __init__(self, enabled: bool = True, skip_interval: int = 2) -> None:
        super().__init__(enabled=enabled)
        self._skip_interval = max(1, skip_interval)
        self._frame_count = 0
        self._last_result = {}

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None or not self.enabled:
            return {}
        try:
            # Frame skipping: reuse previous result on skipped frames
            self._frame_count += 1
            if self._skip_interval > 1 and self._frame_count % self._skip_interval != 0:
                return self._last_result

            raw = _perception_cpp.detect_objects(frame)
            if raw is None or raw.size == 0:
                self._last_result = {}
                return {}

            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            # C++ returns flat array: [x1, y1, x2, y2, confidence, class_id, ...]
            # Each detection is 6 floats
            raw_flat = raw.flatten()
            num_values = len(raw_flat)
            if num_values < 6:
                self._last_result = {}
                return {}

            detections = []
            for i in range(0, num_values - 5, 6):
                conf = float(raw_flat[i + 4])
                if conf < _CONF_THRESHOLD:
                    continue

                class_id = int(raw_flat[i + 5])
                if class_id < 0 or class_id >= len(COCO_CLASSES):
                    continue

                # Normalize bbox coordinates to 0-1
                bbox = np.array(
                    [
                        raw_flat[i + 0] / w,
                        raw_flat[i + 1] / h,
                        raw_flat[i + 2] / w,
                        raw_flat[i + 3] / h,
                    ],
                    dtype=np.float32,
                )
                np.clip(bbox, 0.0, 1.0, out=bbox)

                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": COCO_CLASSES[class_id],
                        "confidence": float(np.clip(conf, 0.0, 1.0)),
                        "bbox": bbox,
                    }
                )

            # Apply NMS
            detections = _nms(detections, _IOU_THRESHOLD)

            # Limit max detections
            detections = detections[:_MAX_DETECTIONS]

            result = {"detections": detections, "count": len(detections)}
            self._last_result = result
            return result
        except Exception:
            return {}
