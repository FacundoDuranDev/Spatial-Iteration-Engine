from typing import Optional, Protocol, Tuple

import numpy as np

from ..core.config import EngineConfig
from ..core.types import RenderFrame
from .ascii import AsciiRenderer


class FrameRenderer(Protocol):
    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        ...

    def render(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> RenderFrame:
        ...


__all__ = ["FrameRenderer", "AsciiRenderer"]
