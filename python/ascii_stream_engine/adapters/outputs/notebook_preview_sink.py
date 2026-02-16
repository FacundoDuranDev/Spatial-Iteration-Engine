"""OutputSink que muestra el video dentro del notebook (ipywidgets.Image)."""

import io
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)


class NotebookPreviewSink:
    """
    Muestra cada frame en un widget de imagen dentro del notebook.
    No usa ventana de escritorio (cv2.imshow); ideal cuando el kernel no tiene display.
    """

    def __init__(self, image_widget=None, format: str = "jpeg", quality: int = 85) -> None:
        """
        Args:
            image_widget: ipywidgets.Image() - si es None, se intenta crear al abrir (requiere ipywidgets).
            format: "jpeg" o "png" para el stream mostrado.
            quality: Calidad JPEG (1-100).
        """
        self._widget = image_widget
        self._format = format.lower()
        self._quality = quality
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        self.close()
        self._output_size = output_size
        if self._widget is None:
            try:
                import ipywidgets as widgets
                from IPython.display import display
                self._widget = widgets.Image(format=self._format)
                display(self._widget)
            except ImportError:
                pass
        self._is_open = True

    def write(self, frame: RenderFrame) -> None:
        if not self._is_open or self._widget is None:
            return
        image = frame.image if hasattr(frame, "image") else frame
        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
        else:
            arr = np.asarray(image, dtype=np.uint8)
            if arr.ndim == 2:
                image = Image.fromarray(arr).convert("RGB")
            else:
                image = Image.fromarray(arr)
        buf = io.BytesIO()
        if self._format == "jpeg":
            image.save(buf, format="JPEG", quality=self._quality)
        else:
            image.save(buf, format="PNG")
        self._widget.value = buf.getvalue()

    def close(self) -> None:
        self._is_open = False
        self._output_size = None

    def get_capabilities(self) -> OutputCapabilities:
        return OutputCapabilities(
            capabilities=OutputCapability.STREAMING | OutputCapability.LOW_LATENCY,
            estimated_latency_ms=50.0,
            supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM, OutputQuality.HIGH],
            max_clients=1,
            min_bitrate=None,
            max_bitrate=None,
            protocol_name="Notebook Preview",
            metadata={"display": "notebook"},
        )

    def is_open(self) -> bool:
        return self._is_open

    def get_estimated_latency_ms(self) -> Optional[float]:
        return 50.0

    def supports_multiple_clients(self) -> bool:
        return False
