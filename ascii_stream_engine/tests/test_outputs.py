import os
import tempfile
import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.adapters.outputs.ascii_recorder import AsciiFrameRecorder
from ascii_stream_engine.tests import has_module


class TestAsciiFrameRecorder(unittest.TestCase):
    def test_recorder_writes_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "frames.txt")
            recorder = AsciiFrameRecorder(path=path, flush_every=1)
            recorder.open(EngineConfig(), (10, 10))
            recorder.write(RenderFrame(image=object(), text="abc"))
            recorder.close()

            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("frame=1", content)
            self.assertIn("abc", content)


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestFfmpegUdpOutput(unittest.TestCase):
    def test_udp_output_spawns_ffmpeg(self) -> None:
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.udp import FfmpegUdpOutput

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.data = b""

            def write(self, data):
                self.data += data

            def close(self):
                pass

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig(host="127.0.0.1", port=9999)
        output = FfmpegUdpOutput()
        image = Image.new("RGB", (10, 10))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.udp.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (10, 10))
            output.write(frame)
            output.close()

        args = popen.call_args[0][0]
        self.assertIn("udp://127.0.0.1:9999", args[-1])


if __name__ == "__main__":
    unittest.main()
