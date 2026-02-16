"""
Cámara → filtros C++ → ventana (sin ASCII).

Solo video normal con filtros en C++. Detener con Ctrl+C.

Desde la raíz del repo:
  PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/stream_camera_cpp_preview.py [índice_cámara]
  Índice por defecto: 0. Si la cámara no enciende, prueba 2 o 4 (ej: ...stream_camera_cpp_preview.py 2)
o: ./run_preview_raw.sh
"""
import sys
from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    PassthroughRenderer,
    PreviewSink,
    FilterPipeline,
)
from ascii_stream_engine.adapters.processors import (
    CppBrightnessContrastFilter,
    CppInvertFilter,
)


def main() -> None:
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    config = EngineConfig(host="127.0.0.1", port=1234)
    filters = FilterPipeline([
        CppBrightnessContrastFilter(brightness_delta=10, contrast_factor=1.1),
        CppInvertFilter(),
    ])
    engine = StreamEngine(
        source=OpenCVCameraSource(camera_index),
        renderer=PassthroughRenderer(),
        sink=PreviewSink(),
        config=config,
        filters=filters,
    )
    print(f"Preview: cámara {camera_index} + filtros C++ (sin ASCII). Detener con Ctrl+C.")
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
