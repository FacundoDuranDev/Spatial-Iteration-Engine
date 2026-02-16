"""OutputSink que muestra el video en una ventana con OpenCV (cv2.imshow)."""

from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)


class PreviewSink:
    """
    Muestra cada frame en una ventana con OpenCV.
    Útil para ver el video sin configurar UDP/VLC.
    Cerrar la ventana o pulsar 'q' no detiene el engine; usar Ctrl+C en la terminal.
    """

    WINDOW_NAME = "Spatial-Iteration-Engine Preview"

    def __init__(self, window_name: Optional[str] = None) -> None:
        self._window_name = window_name or self.WINDOW_NAME
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        self.close()
        self._output_size = output_size
        cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)
        self._is_open = True

    def write(self, frame: RenderFrame) -> None:
        if not self._is_open:
            return
        image = frame.image if hasattr(frame, "image") else frame
        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
            arr = np.asarray(image, dtype=np.uint8)
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            arr = np.asarray(image, dtype=np.uint8)
            if arr.ndim == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            elif arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        cv2.imshow(self._window_name, arr)
        cv2.waitKey(1)

    def close(self) -> None:
        if self._is_open:
            try:
                cv2.destroyWindow(self._window_name)
            except Exception:
                pass
        cv2.destroyAllWindows()
        self._is_open = False
        self._output_size = None

    def get_capabilities(self) -> OutputCapabilities:
        return OutputCapabilities(
            capabilities=OutputCapability.STREAMING | OutputCapability.LOW_LATENCY,
            estimated_latency_ms=16.0,
            supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM, OutputQuality.HIGH],
            max_clients=1,
            min_bitrate=None,
            max_bitrate=None,
            protocol_name="OpenCV Preview",
            metadata={"display": "local"},
        )

    def is_open(self) -> bool:
        return self._is_open

    def get_estimated_latency_ms(self) -> Optional[float]:
        return 16.0

    def supports_multiple_clients(self) -> bool:
        return False
