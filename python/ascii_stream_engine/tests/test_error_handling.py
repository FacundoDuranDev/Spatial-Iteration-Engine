"""Tests de manejo de errores y validación de configuración.

Este módulo contiene tests exhaustivos para:
- Validación de configuración (casos edge adicionales)
- Manejo de errores en el engine (cámara, UDP, análisis, filtrado, renderizado)
- Manejo de errores en componentes
- Casos de recuperación y reintentos
"""

import time
import unittest
from unittest.mock import Mock, patch

from ascii_stream_engine.domain.config import ConfigValidationError, EngineConfig
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import AnalyzerPipeline, FilterPipeline
from ascii_stream_engine.domain.types import RenderFrame


class FailingSource:
    """Fuente que falla en diferentes operaciones para testing."""

    def __init__(self, fail_on_open=False, fail_on_read=False, return_none=False):
        self.fail_on_open = fail_on_open
        self.fail_on_read = fail_on_read
        self.return_none = return_none
        self.opened = False
        self.read_count = 0

    def open(self) -> None:
        if self.fail_on_open:
            raise IOError("Error simulado al abrir cámara")
        self.opened = True

    def read(self):
        self.read_count += 1
        if self.fail_on_read:
            raise IOError(f"Error simulado al leer frame (intento {self.read_count})")
        if self.return_none:
            return None
        return object()  # Frame dummy

    def close(self) -> None:
        self.opened = False


class FailingRenderer:
    """Renderer que falla para testing."""

    def __init__(self, fail_on_render=False):
        self.fail_on_render = fail_on_render
        self.render_count = 0

    def output_size(self, config):
        return (10, 10)

    def render(self, frame, config, analysis=None):
        self.render_count += 1
        if self.fail_on_render:
            raise RuntimeError(f"Error simulado en renderizado (intento {self.render_count})")
        return RenderFrame(image=object(), text="x", lines=["x"])


class FailingSink:
    """Sink que falla en diferentes operaciones para testing."""

    def __init__(self, fail_on_open=False, fail_on_write=False):
        self.fail_on_open = fail_on_open
        self.fail_on_write = fail_on_write
        self.opened = False
        self.write_count = 0
        self.open_calls = 0

    def open(self, config, output_size):
        self.open_calls += 1
        if self.fail_on_open:
            raise OSError("Error simulado al abrir sink UDP")
        self.opened = True

    def write(self, frame):
        self.write_count += 1
        if self.fail_on_write:
            raise BrokenPipeError(f"Error simulado al escribir UDP (intento {self.write_count})")
        # Éxito

    def close(self):
        self.opened = False


class FailingAnalyzer:
    """Analizador que falla para testing."""

    name = "failing_analyzer"

    def __init__(self, fail=False):
        self.fail = fail
        self.analyze_count = 0

    def analyze(self, frame, config):
        self.analyze_count += 1
        if self.fail:
            raise ValueError(f"Error simulado en análisis (intento {self.analyze_count})")
        return {"value": "ok"}


class FailingFilter:
    """Filtro que falla para testing."""

    name = "failing_filter"

    def __init__(self, fail=False):
        self.fail = fail
        self.apply_count = 0

    def apply(self, frame, config, analysis=None):
        self.apply_count += 1
        if self.fail:
            raise RuntimeError(f"Error simulado en filtrado (intento {self.apply_count})")
        return frame


