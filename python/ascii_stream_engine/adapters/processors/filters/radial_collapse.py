"""Radial Collapse / Singularity filter -- polar coordinate remap distortion.

Warps pixels radially toward or away from a center point using exponential
falloff. LUT-cached: remap tables rebuilt only when center, strength, falloff,
or mode change. Analysis-reactive: can follow face centroid.

LUT-cached: _map_x/_map_y rebuilt on param/resolution change.
"""

import cv2
import numpy as np

from .base import BaseFilter


class RadialCollapseFilter(BaseFilter):
    """Radial warp distortion with LUT-cached remap tables."""

    name = "radial_collapse"

    def __init__(
        self,
        center_x: float = 0.5,
        center_y: float = 0.5,
        strength: float = 0.5,
        falloff: float = 0.3,
        mode: str = "collapse",
        follow_face: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._center_x = center_x
        self._center_y = center_y
        self._strength = strength
        self._falloff = falloff
        self._mode = mode
        self._follow_face = follow_face
        # LUT cache
        self._map_x = None
        self._map_y = None
        self._params_dirty = True
        self._last_shape = None
        self._last_center = None

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
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        self._strength = value
        self._params_dirty = True

    @property
    def falloff(self):
        return self._falloff

    @falloff.setter
    def falloff(self, value):
        self._falloff = value
        self._params_dirty = True

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        self._mode = value
        self._params_dirty = True

    def apply(self, frame, config, analysis=None):
        if self._strength == 0:
            return frame

        h, w = frame.shape[:2]
        cx, cy = self._center_x, self._center_y

        # Follow face centroid if enabled and available
        if self._follow_face and analysis and "face" in analysis:
            face_data = analysis["face"]
            points = face_data.get("points")
            if points is not None and len(points) > 0:
                cx = float(np.mean(points[:, 0]))
                cy = float(np.mean(points[:, 1]))

        current_center = (cx, cy)

        # Rebuild maps if needed
        needs_rebuild = (
            self._params_dirty or (h, w) != self._last_shape or current_center != self._last_center
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
        """Build radial distortion remap tables."""
        # Create coordinate grids
        map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)

        # Center in pixel coordinates
        cx_px = cx * (w - 1)
        cy_px = cy * (h - 1)

        # Displacement from center
        dx = map_x - cx_px
        dy = map_y - cy_px

        # Radius (normalized by diagonal half-length)
        diag = np.sqrt(float(w**2 + h**2)) / 2.0
        r = np.sqrt(dx**2 + dy**2) / max(diag, 1.0)

        # Falloff: Gaussian-like decay from center
        falloff_sq = max(self._falloff**2, 1e-6)
        weight = np.exp(-(r**2) / falloff_sq)

        # Distortion factor
        if self._mode == "collapse":
            factor = 1.0 - self._strength * weight
        else:  # "expand"
            factor = 1.0 + self._strength * weight

        # Apply distortion
        self._map_x = (cx_px + dx * factor).astype(np.float32)
        self._map_y = (cy_px + dy * factor).astype(np.float32)
