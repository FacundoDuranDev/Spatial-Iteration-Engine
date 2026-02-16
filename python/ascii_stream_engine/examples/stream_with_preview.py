"""
MVP_02 — One C++ filter in live pipeline.

Pipeline: Camera → FilterPipeline (1 C++ filter) → PassthroughRenderer → PreviewSink.

Requisitos: ./cpp/build.sh y PYTHONPATH=python:cpp/build.
Desde la raíz del repo: ./run_preview.sh [índice_cámara]
  Ejemplo: ./run_preview.sh 0   o   ./run_preview.sh 1
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
from ascii_stream_engine.adapters.processors import CppInvertFilter


def main() -> None:
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    # Comprobar que la cámara abre y devuelve un frame antes de arrancar el engine
    source = OpenCVCameraSource(camera_index)
    source.open()
    test_frame = source.read()
    source.close()
    if test_frame is None:
        print(f"No se pudo leer de la cámara (índice {camera_index}).")
        print("  - Prueba otro índice: ./run_preview.sh 1   o   ./run_preview.sh 2")
        print("  - Diagnóstico: PYTHONPATH=python python python/ascii_stream_engine/examples/diagnose_camera.py")
        print("  - Permisos: sudo usermod -aG video $USER   (luego cierra sesión)")
        sys.exit(1)
    config = EngineConfig(host="127.0.0.1", port=1234, frame_buffer_size=0, sleep_on_empty=0.001)
    filters = FilterPipeline([CppInvertFilter()])
    engine = StreamEngine(
        source=OpenCVCameraSource(camera_index),
        renderer=PassthroughRenderer(),
        sink=PreviewSink(),
        config=config,
        filters=filters,
    )
    print(f"MVP_02 Preview — cámara {camera_index}, 1 filtro C++ (invert). Ctrl+C para salir.")
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
