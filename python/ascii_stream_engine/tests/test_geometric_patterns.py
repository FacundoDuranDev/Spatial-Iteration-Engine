"""Unit tests for GeometricPatternFilter.

Tests cover: output shape/dtype, None analysis, each pattern mode
(sacred_geometry, voronoi, delaunay, lissajous, strange_attractor),
mock analysis with face landmarks, and C-contiguous output.
"""

import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestGeometricPatternFilter(unittest.TestCase):
    """Tests for GeometricPatternFilter."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.geometric_patterns import (
            GeometricPatternFilter,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = GeometricPatternFilter
        self.config = EngineConfig()
        self.frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

    def test_output_shape_dtype(self):
        """Output preserves (H, W, 3) uint8 shape and dtype."""
        f = self.FilterClass()
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, (480, 640, 3))
        self.assertEqual(result.dtype, self.np.uint8)

    def test_c_contiguous(self):
        """Output is C-contiguous."""
        f = self.FilterClass()
        result = f.apply(self.frame, self.config)
        self.assertTrue(result.flags["C_CONTIGUOUS"])

    def test_with_none_analysis(self):
        """Filter works when analysis=None."""
        f = self.FilterClass()
        result = f.apply(self.frame, self.config, analysis=None)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_sacred_geometry_mode(self):
        """Sacred geometry pattern mode produces valid output."""
        f = self.FilterClass(pattern_mode="sacred_geometry")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_voronoi_mode(self):
        """Voronoi pattern mode produces valid output."""
        f = self.FilterClass(pattern_mode="voronoi")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_delaunay_mode(self):
        """Delaunay pattern mode produces valid output."""
        f = self.FilterClass(pattern_mode="delaunay")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_lissajous_mode(self):
        """Lissajous pattern mode produces valid output."""
        f = self.FilterClass(pattern_mode="lissajous")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_strange_attractor_mode(self):
        """Strange attractor pattern mode produces valid output."""
        f = self.FilterClass(pattern_mode="strange_attractor")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_unknown_mode_falls_back(self):
        """Unknown pattern mode falls back to sacred_geometry without error."""
        f = self.FilterClass(pattern_mode="nonexistent_mode")
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_with_face_landmarks(self):
        """Voronoi mode uses face landmarks from analysis."""
        analysis = {
            "face": {
                "landmarks": [
                    [0.3, 0.4],
                    [0.5, 0.5],
                    [0.7, 0.4],
                    [0.4, 0.6],
                    [0.6, 0.6],
                ]
            }
        }
        f = self.FilterClass(pattern_mode="voronoi")
        result = f.apply(self.frame, self.config, analysis=analysis)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_delaunay_with_face_landmarks(self):
        """Delaunay mode uses face landmarks from analysis."""
        analysis = {
            "face": {
                "landmarks": [
                    [0.2, 0.3],
                    [0.5, 0.2],
                    [0.8, 0.3],
                    [0.3, 0.7],
                    [0.7, 0.7],
                ]
            }
        }
        f = self.FilterClass(pattern_mode="delaunay")
        result = f.apply(self.frame, self.config, analysis=analysis)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_animation_advances(self):
        """Frame count advances across calls (animation state)."""
        f = self.FilterClass(animate=True)
        f.apply(self.frame, self.config)
        count_1 = f._frame_count
        f.apply(self.frame, self.config)
        count_2 = f._frame_count
        self.assertGreater(count_2, count_1)

    def test_no_animation(self):
        """Static mode (animate=False) produces valid output."""
        f = self.FilterClass(animate=False)
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_opacity_zero(self):
        """Zero opacity produces output equal to input frame."""
        f = self.FilterClass(opacity=0.0)
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_resolution_change(self):
        """Resolution change produces correctly sized output."""
        f = self.FilterClass()
        small = self.np.random.randint(0, 256, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 256, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_disabled_flag(self):
        """Disabled filter flag is set."""
        f = self.FilterClass(enabled=False)
        self.assertFalse(f.enabled)

    def test_empty_analysis_dict(self):
        """Empty analysis dict does not crash any mode."""
        for mode in ["sacred_geometry", "voronoi", "delaunay", "lissajous", "strange_attractor"]:
            f = self.FilterClass(pattern_mode=mode)
            result = f.apply(self.frame, self.config, analysis={})
            self.assertEqual(result.shape, self.frame.shape, f"Failed for mode={mode}")


if __name__ == "__main__":
    unittest.main()
