"""Vans Face Tiles -- tile detected faces in a checkerboard grid Vans-style.

Crops the largest detected face from the frame and replicates it across an
NxM grid. Optionally renders only alternating cells (true Vans checker
pattern) leaving the rest as a solid color.

Reads:
  analysis["face"]["faces"][i]["bbox"] -- [x, y, w, h] normalized (0..1)

If no faces are detected, returns the original frame unchanged.
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseFilter


class VansFaceTilesFilter(BaseFilter):
    """Tiles the largest detected face in a Vans-style checker grid."""

    name = "vans_face_tiles"

    def __init__(
        self,
        cols: int = 8,
        rows: int = 6,
        checker: bool = True,
        bg_b: int = 0,
        bg_g: int = 0,
        bg_r: int = 0,
        face_pad: float = 0.15,
        smoothing: float = 0.4,
        hold_frames: int = 8,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._cols = max(1, int(cols))
        self._rows = max(1, int(rows))
        self._checker = bool(checker)
        self._bg = (int(bg_b), int(bg_g), int(bg_r))
        self._face_pad = max(0.0, float(face_pad))
        self._smoothing = float(np.clip(smoothing, 0.0, 0.95))
        self._hold_frames = max(0, int(hold_frames))
        self._last_bbox: Optional[Tuple[float, float, float, float]] = None
        self._lost_frames = 0

    # --- params (uniform setter pattern used elsewhere) ---
    @property
    def cols(self) -> int: return self._cols
    @cols.setter
    def cols(self, v: int) -> None: self._cols = max(1, int(v))

    @property
    def rows(self) -> int: return self._rows
    @rows.setter
    def rows(self, v: int) -> None: self._rows = max(1, int(v))

    @property
    def checker(self) -> bool: return self._checker
    @checker.setter
    def checker(self, v: bool) -> None: self._checker = bool(v)

    @property
    def face_pad(self) -> float: return self._face_pad
    @face_pad.setter
    def face_pad(self, v: float) -> None: self._face_pad = max(0.0, float(v))

    @property
    def smoothing(self) -> float: return self._smoothing
    @smoothing.setter
    def smoothing(self, v: float) -> None:
        self._smoothing = float(np.clip(v, 0.0, 0.95))

    def reset(self) -> None:
        self._last_bbox = None
        self._lost_frames = 0

    # --- core ---
    def _largest_face_bbox(self, analysis) -> Optional[Tuple[float, float, float, float]]:
        if not analysis:
            return None
        face = analysis.get("face") if hasattr(analysis, "get") else None
        if not face or not isinstance(face, dict):
            return None
        faces = face.get("faces") or []
        if not faces:
            return None
        best = max(faces, key=lambda f: (f.get("bbox", [0, 0, 0, 0])[2] *
                                         f.get("bbox", [0, 0, 0, 0])[3]))
        bb = best.get("bbox")
        if not bb or len(bb) < 4:
            return None
        return tuple(float(x) for x in bb[:4])

    def _smoothed_bbox(self, current):
        if current is None:
            self._lost_frames += 1
            if self._lost_frames > self._hold_frames:
                self._last_bbox = None
            return self._last_bbox
        self._lost_frames = 0
        if self._last_bbox is None or self._smoothing <= 0.0:
            self._last_bbox = current
        else:
            a = self._smoothing
            self._last_bbox = tuple(
                a * p + (1.0 - a) * c for p, c in zip(self._last_bbox, current)
            )
        return self._last_bbox

    def apply(self, frame: np.ndarray, config, analysis: Optional[dict] = None):
        if frame is None or frame.size == 0:
            return frame

        bbox = self._smoothed_bbox(self._largest_face_bbox(analysis))
        if bbox is None:
            return frame  # passthrough when no face

        h, w = frame.shape[:2]
        bx, by, bw, bh = bbox
        # Convert to pixel coords with padding
        cx = bx + bw / 2.0
        cy = by + bh / 2.0
        size = max(bw, bh) * (1.0 + self._face_pad)
        # Crop region (square) in pixel coords
        x0 = int(np.clip((cx - size / 2.0) * w, 0, w - 1))
        y0 = int(np.clip((cy - size / 2.0) * h, 0, h - 1))
        x1 = int(np.clip((cx + size / 2.0) * w, x0 + 2, w))
        y1 = int(np.clip((cy + size / 2.0) * h, y0 + 2, h))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return frame

        face_crop = frame[y0:y1, x0:x1]
        if face_crop.size == 0:
            return frame

        # Build output canvas filled with bg color
        out = np.full_like(frame, self._bg, dtype=frame.dtype)

        # Tile dimensions (integer division — last col/row absorb remainder)
        tile_w = w // self._cols
        tile_h = h // self._rows
        if tile_w < 1 or tile_h < 1:
            return frame

        # Pre-resize face to tile size once (cheap re-use)
        face_tile = cv2.resize(face_crop, (tile_w, tile_h),
                               interpolation=cv2.INTER_AREA)

        for r in range(self._rows):
            for c in range(self._cols):
                if self._checker and ((r + c) % 2 == 0):
                    continue
                y_dst = r * tile_h
                x_dst = c * tile_w
                out[y_dst:y_dst + tile_h, x_dst:x_dst + tile_w] = face_tile

        return out
