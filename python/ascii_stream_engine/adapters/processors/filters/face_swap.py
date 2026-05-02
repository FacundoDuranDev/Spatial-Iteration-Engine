"""Face swap filter — exchanges faces among everyone visible in the frame.

For 2 faces it swaps A↔B. For N>2 it cyclically rotates faces by one slot
(face[0]→bbox[1], face[1]→bbox[2], ..., face[N-1]→bbox[0]).

Uses an elliptical feathered mask sized to each target bbox so the paste
blends smoothly with the surrounding skin/background.

Reads:
  analysis["face"]["faces"][i]["bbox"] — [x, y, w, h] normalized (0..1)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .base import BaseFilter


class FaceSwapFilter(BaseFilter):
    """Swap face regions between every detected face."""

    name = "face_swap"

    def __init__(
        self,
        feather: float = 0.25,
        scale: float = 1.05,
        smoothing: float = 0.5,
        hold_frames: int = 8,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._feather = float(feather)
        self._scale = float(scale)
        self._smoothing = float(smoothing)
        self._hold_frames = int(hold_frames)
        self._smooth_bboxes: List[Tuple[float, float, float, float]] = []
        self._lost_frames = 0

    @property
    def feather(self) -> float: return self._feather
    @feather.setter
    def feather(self, v: float) -> None: self._feather = float(v)

    @property
    def scale(self) -> float: return self._scale
    @scale.setter
    def scale(self, v: float) -> None: self._scale = float(v)

    def reset(self) -> None:
        self._smooth_bboxes = []
        self._lost_frames = 0

    def apply(self, frame: np.ndarray, config, analysis: Optional[dict] = None):
        if frame is None or frame.size == 0:
            return frame

        bboxes = self._read_bboxes(analysis, frame.shape[:2])

        if bboxes:
            bboxes = self._smooth(bboxes)
            self._smooth_bboxes = bboxes
            self._lost_frames = 0
        elif self._smooth_bboxes and self._lost_frames < self._hold_frames:
            bboxes = self._smooth_bboxes
            self._lost_frames += 1
        else:
            self._smooth_bboxes = []
            return frame

        if len(bboxes) < 2:
            return frame

        return self._swap(frame, bboxes)

    # ── helpers ──────────────────────────────────────────────────────────
    def _read_bboxes(
        self, analysis, shape: Tuple[int, int]
    ) -> List[Tuple[float, float, float, float]]:
        if not analysis:
            return []
        face = analysis.get("face") if hasattr(analysis, "get") else None
        if not face or not isinstance(face, dict):
            return []
        faces = face.get("faces") or []

        h, w = shape
        result: List[Tuple[float, float, float, float]] = []
        for f in faces:
            bb = f.get("bbox") if isinstance(f, dict) else None
            if not bb or len(bb) != 4:
                continue
            cx = (float(bb[0]) + float(bb[2]) * 0.5) * w
            cy = (float(bb[1]) + float(bb[3]) * 0.5) * h
            bw = max(float(bb[2]) * w * self._scale, 8.0)
            bh = max(float(bb[3]) * h * self._scale, 8.0)
            result.append((cx, cy, bw, bh))
        # sort left-to-right for stable pairing across frames
        result.sort(key=lambda b: b[0])
        return result

    def _smooth(self, bboxes):
        if not self._smooth_bboxes or len(self._smooth_bboxes) != len(bboxes):
            return bboxes
        a = self._smoothing
        out = []
        for new, old in zip(bboxes, self._smooth_bboxes):
            out.append(tuple(a * new[i] + (1.0 - a) * old[i] for i in range(4)))
        return out

    def _swap(self, frame: np.ndarray, bboxes) -> np.ndarray:
        h, w = frame.shape[:2]
        n = len(bboxes)

        # Snapshot every source ROI BEFORE writing anything to `out`.
        sources: List[Tuple[np.ndarray, Tuple[int, int, int, int]]] = []
        for cx, cy, bw, bh in bboxes:
            x1 = int(np.clip(cx - bw * 0.5, 0, w - 1))
            x2 = int(np.clip(cx + bw * 0.5, 0, w))
            y1 = int(np.clip(cy - bh * 0.5, 0, h - 1))
            y2 = int(np.clip(cy + bh * 0.5, 0, h))
            if x2 <= x1 or y2 <= y1:
                sources.append((np.empty((0, 0, 3), dtype=frame.dtype), (0, 0, 0, 0)))
                continue
            roi = frame[y1:y2, x1:x2].copy()
            sources.append((roi, (x1, y1, x2, y2)))

        out = frame.copy()
        # Cyclic rotation: face i takes the appearance of face (i+1) % n.
        for i in range(n):
            src_roi, _ = sources[(i + 1) % n]
            _, dst_box = sources[i]
            x1, y1, x2, y2 = dst_box
            tw, th = x2 - x1, y2 - y1
            if src_roi.size == 0 or tw <= 0 or th <= 0:
                continue

            resized = cv2.resize(src_roi, (tw, th), interpolation=cv2.INTER_LINEAR)
            mask = self._ellipse_mask(th, tw)
            mask3 = mask[:, :, None]
            dst = out[y1:y2, x1:x2].astype(np.float32)
            blended = dst * (1.0 - mask3) + resized.astype(np.float32) * mask3
            out[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)

        return out

    def _ellipse_mask(self, h: int, w: int) -> np.ndarray:
        ys, xs = np.meshgrid(
            np.linspace(-1.0, 1.0, h, dtype=np.float32),
            np.linspace(-1.0, 1.0, w, dtype=np.float32),
            indexing="ij",
        )
        d = np.sqrt(xs * xs + ys * ys)
        # Solid inside up to (1 - feather), then linear roll-off to 0 at edge.
        f = max(min(self._feather, 0.95), 0.01)
        edge = 1.0
        inner = edge - f
        m = np.clip((edge - d) / max(edge - inner, 1e-3), 0.0, 1.0)
        return m.astype(np.float32)
