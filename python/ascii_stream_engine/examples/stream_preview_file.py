"""
Preview desde archivo de video → 1 filtro C++ → PassthroughRenderer → PreviewSink.

Útil cuando la cámara no funciona: usa un .mp4 o .avi.

Uso (desde la raíz del repo):
  PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/stream_preview_file.py /ruta/al/video.mp4
"""

import sys

from ascii_stream_engine import (
    EngineConfig,
    FilterPipeline,
    PassthroughRenderer,
    PreviewSink,
    StreamEngine,
)
from ascii_stream_engine.adapters.processors import CppInvertFilter
from ascii_stream_engine.adapters.sources import VideoFileSource


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: stream_preview_file.py <ruta_video.mp4>")
        sys.exit(1)
    path = sys.argv[1]
    source = VideoFileSource(path)
    source.open()
    if source.read() is None:
        print(f"No se pudo abrir el video: {path}")
        source.close()
        sys.exit(1)
    source.close()
    config = EngineConfig(host="127.0.0.1", port=1234, frame_buffer_size=0, sleep_on_empty=0.001)
    engine = StreamEngine(
        source=VideoFileSource(path),
        renderer=PassthroughRenderer(),
        sink=PreviewSink(),
        config=config,
        filters=FilterPipeline([CppInvertFilter()]),
    )
    print(f"Preview desde archivo: {path} + filtro C++ invert. Ctrl+C para salir.")
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
