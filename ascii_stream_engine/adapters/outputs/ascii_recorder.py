import os
from typing import Optional, Tuple

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame


class AsciiFrameRecorder:
    def __init__(self, path: str = "ascii_frames.txt", flush_every: int = 1) -> None:
        self._path = path
        self._flush_every = max(1, int(flush_every))
        self._file = None
        self._frame_index = 0

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._file = open(self._path, "w", encoding="utf-8")
        self._file.write("# ascii recorder\n")
        self._file.write(f"# size={output_size[0]}x{output_size[1]}\n")

    def write(self, frame: RenderFrame) -> None:
        if self._file is None:
            return
        text = None
        timestamp = None
        if isinstance(frame, RenderFrame):
            text = frame.text
            if frame.metadata:
                analysis = frame.metadata.get("analysis")
                if isinstance(analysis, dict):
                    timestamp = analysis.get("timestamp")
        if not text:
            return

        self._frame_index += 1
        header = f"# frame={self._frame_index}"
        if timestamp is not None:
            header += f" ts={timestamp}"
        self._file.write(header + "\n")
        self._file.write(text + "\n")
        self._file.write("--FRAME--\n")
        if self._frame_index % self._flush_every == 0:
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
