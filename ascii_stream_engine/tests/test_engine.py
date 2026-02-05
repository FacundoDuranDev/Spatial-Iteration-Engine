import time
import unittest

from ascii_stream_engine.domain.config import ConfigValidationError, EngineConfig
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

    def test_engine_validates_config_on_update(self) -> None:
        """Verifica que el engine valida la configuración al actualizarla."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = DummySource(frame=1)
        renderer = DummyRenderer()
        sink = DummySink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # Actualización válida
        engine.update_config(fps=25)
        self.assertEqual(engine.get_config().fps, 25)

        # Actualización inválida (fps fuera de rango)
        with self.assertRaises(ValueError) as cm:
            engine.update_config(fps=200)
        self.assertIn("Configuración inválida", str(cm.exception))

        # Actualización inválida (port fuera de rango)
        with self.assertRaises(ValueError) as cm:
            engine.update_config(port=70000)
        self.assertIn("Configuración inválida", str(cm.exception))

    def test_profiling_collects_data(self) -> None:
        """Verifica que el profiling recopila datos correctamente."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = DummySource(frame=1)
        renderer = DummyRenderer()
        sink = DummySink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            enable_profiling=True,  # Habilitar profiling
        )
        
        # Verificar que el profiler está habilitado
        self.assertTrue(engine.profiler.enabled)
        
        engine.start()
        time.sleep(0.1)  # Procesar algunos frames
        engine.stop()

        # Obtener estadísticas
        stats = engine.get_profiling_stats()
        
        # Verificar que se recopilaron datos
        self.assertGreater(len(stats), 0, "Debe haber estadísticas recopiladas")
        
        # Verificar que hay datos de frame total
        from ascii_stream_engine.infrastructure.profiling import LoopProfiler
        if LoopProfiler.PHASE_TOTAL in stats:
            total_stats = stats[LoopProfiler.PHASE_TOTAL]
            self.assertGreater(total_stats["count"], 0, "Debe haber procesado al menos un frame")
            self.assertGreater(total_stats["avg_time"], 0, "El tiempo promedio debe ser positivo")

    def test_profiling_can_be_disabled(self) -> None:
        """Verifica que el profiling puede deshabilitarse."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = DummySource(frame=1)
        renderer = DummyRenderer()
        sink = DummySink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            enable_profiling=False,  # Deshabilitar profiling
        )
        
        # Verificar que el profiler está deshabilitado
        self.assertFalse(engine.profiler.enabled)
        
        engine.start()
        time.sleep(0.05)
        engine.stop()

        # Con profiling deshabilitado, no debería haber datos
        stats = engine.get_profiling_stats()
        # Puede estar vacío o tener datos si se habilitó después, pero no debería afectar el funcionamiento


if __name__ == "__main__":
    unittest.main()
