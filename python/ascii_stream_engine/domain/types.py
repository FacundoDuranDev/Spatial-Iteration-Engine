from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image


@dataclass
class ROI:
    """Region of interest with normalized coordinates (0-1)."""

    x: float
    y: float
    w: float
    h: float
    confidence: float = 1.0
    label: str = ""
    landmarks: Optional[np.ndarray] = None  # (N, 2) float32

    @property
    def center(self) -> Tuple[float, float]:
        """Center point of the ROI."""
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    @property
    def area(self) -> float:
        """Area of the ROI in normalized coordinates."""
        return self.w * self.h

    def to_pixel_rect(self, frame_h: int, frame_w: int) -> Tuple[int, int, int, int]:
        """Convert to pixel coordinates (x1, y1, x2, y2), clamped to frame bounds."""
        x1 = max(0, int(self.x * frame_w))
        y1 = max(0, int(self.y * frame_h))
        x2 = min(frame_w, int((self.x + self.w) * frame_w))
        y2 = min(frame_h, int((self.y + self.h) * frame_h))
        return (x1, y1, x2, y2)


@dataclass
class RenderFrame:
    image: Image.Image
    text: Optional[str] = None
    lines: Optional[List[str]] = None
    metadata: Optional[Dict[str, object]] = None
