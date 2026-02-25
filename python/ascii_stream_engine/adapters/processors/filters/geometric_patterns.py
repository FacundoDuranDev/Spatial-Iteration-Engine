"""Geometric Pattern filter -- procedural geometry overlay.

Renders geometric patterns as semi-transparent overlays on the frame.
Supports multiple pattern modes: sacred geometry, Voronoi, Delaunay,
Lissajous curves, and strange attractors.

Initially uses fixed parameters. Landmark-reactive mode prepared
but not connected until Phase 2.
"""

import math

import cv2
import numpy as np

from .base import BaseFilter


class GeometricPatternFilter(BaseFilter):
    """Procedural geometric pattern overlay."""

    name = "geometric_patterns"

    # Temporal declaration: use previous output for trail accumulation
    needs_previous_output = True

    def __init__(
        self,
        pattern_mode: str = "sacred_geometry",
        opacity: float = 0.4,
        color: tuple = (255, 200, 100),  # BGR
        line_thickness: int = 1,
        scale: float = 1.0,
        animate: bool = True,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._pattern_mode = pattern_mode
        self._opacity = opacity
        self._color = color
        self._line_thickness = line_thickness
        self._scale = scale
        self._animate = animate
        self._frame_count = 0
        # Attractor state
        self._attractor_points = None

    def apply(self, frame, config, analysis=None):
        h, w = frame.shape[:2]
        self._frame_count += 1

        # Create overlay canvas
        overlay = np.zeros_like(frame)

        # Route to pattern generator
        mode = self._pattern_mode
        if mode == "sacred_geometry":
            self._draw_sacred_geometry(overlay, w, h)
        elif mode == "voronoi":
            self._draw_voronoi(overlay, w, h, analysis)
        elif mode == "delaunay":
            self._draw_delaunay(overlay, w, h, analysis)
        elif mode == "lissajous":
            self._draw_lissajous(overlay, w, h)
        elif mode == "strange_attractor":
            self._draw_strange_attractor(overlay, w, h)
        else:
            self._draw_sacred_geometry(overlay, w, h)

        # Accumulate trails from previous output if available
        prev_output = getattr(analysis, "previous_output", None)
        if prev_output is not None and prev_output.shape == frame.shape:
            # Blend previous output patterns (faded) into current overlay for trail effect
            prev_gray = cv2.cvtColor(prev_output, cv2.COLOR_BGR2GRAY)
            prev_mask = prev_gray > 30  # Only accumulate visible pixels
            if prev_mask.any():
                fade = 0.3  # Trail fade factor
                overlay[prev_mask] = np.clip(
                    overlay[prev_mask].astype(np.float32)
                    + prev_output[prev_mask].astype(np.float32) * fade,
                    0,
                    255,
                ).astype(np.uint8)

        # Blend overlay with frame
        out = frame.copy(order="C")
        mask = overlay.any(axis=2)
        if mask.any():
            out[mask] = cv2.addWeighted(
                frame[mask].reshape(-1, 3),
                1.0 - self._opacity,
                overlay[mask].reshape(-1, 3),
                self._opacity,
                0,
            ).reshape(-1, 3)
        return out

    def _draw_sacred_geometry(self, overlay, w, h):
        """Draw concentric circles, flower of life, Metatron's cube."""
        cx, cy = w // 2, h // 2
        base_r = int(min(w, h) * 0.3 * self._scale)
        color = self._color
        thick = self._line_thickness

        # Animation phase
        phase = self._frame_count * 0.02 if self._animate else 0

        # Concentric circles
        for i in range(1, 7):
            r = int(base_r * i / 6)
            cv2.circle(overlay, (cx, cy), r, color, thick)

        # Flower of life: 6 circles around center
        for i in range(6):
            angle = i * math.pi / 3 + phase
            px = int(cx + base_r / 3 * math.cos(angle))
            py = int(cy + base_r / 3 * math.sin(angle))
            cv2.circle(overlay, (px, py), base_r // 3, color, thick)

        # Hexagonal connections (Metatron's cube outline)
        pts = []
        for i in range(6):
            angle = i * math.pi / 3 + phase
            px = int(cx + base_r * 0.6 * math.cos(angle))
            py = int(cy + base_r * 0.6 * math.sin(angle))
            pts.append((px, py))
        # Connect all vertices
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                cv2.line(overlay, pts[i], pts[j], color, thick)

    def _draw_voronoi(self, overlay, w, h, analysis):
        """Draw Voronoi tessellation from landmarks or random points."""
        # Get seed points from analysis or use random
        seeds = self._get_landmark_points(analysis, w, h)
        if len(seeds) < 4:
            # Generate random seed points
            np.random.seed(42)  # Deterministic for consistency
            n_pts = 20
            seeds = np.column_stack(
                [
                    np.random.randint(0, w, n_pts),
                    np.random.randint(0, h, n_pts),
                ]
            )

        # Use OpenCV Subdiv2D for Voronoi
        rect = (0, 0, w, h)
        subdiv = cv2.Subdiv2D(rect)
        for pt in seeds:
            x, y = int(np.clip(pt[0], 1, w - 2)), int(np.clip(pt[1], 1, h - 2))
            try:
                subdiv.insert((x, y))
            except cv2.error:
                continue

        # Draw Voronoi edges
        try:
            facets, centers = subdiv.getVoronoiFacetList([])
            for facet in facets:
                pts = np.array(facet, dtype=np.int32)
                cv2.polylines(overlay, [pts], True, self._color, self._line_thickness)
        except cv2.error:
            pass

    def _draw_delaunay(self, overlay, w, h, analysis):
        """Draw Delaunay triangulation from landmarks or random points."""
        seeds = self._get_landmark_points(analysis, w, h)
        if len(seeds) < 3:
            np.random.seed(42)
            n_pts = 15
            seeds = np.column_stack(
                [
                    np.random.randint(0, w, n_pts),
                    np.random.randint(0, h, n_pts),
                ]
            )

        rect = (0, 0, w, h)
        subdiv = cv2.Subdiv2D(rect)
        for pt in seeds:
            x, y = int(np.clip(pt[0], 1, w - 2)), int(np.clip(pt[1], 1, h - 2))
            try:
                subdiv.insert((x, y))
            except cv2.error:
                continue

        # Draw Delaunay triangles
        try:
            triangles = subdiv.getTriangleList()
            for t in triangles:
                p1 = (int(t[0]), int(t[1]))
                p2 = (int(t[2]), int(t[3]))
                p3 = (int(t[4]), int(t[5]))
                # Only draw if all points are inside frame
                if all(0 <= p[0] < w and 0 <= p[1] < h for p in [p1, p2, p3]):
                    cv2.line(overlay, p1, p2, self._color, self._line_thickness)
                    cv2.line(overlay, p2, p3, self._color, self._line_thickness)
                    cv2.line(overlay, p3, p1, self._color, self._line_thickness)
        except cv2.error:
            pass

    def _draw_lissajous(self, overlay, w, h):
        """Draw Lissajous parametric curves."""
        cx, cy = w // 2, h // 2
        a_freq, b_freq = 3, 2
        phase = self._frame_count * 0.03 if self._animate else 0
        amp_x = int(w * 0.35 * self._scale)
        amp_y = int(h * 0.35 * self._scale)

        pts = []
        for i in range(500):
            t = i * 2 * math.pi / 500
            x = int(cx + amp_x * math.sin(a_freq * t + phase))
            y = int(cy + amp_y * math.sin(b_freq * t))
            pts.append([x, y])

        if len(pts) > 1:
            pts_arr = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(overlay, [pts_arr], False, self._color, self._line_thickness)

    def _draw_strange_attractor(self, overlay, w, h):
        """Draw Clifford attractor traces."""
        if self._attractor_points is None or len(self._attractor_points) == 0:
            self._attractor_points = self._compute_clifford_attractor()

        cx, cy = w // 2, h // 2
        scale_x = w * 0.2 * self._scale
        scale_y = h * 0.2 * self._scale

        # Map attractor points to screen coords
        pts = self._attractor_points
        screen_x = (pts[:, 0] * scale_x + cx).astype(np.int32)
        screen_y = (pts[:, 1] * scale_y + cy).astype(np.int32)

        # Clip to frame bounds
        valid = (screen_x >= 0) & (screen_x < w) & (screen_y >= 0) & (screen_y < h)
        screen_x = screen_x[valid]
        screen_y = screen_y[valid]

        # Draw points
        overlay[screen_y, screen_x] = self._color

    def _compute_clifford_attractor(self, n_points=50000):
        """Compute Clifford attractor points."""
        # Clifford attractor parameters (chosen for interesting patterns)
        phase = (self._frame_count * 0.01) if self._animate else 0
        a = -1.4 + 0.1 * math.sin(phase)
        b = 1.6
        c = 1.0
        d = 0.7

        points = np.zeros((n_points, 2), dtype=np.float32)
        x, y = 0.1, 0.1
        for i in range(n_points):
            x_new = math.sin(a * y) + c * math.cos(a * x)
            y_new = math.sin(b * x) + d * math.cos(b * y)
            points[i] = [x_new, y_new]
            x, y = x_new, y_new
        return points

    def _get_landmark_points(self, analysis, w, h):
        """Extract landmark points from analysis data, scaled to pixel coords."""
        points = []
        if analysis is None:
            return np.array(points).reshape(0, 2)

        # Face landmarks (normalized 0-1)
        face = analysis.get("face") if hasattr(analysis, "get") else None
        if face and isinstance(face, dict):
            landmarks = face.get("landmarks", [])
            for lm in landmarks:
                if isinstance(lm, (list, tuple)) and len(lm) >= 2:
                    points.append([int(lm[0] * w), int(lm[1] * h)])

        # Hand landmarks
        hands = analysis.get("hands") if hasattr(analysis, "get") else None
        if hands and isinstance(hands, dict):
            for hand in hands.get("landmarks", []):
                if isinstance(hand, (list, tuple)):
                    for lm in hand:
                        if isinstance(lm, (list, tuple)) and len(lm) >= 2:
                            points.append([int(lm[0] * w), int(lm[1] * h)])

        return np.array(points) if points else np.array([]).reshape(0, 2)
