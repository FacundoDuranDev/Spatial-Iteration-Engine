"""Unit tests for CRTGlitchFilter.

Tests cover: output shape/dtype, None analysis, individual sub-effects,
zero-intensity parameters (should not crash), and C-contiguous output.
"""

import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestCRTGlitchFilter(unittest.TestCase):
    """Tests for CRTGlitchFilter."""

    def setUp(self):
        import numpy as np

        from ascii_stream_engine.adapters.processors.filters.crt_glitch import CRTGlitchFilter
        from ascii_stream_engine.domain.config import EngineConfig

        self.np = np
        self.FilterClass = CRTGlitchFilter
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

    def test_scanlines_only(self):
        """Scanlines sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=True,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=False,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_aberration_only(self):
        """Chromatic aberration sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=True,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=False,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_noise_only(self):
        """Noise sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=True,
            enable_tear=False,
            enable_barrel=False,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_tear_only(self):
        """Screen tear sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=True,
            tear_probability=1.0,  # Force tear to always trigger
            enable_barrel=False,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_barrel_only(self):
        """Barrel distortion sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=True,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_vhs_only(self):
        """VHS tracking sub-effect produces valid output when enabled alone."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=False,
            enable_vhs=True,
            vhs_tracking=1.0,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_all_effects_enabled(self):
        """All sub-effects enabled simultaneously produces valid output."""
        f = self.FilterClass(
            enable_scanlines=True,
            enable_aberration=True,
            enable_noise=True,
            enable_tear=True,
            tear_probability=1.0,
            enable_barrel=True,
            enable_vhs=True,
            vhs_tracking=1.0,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.assertEqual(result.dtype, self.np.uint8)

    def test_zero_intensity_scanlines(self):
        """Zero scanline intensity should not crash."""
        f = self.FilterClass(
            scanline_intensity=0.0,
            enable_scanlines=True,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)

    def test_zero_aberration_strength(self):
        """Zero aberration strength should not crash."""
        f = self.FilterClass(
            aberration_strength=0.0,
            enable_scanlines=False,
            enable_aberration=True,
            enable_noise=False,
            enable_tear=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)

    def test_zero_noise_amount(self):
        """Zero noise amount should not crash."""
        f = self.FilterClass(
            noise_amount=0.0,
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=True,
            enable_tear=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)

    def test_zero_tear_probability(self):
        """Zero tear probability should not crash (tear never triggers)."""
        f = self.FilterClass(
            tear_probability=0.0,
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=True,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)

    def test_zero_barrel_strength(self):
        """Zero barrel strength should not crash."""
        f = self.FilterClass(
            barrel_strength=0.0,
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=True,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)

    def test_all_disabled(self):
        """All sub-effects disabled returns valid frame copy."""
        f = self.FilterClass(
            enable_scanlines=False,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
            enable_barrel=False,
            enable_vhs=False,
        )
        result = f.apply(self.frame, self.config)
        self.assertEqual(result.shape, self.frame.shape)
        self.np.testing.assert_array_equal(result, self.frame)

    def test_resolution_change(self):
        """Resolution change rebuilds scanline mask correctly."""
        f = self.FilterClass(
            enable_scanlines=True,
            enable_aberration=False,
            enable_noise=False,
            enable_tear=False,
        )
        small = self.np.random.randint(0, 256, (100, 100, 3), dtype=self.np.uint8)
        f.apply(small, self.config)
        large = self.np.random.randint(0, 256, (200, 300, 3), dtype=self.np.uint8)
        result = f.apply(large, self.config)
        self.assertEqual(result.shape, (200, 300, 3))

    def test_disabled_flag(self):
        """Disabled filter flag is set."""
        f = self.FilterClass(enabled=False)
        self.assertFalse(f.enabled)


if __name__ == "__main__":
    unittest.main()
