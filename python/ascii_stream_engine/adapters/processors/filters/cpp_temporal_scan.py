"""Angle-aware temporal slit-scan delegated to C++ (filters_cpp).

Replaces slit_scan + chrono_scan with a single filter that accepts any scan
angle (0–360°). For each pixel, samples from a different past frame in a ring
buffer; the frame index is the pixel's normalized coord projected onto the
direction vector.

Falls back to a pure-Python vectorized implementation when the C++ module is
unavailable so the pipeline keeps running without filters_cpp.
"""

from typing import Optional

import numpy as np

from ....domain.config import EngineConfig
from .base import BaseFilter

try:
    import filters_cpp as _filters_cpp

    _CPP_AVAILABLE = hasattr(_filters_cpp, "TemporalScan")
except ImportError:
    _filters_cpp = None
    _CPP_AVAILABLE = False


_CURVES = {"linear": 0, "ease": 1}


class CppTemporalScanFilter(BaseFilter):
    """Angle-aware temporal slit-scan (C++ backend, Python fallback).

    Each pixel reads from a past frame whose index depends on the pixel's
    position projected onto a direction vector. ``angle_deg = 0`` reproduces
    classic horizontal slit-scan (left = oldest, right = newest); ``90``
    gives vertical scan; any other value produces a diagonal scan.
    """

    name = "cpp_temporal_scan"
    enabled = True

    def __init__(
        self,
        angle_deg: float = 0.0,
        max_frames: int = 30,
        curve: str = "linear",
        bands: int = 0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._angle_deg = float(angle_deg)
        self._max_frames = max(2, int(max_frames))
        self._curve_name = curve if curve in _CURVES else "linear"
        # 0 means "one band per stored frame" (legacy). Otherwise the screen
        # is split into `bands` stripes that pick from the buffer at strided
        # offsets — wide bands + deep buffer become independently tunable.
        self._bands = max(0, int(bands))
        # C++ instance (lazy init on first apply so construction never fails)
        self._cpp: Optional[object] = None
        # Python fallback state (ring buffer + write index)
        self._py_buffer: Optional[np.ndarray] = None
        self._py_write_idx = 0
        self._py_n_frames = 0
        self._py_last_shape: Optional[tuple] = None

    @property
    def cpp_available(self) -> bool:
        return _CPP_AVAILABLE

    @property
    def angle_deg(self) -> float:
        return self._angle_deg

    @angle_deg.setter
    def angle_deg(self, value: float) -> None:
        self._angle_deg = float(value)
        if self._cpp is not None:
            self._cpp.angle_deg = self._angle_deg

    @property
    def max_frames(self) -> int:
        return self._max_frames

    @max_frames.setter
    def max_frames(self, value: int) -> None:
        new_max = max(2, int(value))
        if new_max != self._max_frames:
            self._max_frames = new_max
            # Reinstantiate on next apply to pick up new buffer size
            self._cpp = None
            self._py_buffer = None
            self._py_n_frames = 0
            self._py_write_idx = 0
            self._py_last_shape = None

    @property
    def curve(self) -> str:
        return self._curve_name

    @curve.setter
    def curve(self, value: str) -> None:
        if value not in _CURVES:
            return
        self._curve_name = value
        if self._cpp is not None:
            self._cpp.curve = _CURVES[value]

    @property
    def bands(self) -> int:
        return self._bands

    @bands.setter
    def bands(self, value: int) -> None:
        new_bands = max(0, int(value))
        self._bands = new_bands
        if self._cpp is not None:
            self._cpp.bands = new_bands

    def reset(self) -> None:
        if self._cpp is not None:
            self._cpp.reset()
        self._py_n_frames = 0
        self._py_write_idx = 0

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if not self.enabled or frame is None or frame.size == 0:
            return frame

        if _CPP_AVAILABLE:
            return self._apply_cpp(frame)
        return self._apply_py(frame)

    # ------------------------------------------------------------------ cpp
    def _apply_cpp(self, frame: np.ndarray) -> np.ndarray:
        if self._cpp is None:
            self._cpp = _filters_cpp.TemporalScan(self._max_frames, self._angle_deg)
            self._cpp.curve = _CURVES[self._curve_name]
            # `bands` may not exist on older compiled bindings — guard so we
            # still run on a stale .so until cpp/build is refreshed.
            if hasattr(self._cpp, "bands"):
                self._cpp.bands = self._bands
        # Ensure C-contiguous uint8 input (the binding requires it).
        arr = np.ascontiguousarray(frame, dtype=np.uint8)
        return self._cpp.apply(arr)

    # -------------------------------------------------------------- python
    def _apply_py(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        shape = (self._max_frames, *frame.shape)
        if self._py_buffer is None or self._py_last_shape != frame.shape:
            self._py_buffer = np.zeros(shape, dtype=frame.dtype)
            self._py_last_shape = frame.shape
            self._py_n_frames = 0
            self._py_write_idx = 0

        current_slot = self._py_write_idx
        np.copyto(self._py_buffer[current_slot], frame)
        self._py_write_idx = (self._py_write_idx + 1) % self._max_frames
        if self._py_n_frames < self._max_frames:
            self._py_n_frames += 1

        if self._py_n_frames < 2:
            return frame.copy()

        rad = np.deg2rad(self._angle_deg)
        cos_a, sin_a = float(np.cos(rad)), float(np.sin(rad))
        proj_max = abs(cos_a) + abs(sin_a)
        if proj_max < 1e-9:
            return frame.copy()

        yy, xx = np.mgrid[0:h, 0:w]
        xn = (xx / max(1, w - 1)) * 2.0 - 1.0
        yn = (yy / max(1, h - 1)) * 2.0 - 1.0
        t_norm = (xn * cos_a + yn * sin_a + proj_max) / (2.0 * proj_max)
        if self._curve_name == "ease":
            t_norm = np.clip(t_norm, 0.0, 1.0)
            t_norm = t_norm * t_norm * (3.0 - 2.0 * t_norm)

        max_t = self._py_n_frames - 1
        # Effective band count mirrors the C++ logic.
        if self._bands > 0:
            band_count = min(self._bands, self._py_n_frames)
            if band_count < 2:
                band_count = max(2, self._py_n_frames)
        else:
            band_count = self._py_n_frames
        max_band = band_count - 1

        band_idx = np.clip(np.rint(t_norm * max_band).astype(np.int32), 0, max_band)
        # band_idx -> t with rounding so band 0 hits newest, band max_band hits oldest.
        if max_band > 0:
            t_idx = ((band_idx * max_t) + (max_band // 2)) // max_band
        else:
            t_idx = np.zeros_like(band_idx)

        out = np.empty_like(frame)
        # Loop bound ≤ max_frames (≤ 30 in practice), not per-pixel.
        for t in range(self._py_n_frames):
            mask = t_idx == t
            if not mask.any():
                continue
            slot = (current_slot - t) % self._max_frames
            out[mask] = self._py_buffer[slot][mask]
        return out
