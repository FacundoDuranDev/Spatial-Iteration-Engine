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
                                                                                  


