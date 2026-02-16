"""
MVP_01 — Live Preview Canonical Path.

Pipeline: Camera → FilterPipeline (0 o 1 filtro Python) → PassthroughRenderer → PreviewSink.

Uso (desde la raíz del repo):
  PYTHONPATH=python python python/ascii_stream_engine/examples/stream_camera_preview_only.py [índice]

Criterio de éxito: se abre una ventana, la cámara se ve en tiempo real;
si se agrega un filtro (p. ej. InvertFilter), el efecto se ve.
"""
import sys
from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    PassthroughRenderer,
    PreviewSink,
    FilterPipeline,
    InvertFilter,
)

def main():
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    source = OpenCVCameraSource(camera_index)
    source.open()
    test_frame = source.read()
    source.close()
    if test_frame is None:
        print(f"No se pudo leer de la cámara (índice {camera_index}).")
        print("  - Prueba otro índice como argumento, p. ej. .../stream_camera_preview_only.py 1")
        print("  - Diagnóstico: PYTHONPATH=python python python/ascii_stream_engine/examples/diagnose_camera.py")
        print("  - Permisos: sudo usermod -aG video $USER   (luego cierra sesión)")
        sys.exit(1)
    config = EngineConfig(
        host="127.0.0.1",
        port=1234,
        frame_buffer_size=0,
        sleep_on_empty=0.001,
    )
    # 0 filtros: imagen tal cual. Para ver efecto, usar por ejemplo:
    # filters=FilterPipeline([InvertFilter()])
    filters = FilterPipeline([])
    engine = StreamEngine(
        source=OpenCVCameraSource(camera_index),
        renderer=PassthroughRenderer(),
        sink=PreviewSink(),
        config=config,
        filters=filters,
    )
    print(f"MVP_01 Preview — Cámara {camera_index} → ventana. Ctrl+C para salir.")
    engine.start(blocking=True)

if __name__ == "__main__":
    main()
