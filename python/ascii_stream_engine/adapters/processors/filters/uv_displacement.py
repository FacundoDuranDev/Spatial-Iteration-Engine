"""UV Math Displacement filter -- parametric math-based remap distortion.

Builds remap tables using parametric math functions (sin, cos, spiral, noise)
and applies cv2.remap(). Maps are LUT-cached and only rebuilt when function_type,
amplitude, or frequency change. Phase animates per-frame via a cheap float add
without triggering a LUT rebuild.

LUT-cached: _base_map_x/_base_map_y rebuilt on param change or resolution change.
"""

import cv2
import numpy as np

from .base import BaseFilter


class UVDisplacementFilter(BaseFilter):
    """Parametric math-based UV displacement distortion."""

    name = "uv_displacement"

    def __init__(
        self,
        function_type: str = "sin",
        amplitude: float = 10.0,
        frequency: float = 2.0,
        phase_speed: float = 0.05,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._function_type = function_type
        self._amplitude = amplitude
        self._frequency = frequency
        self._phase_speed = phase_speed
        # LUT cache
        self._base_map_x = None
        self._base_map_y = None
        self._map_x = None
        self._map_y = None
        self._identity_x = None
        self._identity_y = None
        self._params_dirty = True
        self._last_shape = None
        self._phase = 0.0

    @property
    def amplitude(self):
        return self._amplitude

    @amplitude.setter
    def amplitude(self, value):
        self._amplitude = value
        self._params_dirty = True

    @property
    def frequency(self):
        return self._frequency

    @frequency.setter
    def frequency(self, value):
        self._frequency = value
        self._params_dirty = True

    @property
    def function_type(self):
        return self._function_type

    @function_type.setter
    def function_type(self, value):
        self._function_type = value
        self._params_dirty = True

    def apply(self, frame, config, analysis=None):
        if self._amplitude == 0:
            return frame

        h, w = frame.shape[:2]

        # Rebuild base maps if params changed or resolution changed
        if self._params_dirty or (h, w) != self._last_shape:
            self._build_base_maps(h, w)
            self._last_shape = (h, w)
            self._params_dirty = False

        # Apply phase offset (cheap per-frame operation, no LUT rebuild)
        self._apply_phase_offset(h, w)

        # Remap
        out = cv2.remap(
            frame,
            self._map_x,
            self._map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )

        # Advance phase
        self._phase += self._phase_speed

        return out

    def _build_base_maps(self, h, w):
        """Build base remap tables from parametric function."""
        # Identity maps
        self._identity_y, self._identity_x = np.mgrid[0:h, 0:w].astype(np.float32)

        # Normalized coordinates for function input
        ny = self._identity_y / max(h - 1, 1)
        nx = self._identity_x / max(w - 1, 1)

        func = self._function_type
        amp = self._amplitude
        freq = self._frequency

        if func == "sin":
            self._base_map_x = amp * np.sin(freq * ny * 2 * np.pi)
            self._base_map_y = amp * np.cos(freq * nx * 2 * np.pi)
        elif func == "cos":
            self._base_map_x = amp * np.cos(freq * ny * 2 * np.pi)
            self._base_map_y = amp * np.sin(freq * nx * 2 * np.pi)
        elif func == "spiral":
            cx, cy = w / 2.0, h / 2.0
            dx = self._identity_x - cx
            dy = self._identity_y - cy
            r = np.sqrt(dx**2 + dy**2) / max(cx, cy)
            angle = np.arctan2(dy, dx)
            self._base_map_x = amp * np.sin(freq * r * 2 * np.pi + angle)
            self._base_map_y = amp * np.cos(freq * r * 2 * np.pi + angle)
        elif func == "noise":
            # Perlin-like smooth noise using sin composition
            self._base_map_x = amp * (
                np.sin(freq * ny * 2 * np.pi) + 0.5 * np.sin(freq * 2 * nx * 2 * np.pi)
            )
            self._base_map_y = amp * (
                np.cos(freq * nx * 2 * np.pi) + 0.5 * np.cos(freq * 2 * ny * 2 * np.pi)
            )
        else:
            # Default to sin
            self._base_map_x = amp * np.sin(freq * ny * 2 * np.pi)
            self._base_map_y = amp * np.cos(freq * nx * 2 * np.pi)

        self._base_map_x = self._base_map_x.astype(np.float32)
        self._base_map_y = self._base_map_y.astype(np.float32)

    def _apply_phase_offset(self, h, w):
        """Apply phase animation offset to base maps (cheap operation)."""
        phase_offset_x = self._amplitude * 0.3 * np.float32(np.sin(self._phase))
        phase_offset_y = self._amplitude * 0.3 * np.float32(np.cos(self._phase))

        self._map_x = self._identity_x + self._base_map_x + phase_offset_x
        self._map_y = self._identity_y + self._base_map_y + phase_offset_y
