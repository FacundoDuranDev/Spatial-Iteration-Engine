"""Scene segmentation analyzer using C++ perception_cpp. MVP_03.

Produces a per-pixel class mask for background removal and scene understanding.
Uses a lightweight segmentation model via OnnxRunner.

Output schema:
    analysis["segmentation"] = {
        "mask": np.ndarray,            # (H, W) uint8, class ID per pixel
        "person_mask": np.ndarray,     # (H, W) bool, True where person detected
        "num_classes": int,            # number of unique classes in this frame
    }
"""

from typing import Any, Dict

import numpy as np

from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer
from ascii_stream_engine.domain.config import EngineConfig

try:
    import perception_cpp as _perception_cpp

    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# Pascal VOC person class index
_PERSON_CLASS_ID = 15

# Default model output spatial size (common for lightweight seg models)
_MODEL_OUTPUT_H = 256
_MODEL_OUTPUT_W = 256
_NUM_CLASSES_DEFAULT = 21  # Pascal VOC 21 classes


class SceneSegmentationAnalyzer(BaseAnalyzer):
    """Scene segmentation producing per-pixel class mask.

    Delegates inference to perception_cpp.detect_segmentation which returns
    raw logits. Reshapes, applies argmax, resizes to original frame dimensions.

    Output dict keys:
        mask (np.ndarray): (H, W) uint8, class index per pixel
        person_mask (np.ndarray): (H, W) bool, True where person detected
        num_classes (int): number of unique classes in this frame
    """

    name = "segmentation"
    enabled = True

    # Frame-skipping for heavy analyzers
    _skip_interval = 3
    _frame_count = 0
    _last_result: Dict[str, Any] = {}

    def __init__(self, enabled: bool = True, skip_interval: int = 3) -> None:
        super().__init__(enabled=enabled)
        self._skip_interval = max(1, skip_interval)
        self._frame_count = 0
        self._last_result = {}

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None or not self.enabled:
            return {}
        try:
            # Frame skipping
            self._frame_count += 1
            if self._skip_interval > 1 and self._frame_count % self._skip_interval != 0:
                return self._last_result

            raw = _perception_cpp.detect_segmentation(frame)
            if raw is None or raw.size == 0:
                self._last_result = {}
                return {}

            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                return {}

            raw_flat = raw.flatten().astype(np.float32)

            # Determine output shape from raw data size
            total_elements = raw_flat.size

            # Try to infer num_classes and spatial dims
            # Expected: (num_classes, model_H, model_W) flattened
            num_classes = _NUM_CLASSES_DEFAULT
            model_h = _MODEL_OUTPUT_H
            model_w = _MODEL_OUTPUT_W

            expected_size = num_classes * model_h * model_w
            if total_elements == expected_size:
                logits = raw_flat.reshape(num_classes, model_h, model_w)
            elif total_elements == 2 * model_h * model_w:
                # Binary segmentation (2 classes)
                num_classes = 2
                logits = raw_flat.reshape(2, model_h, model_w)
            elif total_elements > 0:
                # Try to find compatible dimensions
                # Assume square spatial with the most likely class count
                for nc in [21, 2, 19, 80]:
                    spatial = total_elements // nc
                    side = int(np.sqrt(spatial))
                    if side * side * nc == total_elements:
                        num_classes = nc
                        model_h = side
                        model_w = side
                        logits = raw_flat.reshape(num_classes, model_h, model_w)
                        break
                else:
                    self._last_result = {}
                    return {}
            else:
                self._last_result = {}
                return {}

            # Argmax along class axis to get per-pixel class index
            mask_small = np.argmax(logits, axis=0).astype(np.uint8)

            # Resize to original frame dimensions using nearest-neighbor
            if _CV2_AVAILABLE:
                mask = cv2.resize(mask_small, (w, h), interpolation=cv2.INTER_NEAREST)
            else:
                # Fallback: simple nearest-neighbor resize via numpy
                row_idx = (np.arange(h) * model_h // h).clip(0, model_h - 1)
                col_idx = (np.arange(w) * model_w // w).clip(0, model_w - 1)
                mask = mask_small[np.ix_(row_idx, col_idx)]

            mask = mask.astype(np.uint8)

            # Person mask
            person_mask = mask == _PERSON_CLASS_ID

            # Count unique classes
            unique_classes = int(len(np.unique(mask)))

            result = {
                "mask": mask,
                "person_mask": person_mask,
                "num_classes": unique_classes,
            }
            self._last_result = result
            return result
        except Exception:
            return {}
