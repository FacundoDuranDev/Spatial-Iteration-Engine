"""
Preview sin cámara: patrón animado → 1 filtro C++ → PassthroughRenderer → PreviewSink.

Sirve para probar MVP_02 cuando la cámara no funciona (permisos, WSL, sin dispositivo).
Mismo pipeline que run_preview.sh pero con fuente sintética.

Uso (desde la raíz del repo):
  PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/stream_preview_pattern.py
o: ./run_preview_pattern.sh
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

try:
    from ascii_stream_engine import GeneratorSource, PatternGenerator
except ImportError:
    from ascii_stream_engine.adapters.generators import GeneratorSource, PatternGenerator


def main() -> None:
    config = EngineConfig(host="127.0.0.1", port=1234, frame_buffer_size=0, sleep_on_empty=0.001)
    source = GeneratorSource(
        PatternGenerator(pattern_type="turing", speed=0.5), width=640, height=480
    )
    filters = FilterPipeline([CppInvertFilter()])
    engine = StreamEngine(
        source=source,
        renderer=PassthroughRenderer(),
        sink=PreviewSink(),
        config=config,
        filters=filters,
    )
    print("Preview con patrón (sin cámara) + filtro C++ invert. Ctrl+C para salir.")
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
