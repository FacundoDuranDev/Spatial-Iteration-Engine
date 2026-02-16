"""Renderer que pasa el frame tal cual a la salida (sin ASCII ni deformación)."""

from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer


class PassthroughRenderer:
    """Muestra el frame sin modificación visual (solo conversión a PIL para el sink)."""

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        # El tamaño lo decide la fuente; usamos valores por defecto si hace falta
        w = getattr(config, "raw_width", None) or getattr(config, "output_width", None)
        h = getattr(config, "raw_height", None) or getattr(config, "output_height", None)
        if w is not None and h is not None:
            return int(w), int(h)
        return 640, 480

    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> RenderFrame:
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        return RenderFrame(image=img, metadata={"source": "passthrough"})
