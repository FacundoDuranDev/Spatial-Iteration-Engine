"""NDI (Network Device Interface) output sink.

Streams rendered frames over NDI for discovery and reception by any
NDI-compatible receiver on the local network. Requires ndi-python
and the NDI SDK to be installed.
"""

import logging
import threading
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from ....domain.config import EngineConfig
from ....domain.types import RenderFrame
from ....ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)

logger = logging.getLogger(__name__)

# Try to import NDI, handle gracefully if not available
try:
    import NDIlib as ndi

    NDI_AVAILABLE = True
except ImportError:
    NDI_AVAILABLE = False
    ndi = None  # type: ignore
    logger.warning(
        "NDI SDK is not available. Install 'ndi-python' and the NDI SDK "
        "to use the NDI output."
    )


class NdiOutputSink:
    """Output sink that sends frames via NDI (Network Device Interface).

    Requires:
    - ndi-python: pip install ndi-python
    - NDI SDK from https://www.ndi.tv/sdk/

    Args:
        source_name: NDI source name (default: "Spatial Iteration Engine").
        groups: NDI groups (comma-separated).
        clock_video: If True, sync video to system clock.
        clock_audio: If True, sync audio to system clock.
    """

    def __init__(
        self,
        source_name: Optional[str] = None,
        groups: Optional[str] = None,
        clock_video: bool = True,
        clock_audio: bool = False,
    ) -> None:
        if not NDI_AVAILABLE:
            raise ImportError(
                "NDI SDK is not available. Install 'ndi-python' and the NDI SDK."
            )

        self._source_name = source_name or "Spatial Iteration Engine"
        self._groups = groups
        self._clock_video = clock_video
        self._clock_audio = clock_audio

        self._ndi_send: Optional[object] = None
        self._video_frame: Optional[object] = None
        self._output_size: Optional[Tuple[int, int]] = None
        self._fps: Optional[float] = None
        self._lock = threading.RLock()
        self._is_open = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """Open the NDI connection and prepare for sending frames.

        Args:
            config: Engine configuration.
            output_size: Output dimensions as (width, height).
        """
        if not NDI_AVAILABLE:
            raise RuntimeError("NDI SDK is not available")

        with self._lock:
            self.close()

            # Initialize NDI
            if not ndi.initialize():
                raise RuntimeError("Failed to initialize NDI")

            # Create NDI send settings
            send_settings = ndi.LibNDISendCreate()
            send_settings.ndi_name = self._source_name
            if self._groups:
                send_settings.ndi_groups = self._groups
            send_settings.clock_video = self._clock_video
            send_settings.clock_audio = self._clock_audio

            # Create NDI sender
            self._ndi_send = ndi.send_create(send_settings)
            if not self._ndi_send:
                raise RuntimeError("Failed to create NDI sender")

            # Prepare NDI video frame
            self._output_size = output_size
            self._fps = config.fps
            out_w, out_h = output_size

            self._video_frame = ndi.VideoFrameV2()
            self._video_frame.xres = out_w
            self._video_frame.yres = out_h
            self._video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRA
            self._video_frame.frame_rate_N = config.fps
            self._video_frame.frame_rate_D = 1
            self._video_frame.picture_aspect_ratio = out_w / out_h

            # Pre-allocate frame buffer (BGRA = 4 bytes per pixel)
            frame_size = out_w * out_h * 4
            self._video_frame.p_data = np.zeros(frame_size, dtype=np.uint8)

            self._is_open = True
            logger.info(
                f"NDI output opened: {self._source_name} "
                f"({out_w}x{out_h} @ {config.fps} fps)"
            )

    def write(self, frame: RenderFrame) -> None:
        """Write a frame to the NDI stream.

        Args:
            frame: Rendered frame to send.
        """
        if not NDI_AVAILABLE or not self._is_open:
            return

        with self._lock:
            if not self._ndi_send or not self._video_frame:
                return

            try:
                image = frame.image if isinstance(frame, RenderFrame) else frame
                if not isinstance(image, Image.Image):
                    logger.warning("Frame does not contain a valid PIL Image")
                    return

                # Convert to RGB if necessary
                if image.mode != "RGB":
                    image = image.convert("RGB")

                # Resize if necessary
                if self._output_size:
                    out_w, out_h = self._output_size
                    if image.size != (out_w, out_h):
                        image = image.resize(
                            (out_w, out_h), Image.Resampling.LANCZOS
                        )

                # Convert RGB to BGRA (required by NDI)
                rgb_array = np.array(image, dtype=np.uint8)

                # Use cv2 if available for faster conversion, else numpy
                try:
                    import cv2

                    bgra_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGRA)
                except ImportError:
                    bgra_array = np.zeros(
                        (rgb_array.shape[0], rgb_array.shape[1], 4), dtype=np.uint8
                    )
                    bgra_array[:, :, 0] = rgb_array[:, :, 2]  # B
                    bgra_array[:, :, 1] = rgb_array[:, :, 1]  # G
                    bgra_array[:, :, 2] = rgb_array[:, :, 0]  # R
                    bgra_array[:, :, 3] = 255  # A (opaque)

                # Copy data to NDI frame buffer
                frame_data = bgra_array.flatten()
                if len(frame_data) == len(self._video_frame.p_data):
                    self._video_frame.p_data[:] = frame_data
                else:
                    self._video_frame.p_data = frame_data

                # Send frame
                ndi.send_send_video_v2(self._ndi_send, self._video_frame)

            except Exception as e:
                logger.error(f"Error sending NDI frame: {e}", exc_info=True)

    def close(self) -> None:
        """Close the NDI connection and release resources. Idempotent."""
        with self._lock:
            if self._ndi_send:
                try:
                    ndi.send_destroy(self._ndi_send)
                except Exception as e:
                    logger.warning(f"Error destroying NDI sender: {e}")
                self._ndi_send = None

            self._video_frame = None
            self._output_size = None
            self._fps = None
            self._is_open = False

            if NDI_AVAILABLE and ndi is not None:
                try:
                    ndi.destroy()
                except Exception as e:
                    logger.debug(f"Error destroying NDI runtime: {e}")

    def is_open(self) -> bool:
        """Check if the sink is open and ready to write."""
        return self._is_open

    def get_capabilities(self) -> OutputCapabilities:
        """Get the capabilities of this NDI sink."""
        return OutputCapabilities(
            capabilities=(
                OutputCapability.STREAMING
                | OutputCapability.NDI
                | OutputCapability.LOW_LATENCY
                | OutputCapability.MULTI_CLIENT
                | OutputCapability.HIGH_QUALITY
                | OutputCapability.ADAPTIVE_QUALITY
            ),
            estimated_latency_ms=10.0,
            supported_qualities=[
                OutputQuality.LOW,
                OutputQuality.MEDIUM,
                OutputQuality.HIGH,
                OutputQuality.ULTRA,
            ],
            max_clients=None,  # NDI supports unlimited receivers
            protocol_name="NDI",
            metadata={
                "source_name": self._source_name,
                "groups": self._groups,
            },
        )

    def get_estimated_latency_ms(self) -> Optional[float]:
        """Get the estimated latency in milliseconds."""
        return 10.0

    def supports_multiple_clients(self) -> bool:
        """NDI supports unlimited receivers on the network."""
        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
