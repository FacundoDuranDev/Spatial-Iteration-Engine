import subprocess
from typing import Optional, Tuple

from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)


class FfmpegUdpOutput:
    """
    Backend de salida UDP usando ffmpeg.

    Soporta streaming UDP con broadcast opcional. Optimizado para baja latencia.
    """

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
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        self.close()
        host = self._host or config.host
        port = self._port or config.port
        pkt_size = self._pkt_size or config.pkt_size
        bitrate = self._bitrate or config.bitrate
        broadcast = self._broadcast if self._broadcast is not None else config.udp_broadcast
        out_w, out_h = output_size
        self._output_size = output_size
        url = f"udp://{host}:{port}?pkt_size={pkt_size}"
        if broadcast:
            url += "&broadcast=1"
        cmd = [
            "ffmpeg",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
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
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-g",
            "1",  # keyframe every frame — instant decode at receiver
            "-bf",
            "0",  # no B-frames
            "-b:v",
            bitrate,
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-flush_packets",
            "1",
            "-f",
            "mpegts",
            url,
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self._is_open = True

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
        self._is_open = False
        self._output_size = None

    def get_capabilities(self) -> OutputCapabilities:
        """
        Obtiene las capacidades del backend UDP.

        UDP con ffmpeg soporta streaming, broadcast, y baja latencia.
        """
        capabilities = (
            OutputCapability.STREAMING
            | OutputCapability.UDP
            | OutputCapability.LOW_LATENCY
            | OutputCapability.CUSTOM_BITRATE
        )

        if self._broadcast or (self._broadcast is None):
            capabilities |= OutputCapability.BROADCAST

        return OutputCapabilities(
            capabilities=capabilities,

            supported_qualities=[
                OutputQuality.LOW,
                OutputQuality.MEDIUM,
                OutputQuality.HIGH,
            ],
            max_clients=None,
            min_bitrate="500k",
            max_bitrate="10m",
            protocol_name="UDP/MPEG-TS",
            metadata={
                "codec": "libx264",
                "preset": "ultrafast",
                "tune": "zerolatency",
                "container": "mpegts",
                "supports_broadcast": True,
            },
        )

    def is_open(self) -> bool:
        """Verifica si el backend está abierto y listo para escribir."""
        return self._is_open and self._proc is not None and self._proc.stdin is not None

    def supports_multiple_clients(self) -> bool:
        """
        UDP soporta múltiples clientes cuando se usa broadcast o multicast.
        En modo unicast, técnicamente solo un cliente puede recibir.
        """
        return self._broadcast is True or (
            self._broadcast is None
        )  # Si no está especificado, asumimos que puede ser configurado
