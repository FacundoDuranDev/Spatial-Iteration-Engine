"""Hand Spatial Warp filter -- deforms space in a band between both hands.

Creates a displacement field that stretches/compresses the image ONLY inside a
rectangular corridor along the line connecting both hands. Pixels outside the
band are untouched. The band width is controlled by falloff.

Only activates when both hands are visible. Holds last position briefly on
hand loss to avoid flickering.

Reactive to hand landmarks from the perception pipeline (analysis["hands"]).
"""

import cv2
import numpy as np

from .base import BaseFilter


class HandSpatialWarpFilter(BaseFilter):
    """Spatial deformation confined to a band between both hands."""

    name = "hand_spatial_warp"

    def __init__(
        self,
        strength: float = 300.0,
        falloff: float = 0.35,
        mode: str = "stretch",
        smoothing: float = 0.3,
        hold_frames: int = 10,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._strength = strength
        self._falloff = falloff
        self._mode = mode  # "stretch", "compress", "twist"
        self._smoothing = smoothing
        self._hold_frames = hold_frames
        # State
        self._smooth_left = None
        self._smooth_right = None
        self._last_valid_left = None
        self._last_valid_right = None
        self._frames_since_lost = 0
        self._last_shape = None
        self._identity_x = None
        self._identity_y = None

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        self._strength = value

    @property
    def falloff(self):
        return self._falloff

    @falloff.setter
    def falloff(self, value):
        self._falloff = value

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        self._mode = value

    def reset(self):
        self._smooth_left = None
        self._smooth_right = None
        self._last_valid_left = None
        self._last_valid_right = None
        self._frames_since_lost = 0
        self._last_shape = None
        self._identity_x = None
        self._identity_y = None

    def apply(self, frame, config, analysis=None):
        if self._strength == 0:
            return frame

        hands = self._get_hands(analysis)

        if hands is not None:
            left_center, right_center = hands
            left_center = self._smooth_point(left_center, is_left=True)
            right_center = self._smooth_point(right_center, is_left=False)
            self._last_valid_left = left_center.copy()
            self._last_valid_right = right_center.copy()
            self._frames_since_lost = 0
        elif (
            self._last_valid_left is not None
            and self._frames_since_lost < self._hold_frames
        ):
            left_center = self._last_valid_left
            right_center = self._last_valid_right
            self._frames_since_lost += 1
        else:
            return frame

        h, w = frame.shape[:2]

        # Ensure identity grids match current resolution
        if (h, w) != self._last_shape:
            self._identity_y, self._identity_x = np.mgrid[0:h, 0:w].astype(np.float32)
            self._last_shape = (h, w)

        map_x, map_y = self._build_warp_maps(h, w, left_center, right_center)

        out = cv2.remap(
            frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        return out

    def _get_hands(self, analysis):
        """Extract hand centers from analysis. Returns (left, right) normalized or None."""
        if not analysis:
            return None
        hands = analysis.get("hands") if hasattr(analysis, "get") else None
        if not hands or not isinstance(hands, dict):
            return None

        left_pts = hands.get("left")
        right_pts = hands.get("right")

        if left_pts is None or right_pts is None:
            return None
        if not hasattr(left_pts, "__len__") or len(left_pts) == 0:
            return None
        if not hasattr(right_pts, "__len__") or len(right_pts) == 0:
            return None

        # Wrist (0) as hand center — most stable landmark
        left_center = np.array([float(left_pts[0][0]), float(left_pts[0][1])])
        right_center = np.array([float(right_pts[0][0]), float(right_pts[0][1])])
        return left_center, right_center

    def _smooth_point(self, point, is_left):
        """Exponential moving average for temporal smoothing."""
        alpha = self._smoothing
        if is_left:
            if self._smooth_left is None:
                self._smooth_left = point.copy()
            else:
                self._smooth_left = alpha * point + (1.0 - alpha) * self._smooth_left
            return self._smooth_left.copy()
        else:
            if self._smooth_right is None:
                self._smooth_right = point.copy()
            else:
                self._smooth_right = alpha * point + (1.0 - alpha) * self._smooth_right
            return self._smooth_right.copy()

    def _build_warp_maps(self, h, w, left_norm, right_norm):
        """Build remap tables — deformation confined to a band between hands."""
        # Convert normalized coords to pixel coords
        lx, ly = left_norm[0] * (w - 1), left_norm[1] * (h - 1)
        rx, ry = right_norm[0] * (w - 1), right_norm[1] * (h - 1)

        # Midpoint and axis
        mx, my = (lx + rx) / 2.0, (ly + ry) / 2.0
        dx_axis = rx - lx
        dy_axis = ry - ly
        axis_len = max(np.sqrt(dx_axis**2 + dy_axis**2), 1.0)

        # Unit vectors: along axis and perpendicular
        ux, uy = dx_axis / axis_len, dy_axis / axis_len
        px, py = -uy, ux  # perpendicular

        # Vector from midpoint to each pixel
        vx = self._identity_x - mx
        vy = self._identity_y - my

        # Project onto axis (t) and perpendicular (s)
        t = vx * ux + vy * uy  # signed distance along axis
        s = vx * px + vy * py  # signed distance perpendicular to axis

        # Band half-width in pixels
        band_half = max(self._falloff * max(h, w), 1.0)
        half_len = axis_len / 2.0

        # Hard band mask: only pixels inside the corridor get warped
        # Along axis: must be between both hands (with small margin)
        margin = band_half * 0.3
        inside_along = np.abs(t) <= (half_len + margin)
        # Perpendicular: must be within band width
        inside_perp = np.abs(s) <= band_half

        # Smooth falloff WITHIN the band (strongest at center, zero at edges)
        # Perpendicular: smooth ramp from center to edge of band
        s_weight = np.clip(1.0 - (np.abs(s) / band_half), 0, 1) ** 2
        # Along axis: smooth ramp near the hand endpoints
        t_weight = np.clip(1.0 - np.clip(np.abs(t) - half_len, 0, None) / max(margin, 1), 0, 1)

        weight = s_weight * t_weight * inside_along * inside_perp

        strength = self._strength

        if self._mode == "stretch":
            # Pull pixels toward the axis line
            disp_px = -s * weight * (strength / 100.0)
            disp_x = disp_px * px
            disp_y = disp_px * py
        elif self._mode == "compress":
            # Push pixels away from axis
            disp_px = s * weight * (strength / 100.0)
            disp_x = disp_px * px
            disp_y = disp_px * py
        elif self._mode == "twist":
            # Twist around the axis
            angle = weight * (strength / 100.0) * 0.05
            cos_a = np.cos(angle)
            sin_a = np.sin(angle)
            new_vx = vx * cos_a - vy * sin_a
            new_vy = vx * sin_a + vy * cos_a
            disp_x = new_vx - vx
        else:
            disp_px = -s * weight * (strength / 100.0)
            disp_x = disp_px * px
            disp_y = disp_px * py

        if self._mode == "twist":
            map_x = (self._identity_x + disp_x).astype(np.float32)
            map_y = (self._identity_y + (new_vy - vy)).astype(np.float32)
        else:
            map_x = (self._identity_x + disp_x).astype(np.float32)
            map_y = (self._identity_y + disp_y).astype(np.float32)

        return map_x, map_y
