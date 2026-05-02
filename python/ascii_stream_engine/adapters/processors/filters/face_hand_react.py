"""Face + Hand reactive distortion filter.

Deforms ONLY the face and hand regions of the frame, while the rest of the
image is left untouched. The face region is additionally color-inverted.
Both deformations react to hand motion: the faster the hands move, the
stronger the swirl on the hands and the wobble on the face.

Inputs (analysis dict):
  - analysis["face"]["faces"][0]["bbox"]  -> [x, y, w, h] normalized (0..1)
  - analysis["hands"]["left"]  / ["right"] -> 21 landmarks normalized (0..1)

Hand loss is tolerated for ``hold_frames`` frames before the effect fades.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from .base import BaseFilter


_WRIST = 0
_MIDDLE_MCP = 9


class FaceHandReactFilter(BaseFilter):
    """Localized swirl on hands + wobble+invert on face, reactive to hand speed."""

    name = "face_hand_react"

    def __init__(
        self,
        strength: float = 0.6,
        react: float = 1.0,
        face_invert: float = 1.0,
        smoothing: float = 0.4,
        hold_frames: int = 12,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._strength = float(strength)
        self._react = float(react)
        self._face_invert = float(face_invert)
        self._smoothing = float(smoothing)
        self._hold_frames = int(hold_frames)

        self._prev_hand_centers: Dict[str, np.ndarray] = {}
        self._smooth_speed: float = 0.0
        self._hand_state: Dict[str, Dict[str, Any]] = {
            "left": {"center": None, "lost": 0},
            "right": {"center": None, "lost": 0},
        }
        self._face_state: Dict[str, Any] = {"bbox": None, "lost": 0}

        self._grid_cache: Optional[Tuple[int, int, np.ndarray, np.ndarray]] = None

    # ── parameter setters used by the v3 registry ────────────────────────
    @property
    def strength(self) -> float: return self._strength
    @strength.setter
    def strength(self, v: float) -> None: self._strength = float(v)

    @property
    def react(self) -> float: return self._react
    @react.setter
    def react(self, v: float) -> None: self._react = float(v)

    @property
    def face_invert(self) -> float: return self._face_invert
    @face_invert.setter
    def face_invert(self, v: float) -> None: self._face_invert = float(v)

    def reset(self) -> None:
        self._prev_hand_centers.clear()
        self._smooth_speed = 0.0
        for s in self._hand_state.values():
            s["center"] = None
            s["lost"] = 0
        self._face_state["bbox"] = None
        self._face_state["lost"] = 0

    # ── core ─────────────────────────────────────────────────────────────
    def apply(self, frame: np.ndarray, config, analysis: Optional[dict] = None):
        if frame is None or frame.size == 0:
            return frame

        h, w = frame.shape[:2]
        face_bbox = self._track_face(analysis)
        hand_centers = self._track_hands(analysis)
        speed = self._update_speed(hand_centers)

        if face_bbox is None and not hand_centers:
            return frame

        # Build identity remap grid (cached per frame size).
        gx, gy = self._identity_grid(h, w)
        map_x = gx.copy()
        map_y = gy.copy()

        # Reactive multiplier: 1.0 at rest, grows with normalized hand speed.
        react_mul = 1.0 + self._react * min(speed * 6.0, 2.5)
        amp_px = self._strength * 18.0 * react_mul  # max ~45 px when reactive

        face_mask = None
        if face_bbox is not None:
            face_mask = self._apply_face_wobble(map_x, map_y, gx, gy, face_bbox, amp_px)

        for side, center in hand_centers.items():
            self._apply_hand_swirl(map_x, map_y, gx, gy, center, amp_px, side)

        warped = cv2.remap(
            frame, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

        if face_mask is not None and self._face_invert > 0.0:
            inv = 255 - warped
            m = (face_mask * self._face_invert).astype(np.float32)
            m3 = m[:, :, None]
            out = warped.astype(np.float32) * (1.0 - m3) + inv.astype(np.float32) * m3
            warped = np.clip(out, 0, 255).astype(np.uint8)

        return warped

    # ── tracking helpers ─────────────────────────────────────────────────
    def _track_face(self, analysis):
        face_bbox = None
        if analysis:
            face = analysis.get("face") if hasattr(analysis, "get") else None
            if face and isinstance(face, dict):
                faces = face.get("faces") or []
                if faces:
                    bbox = faces[0].get("bbox")
                    if bbox and len(bbox) == 4:
                        face_bbox = (
                            float(bbox[0]) + float(bbox[2]) * 0.5,
                            float(bbox[1]) + float(bbox[3]) * 0.5,
                            max(float(bbox[2]), 1e-3),
                            max(float(bbox[3]), 1e-3),
                        )

        prev = self._face_state["bbox"]
        if face_bbox is not None:
            if prev is not None:
                a = self._smoothing
                face_bbox = tuple(
                    a * face_bbox[i] + (1.0 - a) * prev[i] for i in range(4)
                )
            self._face_state["bbox"] = face_bbox
            self._face_state["lost"] = 0
            return face_bbox

        if prev is not None and self._face_state["lost"] < self._hold_frames:
            self._face_state["lost"] += 1
            return prev
        self._face_state["bbox"] = None
        return None

    def _track_hands(self, analysis) -> Dict[str, np.ndarray]:
        result: Dict[str, np.ndarray] = {}
        hands = None
        if analysis:
            hands = analysis.get("hands") if hasattr(analysis, "get") else None

        for side in ("left", "right"):
            pts = hands.get(side) if isinstance(hands, dict) else None
            center = None
            if pts is not None and hasattr(pts, "__len__") and len(pts) > _MIDDLE_MCP:
                p_wrist = pts[_WRIST]
                p_mid = pts[_MIDDLE_MCP]
                center = np.array([
                    (float(p_wrist[0]) + float(p_mid[0])) * 0.5,
                    (float(p_wrist[1]) + float(p_mid[1])) * 0.5,
                ], dtype=np.float32)

            state = self._hand_state[side]
            if center is not None:
                if state["center"] is not None:
                    a = self._smoothing
                    center = a * center + (1.0 - a) * state["center"]
                state["center"] = center
                state["lost"] = 0
                result[side] = center
            elif state["center"] is not None and state["lost"] < self._hold_frames:
                state["lost"] += 1
                result[side] = state["center"]
            else:
                state["center"] = None
        return result

    def _update_speed(self, centers: Dict[str, np.ndarray]) -> float:
        inst = 0.0
        n = 0
        for side, c in centers.items():
            prev = self._prev_hand_centers.get(side)
            if prev is not None:
                inst += float(np.linalg.norm(c - prev))
                n += 1
            self._prev_hand_centers[side] = c.copy()
        if n:
            inst /= n
        # EMA smoothing for stability
        self._smooth_speed = 0.7 * self._smooth_speed + 0.3 * inst
        return self._smooth_speed

    # ── deformation kernels ──────────────────────────────────────────────
    def _identity_grid(self, h: int, w: int) -> Tuple[np.ndarray, np.ndarray]:
        cache = self._grid_cache
        if cache is not None and cache[0] == h and cache[1] == w:
            return cache[2], cache[3]
        ys, xs = np.meshgrid(
            np.arange(h, dtype=np.float32),
            np.arange(w, dtype=np.float32),
            indexing="ij",
        )
        self._grid_cache = (h, w, xs, ys)
        return xs, ys

    def _apply_face_wobble(
        self, map_x, map_y, gx, gy, face_bbox, amp_px,
    ) -> np.ndarray:
        h, w = map_x.shape
        cx_n, cy_n, bw_n, bh_n = face_bbox
        cx, cy = cx_n * w, cy_n * h
        rx = max(bw_n * w * 0.6, 8.0)
        ry = max(bh_n * h * 0.6, 8.0)

        dx = (gx - cx) / rx
        dy = (gy - cy) / ry
        dist2 = dx * dx + dy * dy
        mask = np.exp(-dist2 * 1.4).astype(np.float32)

        # Horizontal wobble depending on y; gives a "melting" feel.
        wob = np.sin(dy * 6.0) * amp_px
        map_x += wob * mask
        map_y += np.cos(dx * 6.0) * (amp_px * 0.5) * mask
        return mask

    def _apply_hand_swirl(self, map_x, map_y, gx, gy, center, amp_px, side: str):
        h, w = map_x.shape
        cx = float(center[0]) * w
        cy = float(center[1]) * h
        radius = max(min(h, w) * 0.18, 40.0)

        rel_x = gx - cx
        rel_y = gy - cy
        r2 = rel_x * rel_x + rel_y * rel_y
        sigma2 = radius * radius
        mask = np.exp(-r2 / (sigma2 * 0.6)).astype(np.float32)

        # Swirl: opposite directions per hand for a "twisting space" feel.
        sign = 1.0 if side == "left" else -1.0
        angle = sign * mask * (amp_px / 20.0)
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        new_rel_x = rel_x * cos_a - rel_y * sin_a
        new_rel_y = rel_x * sin_a + rel_y * cos_a

        map_x += (new_rel_x - rel_x) * mask
        map_y += (new_rel_y - rel_y) * mask
