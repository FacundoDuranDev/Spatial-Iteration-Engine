import time

from .ascii_streamer import AsciiStreamer
from .config import AsciiStreamConfig


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Stream ASCII por UDP con ffmpeg.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--grid-w", type=int, default=120)
    parser.add_argument("--grid-h", type=int, default=60)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--contrast", type=float, default=1.2)
    parser.add_argument("--brightness", type=int, default=0)
    parser.add_argument("--charset", default="suave")
    parser.add_argument("--camera", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = AsciiStreamConfig(
        grid_w=args.grid_w,
        grid_h=args.grid_h,
        fps=args.fps,
        invert=args.invert,
        contrast=args.contrast,
        brightness=args.brightness,
        charset=args.charset,
        host=args.host,
        port=args.port,
    )
    streamer = AsciiStreamer(cfg)
    streamer.start(camera_index=args.camera)
    try:
        while streamer.is_running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        streamer.stop()


if __name__ == "__main__":
    main()
