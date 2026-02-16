# Reglas derivadas de graveyard/docs

**Origen:** El contenido de `graveyard/docs/` es documentación archivada/referencia. Estas reglas extraen y fijan las ideas que el proyecto adopta como normativas. La autoridad canónica sigue siendo `rules/ARCHITECTURE.md` y `rules/MVP_INDEX.md`; este archivo complementa con reglas de diseño, pipeline, C++ y buenas prácticas.

---

## 1. Arquitectura hexagonal (capas y dependencias)

- **Domain** no depende de nadie. Contiene config, types, events, tracking_data, frame_metadata.
- **Ports** solo depende de domain. Define FrameSource, FrameRenderer, OutputSink, Filter, Analyzer, etc.
- **Application** depende de domain y ports. Orquesta engine, pipelines, orquestación, servicios.
- **Adapters** depende de ports y domain. Implementaciones concretas (sources, renderers, outputs, filters, analyzers).
- **Infrastructure** es transversal; application puede usarlo (event_bus, logging, plugins, metrics, profiling).
- **Presentation** depende de application y adapters (o solo API pública); ej. notebook_api.

**Regla:** No invertir dependencias. Nuevos adapters se añaden sin tocar application; nueva lógica de orquestación en application sin tocar domain/ports.

---

## 2. Pipeline conceptual (seis capas, orden de ejecución)

Orden en el flujo:

1. **Source** — Lectura del frame.
2. **Perception** — Análisis (detección, pose, segmentación); resultado en `analysis`; no modifica la imagen.
3. **Tracking** (opcional) — Sobre detecciones.
4. **Semantic / Transformations** — Transformaciones espaciales y/o semánticas (estilo, temporal).
5. **Visual Modifiers (Filters)** — Filtros aplicados al frame; pueden usar `analysis`.
6. **Renderer** — Frame → RenderFrame (imagen + metadata).
7. **Output** — Escritura en el sink.

**Regla:** Respetar este orden en el orquestador. Percepción solo describe; filtros y renderer permanecen agnósticos al origen/concreto del sink.

---

## 3. Contrato Python ↔ C++

- **Buffers:** `numpy.ndarray` C-contiguous, uint8. Frame: shape `(height, width, 3)` (BGR o RGB según contrato). Máscara opcional: `(height, width)`, 0 = fondo, 255 = región activa.
- **Propiedad:** Python es dueño de los arrays. C++ no guarda referencias más allá de la llamada; no almacenar punteros con GIL soltado.
- **Salida:** Preferir in-place (Python preasigna, C++ escribe) o retorno explícito documentando quién libera.
- **API mínima bridge:** `render(frame, mask=None) -> frame_out`; mismo shape que entrada; si el módulo no está, fallback seguro (passthrough).

**Regla:** C++ no orquesta; recibe buffers y modifica imagen. Adapters Python (CppInvertFilter, CppImageModifierFilter, etc.) delegan en el bridge y manejan ImportError sin romper el pipeline.

---

## 4. Configuración y rendimiento

- Centralizar valores en EngineConfig; validar rangos antes de aplicar.
- Evitar copias de frames innecesarias; preferir operaciones vectorizadas (numpy, cv2).
- Mantener frame_buffer_size bajo para baja latencia.
- Usar locks solo donde sea necesario; no trabajo pesado dentro del lock; cortar hilos de forma segura en stop().

---

## 5. Errores y diseño

- Fallar rápido si falta dependencia crítica.
- Manejar excepciones en pipelines y outputs; logs simples para diagnóstico.
- Respetar límites de capas; colocar adapters nuevos sin tocar application.
- Mantener `__all__` y API pública claros.

---

## 6. Testing

- Tests unitarios para domain y application.
- Mocks para cv2 y ffmpeg (VideoCapture, subprocess) para no depender de cámara/red.
- Skips condicionales si faltan dependencias.
- Validar que los pipelines respetan el orden; probar update_config con valores válidos e inválidos.

---

## 7. Extensiones (cómo añadir sin romper reglas)

- **Nuevo filtro:** Implementar protocolo Filter en `adapters/processors/filters/`; añadir a FilterPipeline.
- **Nuevo output:** Implementar OutputSink en `adapters/outputs/` (open, write, close); usar como sink del engine.
- **Nueva fuente:** Implementar FrameSource en `adapters/sources/` (open, read, close).
- **Nuevo renderer:** Implementar FrameRenderer (output_size, render); usar set_renderer o constructor.
- No inventar nuevas capas ni conceptos no presentes en ARCHITECTURE ni en este documento; si algo falta, preguntar antes de añadir.

---

## 8. Benchmarks y métricas

- Cuando el pipeline esté estable: medir FPS, latencia end-to-end (p50/p95), frames dropped, memoria/CPU.
- Usar `infrastructure/profiling.LoopProfiler` para cuellos de botella por fase (capture, analysis, filter, render, write).
- Documentar resultados en tabla (configuración, FPS, latencia, memoria, CPU).

---

## 9. Graveyard/docs como referencia

- `graveyard/docs/` no es la fuente de verdad ejecutable; es documentación archivada.
- Las reglas activas están en `rules/` (ARCHITECTURE.md, MVP_INDEX.md, MVP_*.md, mission.md, este archivo).
- Para dudas de diseño (capas, pipeline, C++, buenas prácticas) se puede consultar graveyard/docs; las decisiones que cuentan son las reflejadas en rules/.
