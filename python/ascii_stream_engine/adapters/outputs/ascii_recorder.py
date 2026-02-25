import os
from typing import Tuple

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)


class AsciiFrameRecorder:
    """
    Backend de salida que graba frames ASCII a un archivo de texto.

    Útil para debugging y análisis offline.
    """

    def __init__(self, path: str = "ascii_frames.txt", flush_every: int = 1) -> None:
        self._path = path
        self._flush_every = max(1, int(flush_every))
        self._file = None
        self._frame_index = 0
        self._is_open = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._file = open(self._path, "w", encoding="utf-8")
        self._file.write("# ascii recorder\n")
        self._file.write(f"# size={output_size[0]}x{output_size[1]}\n")
        self._is_open = True

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
        self._is_open = False

    def get_capabilities(self) -> OutputCapabilities:
        """
        Obtiene las capacidades del backend de grabación ASCII.

        Este backend solo soporta grabación a archivo, no streaming.
        """
        return OutputCapabilities(
            capabilities=OutputCapability.RECORDING,

            supported_qualities=[OutputQuality.LOW],  # Solo texto ASCII
            max_clients=1,  # Solo un archivo a la vez
            protocol_name="File (ASCII)",
            metadata={
                "format": "text",
                "encoding": "utf-8",
            },
        )

    def is_open(self) -> bool:
        """Verifica si el backend está abierto y listo para escribir."""
        return self._is_open and self._file is not None

    def supports_multiple_clients(self) -> bool:
        """No soporta múltiples clientes (solo un archivo)."""
        return False
