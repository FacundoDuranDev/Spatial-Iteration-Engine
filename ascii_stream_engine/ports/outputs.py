from typing import Protocol, Tuple

from ..domain.config import EngineConfig
from ..domain.types import RenderFrame


class OutputSink(Protocol):
    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        ...

    def write(self, frame: RenderFrame) -> None:
        ...

    def close(self) -> None:
        ...
