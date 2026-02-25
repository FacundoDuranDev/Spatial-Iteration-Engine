"""Edge-Aware Smoothing filter -- bilateral filter with blend control.

Applies cv2.bilateralFilter to smooth flat regions while preserving edges.
Optionally blends the smoothed result with the original frame via strength.

No state, no LUT. Pure convolution per frame.
"""

import cv2

from .base import BaseFilter


class EdgeSmoothFilter(BaseFilter):
    """Edge-preserving bilateral smoothing with configurable strength."""

    name = "edge_smooth"

    def __init__(
        self,
        diameter: int = 9,
        sigma_color: float = 75.0,
        sigma_space: float = 75.0,
        strength: float = 1.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._diameter = diameter
        self._sigma_color = sigma_color
        self._sigma_space = sigma_space
        self._strength = strength

    def apply(self, frame, config, analysis=None):
        if self._strength == 0:
            return frame

        smoothed = cv2.bilateralFilter(
            frame,
            d=self._diameter,
            sigmaColor=self._sigma_color,
            sigmaSpace=self._sigma_space,
        )

        if self._strength >= 1.0:
            return smoothed

        # Blend original with smoothed
        return cv2.addWeighted(
            frame,
            1.0 - self._strength,
            smoothed,
            self._strength,
            0,
        )
