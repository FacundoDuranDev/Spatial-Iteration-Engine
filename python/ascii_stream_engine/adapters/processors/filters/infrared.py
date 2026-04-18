"""Infrared / thermal-look filter — luma-based colormap for a heat-camera aesthetic."""

import cv2
import numpy as np

from .base import BaseFilter

# Mapping of friendly names → OpenCV colormap constants.
_COLORMAPS = {
    "inferno": cv2.COLORMAP_INFERNO,
    "magma": cv2.COLORMAP_MAGMA,
    "plasma": cv2.COLORMAP_PLASMA,
    "viridis": cv2.COLORMAP_VIRIDIS,
    "jet": cv2.COLORMAP_JET,
    "turbo": cv2.COLORMAP_TURBO if hasattr(cv2, "COLORMAP_TURBO") else cv2.COLORMAP_JET,
    "hot": cv2.COLORMAP_HOT,
    "cool": cv2.COLORMAP_COOL,
    "bone": cv2.COLORMAP_BONE,
}


class InfraredFilter(BaseFilter):
    """Converts luma to a thermal-style colormap (infrared camera look)."""

    name = "infrared"

    def __init__(
        self,
        colormap: str = "inferno",
        intensity: float = 1.0,
        contrast: float = 1.2,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._colormap_name = colormap
        self._intensity = intensity
        self._contrast = contrast

    @property
    def colormap(self) -> str:
        return self._colormap_name

    @colormap.setter
    def colormap(self, value: str) -> None:
        self._colormap_name = value

    @property
    def intensity(self) -> float:
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        self._intensity = float(value)

    def apply(self, frame, config, analysis=None):
        if not self.enabled or frame is None or frame.size == 0:
            return frame

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

        if self._contrast != 1.0:
            gray = np.clip(
                (gray.astype(np.float32) - 128.0) * self._contrast + 128.0, 0, 255
            ).astype(np.uint8)

        cmap = _COLORMAPS.get(self._colormap_name, cv2.COLORMAP_INFERNO)
        thermal = cv2.applyColorMap(gray, cmap)

        if self._intensity >= 0.999 or frame.ndim == 2:
            return thermal
        alpha = float(np.clip(self._intensity, 0.0, 1.0))
        return cv2.addWeighted(frame, 1.0 - alpha, thermal, alpha, 0.0)
