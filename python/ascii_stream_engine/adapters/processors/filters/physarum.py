"""Physarum Simulation Overlay filter -- slime mold simulation.

Maintains a population of agents on a 2D trail map at reduced resolution.
Each agent: sense ahead (3 sensors), rotate toward strongest trail, deposit
trail, move forward. Trail map is diffused and decayed each step, then
overlaid onto the frame via alpha blending.

Stateful: stores trail_map, agents, last_shape.
Heavy filter: runs at sim_scale (default 1/4 resolution) to meet budget.

Memory usage:
  - _trail_map: (H/s) * (W/s) * 4 bytes (float32)
  - _agents_x/y/angle: num_agents * 4 bytes each (float32)
"""

import cv2
import numpy as np

from .base import BaseFilter


class PhysarumFilter(BaseFilter):
    """Physarum slime mold simulation overlay."""

    name = "physarum"

    def __init__(
        self,
        num_agents: int = 4000,
        sensor_angle: float = 0.4,
        sensor_distance: float = 9.0,
        turn_speed: float = 0.4,
        move_speed: float = 1.0,
        deposit_amount: float = 10.0,
        decay_factor: float = 0.98,
        diffusion_sigma: float = 0.5,
        opacity: float = 0.7,
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
        self._trail_map = None
        self._agents_x = None
        self._agents_y = None
        self._agents_angle = None
        self._last_shape = None
        self._sim_h = 0
        self._sim_w = 0

    def reset(self):
        """Clear internal state. Called on pipeline reset."""
        self._trail_map = None
        self._agents_x = None
        self._agents_y = None
        self._agents_angle = None
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        h, w = frame.shape[:2]

        # Resolution change: reinitialize
        if (h, w) != self._last_shape:
            self._init_simulation(h, w)
            self._last_shape = (h, w)

        # Run one simulation step
        self._step()

        # Convert trail map to BGR overlay with adaptive normalization
        trail_max = self._trail_map.max()
        if trail_max > 1e-6:
            trail_normalized = (self._trail_map / trail_max * 255).astype(np.uint8)
        else:
            trail_normalized = np.zeros_like(self._trail_map, dtype=np.uint8)
        overlay_small = cv2.applyColorMap(trail_normalized, self._colormap)

        # Upscale overlay to frame resolution
        if self._sim_scale > 1:
            overlay = cv2.resize(overlay_small, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            overlay = overlay_small

        # Blend with frame
        out = frame.copy(order="C")
        cv2.addWeighted(out, 1.0 - self._opacity, overlay, self._opacity, 0, dst=out)
        return out

    def _init_simulation(self, h, w):
        """Initialize simulation at reduced resolution."""
        self._sim_h = max(2, h // self._sim_scale)
        self._sim_w = max(2, w // self._sim_scale)

        # Initialize trail map
        self._trail_map = np.zeros((self._sim_h, self._sim_w), dtype=np.float32)

        # Initialize agents at random positions with random angles
        n = self._num_agents
        self._agents_x = np.random.uniform(0, self._sim_w, size=n).astype(np.float32)
        self._agents_y = np.random.uniform(0, self._sim_h, size=n).astype(np.float32)
        self._agents_angle = np.random.uniform(0, 2 * np.pi, size=n).astype(np.float32)

    def _step(self):
        """Run one simulation step (vectorized numpy)."""
        sh, sw = self._sim_h, self._sim_w
        sa = self._sensor_angle
        sd = self._sensor_distance
        ts = self._turn_speed
        ms = self._move_speed

        # --- Sense: sample trail at 3 forward sensor positions ---
        # Left sensor
        lx = self._agents_x + sd * np.cos(self._agents_angle - sa)
        ly = self._agents_y + sd * np.sin(self._agents_angle - sa)
        # Center sensor
        cx = self._agents_x + sd * np.cos(self._agents_angle)
        cy = self._agents_y + sd * np.sin(self._agents_angle)
        # Right sensor
        rx = self._agents_x + sd * np.cos(self._agents_angle + sa)
        ry = self._agents_y + sd * np.sin(self._agents_angle + sa)

        # Wrap sensor positions (toroidal boundary)
        lx_i = np.clip(lx.astype(np.int32) % sw, 0, sw - 1)
        ly_i = np.clip(ly.astype(np.int32) % sh, 0, sh - 1)
        cx_i = np.clip(cx.astype(np.int32) % sw, 0, sw - 1)
        cy_i = np.clip(cy.astype(np.int32) % sh, 0, sh - 1)
        rx_i = np.clip(rx.astype(np.int32) % sw, 0, sw - 1)
        ry_i = np.clip(ry.astype(np.int32) % sh, 0, sh - 1)

        # Sample trail values
        left_val = self._trail_map[ly_i, lx_i]
        center_val = self._trail_map[cy_i, cx_i]
        right_val = self._trail_map[ry_i, rx_i]

        # --- Rotate toward strongest trail ---
        # If center is strongest, go straight. If left > right, turn left. Else turn right.
        turn_left = (left_val > center_val) & (left_val > right_val)
        turn_right = (right_val > center_val) & (right_val > left_val)
        random_turn = ~turn_left & ~turn_right & (center_val <= left_val)

        self._agents_angle[turn_left] -= ts
        self._agents_angle[turn_right] += ts
        # Random small turn when no clear direction
        random_mask = random_turn
        self._agents_angle[random_mask] += np.random.uniform(
            -ts * 0.5, ts * 0.5, size=np.sum(random_mask)
        ).astype(np.float32)

        # --- Move forward ---
        self._agents_x += ms * np.cos(self._agents_angle)
        self._agents_y += ms * np.sin(self._agents_angle)

        # Wrap positions (toroidal)
        self._agents_x = self._agents_x % sw
        self._agents_y = self._agents_y % sh

        # --- Deposit trail ---
        dep_x = np.clip(self._agents_x.astype(np.int32), 0, sw - 1)
        dep_y = np.clip(self._agents_y.astype(np.int32), 0, sh - 1)
        np.add.at(self._trail_map, (dep_y, dep_x), self._deposit_amount)

        # --- Diffuse trail map ---
        if self._diffusion_sigma > 0:
            ksize = 3
            self._trail_map = cv2.GaussianBlur(
                self._trail_map, (ksize, ksize), self._diffusion_sigma
            )

        # --- Decay trail map ---
        self._trail_map *= self._decay_factor
