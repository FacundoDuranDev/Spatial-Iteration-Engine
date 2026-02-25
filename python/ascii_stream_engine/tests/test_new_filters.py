"""Unit tests for 7 new image filters.

Tests cover: no-op paths, output shape/dtype, C-contiguous output,
stateful filter reset/resolution change, LUT cache hit/invalidation,
analysis dict interaction, and edge cases.
"""

import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestOpticalFlowParticlesFilter(unittest.TestCase):
    """Tests for OpticalFlowParticlesFilter (stateful)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.optical_flow_particles import (
            OpticalFlowParticlesFilter,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = OpticalFlowParticlesFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when max_particles=0 returns same frame reference."""
        f = self.FilterClass(max_particles=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_first_frame_returns_same_ref(self):
        """First frame (no previous gray) returns same reference."""
        f = self.FilterClass(max_particles=100)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(max_particles=500, spawn_threshold=0.5)
        frame1 = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        f.apply(frame1, self.config)
        frame2 = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame2, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(max_particles=500, spawn_threshold=0.5)
        frame1 = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        f.apply(frame1, self.config)
        frame2 = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame2, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_reset_clears_state(self):
        """reset() clears internal state completely."""
        f = self.FilterClass(max_particles=100)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertIsNotNone(f._prev_gray)
        f.reset()
        self.assertIsNone(f._prev_gray)
        self.assertIsNone(f._particles)

    def test_resolution_change(self):
        """Resolution change mid-stream reinitializes buffers."""
        f = self.FilterClass(max_particles=100)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_no_analysis(self):
        """Filter works when analysis=None."""
        f = self.FilterClass(max_particles=100)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config, analysis=None)
        self.assertEqual(result.shape, frame.shape)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestStipplingFilter(unittest.TestCase):
    """Tests for StipplingFilter (LUT-cached)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.stippling import StipplingFilter
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = StipplingFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when density=0 returns same frame reference."""
        f = self.FilterClass(density=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(density=0.5)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(density=0.5)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_lut_cache_hit(self):
        """Same params reuse cached grid (no rebuild)."""
        f = self.FilterClass(density=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertFalse(f._params_dirty)
        grid_id = id(f._sampling_grid)
        f.apply(frame, self.config)
        self.assertEqual(id(f._sampling_grid), grid_id)

    def test_param_change_invalidates_cache(self):
        """Changing density sets _params_dirty and rebuilds grid."""
        f = self.FilterClass(density=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        f.density = 0.8
        self.assertTrue(f._params_dirty)
        f.apply(frame, self.config)
        self.assertFalse(f._params_dirty)

    def test_resolution_change_rebuilds(self):
        """Resolution change forces grid rebuild."""
        f = self.FilterClass(density=0.5)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_tiny_frame(self):
        """Filter handles tiny frames gracefully."""
        f = self.FilterClass(density=0.5)
        frame = self.np.random.randint(0, 255, (4, 4, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (4, 4, 3))


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestUVDisplacementFilter(unittest.TestCase):
    """Tests for UVDisplacementFilter (LUT-cached)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.uv_displacement import (
            UVDisplacementFilter,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = UVDisplacementFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when amplitude=0 returns same frame reference."""
        f = self.FilterClass(amplitude=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(amplitude=10.0, frequency=2.0)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(amplitude=10.0, frequency=2.0)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_lut_cache_hit(self):
        """Same params reuse cached maps (no rebuild)."""
        f = self.FilterClass(amplitude=10.0, frequency=2.0)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertFalse(f._params_dirty)
        base_map_id = id(f._base_map_x)
        f.apply(frame, self.config)
        self.assertEqual(id(f._base_map_x), base_map_id)

    def test_param_change_invalidates(self):
        """Changing amplitude sets _params_dirty."""
        f = self.FilterClass(amplitude=10.0, frequency=2.0)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        f.amplitude = 20.0
        self.assertTrue(f._params_dirty)
        f.apply(frame, self.config)
        self.assertFalse(f._params_dirty)

    def test_phase_advances(self):
        """Phase advances each frame (animation)."""
        f = self.FilterClass(amplitude=10.0, phase_speed=0.1)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        phase_after_1 = f._phase
        f.apply(frame, self.config)
        phase_after_2 = f._phase
        self.assertGreater(phase_after_2, phase_after_1)

    def test_function_types(self):
        """All function types produce valid output."""
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        for func in ("sin", "cos", "spiral", "noise"):
            f = self.FilterClass(amplitude=5.0, function_type=func)
            result = f.apply(frame, self.config)
            self.assertEqual(result.shape, frame.shape, f"Failed for function_type={func}")

    def test_resolution_change_rebuilds(self):
        """Resolution change forces map rebuild."""
        f = self.FilterClass(amplitude=10.0)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestEdgeSmoothFilter(unittest.TestCase):
    """Tests for EdgeSmoothFilter (simple convolution)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.edge_smooth import EdgeSmoothFilter
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = EdgeSmoothFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when strength=0 returns same frame reference."""
        f = self.FilterClass(strength=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass()
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass()
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_blend_strength(self):
        """Partial strength blends with original."""
        f = self.FilterClass(strength=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_large_frame(self):
        """Filter handles large frames."""
        f = self.FilterClass()
        frame = self.np.random.randint(0, 255, (480, 640, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, frame.shape)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestRadialCollapseFilter(unittest.TestCase):
    """Tests for RadialCollapseFilter (LUT-cached)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.radial_collapse import (
            RadialCollapseFilter,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = RadialCollapseFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when strength=0 returns same frame reference."""
        f = self.FilterClass(strength=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(strength=0.5)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(strength=0.5)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_lut_cache_hit(self):
        """Same params reuse cached maps."""
        f = self.FilterClass(strength=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertFalse(f._params_dirty)
        map_id = id(f._map_x)
        f.apply(frame, self.config)
        self.assertEqual(id(f._map_x), map_id)

    def test_param_change_invalidates(self):
        """Changing strength sets _params_dirty."""
        f = self.FilterClass(strength=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        f.strength = 0.8
        self.assertTrue(f._params_dirty)

    def test_follow_face(self):
        """follow_face mode reads analysis['face'] safely."""
        f = self.FilterClass(follow_face=True, strength=0.5)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        analysis = {"face": {"points": self.np.array([[0.5, 0.5]])}}
        result = f.apply(frame, self.config, analysis=analysis)
        self.assertEqual(result.shape, frame.shape)

    def test_collapse_vs_expand(self):
        """Both modes produce valid output."""
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        for mode in ("collapse", "expand"):
            f = self.FilterClass(strength=0.5, mode=mode)
            result = f.apply(frame, self.config)
            self.assertEqual(result.shape, frame.shape, f"Failed for mode={mode}")

    def test_resolution_change_rebuilds(self):
        """Resolution change forces LUT rebuild."""
        f = self.FilterClass(strength=0.5)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestPhysarumFilter(unittest.TestCase):
    """Tests for PhysarumFilter (stateful simulation)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.physarum import PhysarumFilter
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = PhysarumFilter
        self.config = EngineConfig()

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(num_agents=100, sim_scale=4)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(num_agents=100, sim_scale=4)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_reset_clears_state(self):
        """reset() clears internal state completely."""
        f = self.FilterClass(num_agents=100, sim_scale=4)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertIsNotNone(f._trail_map)
        f.reset()
        self.assertIsNone(f._trail_map)
        self.assertIsNone(f._agents_x)

    def test_resolution_change(self):
        """Resolution change mid-stream reinitializes buffers."""
        f = self.FilterClass(num_agents=100, sim_scale=4)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_multiple_frames_evolve(self):
        """Trail map evolves over multiple frames (results differ)."""
        f = self.FilterClass(num_agents=200, sim_scale=4)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        result1 = f.apply(frame, self.config)
        result2 = f.apply(frame, self.config)
        self.assertFalse(self.np.array_equal(result1, result2))

    def test_disabled(self):
        """Disabled filter flag is set."""
        f = self.FilterClass(enabled=False)
        self.assertFalse(f.enabled)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestBoidsFilter(unittest.TestCase):
    """Tests for BoidsFilter (stateful flocking)."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.boids import BoidsFilter
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = BoidsFilter
        self.config = EngineConfig()

    def test_noop_returns_same_ref(self):
        """No-op when num_boids=0 returns same frame reference."""
        f = self.FilterClass(num_boids=0)
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertIs(result, frame)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass(num_boids=50)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertEqual(result.shape, (120, 160, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass(num_boids=50)
        frame = self.np.random.randint(0, 255, (120, 160, 3), dtype=self.np.uint8)
        result = f.apply(frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_reset_clears_state(self):
        """reset() clears internal state completely."""
        f = self.FilterClass(num_boids=50)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(frame, self.config)
        self.assertIsNotNone(f._positions)
        f.reset()
        self.assertIsNone(f._positions)
        self.assertIsNone(f._velocities)

    def test_resolution_change(self):
        """Resolution change mid-stream reinitializes boids."""
        f = self.FilterClass(num_boids=50)
        small = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 255, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_with_analysis(self):
        """Boids respond to analysis dict attraction."""
        f = self.FilterClass(num_boids=50, attract_to_analysis=True)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        analysis = {"hands": {"left": self.np.array([[0.3, 0.4]])}}
        result = f.apply(frame, self.config, analysis=analysis)
        self.assertEqual(result.shape, frame.shape)

    def test_does_not_modify_analysis(self):
        """Filter never writes to analysis dict."""
        f = self.FilterClass(num_boids=50, attract_to_analysis=True)
        frame = self.np.random.randint(0, 255, (100, 100, 3), dtype=self.np.uint8)
        original_pts = self.np.array([[0.3, 0.4]])
        analysis = {"hands": {"left": original_pts.copy()}}
        f.apply(frame, self.config, analysis=analysis)
        self.np.testing.assert_array_equal(analysis["hands"]["left"], original_pts)


if __name__ == "__main__":
    unittest.main()
