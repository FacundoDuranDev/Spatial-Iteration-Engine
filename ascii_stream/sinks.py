import subprocess
from typing import Optional, Protocol, Tuple

from PIL import Image

from .config import AsciiStreamConfig


class OutputSink(Protocol):
    def open(self, config: AsciiStreamConfig, output_size: Tuple[int, int]) -> None:
        ...

    def write(self, image: Image.Image) -> None:
        ...

    def close(self) -> None:
        ...


class UdpFfmpegSink:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        pkt_size: Optional[int] = None,
        bitrate: Optional[str] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._pkt_size = pkt_size
        self._bitrate = bitrate
        self._proc: Optional[subprocess.Popen] = None

    def open(self, config: AsciiStreamConfig, output_size: Tuple[int, int]) -> None:
        host = self._host or config.host
        port = self._port or config.port
        pkt_size = self._pkt_size or config.pkt_size
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
            "mpeg1video",
            "-b:v",
            bitrate,
            "-f",
            "mpegts",
            f"udp://{host}:{port}?pkt_size={pkt_size}",
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, image: Image.Image) -> None:
        if not self._proc or not self._proc.stdin:
            return
        if image.mode != "RGB":
            image = image.convert("RGB")
        self._proc.stdin.write(image.tobytes())

    def close(self) -> None:
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
        if self._proc:
            self._proc.wait()
            self._proc = None
