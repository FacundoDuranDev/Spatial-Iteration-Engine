# Benchmarks y métricas V1

Checklist de métricas a medir cuando el pipeline esté estable. Ejecutar y documentar resultados aquí.

## FPS y latencia

- **FPS esperado V1:** 15–20 FPS (con neural); 20–30 sin neural (solo captura + filtros + ASCII).
- **Latencia end-to-end:** Objetivo &lt;66 ms (15 FPS). Medir p50/p95 desde captura hasta write.
- **Frames dropped:** Contar frames no procesados por buffer lleno o timeouts.

## Recursos

- **Uso memoria/CPU:** Memoria del proceso (RSS) y % CPU por núcleo en ejecución continua 60 s.
- **Cuellos de botella:** Per-fase (capture, analysis, filter, render, write) con `ascii_stream_engine.infrastructure.profiling.LoopProfiler`; identificar si el cuello está en análisis, stylizer o render/salida.

## Métricas por componente (cuando existan)

- Style Encoder: ms por inferencia.
- Stylizer: ms por frame.
- Segmentación: ms por frame.

## Herramientas

- Profiling integrado: `infrastructure/profiling.py`.
- OpenVINO Benchmark Tool para modelos individuales.
- En Linux: `perf`, `htop`/`top` para monitoreo de recursos.

## Plantilla de resultados

| Configuración | FPS | Latencia p50 (ms) | Latencia p95 (ms) | Memoria (MB) | CPU % |
|---------------|-----|-------------------|-------------------|--------------|-------|
| Base (sin neural) | — | — | — | — | — |
| Con neural (stub) | — | — | — | — | — |
| Con neural (ONNX) | — | — | — | — | — |

Completar cuando se ejecuten las pruebas.
