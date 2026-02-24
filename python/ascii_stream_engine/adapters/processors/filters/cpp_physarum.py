"""Physarum Simulation via C++ (filters_cpp).

Delegates the simulation step to C++ for 10k+ agents at <5ms.
Falls back to Python PhysarumFilter when C++ module is unavailable.
"""

from typing import Optional

import cv2
import numpy as np

from ....domain.config import EngineConfig
from .base import BaseFilter

try:
    import filters_cpp as _filters_cpp

    _CPP_AVAILABLE = hasattr(_filters_cpp, "physarum_init")
except ImportError:
    _filters_cpp = None
    _CPP_AVAILABLE = False


class CppPhysarumFilter(BaseFilter):
    """Physarum slime mold simulation with C++ acceleration.

    Delegates to filters_cpp.physarum_* functions when available.
    Falls back to Python PhysarumFilter otherwise.
    """

    name = "cpp_physarum"
    enabled = True

    def __init__(
        self,
        num_agents: int = 10000,
        sensor_angle: float = 0.4,
        sensor_distance: float = 9.0,
        turn_speed: float = 0.4,
        move_speed: float = 1.0,
        deposit_amount: float = 5.0,
        decay_factor: float = 0.95,
        diffusion_sigma: float = 0.7,
        opacity: float = 0.5,
        colormap: int = cv2.COLORMAP_INFERNO,
        sim_scale: int = 4,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._num_agents = num_agents
        self._sensor_angle = sensor_angle
        self._sensor_distance = sensor_distance
        self._turn_speed = turn_speed
        self._move_speed = move_speed
        self._deposit_amount = deposit_amount
        self._decay_factor = decay_factor
        self._diffusion_sigma = diffusion_sigma
        self._opacity = opacity
        self._colormap = colormap
        self._sim_scale = max(1, sim_scale)
        # State
        self._last_shape = None
        self._sim_h = 0
        self._sim_w = 0
        self._initialized = False
        # Python fallback
        self._py_fallback = None

    @property
    def cpp_available(self) -> bool:
        return _CPP_AVAILABLE

    def reset(self):
        """Clear internal state."""
        if _CPP_AVAILABLE:
            _filters_cpp.physarum_reset()
        self._initialized = False
        self._last_shape = None
        if self._py_fallback is not None:
            self._py_fallback.reset()

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if not _CPP_AVAILABLE:
            return self._apply_fallback(frame, config, analysis)

        h, w = frame.shape[:2]

        # Initialize or reinitialize on resolution change
        if (h, w) != self._last_shape or not self._initialized:
            self._sim_h = max(2, h // self._sim_scale)
            self._sim_w = max(2, w // self._sim_scale)
            _filters_cpp.physarum_init(self._sim_w, self._sim_h, self._num_agents)
            self._last_shape = (h, w)
            self._initialized = True

        # Get grayscale luminance at simulation resolution
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._sim_scale > 1:
            gray_small = cv2.resize(
                gray, (self._sim_w, self._sim_h), interpolation=cv2.INTER_NEAREST
            )
        else:
            gray_small = gray

        # Run one simulation step in C++
        luminance = np.ascontiguousarray(gray_small, dtype=np.uint8)
        _filters_cpp.physarum_step(
            luminance,
            self._sim_w,
            self._sim_h,
            self._sensor_angle,
            self._sensor_distance,
            self._turn_speed,
            self._move_speed,
            self._deposit_amount,
            self._decay_factor,
            self._diffusion_sigma,
        )

        # Get trail map from C++
        trail = _filters_cpp.physarum_get_trail()
        trail_normalized = np.clip(trail * 10, 0, 255).astype(np.uint8)
        trail_normalized = trail_normalized.reshape(self._sim_h, self._sim_w)
        overlay_small = cv2.applyColorMap(trail_normalized, self._colormap)

        # Upscale and blend
        if self._sim_scale > 1:
            overlay = cv2.resize(overlay_small, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            overlay = overlay_small

        out = frame.copy(order="C")
        cv2.addWeighted(out, 1.0 - self._opacity, overlay, self._opacity, 0, dst=out)
        return out

    def _apply_fallback(self, frame, config, analysis):
        """Fall back to Python implementation."""
        if self._py_fallback is None:
            from .physarum import PhysarumFilter

            # Use reduced agent count for Python fallback
            self._py_fallback = PhysarumFilter(
                num_agents=min(self._num_agents, 2000),
                sensor_angle=self._sensor_angle,
                sensor_distance=self._sensor_distance,
                turn_speed=self._turn_speed,
                move_speed=self._move_speed,
                deposit_amount=self._deposit_amount,
                decay_factor=self._decay_factor,
                diffusion_sigma=self._diffusion_sigma,
                opacity=self._opacity,
                colormap=self._colormap,
                sim_scale=self._sim_scale,
            )
        return self._py_fallback.apply(frame, config, analysis)
