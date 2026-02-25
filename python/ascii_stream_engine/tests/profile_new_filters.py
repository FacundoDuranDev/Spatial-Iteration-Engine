"""Profile new filters individually and combined.

Usage: PYTHONPATH=python:cpp/build python python/ascii_stream_engine/tests/profile_new_filters.py
"""

import time

import cv2
import numpy as np

from ascii_stream_engine.adapters.processors.filters.boids import BoidsFilter
from ascii_stream_engine.adapters.processors.filters.edge_smooth import EdgeSmoothFilter
from ascii_stream_engine.adapters.processors.filters.optical_flow_particles import (
    OpticalFlowParticlesFilter,
)
from ascii_stream_engine.adapters.processors.filters.physarum import PhysarumFilter
from ascii_stream_engine.adapters.processors.filters.radial_collapse import RadialCollapseFilter
from ascii_stream_engine.adapters.processors.filters.stippling import StipplingFilter
from ascii_stream_engine.adapters.processors.filters.uv_displacement import UVDisplacementFilter
from ascii_stream_engine.domain.config import EngineConfig


def profile_filter(name, filter_obj, config, frames, warmup=5, iterations=20):
    """Profile a single filter."""
    # Warm up
    for i in range(min(warmup, len(frames))):
        filter_obj.apply(frames[i % len(frames)], config)

    # Measure
    times = []
    for i in range(iterations):
        frame = frames[i % len(frames)]
        t0 = time.perf_counter()
        filter_obj.apply(frame, config)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    median = sorted(times)[len(times) // 2]
    p95 = sorted(times)[int(len(times) * 0.95)]
    mean = sum(times) / len(times)
    return {"name": name, "median": median, "p95": p95, "mean": mean}


def main():
    config = EngineConfig()
    h, w = 480, 640

    # Generate test frames (multiple for optical flow)
    frames = [np.random.randint(0, 255, (h, w, 3), dtype=np.uint8) for _ in range(10)]

    filters = [
        ("OpticalFlowParticles", OpticalFlowParticlesFilter(max_particles=500)),
        ("Stippling", StipplingFilter(density=0.3)),
        ("UVDisplacement", UVDisplacementFilter(amplitude=10.0, frequency=2.0)),
        ("EdgeSmooth", EdgeSmoothFilter()),
        ("RadialCollapse", RadialCollapseFilter(strength=0.5)),
        ("Physarum", PhysarumFilter(num_agents=2000, sim_scale=4)),
        ("Boids", BoidsFilter(num_boids=200)),
    ]

    print(f"\nProfiling filters at {w}x{h} resolution")
    print(f"{'Filter':<25} {'Median (ms)':>12} {'P95 (ms)':>10} {'Mean (ms)':>10}")
    print("-" * 60)

    results = []
    for name, f in filters:
        result = profile_filter(name, f, config, frames)
        results.append(result)
        print(
            f"{result['name']:<25} {result['median']:>12.2f} {result['p95']:>10.2f} {result['mean']:>10.2f}"
        )

    # Combined chain
    print("-" * 60)
    all_filters = [f for _, f in filters]
    # Reset stateful filters
    for f in all_filters:
        if hasattr(f, "reset"):
            f.reset()

    times = []
    for i in range(30):
        frame = frames[i % len(frames)]
        t0 = time.perf_counter()
        result = frame
        for f in all_filters:
            result = f.apply(result, config)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    # Skip first 5 warmup
    times = times[5:]
    median = sorted(times)[len(times) // 2]
    p95 = sorted(times)[int(len(times) * 0.95)]
    mean = sum(times) / len(times)
    print(f"{'COMBINED CHAIN':<25} {median:>12.2f} {p95:>10.2f} {mean:>10.2f}")
    print(f"\nBudget target: 5ms combined (all active)")
    print(f"Python-only realistic: <50ms combined with moderate params")


if __name__ == "__main__":
    main()
