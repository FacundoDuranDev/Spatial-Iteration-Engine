#!/usr/bin/env python3
"""Test: ASCII effect via composable graph nodes with temporal smoothing.

Graph topology:
  Camera → HandAnalyzer → SpatialMap → SpatialSmoothing ─┬─ video_out ──→ Composite(A)
                                                          ├─ mask_out  ──→ Composite(mask)
                                                          │
                          SpatialMap.roi_video ──→ AsciiProc ──→ Composite(B)

The SpatialSmoothingNode provides:
  - EMA smoothing on the mask/control (eliminates jitter)
  - Hold for N frames after hands are lost (graceful falloff)
  - Optional fade-out during hold period

Usage (from repo root):
    PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/test_ascii_graph.py
    PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/test_ascii_graph.py --camera 0

Keys:
    q    Quit
"""

import argparse
import time

import cv2

from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
from ascii_stream_engine.adapters.spatial.hand_frame_source import HandFrameSpatialSource
from ascii_stream_engine.application.graph.core.graph import Graph
from ascii_stream_engine.application.graph.nodes.analyzer_node import AnalyzerNode
from ascii_stream_engine.application.graph.nodes.ascii_processor_node import AsciiProcessorNode
from ascii_stream_engine.application.graph.nodes.composite_node import CompositeNode
from ascii_stream_engine.application.graph.nodes.source_node import SourceNode
from ascii_stream_engine.application.graph.nodes.spatial_map_node import SpatialMapNode
from ascii_stream_engine.application.graph.nodes.spatial_smoothing_node import SpatialSmoothingNode
from ascii_stream_engine.application.graph.scheduler.graph_scheduler import GraphScheduler
from ascii_stream_engine.domain.config import EngineConfig


class CameraSourceNode(SourceNode):
    """Source node wrapping an OpenCV VideoCapture."""

    name = "camera"

    def __init__(self, cap):
        super().__init__()
        self._cap = cap

    def read_frame(self):
        ret, frame = self._cap.read()
        return frame if ret else None


class HandAnalyzerNode(AnalyzerNode):
    """Analyzer node wrapping HandLandmarkAnalyzer."""

    name = "hands"

    def __init__(self):
        super().__init__()
        self._analyzer = HandLandmarkAnalyzer()

    def analyze(self, frame):
        return self._analyzer.analyze(frame, self.config)


def build_graph(cap):
    """Build the composable ASCII hand-frame graph with smoothing.

    Topology:
        camera → analyzer → spatial_map → smoothing ─┬─ video_out → composite(A)
                                                      └─ mask_out  → composite(mask)
                             spatial_map.roi_video → ascii_proc → composite(B)
    """
    g = Graph()

    source = CameraSourceNode(cap)
    analyzer = HandAnalyzerNode()
    spatial = SpatialMapNode(
        source=HandFrameSpatialSource(padding=0.02),
        produce_crop=True,
        resize_crop=False,
    )
    spatial.name = "spatial_map"
    smoothing = SpatialSmoothingNode(
        smoothing=0.4,
        hold_frames=15,
        fade_out=True,
    )
    ascii_proc = AsciiProcessorNode(
        charset=" .:-=+*#%@",
        font_size=6,
        fg_color=(255, 255, 255),
        bg_color=(0, 0, 0),
    )
    composite = CompositeNode(mode="mask")

    for node in [source, analyzer, spatial, smoothing, ascii_proc, composite]:
        g.add_node(node)

    # source → analyzer
    g.connect(source, "video_out", analyzer, "video_in")

    # analyzer → spatial_map
    g.connect(analyzer, "video_out", spatial, "video_in")
    g.connect(analyzer, "analysis_out", spatial, "analysis_in")

    # spatial_map → smoothing (mask + control + video passthrough)
    g.connect(spatial, "mask_out", smoothing, "mask_in")
    g.connect(spatial, "control_out", smoothing, "control_in")
    g.connect(spatial, "video_out", smoothing, "video_in")

    # smoothing → composite A (original frame, smoothed)
    g.connect(smoothing, "video_out", composite, "video_in_a")

    # spatial ROI → ascii_proc → composite B
    g.connect(spatial, "roi_video_out", ascii_proc, "video_in")
    g.connect(ascii_proc, "video_out", composite, "video_in_b")

    # smoothing mask → composite
    g.connect(smoothing, "mask_out", composite, "mask_in")

    errors = g.validate()
    if errors:
        for e in errors:
            print(f"Graph error: {e}")
        raise RuntimeError("Graph validation failed")

    return g


def main():
    parser = argparse.ArgumentParser(description="Test ASCII graph composition")
    parser.add_argument("--camera", type=int, default=2, help="Camera index")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Cannot open camera {args.camera}")
        return

    config = EngineConfig()
    graph = build_graph(cap)

    scheduler = GraphScheduler(graph=graph, config=config)
    scheduler.setup()

    print("ASCII Graph Composition Test (with smoothing)")
    print("Show both hands to the camera to see ASCII between them.")
    print("Press q to quit")

    fps_t = time.monotonic()
    fps_count = 0
    fps_display = 0.0

    while True:
        success, err = scheduler.process_frame()
        if not success:
            continue

        # Use public API to get composite output
        result = scheduler.get_node_output("composite", "video_out")
        if result is None:
            continue

        # Make writable if fan-out safety set read-only
        if not result.flags.writeable:
            result = result.copy()

        # FPS counter
        fps_count += 1
        now = time.monotonic()
        if now - fps_t >= 1.0:
            fps_display = fps_count / (now - fps_t)
            fps_count = 0
            fps_t = now

        # HUD
        cv2.putText(
            result,
            f"Graph ASCII + Smoothing | FPS: {fps_display:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        # Per-node timings
        timings = scheduler.get_node_timings()
        y = 60
        for name, secs in timings.items():
            cv2.putText(
                result,
                f"{name}: {secs * 1000:.1f}ms",
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (200, 200, 200),
                1,
            )
            y += 20

        cv2.imshow("ASCII Graph Composition", result)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    scheduler.teardown()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
