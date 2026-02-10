# Arquitectura Runtime Audiovisual en Tiempo Real

## 1) Objetivo

Evolucionar `Spatial-Iteration-Engine` (actualmente `ascii_stream_engine`) hacia un runtime audiovisual en tiempo real, clase TouchDesigner/Notch, **sin reescribir desde cero** y preservando su ADN conceptual:

- iteraciones por frame,
- flujos de datos stateful,
- transformaciones espaciales,
- pipelines/nodos componibles.

Ecuación rectora:

`Frame(t+1) = Graph(Frame(t), Inputs, State)`

## 2) Restricciones no negociables

1. Mantener control de topología, parámetros y estado en Python (control-plane).
2. No convertir el sistema en scripts lineales ad-hoc.
3. No procesar píxeles en Python para la ruta runtime objetivo.
4. Evitar re-asignación de recursos GPU por frame.
5. Evitar llamadas bloqueantes en el loop de frame.

---

## 3) Mapeo del código actual a la arquitectura objetivo

### 3.1 Estado actual (resumen)

El proyecto actual implementa una arquitectura hexagonal madura (`domain`, `ports`, `application`, `adapters`, `infrastructure`) con orquestación por etapas:

`capture -> analysis -> transformation -> filtering -> render -> output`

Referencias clave:

- `ascii_stream_engine/application/engine.py` (`StreamEngine`)
- `ascii_stream_engine/application/orchestration/pipeline_orchestrator.py`
- `ascii_stream_engine/application/pipeline/*`
- `ascii_stream_engine/adapters/transformations/warp_transformer.py`
- `ascii_stream_engine/adapters/outputs/udp.py` (FFmpeg output)

### 3.2 Mapeo de responsabilidades

| Módulo actual | Rol actual | Rol en arquitectura objetivo |
|---|---|---|
| `application/engine.py` | loop principal, FPS, orquestación | **Python control-plane**: ciclo de control, telemetría, actualización de parámetros, sincronización de clock |
| `application/orchestration/pipeline_orchestrator.py` | secuenciación de etapas | **Compilador de grafo + scheduler input** (descripción de ejecución que consume C++) |
| `application/pipeline/*.py` | listas secuenciales de procesadores | **IR de grafo** (nodos/edges/resources) y compatibilidad con pipelines existentes |
| `adapters/transformations/*` | warp/perspectiva/blend en CPU | Definición de nodos equivalentes en GPU (`warp`, `mix`, `projection`) |
| `adapters/processors/filters/*` | filtros CPU | Definición de nodos GPU (`blur`, `edge`, `invert`, etc.) |
| `adapters/sources/camera.py` | captura OpenCV en CPU | Migrar a **ingest FFmpeg** y subida/interop GPU |
| `adapters/outputs/udp.py` | encode+send FFmpeg desde PIL bytes | Migrar a **encode/salida sobre superficie GPU** (evitando roundtrip Python) |
| `infrastructure/performance/gpu_accelerator.py` | wrapper best-effort | Fase transicional; reemplazable por runtime C++/GPU dedicado |
| `domain/config.py` | parámetros del motor | Fuente de verdad para parámetros runtime (map a uniforms/params GPU) |

---

## 4) Layout objetivo del runtime

```text
/engine
  /python    # control-plane: topología, parámetros, estado, feedback, IA futura
  /core      # C++ frame runtime: scheduler, buffers, ejecución de nodos
  /gpu       # shaders/kernels: warp, blur, feedback, blending, color
  /io        # FFmpeg ingest/egress, live input/output
  /bindings  # bridge Python <-> C++ (pybind11/cffi)
```

Principio: **Python describe y controla; C++ ejecuta; GPU procesa píxeles**.

---

## 5) Modelo de ejecución por frame

## 5.1 Clock

- Modo fixed: `target_dt = 1 / target_fps`.
- Modo adaptive: ajusta budget de nodos no críticos y resolución dinámica.
- Monotonic time y frame index global (`frame_id`).

## 5.2 Buffers

- `input ring`: frames entrantes (camera/video/live).
- `processing pool`: texturas intermedias persistentes por tamaño/formato.
- `output ring`: texturas listas para display/stream.

No se alocan texturas por frame salvo resize o cambio de formato.

## 5.3 Scheduler determinista

1. Compilar DAG por frame desde `RuntimeGraphSpec`.
2. Separar edges de feedback (`delay >= 1`) para evitar ciclos instantáneos.
3. Ejecutar nodos en orden topológico estable.
4. Resolver inputs:
   - input externo (camera/video/audio/osc),
   - output de nodos del frame actual,
   - feedback desde buffers del frame previo.
5. Commit de outputs + swap de buffers de feedback.

---

## 6) Modelo de nodo runtime

Un nodo runtime debe cumplir:

- Inputs: handles de textura GPU.
- Outputs: handles de textura GPU.
- Parámetros: mutables desde Python (sin copiar imágenes por Python).
- Ejecución: dispatch C++ hacia shader/kernel.

Campos mínimos:

- `node_id`
- `op_type` (`warp`, `blur`, `feedback`, `mix`, `color`, etc.)
- `input_slots` / `output_slots`
- `param_schema` + `param_values`
- `state_policy` (stateless/stateful)
- `quality_policy` (budget-aware)

---

## 7) Diseño de módulos y clases (propuesto)

## 7.1 Python (`/engine/python`)

### `runtime_graph.py`

- `RuntimeGraphSpec`: nodos, edges, recursos, validación.
- `RuntimeNodeSpec`: contrato de nodo.
- `RuntimeEdgeSpec`: conexiones y feedback (`delay_frames`).
- `FrameClockConfig` / `RuntimeExecutionConfig`.

