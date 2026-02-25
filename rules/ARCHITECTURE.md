# 1. Qué es este proyecto
# System Architecture (Authoritative)

This file defines what exists in the system.
If something is not listed here, it does not exist.
All agents must obey this architecture.

Este proyecto es un motor de procesamiento audiovisual en tiempo real que permite construir pipelines de análisis, transformación y renderizado de streams (cámaras, video, red, archivos) usando una arquitectura modular y extensible, combinando Python y C++.

# 2. Qué problema resuelve

- Orquestar flujos de video complejos en tiempo real
- Permitir filtros de alto rendimiento en C++
- Permitir análisis semántico en Python
- Emitir resultados en múltiples formatos (ASCII, NDI, RTSP, notebooks, etc.)
- Facilitar experimentación visual y perceptual

# 3. Módulos que existen

## Núcleo (canónico)
- python/ascii_stream_engine
  - domain (tipos, eventos, config)
  - application (engine, pipeline, orquestación)
  - infrastructure (event bus, logging, plugins)
  - ports (interfaces de sensores, filtros, outputs)
  - adapters (implementaciones concretas)
  - presentation (API notebooks)

## Backend de alto rendimiento
- cpp/src/filters (implementaciones reales)
- cpp/src/bridge (pybind11)

## Datos y modelos
- data/
- onnx_models/

## Ejecución
- run_preview.sh
- run_basic_stream.sh

# 4. Flujo de datos

Sensor / Source
   ↓
Pipeline
   ↓
Filters (Python o C++)
   ↓
Analyzers (perception, tracking)
   ↓
Renderers / Outputs (ASCII, RTSP, NDI, notebooks)

# 5. Qué NO existe todavía

- Un frontend visual dedicado
- Un editor gráfico de pipelines
- Persistencia de proyectos
- UI de control fuera de notebooks

# 6. Núcleo del sistema

El núcleo es el motor de pipeline en python/ascii_stream_engine/application que orquesta flujos de frames entre módulos desacoplados mediante puertos, eventos y adaptadores.

## 7. Temporal Infrastructure

### TemporalManager (`application/services/temporal_manager.py`)
Demand-driven temporal state service. Allocates nothing until filters declare needs via class attributes. Buffer sizes derived from `max()` of all active filter declarations.

Three temporal patterns:
- **Input ring buffer**: Previous input frames (for optical flow, delta frame). Depth = max(required_input_history) + 1 across active filters.
- **Output buffer**: Single previous processed frame (for feedback/accumulation effects).
- **Own state**: Filters like Physarum maintain their own internal state (trail_map) — not managed by TemporalManager.

Lazy computation: optical flow and delta frame computed on first access per frame, cached.

### FilterContext (`application/pipeline/filter_context.py`)
Dict-compatible wrapper providing lazy access to temporal + analysis data. Backwards compatible with existing `analysis.get("key")` patterns. Adds temporal properties: `previous_input`, `previous_output`, `optical_flow`, `delta_frame`.

### Temporal Declarations (`adapters/processors/filters/base.py`)
Class attributes on BaseFilter:
- `required_input_history: int = 0` — how many previous input frames needed
- `needs_previous_output: bool = False` — needs feedback loop
- `needs_optical_flow: bool = False` — needs shared optical flow
- `needs_delta_frame: bool = False` — needs input frame diff
