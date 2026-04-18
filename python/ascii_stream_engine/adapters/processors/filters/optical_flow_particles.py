"""Optical Flow Particles filter -- motion-reactive particle system.

Computes dense optical flow between consecutive frames and spawns particles
at high-motion regions. Particles follow flow vectors, decay over time,
and are rendered as small colored circles.

Stateful: stores previous frame grayscale, particle array, and last shape.
Analysis-reactive: boosts particle spawn near hand/pose landmarks.

Memory usage:
  - _prev_gray: H*W bytes
  - _particles: max_particles * 24 bytes (structured array)
"""

import cv2
import numpy as np

from .base import BaseFilter
from .conversion_cache import get_cached_conversion


class OpticalFlowParticlesFilter(BaseFilter):
    """Motion-reactive particle system driven by optical flow."""

    name = "optical_flow_particles"

    # Temporal declaration: use shared optical flow (auto-derives input_depth >= 1)
    needs_optical_flow = True

    def __init__(
        self,
        max_particles: int = 2000,
        particle_lifetime: int = 30,
        spawn_threshold: float = 2.0,
        particle_size: int = 2,
        color_mode: str = "flow",
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._max_particles = max_particles
        self._particle_lifetime = particle_lifetime
        self._spawn_threshold = spawn_threshold
        self._particle_size = particle_size
        self._color_mode = color_mode
        # State
        self._prev_gray = None
        self._particles = None
        self._last_shape = None

    def reset(self):
        """Clear internal state. Called on pipeline reset."""
        self._prev_gray = None
        self._particles = None
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        if self._max_particles <= 0:
            return frame

        h, w = frame.shape[:2]

        # Resolution change: reinitialize
        if (h, w) != self._last_shape:
            self._prev_gray = None
            self._particles = None
            self._last_shape = (h, w)

        # Try shared optical flow from TemporalManager (via FilterContext)
        flow = getattr(analysis, "optical_flow", None) if analysis else None

        if flow is None:
            # Fallback: compute privately (no TemporalManager available)
            gray = get_cached_conversion(frame, cv2.COLOR_BGR2GRAY)
            if self._prev_gray is None or self._prev_gray.shape[:2] != (h, w):
                self._prev_gray = gray.copy()
                return frame
            flow = cv2.calcOpticalFlowFarneback(
                self._prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

        # Compute flow magnitude
        mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)

        # Spawn new particles at high-motion regions
        new_particles = self._spawn_particles(mag, flow, frame, h, w, analysis)

        # Update existing particles
        if self._particles is not None and len(self._particles) > 0:
            # Update positions with velocities
            self._particles["x"] += self._particles["vx"]
            self._particles["y"] += self._particles["vy"]
            self._particles["lifetime"] -= 1

            # Apply damping to velocity
            self._particles["vx"] *= 0.95
            self._particles["vy"] *= 0.95

            # Remove dead or out-of-bounds particles
            alive = (
                (self._particles["lifetime"] > 0)
                & (self._particles["x"] >= 0)
                & (self._particles["x"] < w)
                & (self._particles["y"] >= 0)
                & (self._particles["y"] < h)
            )
            self._particles = self._particles[alive]
        else:
            self._particles = np.array(
                [],
                dtype=[
                    ("x", np.float32),
                    ("y", np.float32),
                    ("vx", np.float32),
                    ("vy", np.float32),
                    ("lifetime", np.int32),
                    ("r", np.uint8),
                    ("g", np.uint8),
                    ("b", np.uint8),
                ],
            )

        # Merge new particles
        if len(new_particles) > 0:
            if len(self._particles) > 0:
                self._particles = np.concatenate([self._particles, new_particles])
            else:
                self._particles = new_particles

        # Cap particle count
        if len(self._particles) > self._max_particles:
            self._particles = self._particles[-self._max_particles :]

        # Update fallback state (only needed when not using shared flow)
        if getattr(analysis, "optical_flow", None) is None:
            gray = get_cached_conversion(frame, cv2.COLOR_BGR2GRAY)
            self._prev_gray = gray.copy()

        # Render particles
        if len(self._particles) == 0:
            return frame

        out = frame.copy(order="C")
        px = np.clip(self._particles["x"].astype(np.int32), 0, w - 1)
        py = np.clip(self._particles["y"].astype(np.int32), 0, h - 1)

        for i in range(len(self._particles)):
            color = (
                int(self._particles["b"][i]),
                int(self._particles["g"][i]),
                int(self._particles["r"][i]),
            )
            cv2.circle(out, (int(px[i]), int(py[i])), self._particle_size, color, -1)

        return out

    def _spawn_particles(self, mag, flow, frame, h, w, analysis):
        """Spawn new particles at high-motion regions."""
        # Find high-motion pixels (subsample for speed)
        step = max(1, min(h, w) // 50)
        mag_sub = mag[::step, ::step]
        flow_sub = flow[::step, ::step]

        mask = mag_sub > self._spawn_threshold
        ys, xs = np.where(mask)

        if len(ys) == 0:
            return np.array(
                [],
                dtype=[
                    ("x", np.float32),
                    ("y", np.float32),
                    ("vx", np.float32),
                    ("vy", np.float32),
                    ("lifetime", np.int32),
                    ("r", np.uint8),
                    ("g", np.uint8),
                    ("b", np.uint8),
                ],
            )

        # Scale back to full resolution
        ys_full = ys * step
        xs_full = xs * step

        # Limit spawn count
        max_spawn = max(1, self._max_particles // 10)
        if len(ys_full) > max_spawn:
            indices = np.random.choice(len(ys_full), max_spawn, replace=False)
            ys_full = ys_full[indices]
            xs_full = xs_full[indices]
            ys = ys[indices]
            xs = xs[indices]

        n = len(ys_full)
        particles = np.zeros(
            n,
            dtype=[
                ("x", np.float32),
                ("y", np.float32),
                ("vx", np.float32),
                ("vy", np.float32),
                ("lifetime", np.int32),
                ("r", np.uint8),
                ("g", np.uint8),
                ("b", np.uint8),
            ],
        )

        particles["x"] = xs_full.astype(np.float32)
        particles["y"] = ys_full.astype(np.float32)
        particles["vx"] = flow_sub[ys, xs, 0]
        particles["vy"] = flow_sub[ys, xs, 1]
        particles["lifetime"] = self._particle_lifetime

        # Color from flow direction or source frame
        if self._color_mode == "flow":
            angle = np.arctan2(flow_sub[ys, xs, 1], flow_sub[ys, xs, 0])
            hue = ((angle + np.pi) / (2 * np.pi) * 180).astype(np.uint8)
            particles["r"] = hue
            particles["g"] = 200
            particles["b"] = 255
        else:
            # Sample color from frame
            ys_c = np.clip(ys_full, 0, h - 1)
            xs_c = np.clip(xs_full, 0, w - 1)
            particles["b"] = frame[ys_c, xs_c, 0]
            particles["g"] = frame[ys_c, xs_c, 1]
            particles["r"] = frame[ys_c, xs_c, 2]

        return particles
