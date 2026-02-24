"""Video recorder output sink using ffmpeg subprocess.

Records rendered frames to MP4, AVI, MKV, MOV, or WebM video files
using ffmpeg as the encoding backend. Follows the same subprocess
pattern as FfmpegUdpOutput and FfmpegRtspSink.
"""

import logging
import os
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

# Map file extensions to ffmpeg container formats
_FORMAT_MAP = {
    ".mp4": "mp4",
    ".avi": "avi",
    ".mkv": "matroska",
    ".mov": "mov",
    ".webm": "webm",
}


class VideoRecorderSink:
    """Output sink that records rendered frames to video files.

    Uses ffmpeg subprocess to encode raw video frames into MP4, AVI,
    MKV, MOV, or WebM container formats.

    Args:
        output_path: Path to the output video file (default: "output.mp4").
        codec: Video codec (default: "libx264").
        bitrate: Video bitrate (default: "2000k").
        preset: Encoding preset (default: "medium").
        container_format: Container format. Auto-detected from extension if None.
        pixel_format: Output pixel format (default: "yuv420p").
    """

    def __init__(
        self,
        output_path: str = "output.mp4",
        codec: str = "libx264",
        bitrate: str = "2000k",
        preset: str = "medium",
        container_format: Optional[str] = None,
        pixel_format: str = "yuv420p",
    ) -> None:
        self._output_path = output_path
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._container_format = container_format
        self._pixel_format = pixel_format
        self._proc: Optional[subprocess.Popen] = None
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None

    def _detect_format(self) -> str:
        """Detect container format from file extension.

        Returns:
            ffmpeg format string (e.g. "mp4", "matroska").
        """
        if self._container_format:
            return self._container_format

        ext = os.path.splitext(self._output_path)[1].lower()
        return _FORMAT_MAP.get(ext, "mp4")

    def _get_codec_for_format(self, fmt: str) -> str:
        """Get the appropriate codec for the container format.

        WebM requires libvpx; other formats use the configured codec.

        Args:
            fmt: Container format string.

        Returns:
            Codec string.
        """
        if fmt == "webm" and self._codec == "libx264":
            return "libvpx"
        return self._codec

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """Open the video recorder and start the ffmpeg process.

        Args:
            config: Engine configuration.
            output_size: Output dimensions as (width, height).
        """
        self.close()
        self._output_size = output_size

        out_w, out_h = output_size
        fmt = self._detect_format()
        codec = self._get_codec_for_format(fmt)

        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",  # Overwrite output file
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
            codec,
            "-b:v",
            self._bitrate,
            "-preset",
            self._preset,
            "-pix_fmt",
            self._pixel_format,
            "-f",
            fmt,
            self._output_path,
        ]

        logger.info(f"Starting video recording to {self._output_path}")
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
            raise RuntimeError("ffmpeg not found. Please install ffmpeg to use the video recorder.")
        except Exception as e:
            raise RuntimeError(f"Error starting video recorder: {e}")

    def write(self, frame: RenderFrame) -> None:
        """Write a frame to the video file.

        Args:
            frame: Rendered frame to record.
        """
        if not self._is_open or not self._proc or not self._proc.stdin:
            return

        try:
            image = frame.image if isinstance(frame, RenderFrame) else frame
            if isinstance(image, Image.Image):
                if image.mode != "RGB":
                    image = image.convert("RGB")
                self._proc.stdin.write(image.tobytes())
        except BrokenPipeError:
            logger.error("Broken pipe - ffmpeg process may have terminated")
            self._proc = None
            self._is_open = False
        except Exception as e:
            logger.error(f"Error writing frame to recorder: {e}")

    def close(self) -> None:
        """Close the video recorder and finalize the output file.

        Properly closes stdin so ffmpeg can write the moov atom and
        finalize the container. Then waits for process exit.
        """
        cleanup_subprocess(self._proc)
        self._proc = None
        self._is_open = False
        self._output_size = None

    def is_open(self) -> bool:
        """Check if the sink is open and ready to write."""
        return self._is_open and self._proc is not None and self._proc.stdin is not None

    def get_capabilities(self) -> OutputCapabilities:
        """Get the capabilities of this video recorder sink."""
        return OutputCapabilities(
            capabilities=(
                OutputCapability.RECORDING
                | OutputCapability.HIGH_QUALITY
                | OutputCapability.CUSTOM_BITRATE
            ),
            estimated_latency_ms=2.0,
            supported_qualities=[
                OutputQuality.LOW,
                OutputQuality.MEDIUM,
                OutputQuality.HIGH,
                OutputQuality.ULTRA,
            ],
            max_clients=1,
            protocol_name="File (Video)",
            metadata={
                "codec": self._codec,
                "bitrate": self._bitrate,
                "preset": self._preset,
                "output_path": self._output_path,
                "container_format": self._detect_format(),
            },
        )

    def get_estimated_latency_ms(self) -> Optional[float]:
        """Get the estimated latency in milliseconds."""
        return 2.0

    def supports_multiple_clients(self) -> bool:
        """Video files do not support multiple clients."""
        return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
