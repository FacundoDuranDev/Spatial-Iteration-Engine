import time
import unittest

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import AnalyzerPipeline, FilterPipeline
from ascii_stream_engine.domain.types import RenderFrame


class DummySource:
    def __init__(self, frame=1):
        self.frame = frame
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def read(self):
        return self.frame

    def close(self) -> None:
        self.opened = False


class DummyRenderer:
    def __init__(self):
        self.last_frame = None

    def output_size(self, config):
        return (10, 10)

    def render(self, frame, config, analysis=None):
        self.last_frame = frame
        return RenderFrame(image=object(), text="x", lines=["x"])


class DummySink:
    def __init__(self):
        self.count = 0
        self.output_size = None
        self.open_calls = 0

    def open(self, config, output_size):
        self.open_calls += 1
        self.output_size = output_size

    def write(self, frame):
        self.count += 1

    def close(self):
        pass


class DummyAnalyzer:
    name = "dummy"

    def __init__(self, enabled=True):
        self.enabled = enabled

    def analyze(self, frame, config):
        return {"value": frame}


class DummyFilter:
    name = "plus_one"

    def __init__(self, enabled=True):
        self.enabled = enabled

    def apply(self, frame, config, analysis=None):
        return frame + 1


class TestStreamEngine(unittest.TestCase):
    def test_engine_processes_frames(self) -> None:
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = DummySource(frame=1)
        renderer = DummyRenderer()
        sink = DummySink()
        analyzers = AnalyzerPipeline([DummyAnalyzer()])
        filters = FilterPipeline([DummyFilter()])

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            analyzers=analyzers,
            filters=filters,
        )
        engine.start()
        time.sleep(0.05)
        engine.stop()

        self.assertGreaterEqual(sink.count, 1)
        self.assertEqual(renderer.last_frame, 2)
        analysis = engine.get_last_analysis()
        self.assertIn("dummy", analysis)
        self.assertIn("timestamp", analysis)

    def test_engine_reopens_sink_on_broadcast_change(self) -> None:
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = DummySource(frame=1)
        renderer = DummyRenderer()
        sink = DummySink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            analyzers=AnalyzerPipeline([]),
            filters=FilterPipeline([]),
        )
        engine.start()
        time.sleep(0.05)
        initial_opens = sink.open_calls
        engine.update_config(udp_broadcast=True)

        deadline = time.time() + 0.3
        while time.time() < deadline and sink.open_calls < initial_opens + 1:
            time.sleep(0.01)

        engine.stop()
        self.assertGreaterEqual(sink.open_calls, initial_opens + 1)


if __name__ == "__main__":
    unittest.main()
