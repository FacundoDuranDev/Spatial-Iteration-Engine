from dataclasses import dataclass
from typing import Optional


@dataclass
class EngineConfig:
    fps: int = 20
    grid_w: int = 120
    grid_h: int = 60
    charset: str = " .:-=+*#%@"
    render_mode: str = "ascii"  # "ascii" o "raw"
    raw_width: Optional[int] = None
    raw_height: Optional[int] = None
    invert: bool = False
    contrast: float = 1.2
    brightness: int = 0
    host: str = "127.0.0.1"
    port: int = 1234
    pkt_size: int = 1316
    bitrate: str = "1500k"
    udp_broadcast: bool = False
    frame_buffer_size: int = 2
    sleep_on_empty: float = 0.01
