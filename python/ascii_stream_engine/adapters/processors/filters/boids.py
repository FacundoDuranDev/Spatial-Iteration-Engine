"""Boids / Flocking Particles filter -- flocking particle system.

Maintains a flock of particles with position and velocity. Three rules:
separation, alignment, cohesion. Optionally attracts toward analysis
points (hands, face). Particles are rendered as small dots onto the frame.

Stateful: stores positions, velocities, last_shape.
Analysis-reactive: attracts boids toward hand landmarks when enabled.

Memory usage:
  - _positions: num_boids * 8 bytes (float32 x 2)
  - _velocities: num_boids * 8 bytes (float32 x 2)
"""

import cv2
import numpy as np

from .base import BaseFilter


class BoidsFilter(BaseFilter):
    """Flocking particle system with configurable boid rules."""

    name = "boids"

    def __init__(
        self,
        num_boids: int = 200,
        max_speed: float = 4.0,
        separation_radius: float = 15.0,
        alignment_radius: float = 40.0,
        cohesion_radius: float = 60.0,
        separation_weight: float = 1.5,
        alignment_weight: float = 1.0,
        cohesion_weight: float = 1.0,
        boid_size: int = 2,
        boid_color: tuple = (0, 255, 200),
        attract_to_analysis: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._num_boids = num_boids
        self._max_speed = max_speed
        self._separation_radius = separation_radius
        self._alignment_radius = alignment_radius
        self._cohesion_radius = cohesion_radius
        self._separation_weight = separation_weight
        self._alignment_weight = alignment_weight
        self._cohesion_weight = cohesion_weight
        self._boid_size = boid_size
        self._boid_color = boid_color
        self._attract_to_analysis = attract_to_analysis
        # State
        self._positions = None
        self._velocities = None
        self._last_shape = None

    def reset(self):
        """Clear internal state. Called on pipeline reset."""
        self._positions = None
        self._velocities = None
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        if self._num_boids <= 0:
            return frame

        h, w = frame.shape[:2]

        # Initialize or reinitialize on resolution change
        if self._positions is None or (h, w) != self._last_shape:
            self._init_boids(h, w)
            self._last_shape = (h, w)

        # Update boid simulation
        self._update(h, w, analysis)

        # Render boids
        out = frame.copy(order="C")
        px = np.clip(self._positions[:, 0].astype(np.int32), 0, w - 1)
        py = np.clip(self._positions[:, 1].astype(np.int32), 0, h - 1)

        color = (int(self._boid_color[0]), int(self._boid_color[1]), int(self._boid_color[2]))
        for i in range(len(px)):
            cv2.circle(out, (int(px[i]), int(py[i])), self._boid_size, color, -1)

        return out

    def _init_boids(self, h, w):
        """Initialize boids at random positions with random velocities."""
        n = self._num_boids
        self._positions = np.column_stack(
            [
                np.random.uniform(0, w, size=n),
                np.random.uniform(0, h, size=n),
            ]
        ).astype(np.float32)
        self._velocities = np.random.uniform(
            -self._max_speed, self._max_speed, size=(n, 2)
        ).astype(np.float32)

    def _update(self, h, w, analysis):
        """Update boid positions and velocities using flocking rules."""
        n = len(self._positions)
        if n == 0:
            return

        # Compute pairwise distances (vectorized, O(N^2) memory for N boids)
        # For moderate N (200-500), this is fast enough in numpy
        dx = self._positions[:, 0:1] - self._positions[:, 0]  # (N, N)
        dy = self._positions[:, 1:2] - self._positions[:, 1]  # (N, N)
        dist = np.sqrt(dx**2 + dy**2 + 1e-10)  # (N, N), avoid zero div

        # Initialize steering forces
        sep_force = np.zeros((n, 2), dtype=np.float32)
        ali_force = np.zeros((n, 2), dtype=np.float32)
        coh_force = np.zeros((n, 2), dtype=np.float32)

        # Separation: steer away from close neighbors
        sep_mask = (dist < self._separation_radius) & (dist > 0)
        sep_count = sep_mask.sum(axis=1, keepdims=True).clip(1)
        sep_dx = np.where(sep_mask, dx / (dist + 1e-6), 0).sum(axis=1)
        sep_dy = np.where(sep_mask, dy / (dist + 1e-6), 0).sum(axis=1)
        sep_force[:, 0] = sep_dx / sep_count.ravel()
        sep_force[:, 1] = sep_dy / sep_count.ravel()

        # Alignment: match velocity of nearby neighbors
        ali_mask = (dist < self._alignment_radius) & (dist > 0)
        ali_count = ali_mask.sum(axis=1, keepdims=True).clip(1)
        ali_vx = (ali_mask[:, :, None] * self._velocities[None, :, :]).sum(axis=1)
        ali_force = ali_vx / ali_count - self._velocities

        # Cohesion: steer toward center of nearby neighbors
        coh_mask = (dist < self._cohesion_radius) & (dist > 0)
        coh_count = coh_mask.sum(axis=1, keepdims=True).clip(1)
        coh_px = (coh_mask[:, :, None] * self._positions[None, :, :]).sum(axis=1)
        coh_center = coh_px / coh_count
        coh_force = coh_center - self._positions

        # Combine forces
        steer = (
            sep_force * self._separation_weight
            + ali_force * self._alignment_weight
            + coh_force * self._cohesion_weight
        )

        # Analysis attraction
        if self._attract_to_analysis and analysis:
            attract = self._compute_attraction(analysis, h, w)
            if attract is not None:
                steer += attract * 0.5

        # Update velocities
        self._velocities += steer * 0.1

        # Clamp speed
        speed = np.sqrt(
            self._velocities[:, 0] ** 2 + self._velocities[:, 1] ** 2 + 1e-10
        )
        too_fast = speed > self._max_speed
        if np.any(too_fast):
            scale = np.where(too_fast, self._max_speed / speed, 1.0)
            self._velocities[:, 0] *= scale
            self._velocities[:, 1] *= scale

        # Update positions
        self._positions += self._velocities

        # Wrap at boundaries
        self._positions[:, 0] = self._positions[:, 0] % w
        self._positions[:, 1] = self._positions[:, 1] % h

    def _compute_attraction(self, analysis, h, w):
        """Compute attraction force toward analysis landmarks."""
        targets = []

        if "hands" in analysis:
            hands = analysis["hands"]
            for key in ("left", "right"):
                pts = hands.get(key)
                if pts is not None and len(pts) > 0:
                    # Normalized coords -> pixel coords
                    center = np.mean(pts, axis=0)
                    targets.append([center[0] * w, center[1] * h])

        if "face" in analysis:
            face_data = analysis["face"]
            points = face_data.get("points")
            if points is not None and len(points) > 0:
                center = np.mean(points, axis=0)
                targets.append([center[0] * w, center[1] * h])

        if not targets:
            return None

        # Attraction toward nearest target
        target_arr = np.array(targets, dtype=np.float32)
        n = len(self._positions)
        attract = np.zeros((n, 2), dtype=np.float32)
        for t in target_arr:
            diff = t - self._positions
            attract += diff

        attract /= max(len(target_arr), 1)
        # Normalize
        mag = np.sqrt(attract[:, 0] ** 2 + attract[:, 1] ** 2 + 1e-10)
        attract[:, 0] /= mag
        attract[:, 1] /= mag

        return attract
