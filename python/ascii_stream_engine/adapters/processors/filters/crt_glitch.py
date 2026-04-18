"""CRT Glitch filter -- retro TV/VHS distortion effects.

Combines scanlines, chromatic aberration, VHS tracking errors,
screen tearing, noise static, and barrel distortion into a
configurable CRT television effect.

Each sub-effect is independently toggleable and parameterized.
Initially uses static parameters -- perception reactivity added in Phase 2.
"""

import cv2
import numpy as np

from .base import BaseFilter


class CRTGlitchFilter(BaseFilter):
    """CRT/VHS glitch effect with multiple composable sub-effects."""

    name = "crt_glitch"

    # Temporal declarations: use optical flow for motion-reactive glitch
    needs_optical_flow = True
    needs_previous_output = True

    def __init__(
        self,
        scanline_intensity: float = 0.3,
        aberration_strength: float = 3.0,
        noise_amount: float = 0.05,
        tear_probability: float = 0.1,
        barrel_strength: float = 0.3,
        vhs_tracking: float = 0.0,
        enable_scanlines: bool = True,
        enable_aberration: bool = True,
        enable_noise: bool = True,
        enable_tear: bool = True,
        enable_barrel: bool = False,
        enable_vhs: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._scanline_intensity = scanline_intensity
        self._aberration_strength = aberration_strength
        self._noise_amount = noise_amount
        self._tear_probability = tear_probability
        self._barrel_strength = barrel_strength
        self._vhs_tracking = vhs_tracking
        self._enable_scanlines = enable_scanlines
        self._enable_aberration = enable_aberration
        self._enable_noise = enable_noise
        self._enable_tear = enable_tear
        self._enable_barrel = enable_barrel
        self._enable_vhs = enable_vhs
        # Precomputed scanline pattern (lazy, per resolution)
        self._scanline_mask = None
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        h, w = frame.shape[:2]
        out = frame.copy(order="C")

        # Rebuild scanline mask on resolution change
        if (h, w) != self._last_shape:
            self._scanline_mask = None
            self._last_shape = (h, w)

        # Compute motion-reactive modulation from optical flow
        motion_mod = self._compute_motion_modulation(analysis)

        # Modulate parameters by motion (base + motion-driven boost)
        aberration = self._aberration_strength * (1.0 + motion_mod * 2.0)
        tear_prob = min(1.0, self._tear_probability * (1.0 + motion_mod * 3.0))
        noise = self._noise_amount * (1.0 + motion_mod * 1.5)
        vhs = self._vhs_tracking * (1.0 + motion_mod * 2.0)

        # Apply sub-effects in order
        if self._enable_barrel and self._barrel_strength > 0:
            out = self._barrel_distortion(out, self._barrel_strength)

        if self._enable_aberration and aberration > 0:
            out = self._chromatic_aberration(out, aberration)

        if self._enable_vhs and vhs > 0:
            out = self._vhs_tracking_effect(out, vhs)

        if self._enable_tear and np.random.random() < tear_prob:
            out = self._screen_tear(out)

        if self._enable_scanlines and self._scanline_intensity > 0:
            out = self._scanlines(out, self._scanline_intensity)

        if self._enable_noise and noise > 0:
            out = self._noise_static(out, noise)

        return out

    def _compute_motion_modulation(self, analysis):
        """Compute 0-1 motion modulation from optical flow and hand speed."""
        if analysis is None:
            return 0.0

        motion = 0.0

        # Use optical flow magnitude if available (via FilterContext)
        flow = getattr(analysis, "optical_flow", None)
        if flow is not None:
            mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)
            # Normalize: typical motion range 0-20 pixels/frame
            motion = float(np.mean(mag)) / 10.0

        # Boost from hand motion if hands detected (compute from landmark spread)
        hands = analysis.get("hands") if hasattr(analysis, "get") else None
        if hands and isinstance(hands, dict):
            for key in ("left", "right"):
                pts = hands.get(key, None)
                if pts is not None and hasattr(pts, "__len__") and len(pts) > 0:
                    arr = np.asarray(pts)
                    if arr.ndim == 2 and arr.shape[0] > 1:
                        spread = float(np.std(arr))
                        motion += spread * 2.0

        return min(1.0, max(0.0, motion))

    def _scanlines(self, frame, intensity):
        """Apply horizontal scanline darkening effect."""
        h, w = frame.shape[:2]
        if self._scanline_mask is None or self._scanline_mask.shape[:2] != (h, w):
            # Create scanline pattern: darken every other row
            mask = np.ones((h, 1, 1), dtype=np.float32)
            mask[1::2] = 1.0 - intensity
            self._scanline_mask = mask
        # Multiply frame by scanline mask
        result = (frame.astype(np.float32) * self._scanline_mask).clip(0, 255).astype(np.uint8)
        return result

    def _chromatic_aberration(self, frame, offset):
        """Shift R and B channels independently for color fringing."""
        h, w = frame.shape[:2]
        off = int(round(offset))
        if off <= 0:
            return frame
        result = frame.copy()
        # Shift blue channel left, red channel right
        if off < w:
            result[:, off:, 0] = frame[:, :-off, 0]  # Blue: shift right
            result[:, :off, 0] = frame[:, 0:1, 0]  # Fill edge
            result[:, :-off, 2] = frame[:, off:, 2]  # Red: shift left
            result[:, w - off :, 2] = frame[:, -1:, 2]  # Fill edge
        return result

    def _vhs_tracking_effect(self, frame, intensity):
        """Horizontal band displacement simulating VHS tracking errors."""
        h, w = frame.shape[:2]
        result = frame.copy()
        # Create 2-4 horizontal bands with random displacement
        num_bands = np.random.randint(2, 5)
        for _ in range(num_bands):
            band_y = np.random.randint(0, h)
            band_h = np.random.randint(2, max(3, int(h * 0.05)))
            shift = int(np.random.uniform(-intensity * w * 0.1, intensity * w * 0.1))
            y_end = min(band_y + band_h, h)
            if shift > 0 and shift < w:
                result[band_y:y_end, shift:] = frame[band_y:y_end, : w - shift]
                result[band_y:y_end, :shift] = frame[band_y:y_end, :1]
            elif shift < 0 and abs(shift) < w:
                abs_shift = abs(shift)
                result[band_y:y_end, : w - abs_shift] = frame[band_y:y_end, abs_shift:]
                result[band_y:y_end, w - abs_shift :] = frame[band_y:y_end, -1:]
        return result

    def _screen_tear(self, frame):
        """Random horizontal offset for sections of the frame."""
        h, w = frame.shape[:2]
        result = frame.copy()
        # Pick a random tear position and offset
        tear_y = np.random.randint(h // 4, 3 * h // 4)
        tear_h = np.random.randint(5, max(6, h // 10))
        tear_offset = np.random.randint(-w // 8, w // 8)
        y_end = min(tear_y + tear_h, h)
        if tear_offset > 0 and tear_offset < w:
            result[tear_y:y_end, tear_offset:] = frame[tear_y:y_end, : w - tear_offset]
            result[tear_y:y_end, :tear_offset] = 0
        elif tear_offset < 0 and abs(tear_offset) < w:
            abs_off = abs(tear_offset)
            result[tear_y:y_end, : w - abs_off] = frame[tear_y:y_end, abs_off:]
            result[tear_y:y_end, w - abs_off :] = 0
        return result

    def _noise_static(self, frame, amount):
        """Add random noise overlay."""
        h, w = frame.shape[:2]
        noise = np.random.randint(0, 256, (h, w), dtype=np.uint8)
        # Blend noise into frame
        noise_bgr = cv2.cvtColor(noise, cv2.COLOR_GRAY2BGR)
        result = cv2.addWeighted(frame, 1.0 - amount, noise_bgr, amount, 0)
        return result

    def _barrel_distortion(self, frame, strength):
        """Apply barrel distortion simulating CRT screen curvature."""
        h, w = frame.shape[:2]
        # Build distortion map
        cx, cy = w / 2.0, h / 2.0
        # Normalized coords
        xs = np.arange(w, dtype=np.float32) - cx
        ys = np.arange(h, dtype=np.float32) - cy
        xv, yv = np.meshgrid(xs, ys)
        r = np.sqrt(xv**2 + yv**2)
        r_max = np.sqrt(cx**2 + cy**2)
        r_norm = r / r_max
        # Barrel distortion: r_new = r * (1 + k * r^2)
        k = strength * 0.5
        scale = 1.0 + k * r_norm**2
        map_x = (xv / scale + cx).astype(np.float32)
        map_y = (yv / scale + cy).astype(np.float32)
        result = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return result
