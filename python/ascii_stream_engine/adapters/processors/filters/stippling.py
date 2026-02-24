"""Stippling / Pointillism filter -- LUT-cached dot placement effect.

Converts frame to a pointillist style by placing dots on a background.
Dot density and size are controlled by local luminance. The sampling grid
is precomputed (LUT-cached) and only rebuilt when density or resolution changes.

LUT-cached: _sampling_grid rebuilt on density/resolution change.
"""

import cv2
import numpy as np

from .base import BaseFilter
from .conversion_cache import get_cached_conversion


class StipplingFilter(BaseFilter):
    """Pointillism effect with LUT-cached sampling grid."""

    name = "stippling"

    def __init__(
        self,
        density: float = 0.5,
        min_dot_size: int = 1,
        max_dot_size: int = 4,
        background_color: tuple = (0, 0, 0),
        invert_size: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._density = density
        self._min_dot_size = min_dot_size
        self._max_dot_size = max_dot_size
        self._background_color = background_color
        self._invert_size = invert_size
        # LUT cache
        self._sampling_grid = None
        self._params_dirty = True
        self._last_shape = None

    @property
    def density(self):
        return self._density

    @density.setter
    def density(self, value):
        self._density = value
        self._params_dirty = True

    @property
    def min_dot_size(self):
        return self._min_dot_size

    @min_dot_size.setter
    def min_dot_size(self, value):
        self._min_dot_size = value
        self._params_dirty = True

    @property
    def max_dot_size(self):
        return self._max_dot_size

    @max_dot_size.setter
    def max_dot_size(self, value):
        self._max_dot_size = value
        self._params_dirty = True

    def apply(self, frame, config, analysis=None):
        if self._density <= 0:
            return frame

        h, w = frame.shape[:2]

        # Check if grid needs rebuild
        if self._params_dirty or (h, w) != self._last_shape:
            self._build_sampling_grid(h, w)
            self._last_shape = (h, w)
            self._params_dirty = False

        if self._sampling_grid is None or len(self._sampling_grid) == 0:
            return frame

        # Create output with background color
        out = np.full_like(frame, self._background_color, dtype=np.uint8)

        # Get grayscale for luminance-based dot sizing
        gray = get_cached_conversion(frame, cv2.COLOR_BGR2GRAY)

        # Sample colors and luminance at grid points
        gy = self._sampling_grid[:, 0]
        gx = self._sampling_grid[:, 1]

        colors_b = frame[gy, gx, 0]
        colors_g = frame[gy, gx, 1]
        colors_r = frame[gy, gx, 2]
        lum = gray[gy, gx].astype(np.float32) / 255.0

        # Compute dot radii from luminance
        size_range = self._max_dot_size - self._min_dot_size
        if self._invert_size:
            # Brighter = larger dots
            radii = (self._min_dot_size + lum * size_range).astype(np.int32)
        else:
            # Darker = larger dots (classic stippling)
            radii = (self._min_dot_size + (1.0 - lum) * size_range).astype(np.int32)

        radii = np.clip(radii, self._min_dot_size, self._max_dot_size)

        # Draw dots
        for i in range(len(gx)):
            color = (int(colors_b[i]), int(colors_g[i]), int(colors_r[i]))
            cv2.circle(out, (int(gx[i]), int(gy[i])), int(radii[i]), color, -1)

        return out

    def _build_sampling_grid(self, h, w):
        """Build jittered grid of sampling points."""
        # Grid spacing inversely proportional to density
        spacing = max(2, int(1.0 / max(self._density, 0.01) * 3))

        # Create regular grid
        ys = np.arange(spacing // 2, h, spacing)
        xs = np.arange(spacing // 2, w, spacing)
        grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
        grid_y = grid_y.ravel()
        grid_x = grid_x.ravel()

        # Add jitter (up to half spacing)
        jitter = spacing // 4
        if jitter > 0:
            grid_y = grid_y + np.random.randint(-jitter, jitter + 1, size=len(grid_y))
            grid_x = grid_x + np.random.randint(-jitter, jitter + 1, size=len(grid_x))

        # Clamp to frame bounds
        grid_y = np.clip(grid_y, 0, h - 1)
        grid_x = np.clip(grid_x, 0, w - 1)

        self._sampling_grid = np.stack([grid_y, grid_x], axis=1).astype(np.int32)
