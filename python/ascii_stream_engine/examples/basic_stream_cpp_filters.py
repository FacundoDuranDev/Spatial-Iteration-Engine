"""Ejemplo: stream con cámara usando filtros C++ (filters_cpp).

Ejecutar desde la raíz del repo con PYTHONPATH que incluya cpp/build, por ejemplo:
  PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/basic_stream_cpp_filters.py
o: ./run_basic_stream.sh  (si se cambia el script para apuntar a este ejemplo)
"""

from ascii_stream_engine import (
    AsciiRenderer,
    EngineConfig,
    FfmpegUdpOutput,
    FilterPipeline,
    OpenCVCameraSource,
    StreamEngine,
)
from ascii_stream_engine.adapters.processors import (
    CppBrightnessContrastFilter,
    CppInvertFilter,
)


def main() -> None:
    config = EngineConfig(host="127.0.0.1", port=1234)
    filters = FilterPipeline(
        [
            CppBrightnessContrastFilter(brightness_delta=10, contrast_factor=1.1),
            CppInvertFilter(),
        ]
    )
    engine = StreamEngine(
        source=OpenCVCameraSource(0),
        renderer=AsciiRenderer(),
        sink=FfmpegUdpOutput(),
        config=config,
        filters=filters,
    )
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
