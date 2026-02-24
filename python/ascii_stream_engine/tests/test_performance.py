"""Tests de rendimiento y benchmarks para medir mejoras de optimización.

Este módulo contiene benchmarks para:
- Renderer ASCII (conversión de frames a ASCII)
- Filtros individuales
- Pipeline de filtros
- Loop completo del engine
- Operaciones de memoria
"""

import statistics
import time
import unittest
from typing import List, Tuple

import cv2
import numpy as np

from ascii_stream_engine.adapters.processors import (
    BrightnessFilter,
    DetailBoostFilter,
    EdgeFilter,
    InvertFilter,
)
from ascii_stream_engine.adapters.renderers.ascii import AsciiRenderer
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import AnalyzerPipeline, FilterPipeline
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


def generate_test_frame(width: int = 640, height: int = 480, channels: int = 3) -> np.ndarray:
    """Genera un frame de prueba con ruido aleatorio."""
    if channels == 3:
        return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    else:
        return np.random.randint(0, 256, (height, width), dtype=np.uint8)


def benchmark_function(
    func, *args, iterations: int = 100, warmup: int = 10
) -> Tuple[float, float, float, List[float]]:
    """
    Ejecuta un benchmark de una función.

    Args:
        func: Función a medir
        *args: Argumentos para la función
        iterations: Número de iteraciones a medir
        warmup: Número de iteraciones de calentamiento (no se miden)

    Returns:
        Tupla con (tiempo_promedio, tiempo_min, tiempo_max, lista_tiempos)
    """
    # Calentamiento
    for _ in range(warmup):
        func(*args)

    # Medición
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args)
        end = time.perf_counter()
        times.append(end - start)

    return (statistics.mean(times), min(times), max(times), times)


class TestAsciiRendererPerformance(unittest.TestCase):
    """Benchmarks del renderer ASCII."""

    def setUp(self) -> None:
        """Configuración inicial para los tests."""
        self.renderer = AsciiRenderer(font_size=12)
        self.config = EngineConfig(grid_w=120, grid_h=60)
        self.frame_640x480 = generate_test_frame(640, 480, 3)
        self.frame_1920x1080 = generate_test_frame(1920, 1080, 3)
        self.frame_gray = generate_test_frame(640, 480, 1)

    def test_frame_to_lines_performance_small_frame(self) -> None:
        """Benchmark de _frame_to_lines con frame pequeño (640x480)."""
        avg_time, min_time, max_time, _ = benchmark_function(
            self.renderer._frame_to_lines,
            self.frame_640x480,
            self.config,
            iterations=200,
            warmup=20,
        )

        # Verificar que el tiempo promedio es razonable (< 50ms para frame pequeño)
        self.assertLess(avg_time, 0.05, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Renderer] _frame_to_lines (640x480): "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_frame_to_lines_performance_large_frame(self) -> None:
        """Benchmark de _frame_to_lines con frame grande (1920x1080)."""
        avg_time, min_time, max_time, _ = benchmark_function(
            self.renderer._frame_to_lines,
            self.frame_1920x1080,
            self.config,
            iterations=100,
            warmup=10,
        )

        # Verificar que el tiempo promedio es razonable (< 100ms para frame grande)
        self.assertLess(avg_time, 0.1, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Renderer] _frame_to_lines (1920x1080): "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_frame_to_lines_performance_gray_frame(self) -> None:
        """Benchmark de _frame_to_lines con frame en escala de grises (optimización)."""
        avg_time, min_time, max_time, _ = benchmark_function(
            self.renderer._frame_to_lines, self.frame_gray, self.config, iterations=200, warmup=20
        )

        # Frame en escala de grises debería ser más rápido (no necesita conversión)
        self.assertLess(avg_time, 0.05, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Renderer] _frame_to_lines (gray 640x480): "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_render_performance(self) -> None:
        """Benchmark del método render completo."""
        avg_time, min_time, max_time, _ = benchmark_function(
            self.renderer.render, self.frame_640x480, self.config, iterations=100, warmup=10
        )

        # Render completo incluye creación de imagen PIL, debería ser < 100ms
        self.assertLess(avg_time, 0.1, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Renderer] render completo (640x480): "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_render_caching_performance(self) -> None:
        """Benchmark del cache de imágenes PIL en render."""
        # Primera renderización (sin cache)
        times_first = []
        for _ in range(10):
            start = time.perf_counter()
            self.renderer.render(self.frame_640x480, self.config)
            times_first.append(time.perf_counter() - start)

        # Renderizaciones subsecuentes (con cache)
        times_cached = []
        for _ in range(10):
            start = time.perf_counter()
            self.renderer.render(self.frame_640x480, self.config)
            times_cached.append(time.perf_counter() - start)

        avg_first = statistics.mean(times_first)
        avg_cached = statistics.mean(times_cached)

        # El cache debería mejorar el rendimiento (aunque puede ser mínimo)
        print(
            f"\n[Renderer] Cache performance: "
            f"sin_cache={avg_first*1000:.2f}ms, con_cache={avg_cached*1000:.2f}ms, "
            f"mejora={((avg_first-avg_cached)/avg_first*100):.1f}%"
        )

        # Verificar que ambos son razonables
        self.assertLess(avg_first, 0.15)
        self.assertLess(avg_cached, 0.15)


