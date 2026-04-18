"""Kaleidoscope filter -- polar-coordinate segment mirroring.

Divides the frame into N angular segments around a center point, mirrors one
segment across all others to produce radial symmetry. LUT-cached: remap tables
rebuilt only when segments, rotation, center, or resolution change.
Analysis-reactive: can follow right-hand wrist position.

LUT-cached: _map_x/_map_y rebuilt on param/resolution change.
"""

import cv2
import numpy as np

from .base import BaseFilter


class KaleidoscopeFilter(BaseFilter):
    """Kaleidoscope symmetry filter with LUT-cached remap tables."""

    name = "kaleidoscope"

    def __init__(
        self,
        segments: int = 6,
        rotation: float = 0.0,
        center_x: float = 0.5,
        center_y: float = 0.5,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._segments = segments
        self._rotation = rotation
        self._center_x = center_x
        self._center_y = center_y
        # LUT cache
        self._map_x = None
        self._map_y = None
        self._params_dirty = True
        self._last_shape = None
        self._last_center = None

    @property
    def segments(self):
        return self._segments

    @segments.setter
    def segments(self, value):
        self._segments = value
        self._params_dirty = True

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        self._rotation = value
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

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        if self._segments < 2:
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

        # Apply remap
        out = cv2.remap(
            frame,
            self._map_x,
            self._map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        return out

    def _build_maps(self, h, w, cx, cy):
        """Build kaleidoscope remap tables via polar segment mirroring."""
        # Create coordinate grids
        map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)

        # Center in pixel coordinates
        cx_px = cx * (w - 1)
        cy_px = cy * (h - 1)

        # Displacement from center
        dx = map_x - cx_px
        dy = map_y - cy_px

        # Convert to polar
        r = np.sqrt(dx**2 + dy**2)
        theta = np.arctan2(dy, dx) - self._rotation

        # Segment angular width
        seg_angle = 2.0 * np.pi / self._segments

        # Fold angle into first segment [0, seg_angle)
        theta_mod = np.mod(theta, seg_angle)

        # Mirror: reflect the second half of each segment onto the first
        theta_mirror = np.where(
            theta_mod > seg_angle / 2.0,
            seg_angle - theta_mod,
            theta_mod,
        )

        # Add rotation back for source lookup
        theta_final = theta_mirror + self._rotation

        # Convert back to cartesian
        self._map_x = (cx_px + r * np.cos(theta_final)).astype(np.float32)
        self._map_y = (cy_px + r * np.sin(theta_final)).astype(np.float32)