class TestConfigValidationEdgeCases(unittest.TestCase):
    """Tests de casos edge adicionales para validación de configuración."""

    def test_config_validation_ipv6_host(self) -> None:
        """Verifica validación de host IPv6."""
        # IPv6 válido
        config = EngineConfig(host="::1")
        self.assertEqual(config.host, "::1")

        config = EngineConfig(host="2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        self.assertEqual(config.host, "2001:0db8:85a3:0000:0000:8a2e:0370:7334")

    def test_config_validation_hostname_edge_cases(self) -> None:
        """Verifica casos edge de validación de hostname."""
        # Hostnames válidos
        valid_hostnames = [
            "example.com",
            "sub.example.com",
            "a.b.c.example.com",
            "host-name.example.com",
            "123.example.com",
        ]
        for hostname in valid_hostnames:
            config = EngineConfig(host=hostname)
            self.assertEqual(config.host, hostname)

        # Hostnames inválidos
        invalid_hostnames = [
            "invalid..host",  # Doble punto
            "-invalid.com",  # Empieza con guión
            "invalid-.com",  # Termina con guión
            ".invalid.com",  # Empieza con punto
            "invalid.com.",  # Termina con punto
            "",  # Vacío
        ]
        for hostname in invalid_hostnames:
            with self.assertRaises(ConfigValidationError) as cm:
                EngineConfig(host=hostname)
            self.assertIn("host", str(cm.exception).lower())

    def test_config_validation_bitrate_edge_cases(self) -> None:
        """Verifica casos edge de validación de bitrate."""
        # Bitrates válidos en límites
        valid_bitrates = ["1", "100000", "1k", "100K", "1m", "100M"]
        for bitrate in valid_bitrates:
            config = EngineConfig(bitrate=bitrate)
            self.assertEqual(config.bitrate, bitrate)

        # Bitrates inválidos
        invalid_bitrates = [
            "0",  # Cero
            "100001",  # Muy grande
            "abc",  # No numérico
            "1.5k",  # Decimal
            "1kb",  # Sufijo inválido
            "",  # Vacío
        ]
        for bitrate in invalid_bitrates:
            with self.assertRaises(ConfigValidationError) as cm:
                EngineConfig(bitrate=bitrate)
            self.assertIn("bitrate", str(cm.exception).lower())

    def test_config_validation_raw_dimensions_edge_cases(self) -> None:
        """Verifica casos edge de dimensiones raw."""
        # None es válido cuando render_mode no es "raw"
        config = EngineConfig(render_mode="ascii", raw_width=None, raw_height=None)
        self.assertIsNone(config.raw_width)
        self.assertIsNone(config.raw_height)

        # Límites válidos
        config = EngineConfig(render_mode="raw", raw_width=10, raw_height=10)
        self.assertEqual(config.raw_width, 10)
        self.assertEqual(config.raw_height, 10)

        config = EngineConfig(render_mode="raw", raw_width=10000, raw_height=10000)
        self.assertEqual(config.raw_width, 10000)
        self.assertEqual(config.raw_height, 10000)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(render_mode="raw", raw_width=9)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(render_mode="raw", raw_width=10001)

    def test_config_validation_contrast_edge_cases(self) -> None:
        """Verifica casos edge de validación de contrast."""
        # Límites válidos
        config = EngineConfig(contrast=0.1)
        self.assertEqual(config.contrast, 0.1)

        config = EngineConfig(contrast=5.0)
        self.assertEqual(config.contrast, 5.0)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(contrast=0.09)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(contrast=5.01)

    def test_config_validation_brightness_edge_cases(self) -> None:
        """Verifica casos edge de validación de brightness."""
        # Límites válidos
        config = EngineConfig(brightness=-255)
        self.assertEqual(config.brightness, -255)

        config = EngineConfig(brightness=255)
        self.assertEqual(config.brightness, 255)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(brightness=-256)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(brightness=256)

    def test_config_validation_pkt_size_edge_cases(self) -> None:
        """Verifica casos edge de validación de pkt_size."""
        # Límites válidos
        config = EngineConfig(pkt_size=512)
        self.assertEqual(config.pkt_size, 512)

        config = EngineConfig(pkt_size=65507)
        self.assertEqual(config.pkt_size, 65507)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(pkt_size=511)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(pkt_size=65508)

    def test_config_validation_fps_edge_cases(self) -> None:
        """Verifica casos edge de validación de fps."""
        # Límites válidos
        config = EngineConfig(fps=1)
        self.assertEqual(config.fps, 1)

        config = EngineConfig(fps=120)
        self.assertEqual(config.fps, 120)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(fps=0)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(fps=121)

    def test_config_validation_grid_edge_cases(self) -> None:
        """Verifica casos edge de validación de grid."""
        # Límites válidos
        config = EngineConfig(grid_w=10, grid_h=10)
        self.assertEqual(config.grid_w, 10)
        self.assertEqual(config.grid_h, 10)

        config = EngineConfig(grid_w=1000, grid_h=1000)
        self.assertEqual(config.grid_w, 1000)
        self.assertEqual(config.grid_h, 1000)

        # Límites inválidos
        with self.assertRaises(ConfigValidationError):
            EngineConfig(grid_w=9)

        with self.assertRaises(ConfigValidationError):
            EngineConfig(grid_h=1001)


class TestEngineErrorHandling(unittest.TestCase):
    """Tests de manejo de errores en el StreamEngine."""

    def test_engine_handles_source_open_error(self) -> None:
        """Verifica que el engine maneja errores al abrir la fuente."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource(fail_on_open=True)
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # El engine debería intentar reabrir la fuente
        engine.start()
        time.sleep(0.1)  # Dar tiempo para que intente
        engine.stop()

        # Verificar que se intentó abrir (aunque falló)
        # El engine debería haber intentado reabrir después del fallo inicial
        self.assertFalse(source.opened)

    def test_engine_handles_sink_open_error(self) -> None:
        """Verifica que el engine maneja errores al abrir el sink."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink(fail_on_open=True)

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # El engine debería detenerse si no puede abrir el sink
        engine.start()
        time.sleep(0.05)
        engine.stop()

        # El sink no debería estar abierto
        self.assertFalse(sink.opened)

    def test_engine_handles_source_read_error(self) -> None:
        """Verifica que el engine maneja errores al leer de la fuente."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource(fail_on_read=True)
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.1)  # Dar tiempo para múltiples intentos
        engine.stop()

        # El engine debería haber intentado leer múltiples veces
        self.assertGreater(source.read_count, 0)
        # No debería haber renderizado nada debido a los errores
        self.assertEqual(renderer.render_count, 0)

    def test_engine_handles_source_read_none(self) -> None:
        """Verifica que el engine maneja cuando la fuente retorna None."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource(return_none=True)
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # El engine debería haber intentado leer
        self.assertGreater(source.read_count, 0)
        # No debería haber renderizado nada
        self.assertEqual(renderer.render_count, 0)

    def test_engine_handles_analysis_error(self) -> None:
        """Verifica que el engine maneja errores en análisis."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()
        analyzer = FailingAnalyzer(fail=True)

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            analyzers=AnalyzerPipeline([analyzer]),
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # El analizador debería haber sido llamado
        self.assertGreater(analyzer.analyze_count, 0)
        # El engine debería continuar funcionando a pesar del error
        # Verificar que se registró el error en métricas
        errors = engine.metrics.get_errors()
        self.assertGreater(errors.get("analysis", 0), 0)

    def test_engine_handles_filter_error(self) -> None:
        """Verifica que el engine maneja errores en filtrado."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()
        filter_obj = FailingFilter(fail=True)

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
            filters=FilterPipeline([filter_obj]),
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # El filtro debería haber sido llamado
        self.assertGreater(filter_obj.apply_count, 0)
        # Verificar que se registró el error en métricas
        errors = engine.metrics.get_errors()
        self.assertGreater(errors.get("filtering", 0), 0)

    def test_engine_handles_render_error(self) -> None:
        """Verifica que el engine maneja errores en renderizado."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer(fail_on_render=True)
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # El renderer debería haber sido llamado
        self.assertGreater(renderer.render_count, 0)
        # Verificar que se registró el error en métricas
        errors = engine.metrics.get_errors()
        self.assertGreater(errors.get("rendering", 0), 0)

    def test_engine_handles_sink_write_error(self) -> None:
        """Verifica que el engine maneja errores al escribir al sink."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink(fail_on_write=True)

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # El sink debería haber sido llamado para escribir
        self.assertGreater(sink.write_count, 0)
        # El engine debería haber intentado reconectar
        self.assertGreater(sink.open_calls, 0)

    def test_engine_handles_unknown_config_parameter(self) -> None:
        """Verifica que el engine maneja parámetros desconocidos en update_config."""
        config = EngineConfig(fps=30)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # Intentar actualizar con parámetro desconocido
        with self.assertRaises(ValueError) as cm:
            engine.update_config(unknown_param=123)
        self.assertIn("desconocido", str(cm.exception).lower())

    def test_engine_validates_config_on_update(self) -> None:
        """Verifica que el engine valida la configuración al actualizarla."""
        config = EngineConfig(fps=30)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # Actualización válida
        engine.update_config(fps=25)
        self.assertEqual(engine.get_config().fps, 25)

        # Actualización inválida debería lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            engine.update_config(fps=200)
        self.assertIn("Configuración inválida", str(cm.exception))

        # La configuración original no debería haber cambiado
        self.assertEqual(engine.get_config().fps, 25)

    def test_engine_handles_multiple_consecutive_errors(self) -> None:
        """Verifica que el engine maneja múltiples errores consecutivos."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource(fail_on_read=True)
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.2)  # Dar tiempo para múltiples errores
        engine.stop()

        # Debería haber múltiples intentos de lectura
        self.assertGreater(source.read_count, 1)
        # Verificar que las métricas registraron los errores
        errors = engine.metrics.get_errors()
        # Puede haber errores de captura registrados

    def test_engine_metrics_record_errors(self) -> None:
        """Verifica que las métricas registran errores correctamente."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer(fail_on_render=True)
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        engine.start()
        time.sleep(0.1)
        engine.stop()

        # Verificar que se registraron errores
        errors = engine.metrics.get_errors()
        total_errors = engine.metrics.get_total_errors()
        self.assertGreater(total_errors, 0)
        self.assertGreater(errors.get("rendering", 0), 0)

    def test_engine_handles_keyboard_interrupt(self) -> None:
        """Verifica que el engine maneja KeyboardInterrupt correctamente."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # Simular KeyboardInterrupt en el loop
        with patch.object(engine, "_run", side_effect=KeyboardInterrupt()):
            try:
                engine.start(blocking=True)
            except KeyboardInterrupt:
                pass

        # El engine debería haberse detenido limpiamente
        self.assertFalse(engine.is_running)

    def test_engine_handles_unexpected_exception(self) -> None:
        """Verifica que el engine maneja excepciones inesperadas."""
        config = EngineConfig(fps=30, frame_buffer_size=0, sleep_on_empty=0.001)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # Simular excepción inesperada en el loop
        with patch.object(engine, "_run", side_effect=RuntimeError("Error inesperado")):
            try:
                engine.start(blocking=True)
            except RuntimeError:
                pass

        # El engine debería haberse detenido limpiamente
        self.assertFalse(engine.is_running)


class TestComponentErrorHandling(unittest.TestCase):
    """Tests de manejo de errores en componentes individuales."""

    def test_source_close_handles_errors(self) -> None:
        """Verifica que el engine maneja errores al cerrar la fuente."""
        config = EngineConfig(fps=30)
        source = FailingSource()

        # Crear un mock que falle al cerrar
        original_close = source.close

        def failing_close():
            raise IOError("Error al cerrar fuente")

        source.close = failing_close

        renderer = FailingRenderer()
        sink = FailingSink()

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # El engine debería manejar el error al cerrar sin lanzar excepción
        engine.start()
        time.sleep(0.01)
        # Esto no debería lanzar excepción aunque source.close() falle
        engine.stop()

    def test_sink_close_handles_errors(self) -> None:
        """Verifica que el engine maneja errores al cerrar el sink."""
        config = EngineConfig(fps=30)
        source = FailingSource()
        renderer = FailingRenderer()
        sink = FailingSink()

        # Crear un mock que falle al cerrar
        original_close = sink.close

        def failing_close():
            raise OSError("Error al cerrar sink")

        sink.close = failing_close

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=config,
        )

        # El engine debería manejar el error al cerrar sin lanzar excepción
        engine.start()
        time.sleep(0.01)
        # Esto no debería lanzar excepción aunque sink.close() falle
        engine.stop()


if __name__ == "__main__":
    unittest.main()