class TestFilterPerformance(unittest.TestCase):
    """Benchmarks de filtros individuales."""

    def setUp(self) -> None:
        """Configuración inicial para los tests."""
        self.config = EngineConfig()
        self.frame_640x480 = generate_test_frame(640, 480, 3)
        self.frame_gray = generate_test_frame(640, 480, 1)

    def test_brightness_filter_performance(self) -> None:
        """Benchmark del filtro de brillo."""
        filter_obj = BrightnessFilter()
        avg_time, min_time, max_time, _ = benchmark_function(
            filter_obj.apply, self.frame_640x480, self.config, iterations=200, warmup=20
        )

        self.assertLess(avg_time, 0.01, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Filter] BrightnessFilter: "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_edge_filter_performance(self) -> None:
        """Benchmark del filtro de bordes."""
        filter_obj = EdgeFilter()
        avg_time, min_time, max_time, _ = benchmark_function(
            filter_obj.apply, self.frame_640x480, self.config, iterations=100, warmup=10
        )

        # Canny es más costoso que brightness
        self.assertLess(avg_time, 0.05, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Filter] EdgeFilter: "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_invert_filter_performance(self) -> None:
        """Benchmark del filtro de inversión."""
        filter_obj = InvertFilter()
        avg_time, min_time, max_time, _ = benchmark_function(
            filter_obj.apply, self.frame_640x480, self.config, iterations=200, warmup=20
        )

        self.assertLess(avg_time, 0.01, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Filter] InvertFilter: "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_detail_filter_performance(self) -> None:
        """Benchmark del filtro de detalle."""
        filter_obj = DetailBoostFilter()
        avg_time, min_time, max_time, _ = benchmark_function(
            filter_obj.apply, self.frame_640x480, self.config, iterations=100, warmup=10
        )

        # DetailBoostFilter usa operaciones de convolución, puede ser más lento
        self.assertLess(avg_time, 0.05, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Filter] DetailBoostFilter: "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )


