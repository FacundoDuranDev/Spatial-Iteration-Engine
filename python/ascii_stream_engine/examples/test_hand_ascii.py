#!/usr/bin/env python3
"""Quick test: HandFrameFilter with ASCII effect.

Shows a live camera feed where the region between both hands
is converted to ASCII art in real-time.

Usage (from repo root):
    PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/test_hand_ascii.py
    PYTHONPATH=python:cpp/build python python/ascii_stream_engine/examples/test_hand_ascii.py --camera 0

Keys:
    1-6  Switch effect (ascii, invert, blur, pixelate, edge, tint)
    +/-  Change ASCII font size
    q    Quit
"""

import argparse
import time

import cv2
import numpy as np

from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
from ascii_stream_engine.adapters.processors.filters.hand_frame import HandFrameFilter
from ascii_stream_engine.domain.config import EngineConfig


def main():
    parser = argparse.ArgumentParser(description="Test HandFrameFilter ASCII effect")
    parser.add_argument("--camera", type=int, default=2, help="Camera index")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Cannot open camera {args.camera}")
        return

    analyzer = HandLandmarkAnalyzer()
    hf = HandFrameFilter(
        effect="ascii",
        ascii_color=(0, 255, 0),
        ascii_bg=(0, 0, 0),
        ascii_font_size=10,
        border_color=(0, 255, 0),
        border_thickness=2,
        smoothing=0.4,
        hold_frames=15,
    )
    config = EngineConfig()

    effects = ["ascii", "invert", "blur", "pixelate", "edge", "tint"]
    current_effect = "ascii"

    print("HandFrameFilter ASCII Test")
    print("Show both hands to the camera to see the effect.")
    print("Keys: 1-6 switch effect, +/- font size, q quit")

    fps_t = time.monotonic()
    fps_count = 0
    fps_display = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Analyze hands
        analysis = {"hands": analyzer.analyze(frame, config)}

        # Apply filter
        result = hf.apply(frame, config, analysis=analysis)

        # FPS counter
        fps_count += 1
        now = time.monotonic()
        if now - fps_t >= 1.0:
            fps_display = fps_count / (now - fps_t)
            fps_count = 0
            fps_t = now

        # HUD
        cv2.putText(
            result, f"Effect: {current_effect} | FPS: {fps_display:.1f}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
        )

        hands = analysis.get("hands", {})
        has_left = hands.get("left") is not None and len(hands.get("left", [])) > 0
        has_right = hands.get("right") is not None and len(hands.get("right", [])) > 0
        status = "BOTH" if (has_left and has_right) else "partial" if (has_left or has_right) else "none"
        cv2.putText(
            result, f"Hands: {status}",
            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 1,
        )

        cv2.imshow("HandFrame ASCII Test", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif ord("1") <= key <= ord("6"):
            idx = key - ord("1")
            if idx < len(effects):
                current_effect = effects[idx]
                hf.effect = current_effect
                print(f"Effect: {current_effect}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
