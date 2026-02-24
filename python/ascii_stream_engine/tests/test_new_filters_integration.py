"""Integration tests for new image filters.

Tests cover: filter chains, analysis dict interaction, resolution changes,
and combined latency measurements.
"""

import time
import unittest

import pytest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestFilterChains(unittest.TestCase):
    """Integration tests for filter chains."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.boids import BoidsFilter
        from ascii_stream_engine.adapters.processors.filters.edge_smooth import EdgeSmoothFilter
        from ascii_stream_engine.adapters.processors.filters.optical_flow_particles import (
            OpticalFlowParticlesFilter,
        )
        from ascii_stream_engine.adapters.processors.filters.physarum import PhysarumFilter
        from ascii_stream_engine.adapters.processors.filters.radial_collapse import (
            RadialCollapseFilter,
        )
        from ascii_stream_engine.adapters.processors.filters.stippling import StipplingFilter
        from ascii_stream_engine.adapters.processors.filters.uv_displacement import (
            UVDisplacementFilter,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.config = EngineConfig()
        self.OpticalFlowParticlesFilter = OpticalFlowParticlesFilter
        self.StipplingFilter = StipplingFilter
        self.UVDisplacementFilter = UVDisplacementFilter
        self.EdgeSmoothFilter = EdgeSmoothFilter
        self.RadialCollapseFilter = RadialCollapseFilter
        self.PhysarumFilter = PhysarumFilter
        self.BoidsFilter = BoidsFilter

    @pytest.mark.integration
    def test_multiple_new_filters_in_chain(self):
        """Multiple new filters applied sequentially produce valid output."""
        filters = [
            self.EdgeSmoothFilter(strength=0.5),
            self.StipplingFilter(density=0.3),
            self.UVDisplacementFilter(amplitude=5.0),
        ]
        frame = self.np.random.randint(0, 255, (240, 320, 3), dtype=self.np.uint8)
        result = frame
        for f in filters:
            result = f.apply(result, self.config)
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    @pytest.mark.integration
    def test_stateful_filters_in_chain(self):
        """Stateful filters chain correctly over multiple frames."""
        filters = [
            self.OpticalFlowParticlesFilter(max_particles=100),
            self.BoidsFilter(num_boids=50),
        ]
        for _ in range(5):
            frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
            result = frame
            for f in filters:
                result = f.apply(result, self.config)
            self.assertEqual(result.shape, frame.shape)

    @pytest.mark.integration
    def test_filters_with_perception_data(self):
        """Filters correctly use perception analysis dict."""
        analysis = {
            "face": {"points": self.np.random.rand(5, 2).astype(self.np.float32)},
            "hands": {
                "left": self.np.random.rand(21, 2).astype(self.np.float32),
                "right": self.np.random.rand(21, 2).astype(self.np.float32),
            },
            "pose": {"joints": self.np.random.rand(17, 2).astype(self.np.float32)},
        }
        filters = [
            self.RadialCollapseFilter(follow_face=True, strength=0.3),
            self.OpticalFlowParticlesFilter(max_particles=100),
            self.BoidsFilter(num_boids=50, attract_to_analysis=True),
        ]
        frame = self.np.random.randint(0, 255, (240, 320, 3), dtype=self.np.uint8)
        for f in filters:
            frame = f.apply(frame, self.config, analysis=analysis)
        self.assertEqual(frame.shape, (240, 320, 3))

    @pytest.mark.integration
    def test_filters_with_empty_analysis(self):
        """All filters handle empty analysis gracefully."""
        filters = [
            self.RadialCollapseFilter(follow_face=True),
            self.OpticalFlowParticlesFilter(max_particles=100),
            self.BoidsFilter(attract_to_analysis=True, num_boids=50),
        ]
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        for f in filters:
            frame = f.apply(frame, self.config, analysis={})
        self.assertEqual(frame.shape, (120, 160, 3))

    @pytest.mark.integration
    def test_resolution_change_all_filters(self):
        """All filters handle resolution change without crashing."""
        filters = [
            self.OpticalFlowParticlesFilter(max_particles=100),
            self.StipplingFilter(density=0.3),
            self.UVDisplacementFilter(amplitude=5.0),
            self.EdgeSmoothFilter(),
            self.RadialCollapseFilter(strength=0.3),
            self.PhysarumFilter(num_agents=100, sim_scale=4),
            self.BoidsFilter(num_boids=50),
        ]
        # Run at 160x120
        for _ in range(3):
            frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
            for f in filters:
                frame = f.apply(frame, self.config)
        # Switch to 320x240
        for _ in range(3):
            frame = self.np.random.randint(0, 255, (240, 320, 3), dtype=self.np.uint8)
            for f in filters:
                frame = f.apply(frame, self.config)
            self.assertEqual(frame.shape, (240, 320, 3))

    @pytest.mark.integration
    @pytest.mark.slow
    def test_combined_filter_latency(self):
        """All 7 filters combined stay within reasonable bounds."""
        filters = [
            self.OpticalFlowParticlesFilter(max_particles=500),
            self.StipplingFilter(density=0.3),
            self.UVDisplacementFilter(amplitude=5.0),
            self.EdgeSmoothFilter(),
            self.RadialCollapseFilter(strength=0.3),
            self.PhysarumFilter(num_agents=500, sim_scale=4),
            self.BoidsFilter(num_boids=100),
        ]
        frame = self.np.random.randint(0, 255, (480, 640, 3), dtype=self.np.uint8)
        # Warm up
        for _ in range(5):
            result = frame.copy()
            for f in filters:
                result = f.apply(result, self.config)
        # Measure
        times = []
        for _ in range(10):
            frame = self.np.random.randint(0, 255, (480, 640, 3), dtype=self.np.uint8)
            t0 = time.perf_counter()
            result = frame
            for f in filters:
                result = f.apply(result, self.config)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
        median = sorted(times)[len(times) // 2]
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"\nFilter chain: median={median:.1f}ms, p95={p95:.1f}ms")
        # Soft assert: p95 should be under 300ms in Python-only mode at 640x480
        # Production target is 5ms combined with C++ acceleration and reduced params
        self.assertLess(p95, 300, f"Combined filter latency p95={p95:.1f}ms exceeds 300ms")


if __name__ == "__main__":
    unittest.main()