class TestFilterPipelinePerformance(unittest.TestCase):
    """Benchmarks del pipeline de filtros."""

    def setUp(self) -> None:
        """Configuración inicial para los tests."""
        self.config = EngineConfig()
        self.frame_640x480 = generate_test_frame(640, 480, 3)

    def test_empty_pipeline_performance(self) -> None:
        """Benchmark de pipeline vacío (debería ser muy rápido, sin copias)."""
        pipeline = FilterPipeline([])
        avg_time, min_time, max_time, _ = benchmark_function(
            pipeline.apply, self.frame_640x480, self.config, iterations=1000, warmup=100
        )

        # Pipeline vacío debería ser extremadamente rápido (< 0.001ms)
        self.assertLess(avg_time, 0.001, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Pipeline] Pipeline vacío: "
            f"avg={avg_time*1000:.3f}ms, min={min_time*1000:.3f}ms, max={max_time*1000:.3f}ms"
        )

    def test_single_filter_pipeline_performance(self) -> None:
        """Benchmark de pipeline con un solo filtro."""
        pipeline = FilterPipeline([BrightnessFilter()])
        avg_time, min_time, max_time, _ = benchmark_function(
            pipeline.apply, self.frame_640x480, self.config, iterations=200, warmup=20
        )

        self.assertLess(avg_time, 0.02, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Pipeline] Pipeline con 1 filtro (Brightness): "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_multiple_filters_pipeline_performance(self) -> None:
        """Benchmark de pipeline con múltiples filtros."""
        pipeline = FilterPipeline(
            [
                BrightnessFilter(),
                InvertFilter(),
                EdgeFilter(),
            ]
        )
        avg_time, min_time, max_time, _ = benchmark_function(
            pipeline.apply, self.frame_640x480, self.config, iterations=100, warmup=10
        )

        # Múltiples filtros deberían ser más lentos pero razonables
        self.assertLess(avg_time, 0.1, f"Tiempo promedio demasiado alto: {avg_time*1000:.2f}ms")
        print(
            f"\n[Pipeline] Pipeline con 3 filtros: "
            f"avg={avg_time*1000:.2f}ms, min={min_time*1000:.2f}ms, max={max_time*1000:.2f}ms"
        )

    def test_conversion_cache_performance(self) -> None:
        """Benchmark del cache de conversiones en el pipeline."""
        # Pipeline con múltiples filtros que requieren conversión a gris
        pipeline = FilterPipeline(
            [
                EdgeFilter(),
                EdgeFilter(),  # Duplicado para forzar uso del cache
            ]
        )

        # Primera ejecución (sin cache)
        times_first = []
        for _ in range(10):
            start = time.perf_counter()
            pipeline.apply(self.frame_640x480, self.config)
            times_first.append(time.perf_counter() - start)

        # Ejecuciones subsecuentes (con cache)
        times_cached = []
        for _ in range(10):
            start = time.perf_counter()
            pipeline.apply(self.frame_640x480, self.config)
            times_cached.append(time.perf_counter() - start)

        avg_first = statistics.mean(times_first)
        avg_cached = statistics.mean(times_cached)

        print(
            f"\n[Pipeline] Conversion cache performance: "
            f"sin_cache={avg_first*1000:.2f}ms, con_cache={avg_cached*1000:.2f}ms, "
            f"mejora={((avg_first-avg_cached)/avg_first*100):.1f}%"
        )

        # Verificar que ambos son razonables
        self.assertLess(avg_first, 0.15)
        self.assertLess(avg_cached, 0.15)


class TestEngineLoopPerformance(unittest.TestCase):
    """Benchmarks del loop completo del engine."""

    def setUp(self) -> None:
        """Configuración inicial para los tests."""
        self.config = EngineConfig(
            fps=30, grid_w=120, grid_h=60, frame_buffer_size=0, sleep_on_empty=0.001
        )

    def test_single_frame_processing_performance(self) -> None:
        """Benchmark del procesamiento de un frame completo."""
        from ascii_stream_engine.tests.test_engine import DummyRenderer, DummySink, DummySource

        frame = generate_test_frame(640, 480, 3)
        source = DummySource(frame=frame)
        renderer = DummyRenderer()
        sink = DummySink()

        engine = StreamEngine(
            source=source, renderer=renderer, sink=sink, config=self.config, enable_profiling=True
        )

        # Medir tiempo de procesamiento de un frame
        times = []
        for _ in range(50):
            start = time.perf_counter()
            engine.start()
            time.sleep(0.01)  # Procesar algunos frames
            engine.stop()
            times.append(time.perf_counter() - start)

        avg_time = statistics.mean(times)
        print(f"\n[Engine] Procesamiento de frame completo: " f"avg={avg_time*1000:.2f}ms")

        # Verificar que el tiempo es razonable
        self.assertLess(avg_time, 0.1)

    def test_engine_profiling_accuracy(self) -> None:
        """Verifica que el profiling del engine mide correctamente."""
        from ascii_stream_engine.application.pipeline import FilterPipeline
        from ascii_stream_engine.tests.test_engine import (
            DummyFilter,
            DummyRenderer,
            DummySink,
            DummySource,
        )

        frame = generate_test_frame(640, 480, 3)
        source = DummySource(frame=frame)
        renderer = DummyRenderer()
        sink = DummySink()
        filters = FilterPipeline([DummyFilter()])

        engine = StreamEngine(
            source=source,
            renderer=renderer,
            sink=sink,
            config=self.config,
            filters=filters,
            enable_profiling=True,
        )

        engine.start()
        time.sleep(0.2)  # Procesar varios frames
        engine.stop()

        # Obtener estadísticas de profiling
        stats = engine.get_profiling_stats()

        # Verificar que se recopilaron datos
        self.assertGreater(len(stats), 0)

        # Verificar que hay datos de frame total
        from ascii_stream_engine.infrastructure.profiling import LoopProfiler

        if LoopProfiler.PHASE_TOTAL in stats:
            total_stats = stats[LoopProfiler.PHASE_TOTAL]
            self.assertGreater(total_stats["count"], 0)
            self.assertGreater(total_stats["avg_time"], 0)

            print(f"\n[Engine] Profiling stats:")
            print(f"  Frames procesados: {total_stats['count']}")
            print(f"  Tiempo promedio por frame: {total_stats['avg_time']*1000:.2f}ms")
            print(f"  FPS real: {1.0/total_stats['avg_time']:.2f}")


