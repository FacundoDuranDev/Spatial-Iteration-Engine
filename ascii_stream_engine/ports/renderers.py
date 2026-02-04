from typing import Optional, Protocol, Tuple

import numpy as np

from ..domain.config import EngineConfig
from ..domain.types import RenderFrame


class FrameRenderer(Protocol):
    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        ...

    def render(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> RenderFrame:
        ...
