import unittest
from unittest.mock import patch

from ascii_stream_engine.tests import has_module
from ascii_stream_engine.adapters.processors import BaseAnalyzer


class TestAnalyzers(unittest.TestCase):
    def test_base_analyzer_requires_analyze(self) -> None:
        base = BaseAnalyzer()
        with self.assertRaises(NotImplementedError):
            base.analyze(None, None)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2 and numpy",
)
class TestFaceAnalyzer(unittest.TestCase):
    def test_face_analyzer_detects(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.processors import FaceHaarAnalyzer

        class DummyCascade:
            def __init__(self, path):
                self.path = path

            def empty(self):
                return False

            def detectMultiScale(self, gray, scaleFactor, minNeighbors, minSize):
                return [(1, 2, 3, 4)]

        with patch(
            "ascii_stream_engine.adapters.processors.analyzers.face.cv2.CascadeClassifier",
            new=DummyCascade,
        ):
            analyzer = FaceHaarAnalyzer(cascade_path="dummy.xml")
            frame = np.zeros((10, 10), dtype=np.uint8)
            result = analyzer.analyze(frame, None)
            self.assertEqual(result, [{"x": 1, "y": 2, "w": 3, "h": 4}])


if __name__ == "__main__":
    unittest.main()
