"""
MVP_03 — Perception: face, hands, pose landmarks (C++ stubs).

Pipeline: Camera → AnalyzerPipeline(face, hands, pose) → FilterPipeline → LandmarksOverlayRenderer → PreviewSink.

Si perception_cpp no está compilado, el pipeline no se rompe; solo no se dibujan puntos.
Compilar: ./cpp/build.sh  luego PYTHONPATH=python:cpp/build

Uso (desde raíz del repo):
  PYTHONPATH=python python python/ascii_stream_engine/examples/stream_with_landmarks.py [cámara]
  o con C++: PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/stream_with_landmarks.py
"""
import sys
from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    PreviewSink,
    FilterPipeline,
)
from ascii_stream_engine.adapters.perception import (
    FaceLandmarkAnalyzer,
    HandLandmarkAnalyzer,
    PoseLandmarkAnalyzer,
)
from ascii_stream_engine.adapters.renderers import LandmarksOverlayRenderer
from ascii_stream_engine.application.pipeline import AnalyzerPipeline


def main() -> None:
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    config = EngineConfig(host="127.0.0.1", port=1234, frame_buffer_size=0, sleep_on_empty=0.001)
    analyzers = AnalyzerPipeline([
        FaceLandmarkAnalyzer(),
        HandLandmarkAnalyzer(),
        PoseLandmarkAnalyzer(),
    ])
    engine = StreamEngine(
        source=OpenCVCameraSource(camera_index),
        renderer=LandmarksOverlayRenderer(),
        sink=PreviewSink(),
        config=config,
        analyzers=analyzers,
        filters=FilterPipeline([]),
    )
    print("MVP_03 Landmarks — cámara → percepción (face, hands, pose) → overlay → preview. Ctrl+C salir.")
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
