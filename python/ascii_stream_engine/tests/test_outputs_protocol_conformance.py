"""Cross-sink protocol conformance tests.

Verifies that all output sinks correctly implement the OutputSink protocol:
- is_open() returns False before open()
- get_capabilities() returns a valid OutputCapabilities instance
- supports_multiple_clients() returns a bool
- close() can be called twice without raising
- write() on a closed sink does not raise
"""

import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapabilities
from ascii_stream_engine.tests import has_module
from ascii_stream_engine.tests.helpers import DummyProc


class SinkTestMixin:
    """Mixin with shared protocol conformance tests."""

    def get_sink(self):
        """Return an initialized sink instance. Override in subclasses."""
        raise NotImplementedError

    def get_patch_target(self):
        """Return the patch target for subprocess mocking, or None."""
        return None

    def test_is_open_before_open(self) -> None:
        """is_open() returns False before open()."""
        sink = self.get_sink()
        self.assertFalse(sink.is_open())

    def test_capabilities_returns_valid_instance(self) -> None:
        """get_capabilities() returns an OutputCapabilities."""
        sink = self.get_sink()
        caps = sink.get_capabilities()
        self.assertIsInstance(caps, OutputCapabilities)
        self.assertIsNotNone(caps.protocol_name)

    def test_supports_multiple_clients_is_bool(self) -> None:
        """supports_multiple_clients() returns a bool."""
        sink = self.get_sink()
        result = sink.supports_multiple_clients()
        self.assertIsInstance(result, bool)

    def test_close_idempotent(self) -> None:
        """close() can be called twice without raising."""
        sink = self.get_sink()
        sink.close()
        sink.close()

    def test_write_when_closed_no_raise(self) -> None:
        """write() on a closed sink does not raise."""
        sink = self.get_sink()
        frame = RenderFrame(image=Image.new("RGB", (10, 10)))
        sink.write(frame)


class TestUdpConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for FfmpegUdpOutput."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.udp import FfmpegUdpOutput

        return FfmpegUdpOutput()


class TestAsciiRecorderConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for AsciiFrameRecorder."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.ascii_recorder import (
            AsciiFrameRecorder,
        )

        return AsciiFrameRecorder()


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestRtspConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for FfmpegRtspSink."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        return FfmpegRtspSink()


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestRecorderConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for VideoRecorderSink."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.recorder import VideoRecorderSink

        return VideoRecorderSink()


@unittest.skipUnless(has_module("pythonosc"), "requires python-osc")
class TestOscConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for OscOutputSink."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.osc import OscOutputSink

        return OscOutputSink()


@unittest.skipUnless(has_module("aiortc"), "requires aiortc")
@unittest.skipUnless(has_module("aiohttp"), "requires aiohttp")
class TestWebRTCConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for WebRTCOutput."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        return WebRTCOutput(enable_signaling=False)


class TestCompositeConformance(SinkTestMixin, unittest.TestCase):
    """Protocol conformance for CompositeOutputSink."""

    def get_sink(self):
        from ascii_stream_engine.adapters.outputs.ascii_recorder import (
            AsciiFrameRecorder,
        )
        from ascii_stream_engine.adapters.outputs.composite import CompositeOutputSink

        return CompositeOutputSink([AsciiFrameRecorder()])


if __name__ == "__main__":
    unittest.main()
