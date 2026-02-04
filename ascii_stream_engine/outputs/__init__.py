from typing import Protocol, Tuple

from ..core.config import EngineConfig
from ..core.types import RenderFrame
from .ascii_recorder import AsciiFrameRecorder
from .udp import FfmpegUdpOutput


class OutputSink(Protocol):
    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        ...

    def write(self, frame: RenderFrame) -> None:
        ...

    def close(self) -> None:
        ...


__all__ = ["OutputSink", "AsciiFrameRecorder", "FfmpegUdpOutput"]
