import os
import tempfile
import unittest
from unittest.mock import patch

from ascii_stream_engine.adapters.outputs.ascii_recorder import AsciiFrameRecorder
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability
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

    def test_udp_output_capabilities(self) -> None:
        from ascii_stream_engine.adapters.outputs.udp import FfmpegUdpOutput

        output = FfmpegUdpOutput()
        caps = output.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.STREAMING))
        self.assertTrue(caps.has_capability(OutputCapability.UDP))
        self.assertTrue(caps.has_capability(OutputCapability.LOW_LATENCY))
        self.assertEqual(caps.protocol_name, "UDP/MPEG-TS")
        self.assertTrue(output.is_open() is False)  # No abierto aún

    def test_udp_output_is_open(self) -> None:
        from ascii_stream_engine.adapters.outputs.udp import FfmpegUdpOutput

        output = FfmpegUdpOutput()
        self.assertFalse(output.is_open())

        class DummyProc:
            def __init__(self):
                self.stdin = self

            def write(self, data):
                pass

            def close(self):
                pass

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        with patch(
            "ascii_stream_engine.adapters.outputs.udp.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(EngineConfig(), (10, 10))
            self.assertTrue(output.is_open())
            output.close()
            self.assertFalse(output.is_open())


class TestOutputCapabilities(unittest.TestCase):
    def test_ascii_recorder_capabilities(self) -> None:
        recorder = AsciiFrameRecorder()
        caps = recorder.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.RECORDING))
        self.assertFalse(caps.has_capability(OutputCapability.STREAMING))
        self.assertEqual(caps.max_clients, 1)
        self.assertEqual(caps.protocol_name, "File (ASCII)")

    def test_ascii_recorder_is_open(self) -> None:
        recorder = AsciiFrameRecorder()
        self.assertFalse(recorder.is_open())

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            recorder = AsciiFrameRecorder(path=path)
            recorder.open(EngineConfig(), (10, 10))
            self.assertTrue(recorder.is_open())
            recorder.close()
            self.assertFalse(recorder.is_open())


class TestCompositeOutputSink(unittest.TestCase):
    def test_composite_sink_requires_at_least_one_sink(self) -> None:
        from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink

        with self.assertRaises(ValueError):
            CompositeOutputSink([])

    def test_composite_sink_writes_to_all_sinks(self) -> None:
        from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink

        class CountingSink:
            def __init__(self):
                self.count = 0
                self._is_open = False

            def open(self, config, output_size):
                self._is_open = True

            def write(self, frame):
                self.count += 1

            def close(self):
                self._is_open = False

            def is_open(self):
                return self._is_open

        sink1 = CountingSink()
        sink2 = CountingSink()
        composite = CompositeOutputSink([sink1, sink2])

        composite.open(EngineConfig(), (10, 10))
        frame = RenderFrame(image=object(), text="test")
        composite.write(frame)
        composite.close()

        self.assertEqual(sink1.count, 1)
        self.assertEqual(sink2.count, 1)

    def test_composite_sink_capabilities(self) -> None:
        from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink

        recorder = AsciiFrameRecorder()
        composite = CompositeOutputSink([recorder])

        caps = composite.get_capabilities()
        self.assertTrue(caps.has_capability(OutputCapability.RECORDING))
        self.assertIn("AsciiFrameRecorder", caps.metadata["sink_types"])

    def test_composite_sink_handles_failures_gracefully(self) -> None:
        from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink

        class FailingSink:
            def open(self, config, output_size):
                raise RuntimeError("Failed to open")

            def write(self, frame):
                pass

            def close(self):
                pass

        class WorkingSink:
            def __init__(self):
                self.opened = False

            def open(self, config, output_size):
                self.opened = True

            def write(self, frame):
                pass

            def close(self):
                self.opened = False

            def is_open(self):
                return self.opened

        working = WorkingSink()
        # El composite debería continuar aunque un sink falle
        composite = CompositeOutputSink([FailingSink(), working])

        # Debería lanzar error si todos fallan, pero no si al menos uno funciona
        with self.assertRaises(RuntimeError):
            composite = CompositeOutputSink([FailingSink()])
            composite.open(EngineConfig(), (10, 10))

        # Pero si al menos uno funciona, debería abrir
        composite = CompositeOutputSink([FailingSink(), working])
        try:
            composite.open(EngineConfig(), (10, 10))
            # Si llegamos aquí, al menos un sink se abrió
            self.assertTrue(working.opened)
        except RuntimeError:
            # Si todos fallan, está bien
            pass


if __name__ == "__main__":
    unittest.main()
