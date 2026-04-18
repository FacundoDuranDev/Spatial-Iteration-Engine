"""Perception analyzer latency benchmark.

Run: PYTHONPATH=python:cpp/build python python/ascii_stream_engine/tests/bench_perception.py

Measures per-analyzer and combined latency against the 5ms/15ms budget.
"""

import sys
import time

import numpy as np

sys.path.insert(0, "python")

from ascii_stream_engine.domain.config import EngineConfig

config = EngineConfig()


def bench_analyzer(name, cls, frame, iterations=100):
    """Benchmark a single analyzer."""
    analyzer = cls()
    # Warm-up
    for _ in range(3):
        analyzer.analyze(frame, config)

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        analyzer.analyze(frame, config)
        times.append((time.perf_counter() - t0) * 1000)

    times_arr = np.array(times)
    print(
        f"  {name:20s}: mean={np.mean(times_arr):7.2f}ms "
        f"p50={np.median(times_arr):7.2f}ms "
        f"p95={np.percentile(times_arr, 95):7.2f}ms "
        f"p99={np.percentile(times_arr, 99):7.2f}ms"
    )
    return times_arr


def main():
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    print("=" * 70)
    print("Perception Analyzer Latency Benchmark (640x480 BGR uint8)")
    print("=" * 70)

    # Import all analyzers
    from ascii_stream_engine.adapters.perception.hand_gesture import HandGestureAnalyzer
    from ascii_stream_engine.adapters.perception.pose_skeleton import PoseSkeletonAnalyzer

    analyzers = [
        ("hand_gesture", HandGestureAnalyzer),
        ("pose_skeleton", PoseSkeletonAnalyzer),
    ]

    print("\nPer-Analyzer Latency (budget: 5ms each):")
    print("-" * 70)

    all_times = {}
    for name, cls in analyzers:
        times = bench_analyzer(name, cls, frame)
        all_times[name] = times

    # Combined benchmark
    print("\nCombined Latency (budget: 15ms total):")
    print("-" * 70)

    instances = [(name, cls()) for name, cls in analyzers]
    combined_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        for _, analyzer in instances:
            analyzer.analyze(frame, config)
        combined_times.append((time.perf_counter() - t0) * 1000)

    combined_arr = np.array(combined_times)
    print(
        f"  {'COMBINED':20s}: mean={np.mean(combined_arr):7.2f}ms "
        f"p50={np.median(combined_arr):7.2f}ms "
        f"p95={np.percentile(combined_arr, 95):7.2f}ms "
        f"p99={np.percentile(combined_arr, 99):7.2f}ms"
    )

    print("\n" + "=" * 70)
    print("Summary:")
    for name, times in all_times.items():
        mean = np.mean(times)
        status = "OK" if mean < 5.0 else "OVER BUDGET (frame-skip recommended)"
        print(f"  {name:20s}: {mean:7.2f}ms avg -- {status}")

    combined_mean = np.mean(combined_arr)
    combined_status = "OK" if combined_mean < 15.0 else "OVER BUDGET"
    print(f"  {'COMBINED':20s}: {combined_mean:7.2f}ms avg -- {combined_status}")
    print("=" * 70)


if __name__ == "__main__":
    main()
