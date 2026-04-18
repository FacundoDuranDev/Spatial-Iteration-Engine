"""RTSP output sink using ffmpeg subprocess.

Streams rendered frames via RTSP using ffmpeg as the encoding and
transport backend. Supports configurable codec, bitrate, preset,
and multi-client streaming via external RTSP servers (e.g. MediaMTX).
"""

import logging
import subprocess
from typing import Optional, Tuple

from PIL import Image

from ....domain.config import EngineConfig
from ....domain.types import RenderFrame
from ....ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)
from .._subprocess_utils import cleanup_subprocess

logger = logging.getLogger(__name__)


class FfmpegRtspSink:
    """RTSP streaming output sink via ffmpeg subprocess.

    Uses ffmpeg to encode raw video frames and stream them over RTSP.
    For full multi-client support, pair with an external RTSP server
    such as MediaMTX (formerly rtsp-simple-server).

    Args:
        rtsp_url: Full RTSP URL (e.g. "rtsp://localhost:8554/stream").
        bitrate: Video bitrate (e.g. "1500k", "2m").
        codec: Video codec (default: "libx264").
        preset: Encoding preset (default: "ultrafast" for low latency).
        tune: Encoding tune (default: "zerolatency").
        rtsp_transport: RTSP transport protocol (default: "tcp").
        max_clients: Maximum simultaneous clients (informational).
    """

    def __init__(
        self,
        rtsp_url: Optional[str] = None,
        bitrate: Optional[str] = None,
        codec: Optional[str] = None,
        preset: Optional[str] = None,
        tune: Optional[str] = None,
        rtsp_transport: Optional[str] = None,
        max_clients: Optional[int] = None,
    ) -> None:
        self._rtsp_url = rtsp_url
        self._bitrate = bitrate
        self._codec = codec or "libx264"
        self._preset = preset or "ultrafast"
        self._tune = tune or "zerolatency"
        self._rtsp_transport = rtsp_transport or "tcp"
        self._max_clients = max_clients or 10
        self._proc: Optional[subprocess.Popen] = None
        self._output_size: Optional[Tuple[int, int]] = None
        self._is_open = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """Open the RTSP output and start the ffmpeg process.

        Args:
            config: Engine configuration.
            output_size: Output dimensions as (width, height).
        """
        self.close()
        self._output_size = output_size

        # Build RTSP URL
        if not self._rtsp_url:
            host = config.host if config.host != "127.0.0.1" else "0.0.0.0"
            port = config.port if config.port != 1234 else 8554
            stream_path = "stream"
            rtsp_url = f"rtsp://{host}:{port}/{stream_path}"
        else:
            rtsp_url = self._rtsp_url

        bitrate = self._bitrate or config.bitrate
        out_w, out_h = output_size

        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{out_w}x{out_h}",
            "-framerate",
            str(config.fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            self._codec,
            "-preset",
            self._preset,
            "-tune",
            self._tune,
            "-b:v",
            bitrate,
            "-f",
            "rtsp",
            "-rtsp_transport",
            self._rtsp_transport,
            rtsp_url,
        ]

        if self._max_clients:
            logger.info(
                f"Configured for up to {self._max_clients} simultaneous clients. "
                "For full multi-client support, use an external RTSP server."
            )

        logger.info(f"Starting RTSP output at {rtsp_url}")
        logger.debug(f"ffmpeg command: {' '.join(cmd)}")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._is_open = True
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg to use the RTSP output.")
        except Exception as e:
            raise RuntimeError(f"Error starting RTSP output: {e}")

    def write(self, frame: RenderFrame) -> None:
        """Write a frame to the RTSP stream.

        Args:
            frame: Rendered frame to stream.
        """
        if not self._is_open or not self._proc or not self._proc.stdin:
            return

        try:
            image = frame.image if isinstance(frame, RenderFrame) else frame
            if isinstance(image, Image.Image):
                if image.mode != "RGB":
                    image = image.convert("RGB")
                self._proc.stdin.write(image.tobytes())
                self._proc.stdin.flush()
        except BrokenPipeError:
            logger.error("Broken pipe - ffmpeg process may have terminated")
            self._proc = None
            self._is_open = False
        except Exception as e:
            logger.error(f"Error writing frame: {e}")

    def close(self) -> None:
        """Close the RTSP output and terminate the ffmpeg process."""
        cleanup_subprocess(self._proc)
        self._proc = None
        self._is_open = False
        self._output_size = None

    def is_open(self) -> bool:
        """Check if the sink is open and ready to write."""
        return self._is_open and self._proc is not None and self._proc.stdin is not None

    def get_capabilities(self) -> OutputCapabilities:
        """Get the capabilities of this RTSP sink."""
        return OutputCapabilities(
            capabilities=(
                OutputCapability.STREAMING
                | OutputCapability.RTSP
                | OutputCapability.TCP
                | OutputCapability.LOW_LATENCY
                | OutputCapability.CUSTOM_BITRATE
                | OutputCapability.MULTI_CLIENT
            ),
            supported_qualities=[
                OutputQuality.LOW,
                OutputQuality.MEDIUM,
                OutputQuality.HIGH,
            ],
            max_clients=self._max_clients,
            protocol_name="RTSP/H.264",
            metadata={
                "codec": self._codec,
                "preset": self._preset,
                "tune": self._tune,
                "transport": self._rtsp_transport,
            },
        )

    def supports_multiple_clients(self) -> bool:
        """RTSP inherently supports multiple consumers via an RTSP server."""
        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
