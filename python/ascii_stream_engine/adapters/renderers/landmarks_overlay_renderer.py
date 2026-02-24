"""Renderer que dibuja landmarks (face, hands, pose) sobre el frame. MVP_03."""

from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer


def _draw_points(
    img: np.ndarray,
    points: np.ndarray,
    color: Tuple[int, int, int],
    radius: int = 2,
) -> None:
    """Dibuja puntos normalizados (0..1) en la imagen. color BGR."""
    if points is None or points.size == 0:
        return
    h, w = img.shape[:2]
    pts = np.asarray(points, dtype=np.float32)
    if pts.ndim == 1:
        pts = pts.reshape(-1, 2)
    for i in range(pts.shape[0]):
        x = int(pts[i, 0] * w)
        y = int(pts[i, 1] * h)
        if 0 <= x < w and 0 <= y < h:
            cv2.circle(img, (x, y), radius, color, -1)


class LandmarksOverlayRenderer:
    """Dibuja face (verde), hands (izq rojo, der azul), pose (amarillo) sobre el frame.

    Wraps an inner renderer (Passthrough, ASCII, etc). If inner produces an image,
    landmarks are drawn on top. If inner is None, works directly on the raw frame.
    """

    def __init__(self, inner: Optional[FrameRenderer] = None) -> None:
        self._inner = inner

    @property
    def inner(self) -> Optional[FrameRenderer]:
        return self._inner

    @inner.setter
    def inner(self, renderer: Optional[FrameRenderer]) -> None:
        self._inner = renderer

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        if self._inner:
            return self._inner.output_size(config)
        w = getattr(config, "raw_width", None) or getattr(config, "output_width", None)
        h = getattr(config, "raw_height", None) or getattr(config, "output_height", None)
        return (int(w), int(h)) if (w and h) else (640, 480)

    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> RenderFrame:
        # If we have an inner renderer, let it render first, then overlay landmarks
        if self._inner:
            inner_result = self._inner.render(frame, config, analysis)
            # Convert inner result back to BGR numpy for drawing
            if inner_result.image is not None:
                img = np.array(inner_result.image)
                # PIL Image is RGB, convert to BGR for cv2 drawing
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else:
                # Inner produced text-only (ASCII). Fall back to raw frame.
                if frame.ndim == 2:
                    img = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    img = frame.copy()
        else:
            if frame.ndim == 2:
                img = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 3 and frame.dtype != np.uint8:
                img = np.asarray(frame, dtype=np.uint8)
            else:
                img = frame.copy()

        h, w = img.shape[:2]

        total_pts = 0
        if analysis:
            face = analysis.get("face") or {}
            if isinstance(face, dict) and face.get("points") is not None:
                _draw_points(img, face["points"], (0, 255, 0), 2)  # verde
                total_pts += (face["points"].size // 2) if hasattr(face["points"], "size") else 0

            hands = analysis.get("hands") or {}
            if isinstance(hands, dict):
                if hands.get("left") is not None:
                    _draw_points(img, hands["left"], (0, 0, 255), 2)  # rojo BGR
                    arr = hands["left"]
                    total_pts += (arr.size // 2) if hasattr(arr, "size") else 0
                if hands.get("right") is not None:
                    _draw_points(img, hands["right"], (255, 0, 0), 2)  # azul BGR
                    arr = hands["right"]
                    total_pts += (arr.size // 2) if hasattr(arr, "size") else 0

            pose = analysis.get("pose") or {}
            if isinstance(pose, dict) and pose.get("joints") is not None:
                _draw_points(img, pose["joints"], (0, 255, 255), 2)  # amarillo
                arr = pose["joints"]
                total_pts += (arr.size // 2) if hasattr(arr, "size") else 0

        # Indicador visible
        label = "IA" if total_pts == 0 else f"IA ({total_pts})"
        cv2.putText(
            img, label, (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA
        )
        cv2.putText(
            img, label, (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA
        )

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return RenderFrame(image=Image.fromarray(img), metadata={"source": "landmarks_overlay"})
