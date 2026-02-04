import subprocess
from typing import Optional, Tuple

from PIL import Image

from ..core.config import EngineConfig
from ..core.types import RenderFrame


class FfmpegUdpOutput:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        pkt_size: Optional[int] = None,
        bitrate: Optional[str] = None,
        broadcast: Optional[bool] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._pkt_size = pkt_size
        self._bitrate = bitrate
        self._broadcast = broadcast
        self._proc: Optional[subprocess.Popen] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        self.close()
        host = self._host or config.host
        port = self._port or config.port
        pkt_size = self._pkt_size or config.pkt_size
        bitrate = self._bitrate or config.bitrate
        broadcast = (
            self._broadcast if self._broadcast is not None else config.udp_broadcast
        )
        out_w, out_h = output_size
        url = f"udp://{host}:{port}?pkt_size={pkt_size}"
        if broadcast:
            url += "&broadcast=1"
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
            url,
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame: RenderFrame) -> None:
        if not self._proc or not self._proc.stdin:
            return
        image = frame.image if isinstance(frame, RenderFrame) else frame
        if isinstance(image, Image.Image):
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
            try:
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            self._proc = None
