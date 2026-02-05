import unittest
from unittest.mock import patch

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(has_module("cv2"), "requires cv2")
class TestOpenCVCameraSource(unittest.TestCase):
    def test_camera_source_open_read_close(self) -> None:
        from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource

        class DummyCap:
            def __init__(self):
                self.opened = True

            def set(self, prop, value):
                return True

            def isOpened(self):
                return self.opened

            def read(self):
                return True, "frame"

            def release(self):
                self.opened = False

        with patch(
            "ascii_stream_engine.adapters.sources.camera.cv2.VideoCapture",
            return_value=DummyCap(),
        ):
            source = OpenCVCameraSource(camera_index=0, buffer_size=1)
            source.open()
            frame = source.read()
            self.assertEqual(frame, "frame")
            source.close()


if __name__ == "__main__":
    unittest.main()