### `runtime_binding.py`

- `RuntimeBinding` (Protocol): interfaz mínima del backend C++.
- `FrameInputBinding`, `ParameterUpdate`, `FrameExecutionStats`.

### `migration_adapter.py`

- `LegacyPipelineToGraphAdapter`:
  - traduce pipelines actuales (`TransformationPipeline`, `FilterPipeline`) a `RuntimeGraphSpec`,
  - permite migración incremental sin romper API de `StreamEngine`.

## 7.2 Core C++ (`/engine/core`)

Componentes:

- `FrameRuntime`: ciclo principal por frame.
- `GraphScheduler`: ordenación topológica + colas de ejecución.
- `ResourceManager`: textura/buffer pools persistentes.
- `NodeExecutor`: dispatch de nodos sobre backend gráfico.
- `FeedbackStore`: estado temporal de nodos stateful.

## 7.3 GPU (`/engine/gpu`)

Shaders/kernels iniciales:

- `warp` (affine/perspective)
- `blur` (gaussian separable)
- `feedback` (mix con frame previo + decay)
- `mix`/`color` utilitarios

## 7.4 I/O (`/engine/io`)

- `FfmpegInput`: decode cámara/video hacia buffers aptos para GPU.
- `FfmpegOutput`: encode/salida live sin roundtrip Python.
- Soporte para live input/output y clock alignment.

## 7.5 Bindings (`/engine/bindings`)

- Bridge Python/C++ con pybind11/cffi.
- API de bajo acoplamiento: submit graph, update params, tick frame, collect stats.

---

## 8) Flujo de datos objetivo

```text
Python Control Plane
  ├─ define RuntimeGraphSpec
  ├─ updates de parámetros/estado
  └─ tick(clock) ───────────────────────────────┐
                                                 ▼
C++ Frame Runtime (determinista por frame)
  ├─ GraphScheduler (DAG + feedback delayed)
  ├─ ResourceManager (texture pools)
  ├─ NodeExecutor (dispatch GPU)
  └─ I/O bridge (FFmpeg ingest/egress)
                                                 ▼
GPU
  ├─ input textures
  ├─ warp -> blur -> feedback -> output
  └─ output texture(s)
```

---

## 9) Plan de migración incremental (sin reescritura total)

## Fase 0 - Baseline y contratos

- Congelar contratos de `ports/*` actuales.
- Instrumentar métricas de latencia por etapa y FPS efectivos.
- Identificar puntos de copia CPU<->CPU y CPU<->GPU.

## Fase 1 - Introducir IR de grafo en Python

- Agregar `RuntimeGraphSpec` y validador.
- Implementar `LegacyPipelineToGraphAdapter`.
- Mantener ejecución actual en Python como fallback.

## Fase 2 - Runtime C++ mínimo + binding

- Implementar scheduler determinista y gestor de recursos.
- Exponer binding para:
  - crear/actualizar grafo,
  - actualizar parámetros,
  - tick por frame,
  - leer stats.

## Fase 3 - MVP GPU nodes

Objetivo MVP obligatorio:

1. live camera input,
2. tres nodos GPU: `warp`, `blur`, `feedback`,
3. render continuo con FPS estable.

## Fase 4 - FFmpeg zero-copy path

- Sustituir ingest/salida CPU por path GPU-friendly.
- Evitar paso de píxel por objetos Python/PIL.
- Incorporar dobles/triples buffers para jitter control.

## Fase 5 - Consolidación

- Promover runtime C++/GPU a ruta por defecto.
- Mantener fallback CPU bajo feature flag.
- Deprecar gradualmente rutas legacy de pixel processing en Python.

---

## 10) Tradeoffs y racional técnico

1. **Complejidad adicional (binding + C++)**
   - costo: build/toolchain y debugging multi-capa.
   - beneficio: latencia y throughput reales de runtime audiovisual.

2. **Determinismo vs throughput máximo**
   - determinismo por frame simplifica reproducción/debug.
   - puede limitar optimizaciones agresivas out-of-order.

3. **Feedback stateful**
   - habilita lenguaje visual rico.
   - exige disciplina de recursos (double buffering y sincronización).

4. **Migración incremental vs big-bang rewrite**
   - incremental reduce riesgo y preserva valor actual del código.
   - coexistencia temporal de rutas CPU/GPU aumenta complejidad operativa.

5. **FFmpeg + GPU interop**
   - estándar robusto de I/O.
   - requiere ingeniería fina según backend (CUDA/Vulkan/Metal/D3D/VAAPI).

---

## 11) Criterios de aceptación del MVP

- `>= 30 FPS` estables en resolución objetivo definida para MVP.
- jitter de frame acotado (p95 dentro de presupuesto de frame).
- cero copias de píxel a través de Python en ruta runtime.
- nodos `warp`, `blur`, `feedback` ejecutando en GPU.
- parámetros ajustables desde Python en caliente.

---

## 12) Estrategia de compatibilidad con el engine actual

- `StreamEngine` se mantiene como API superior durante transición.
- `PipelineOrchestrator` migra a rol de *graph compiler/controller*.
- `TransformationPipeline`/`FilterPipeline` siguen siendo composición autoral,
  pero su ejecución se traduce a nodos runtime.
- Las rutas legacy CPU permanecen bajo flags para pruebas y rollback.

Esta estrategia preserva el diseño conceptual existente (iteración + flujo + espacio)
sin convertir el sistema en scripts lineales ni duplicar reimplementaciones masivas.
