import unittest

from ascii_stream_engine.tests import has_module
from ascii_stream_engine.filters.base import BaseFilter
from ascii_stream_engine.filters.invert import InvertFilter


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

        from ascii_stream_engine.filters.detail import DetailBoostFilter

        filt = DetailBoostFilter()
        frame = np.zeros((10, 10), dtype=np.uint8)
        result = filt.apply(frame, DummyConfig())
        self.assertEqual(result.shape, frame.shape)

    def test_brightness_filter(self) -> None:
        import numpy as np

        from ascii_stream_engine.filters.brightness import BrightnessFilter

        class Cfg:
            contrast = 2.0
            brightness = 10

        filt = BrightnessFilter()
        frame = np.zeros((2, 2), dtype=np.uint8)
        result = filt.apply(frame, Cfg())
        self.assertEqual(result.shape, frame.shape)

    def test_edge_filter(self) -> None:
        import numpy as np

        from ascii_stream_engine.filters.edges import EdgeFilter

        filt = EdgeFilter()
        frame = np.zeros((10, 10), dtype=np.uint8)
        result = filt.apply(frame, DummyConfig())
        self.assertEqual(result.shape, frame.shape)


if __name__ == "__main__":
    unittest.main()
