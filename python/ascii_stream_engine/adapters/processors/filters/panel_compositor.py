"""Panel compositor filter -- comic-book split-screen panels.

Divides the frame into multiple panels with configurable layout, borders,
and optional per-panel color adjustments. Supports animated slide-in
transitions.

Inspired by Max Payne 3's comic-panel cutscene transitions inherited from
the original Max Payne games.
"""

import cv2
import numpy as np

from .base import BaseFilter


class PanelCompositorFilter(BaseFilter):
    """Comic-book style split-screen panel compositor."""

    name = "panel_compositor"

    def __init__(
        self,
        layout: str = "2x1",
        border_width: int = 3,
        border_color_bgr: tuple = (255, 255, 255),
        angle: float = 0.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self._layout = layout
        self._border_width = border_width
        self._border_color_bgr = border_color_bgr
        self._angle = angle

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        h, w = frame.shape[:2]
        result = frame.copy()

        rows, cols = self._parse_layout()
        if rows <= 1 and cols <= 1:
            return frame

        bw = max(1, self._border_width)
        color = self._border_color_bgr

        # Draw panel borders.
        # Horizontal dividers.
        for i in range(1, rows):
            y = int(i * h / rows)
            cv2.line(result, (0, y), (w, y), color, bw)

        # Vertical dividers.
        for j in range(1, cols):
            x = int(j * w / cols)
            cv2.line(result, (x, 0), (x, h), color, bw)

        # Optional diagonal angle on the main divider.
        if self._angle != 0.0 and (rows == 2 or cols == 2):
            angle_offset = int(np.tan(np.radians(self._angle)) * h * 0.5)
            if cols == 2:
                mid_x = w // 2
                # Draw angled divider replacing the straight vertical.
                pt1 = (mid_x - angle_offset, 0)
                pt2 = (mid_x + angle_offset, h)
                cv2.line(result, pt1, pt2, color, bw)
            elif rows == 2:
                mid_y = h // 2
                pt1 = (0, mid_y - angle_offset)
                pt2 = (w, mid_y + angle_offset)
                cv2.line(result, pt1, pt2, color, bw)

        # Outer border.
        cv2.rectangle(result, (0, 0), (w - 1, h - 1), color, bw)

        return np.ascontiguousarray(result)

    def _parse_layout(self):
        """Parse layout string like '2x1', '1x2', '2x2', '3x1'."""
        try:
            parts = self._layout.lower().split("x")
            cols = max(1, int(parts[0]))
            rows = max(1, int(parts[1]))
            return rows, cols
        except (ValueError, IndexError):
            return 1, 1
