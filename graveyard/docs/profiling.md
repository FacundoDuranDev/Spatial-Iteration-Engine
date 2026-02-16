# Sistema de Profiling del Engine

## Descripción

El sistema de profiling permite medir el rendimiento de cada fase del loop principal del engine para identificar cuellos de botella y optimizar el código.

## Fases Medidas

El profiler mide el tiempo de ejecución de las siguientes fases:

1. **capture**: Captura de frames desde la fuente (cámara o buffer)
2. **analysis**: Análisis de frames mediante el pipeline de analizadores
3. **filtering**: Aplicación de filtros al frame
4. **rendering**: Renderizado del frame a ASCII o RAW
5. **writing**: Escritura del frame renderizado al sink (UDP, recorder, etc.)
6. **total_frame**: Tiempo total de procesamiento de un frame completo

## Uso Básico

### Habilitar Profiling

Para habilitar el profiling, simplemente pasa `enable_profiling=True` al crear el engine:

```python
from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    AsciiRenderer,
    FfmpegUdpOutput,
)

config = EngineConfig(host="127.0.0.1", port=1234)
engine = StreamEngine(
    source=OpenCVCameraSource(0),
    renderer=AsciiRenderer(),
    sink=FfmpegUdpOutput(),
    config=config,
    enable_profiling=True,  # Habilitar profiling
)
```

### Obtener Reporte de Texto

Después de ejecutar el engine, puedes obtener un reporte formateado:

```python
engine.start()
# ... ejecutar el engine ...
engine.stop()

# Obtener reporte de texto
reporte = engine.get_profiling_report()
print(reporte)
```

El reporte incluye:
- Número de muestras por fase
- Tiempo total, promedio, mínimo y máximo
- Desviación estándar
- Análisis de cuellos de botella (porcentaje de tiempo por fase)
- FPS promedio calculado

### Obtener Estadísticas como Diccionario

También puedes obtener las estadísticas como un diccionario para procesamiento programático:

```python
stats = engine.get_profiling_stats()

for phase, phase_stats in stats.items():
    print(f"{phase}:")
    print(f"  Promedio: {phase_stats['avg_time']*1000:.3f} ms")
    print(f"  Mínimo: {phase_stats['min_time']*1000:.3f} ms")
    print(f"  Máximo: {phase_stats['max_time']*1000:.3f} ms")
```

### Acceso Directo al Profiler

Puedes acceder directamente al objeto profiler para control más fino:

```python
profiler = engine.profiler

# Habilitar/deshabilitar en tiempo de ejecución
profiler.enabled = True
profiler.enabled = False

# Reiniciar estadísticas
profiler.reset()

# Obtener estadísticas de una fase específica
capture_stats = profiler.get_stats("capture")
```

## Ejemplo Completo

Ver `ascii_stream_engine/examples/profiling_example.py` para un ejemplo completo que muestra reportes periódicos mientras el engine está ejecutándose.

## Interpretación de Resultados

### Identificar Cuellos de Botella

El reporte automáticamente identifica cuellos de botella mostrando el porcentaje de tiempo que cada fase consume del tiempo total. Las fases con mayor porcentaje son candidatas para optimización.

### Tiempos Esperados

Los tiempos típicos dependen de:
- Resolución de entrada
- Tamaño de grid (grid_w x grid_h)
- Número y complejidad de filtros/analizadores
- Ancho de banda de red (para UDP)

En general:
- **capture**: 10-50 ms (depende de la cámara)
- **analysis**: Variable según analizadores (0 ms si no hay analizadores)
- **filtering**: 5-20 ms (depende de filtros activos)
- **rendering**: 10-100 ms (depende del tamaño del grid y modo)
- **writing**: 1-10 ms (depende de la red)

### Optimización

Si una fase consume más del 50% del tiempo total, considera:
- **capture**: Reducir resolución de entrada, usar buffer más pequeño
- **analysis**: Optimizar analizadores o reducir frecuencia de análisis
- **filtering**: Optimizar filtros, usar vectorización numpy
- **rendering**: Reducir tamaño de grid, optimizar conversiones
- **writing**: Verificar ancho de banda de red, ajustar bitrate

## Limitaciones

- El profiling agrega un overhead mínimo (~0.1-0.5 ms por frame)
- Las muestras se limitan a 1000 por defecto para evitar consumo excesivo de memoria
- El profiling no mide el tiempo del hilo de captura separado (solo la lectura del buffer)

## API de Referencia

### LoopProfiler

- `enabled: bool`: Habilita/deshabilita el profiling
- `start_frame()`: Marca el inicio de un frame
- `end_frame()`: Marca el fin de un frame
- `start_phase(phase: str)`: Marca el inicio de una fase
- `end_phase(phase: str)`: Marca el fin de una fase
- `get_stats(phase: Optional[str])`: Obtiene estadísticas
- `get_report() -> str`: Genera reporte de texto
- `get_summary_dict() -> Dict`: Obtiene estadísticas como diccionario
- `reset()`: Reinicia todas las estadísticas

### StreamEngine

- `profiler: LoopProfiler`: Acceso al profiler
- `get_profiling_report() -> str`: Obtiene reporte de texto
- `get_profiling_stats() -> Dict`: Obtiene estadísticas como diccionario

