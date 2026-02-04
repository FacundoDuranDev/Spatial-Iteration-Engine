from dataclasses import dataclass


@dataclass
class AsciiStreamConfig:
    grid_w: int = 120
    grid_h: int = 60
    fps: int = 20
    invert: bool = False
    contrast: float = 1.2
    brightness: int = 0
    charset: str = "suave"
    host: str = "127.0.0.1"
    port: int = 1234
    pkt_size: int = 1316
    bitrate: str = "1500k"
