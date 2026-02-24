import unittest

from ascii_stream_engine.adapters.processors import BaseFilter, InvertFilter
from ascii_stream_engine.tests import has_module


class DummyConfig:
    invert = True
    contrast = 1.0
    brightness = 0


class TestFilters(unittest.TestCase):
    def test_base_filter_requires_apply(self) -> None:
        base = BaseFilter()
        with self.assertRaises(NotImplementedError):
            base.apply(1, DummyConfig())

    def test_invert_filter(self) -> None:
        config = DummyConfig()
        filt = InvertFilter()
        self.assertEqual(filt.apply(10, config), 245)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestCv2Filters(unittest.TestCase):
    def test_detail_boost_filter(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import DetailBoostFilter

        filt = DetailBoostFilter()
        frame = np.zeros((10, 10), dtype=np.uint8)
        result = filt.apply(frame, DummyConfig())
        self.assertEqual(result.shape, frame.shape)

    def test_brightness_filter(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import BrightnessFilter

        class Cfg:
            contrast = 2.0
            brightness = 10

        filt = BrightnessFilter()
        frame = np.zeros((2, 2), dtype=np.uint8)
        result = filt.apply(frame, Cfg())
        self.assertEqual(result.shape, frame.shape)

    def test_edge_filter(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import EdgeFilter

        filt = EdgeFilter()
        frame = np.zeros((10, 10), dtype=np.uint8)
        result = filt.apply(frame, DummyConfig())
        self.assertEqual(result.shape, frame.shape)


@unittest.skipUnless(
    has_module("numpy"),
    "requires numpy",
)
class TestCppInvertFilter(unittest.TestCase):
    """MVP_02: prove C++ filter integration. With filters_cpp built, apply_invert runs in C++."""

    def test_cpp_invert_filter_returns_frame_shape(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import CppInvertFilter
        from ascii_stream_engine.domain.config import EngineConfig

        filt = CppInvertFilter()
        frame = np.zeros((4, 6, 3), dtype=np.uint8)
        frame[:] = 100
        config = EngineConfig()
        out = filt.apply(frame, config, None)
        self.assertEqual(out.shape, frame.shape)
        self.assertEqual(out.dtype, np.uint8)

    def test_cpp_invert_filter_inverts_when_cpp_available(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import CppInvertFilter
        from ascii_stream_engine.domain.config import EngineConfig

        filt = CppInvertFilter()
        if not filt.cpp_available:
            self.skipTest("filters_cpp not built (run ./cpp/build.sh)")
        frame = np.array([[[50, 100, 200]]], dtype=np.uint8).copy(order="C")
        config = EngineConfig()
        out = filt.apply(frame, config, None)
        self.assertEqual(out[0, 0, 0], 255 - 50)
        self.assertEqual(out[0, 0, 1], 255 - 100)
        self.assertEqual(out[0, 0, 2], 255 - 200)


if __name__ == "__main__":
    unittest.main()
