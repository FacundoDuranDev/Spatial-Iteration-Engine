"""Chromatic Aberration filter -- radial color fringing via per-channel remap.

Splits the frame into B, G, R channels and applies radial displacement to R
(outward) and B (inward) channels relative to a center point, simulating lens
chromatic aberration. Supports radial mode (true lens fringing) and horizontal
mode (CRT-style shift). LUT-cached: remap tables rebuilt only when strength,
center, mode, or resolution change. Analysis-reactive: can follow right-hand
wrist position as aberration center.

LUT-cached: _map_x_r/_map_y_r/_map_x_b/_map_y_b rebuilt on param/resolution change.
"""

import cv2
import numpy as np

from .base import BaseFilter


class ChromaticAberrationFilter(BaseFilter):
    """Radial chromatic aberration filter with LUT-cached remap tables."""

    name = "chromatic_aberration"

    def __init__(
        self,
        strength: float = 3.0,
        center_x: float = 0.5,
        center_y: float = 0.5,
        radial: bool = True,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._strength = strength
        self._center_x = center_x
        self._center_y = center_y
        self._radial = radial
        # LUT cache -- separate maps for R and B channel displacement
        self._map_x_r = None
        self._map_y_r = None
        self._map_x_b = None
        self._map_y_b = None
        self._params_dirty = True
        self._last_shape = None
        self._last_center = None

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        self._strength = value
        self._params_dirty = True

    @property
    def center_x(self):
        return self._center_x

    @center_x.setter
    def center_x(self, value):
        self._center_x = value
        self._params_dirty = True

    @property
    def center_y(self):
        return self._center_y

    @center_y.setter
    def center_y(self, value):
        self._center_y = value
        self._params_dirty = True

    @property
    def radial(self):
        return self._radial

    @radial.setter
    def radial(self, value):
        self._radial = value
        self._params_dirty = True

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        if self._strength == 0:
            return frame

        h, w = frame.shape[:2]
        cx, cy = self._center_x, self._center_y

        # Follow right-hand wrist if available (landmark index 0 = wrist)
        if analysis and "hands" in analysis:
            hands = analysis["hands"]
            right = hands.get("right")
            if right is not None and len(right) > 0:
                cx = float(right[0, 0])
                cy = float(right[0, 1])

        current_center = (cx, cy)

        # Rebuild maps if needed
        needs_rebuild = (
            self._params_dirty
            or (h, w) != self._last_shape
            or current_center != self._last_center
        )
        if needs_rebuild:
            self._build_maps(h, w, cx, cy)
            self._last_shape = (h, w)
            self._last_center = current_center
            self._params_dirty = False

        # Split into B, G, R channels (BGR order)
        b, g, r = cv2.split(frame)

        # Remap R channel outward, B channel inward; G stays untouched
        r_shifted = cv2.remap(
            r,
            self._map_x_r,
            self._map_y_r,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        b_shifted = cv2.remap(
            b,
            self._map_x_b,
            self._map_y_b,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )

        # Merge back to BGR
        out = cv2.merge([b_shifted, g, r_shifted])
        return np.ascontiguousarray(out, dtype=np.uint8)

    def _build_maps(self, h, w, cx, cy):
        """Build per-channel remap tables for chromatic aberration."""
        # Create coordinate grids
        map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)

        if self._radial:
            self._build_radial_maps(h, w, cx, cy, map_x, map_y)
        else:
            self._build_horizontal_maps(h, w, cx, map_x, map_y)

    def _build_radial_maps(self, h, w, cx, cy, map_x, map_y):
        """Build radial displacement maps -- R outward, B inward from center."""
        # Center in pixel coordinates
        cx_px = cx * (w - 1)
        cy_px = cy * (h - 1)

        # Displacement from center
        dx = map_x - cx_px
        dy = map_y - cy_px

        # Normalized radius (by diagonal half-length)
        diag = np.sqrt(float(w**2 + h**2)) / 2.0
        r = np.sqrt(dx**2 + dy**2) / max(diag, 1.0)

        # Per-pixel displacement scale: strength pixels at max radius,
        # linearly proportional to distance from center
        shift = self._strength * r

        # Unit direction vectors (avoid division by zero)
        dist = np.sqrt(dx**2 + dy**2)
        safe_dist = np.maximum(dist, 1e-6)
        ux = dx / safe_dist
        uy = dy / safe_dist

        # R channel: shift outward (source pixel is further from center)
        self._map_x_r = (map_x + ux * shift).astype(np.float32)
        self._map_y_r = (map_y + uy * shift).astype(np.float32)

        # B channel: shift inward (source pixel is closer to center)
        self._map_x_b = (map_x - ux * shift).astype(np.float32)
        self._map_y_b = (map_y - uy * shift).astype(np.float32)

    def _build_horizontal_maps(self, h, w, cx, map_x, map_y):
        """Build horizontal-only displacement maps -- CRT-style shift."""
        # R shifts right, B shifts left (in source coordinates: opposite)
        shift = self._strength

        # R channel: sample from further right (shift source right)
        self._map_x_r = (map_x + shift).astype(np.float32)
        self._map_y_r = map_y.copy()

        # B channel: sample from further left (shift source left)
        self._map_x_b = (map_x - shift).astype(np.float32)
        self._map_y_b = map_y.copy()