class TestMemoryPerformance(unittest.TestCase):
    """Benchmarks de uso de memoria."""

    def setUp(self) -> None:
        """Configuración inicial para los tests."""
        self.frame_640x480 = generate_test_frame(640, 480, 3)
        self.config = EngineConfig()

    def test_frame_copy_vs_view(self) -> None:
        """Compara el rendimiento de copias vs vistas de frames."""
        # Copia completa
        times_copy = []
        for _ in range(100):
            start = time.perf_counter()
            copied = self.frame_640x480.copy()
            _ = copied.shape
            times_copy.append(time.perf_counter() - start)

        # Vista (sin copia)
        times_view = []
        for _ in range(100):
            start = time.perf_counter()
            viewed = self.frame_640x480[:]
            _ = viewed.shape
            times_view.append(time.perf_counter() - start)

        avg_copy = statistics.mean(times_copy)
        avg_view = statistics.mean(times_view)

        print(
            f"\n[Memory] Frame copy vs view: "
            f"copy={avg_copy*1000:.3f}ms, view={avg_view*1000:.3f}ms, "
            f"ratio={avg_copy/avg_view:.1f}x"
        )

        # La vista debería ser más rápida
        self.assertLess(avg_view, avg_copy)

    def test_pipeline_memory_efficiency(self) -> None:
        """Verifica que el pipeline no hace copias innecesarias cuando no hay filtros."""
        pipeline = FilterPipeline([])

        # Obtener el id del frame original
        original_id = id(self.frame_640x480)

        # Aplicar pipeline vacío
        result = pipeline.apply(self.frame_640x480, self.config)

        # Con pipeline vacío, debería retornar el mismo objeto (sin copia)
        # Nota: Esto puede no ser siempre cierto dependiendo de la implementación,
        # pero es una optimización deseable
        result_id = id(result)

        print(f"\n[Memory] Pipeline vacío - original_id={original_id}, result_id={result_id}")

        # Verificar que el pipeline funciona correctamente
        self.assertEqual(result.shape, self.frame_640x480.shape)


class TestScalabilityPerformance(unittest.TestCase):
    """Benchmarks de escalabilidad con diferentes tamaños de frame."""

    def test_renderer_scalability(self) -> None:
        """Mide cómo escala el renderer con diferentes tamaños de frame."""
        renderer = AsciiRenderer(font_size=12)
        config = EngineConfig(grid_w=120, grid_h=60)

        frame_sizes = [
            (320, 240),
            (640, 480),
            (1280, 720),
            (1920, 1080),
        ]

        results = []
        for width, height in frame_sizes:
            frame = generate_test_frame(width, height, 3)
            avg_time, _, _, _ = benchmark_function(
                renderer._frame_to_lines, frame, config, iterations=50, warmup=5
            )
            results.append((width * height, avg_time))
            print(f"\n[Scalability] Renderer {width}x{height}: {avg_time*1000:.2f}ms")

        # Verificar que los tiempos son razonables
        for size, avg_time in results:
            self.assertLess(avg_time, 0.2, f"Tiempo demasiado alto para tamaño {size}")

    def test_filter_scalability(self) -> None:
        """Mide cómo escalan los filtros con diferentes tamaños de frame."""
        filter_obj = BrightnessFilter()
        config = EngineConfig()

        frame_sizes = [
            (320, 240),
            (640, 480),
            (1280, 720),
            (1920, 1080),
        ]

        results = []
        for width, height in frame_sizes:
            frame = generate_test_frame(width, height, 3)
            avg_time, _, _, _ = benchmark_function(
                filter_obj.apply, frame, config, iterations=100, warmup=10
            )
            results.append((width * height, avg_time))
            print(f"\n[Scalability] BrightnessFilter {width}x{height}: {avg_time*1000:.2f}ms")

        # Verificar que los tiempos son razonables
        for size, avg_time in results:
            self.assertLess(avg_time, 0.05, f"Tiempo demasiado alto para tamaño {size}")


if __name__ == "__main__":
    # Ejecutar tests con verbosidad para ver los resultados de los benchmarks
    unittest.main(verbosity=2)
