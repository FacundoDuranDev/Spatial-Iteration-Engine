# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `feat(temporal)`: TemporalManager service — demand-driven temporal state with lazy buffer allocation
- `feat(pipeline)`: FilterContext — dict-compatible wrapper with temporal access for filters
- `feat(filters)`: CRT Glitch filter — scanlines, chromatic aberration, VHS tracking, screen tear, noise, barrel distortion (perception-reactive via optical flow)
- `feat(filters)`: Geometric Patterns filter — sacred geometry, Voronoi, Delaunay, Lissajous, strange attractors (landmark-reactive, trail accumulation)
- `feat(filters)`: Temporal declarations on BaseFilter (required_input_history, needs_optical_flow, needs_delta_frame, needs_previous_output)

### Changed
- `refactor(filters)`: Physarum — better defaults (4000 agents, 0.98 decay, adaptive normalization), delta frame as motion attractant
- `refactor(filters)`: OpticalFlowParticles — uses shared optical flow from TemporalManager (with private fallback)
- `feat(filters)`: Optical Flow Particles filter -- motion-reactive particle system (stateful)
- `feat(filters)`: Stippling / Pointillism filter -- LUT-cached dot placement effect
- `feat(filters)`: UV Math Displacement filter -- parametric math-based remap distortion
- `feat(filters)`: Edge-Aware Smoothing filter -- bilateral filter with blend control
- `feat(filters)`: Radial Collapse / Singularity filter -- polar coordinate remap distortion
- `feat(filters)`: Physarum Simulation Overlay filter -- slime mold simulation (C++ wrapper ready)
- `feat(filters)`: Boids / Flocking Particles filter -- flocking particle system (stateful)
- `feat(filters)`: C++ Physarum wrapper with Python fallback (`CppPhysarumFilter`)
- `feat(presentation)`: Advanced diagnostics panel (`build_advanced_diagnostics_panel`) with profiler stats, memory, CPU, error breakdown, auto-refresh
- `feat(presentation)`: Perception control panel (`build_perception_control_panel`) with per-analyzer toggles, confidence thresholds, model info, visualization mode
- `feat(presentation)`: Filter designer panel (`build_filter_designer_panel`) with per-filter parameter sliders, enable/disable checkboxes, clear all
- `feat(presentation)`: Output manager panel (`build_output_manager_panel`) with multi-sink configuration, add/remove sinks, status display
- `feat(presentation)`: Performance monitor panel (`build_performance_monitor_panel`) with latency budget visualization, FPS gauge, degradation suggestions, bottleneck detection
- `feat(presentation)`: Preset manager panel (`build_preset_manager_panel`) with save/load/delete named presets, JSON import/export
- `feat(presentation)`: Full dashboard (`build_full_dashboard`) combining all 7 panels in a tabbed interface
- `feat(presentation)`: Shared helpers: `_status_style` (module-level), `_periodic_refresh`, `_safe_engine_call`, `_make_labeled_section`
- Estructura de proyecto reorganizada con separación clara entre `python/` y `cpp/`
- Documentación de gitflow (`GITFLOW.md`) con reglas y buenas prácticas
- Sistema de changelog para tracking de cambios
- Módulos C++ con pybind11 para filtros y percepción
- Soporte para modelos ONNX en módulos de percepción
- Scripts de build para compilación de módulos C++
- `chore`: Configuración de pre-commit hooks (`.pre-commit-config.yaml`)
- `chore`: Configuración de editor (`.editorconfig`)
- `chore`: Makefile para automatización de tareas comunes
- `feat(cpp/perception)`: Integración completa de ONNX Runtime para inferencia real de IA
  - Módulo `perception_cpp` compilado con soporte ONNX Runtime
  - Detección de landmarks faciales, manos y pose usando modelos ONNX
  - Adapters Python (`FaceLandmarkAnalyzer`, `HandLandmarkAnalyzer`, `PoseLandmarkAnalyzer`) funcionando

### Changed
- Reorganización de código Python: `ascii_stream_engine` movido a `python/ascii_stream_engine/`
- Estructura de documentación: docs movidos a `graveyard/docs/` y nueva estructura en `docs/`
- Sistema de build: CMakeLists.txt actualizado con soporte para ONNX Runtime opcional
- `docs`: Actualización de GITFLOW.md con flujo simplificado (main, develop, feature/*)
- `refactor(python)`: Limpieza y optimización del notebook de ejemplo `notebook_full_control.ipynb`
- `chore(python)`: Actualización de dependencias en `pyproject.toml`
- `fix(cpp/perception)`: Corrección de detección de ONNX Runtime en CMakeLists.txt para entornos conda
- `fix(cpp/perception)`: Corrección de include path para `onnxruntime_cxx_api.h` en onnx_runner.cpp

### Fixed
- N/A

### Removed
- Archivos antiguos de `ascii_stream_engine/` en raíz (movidos a `python/`)
- Documentación antigua movida a `graveyard/`

---

## Tipos de Cambios

- **Added**: Para nuevas funcionalidades
- **Changed**: Para cambios en funcionalidades existentes
- **Deprecated**: Para funcionalidades que serán removidas
- **Removed**: Para funcionalidades removidas
- **Fixed**: Para correcciones de bugs
- **Security**: Para vulnerabilidades de seguridad

## Formato de Entradas

Cada entrada debe seguir este formato:

```markdown
### [Tipo]
- `tipo(alcance)`: Descripción del cambio
  - Detalles adicionales si son necesarios
  - Referencias a issues, PRs o MVPs
```

### Ejemplo

```markdown
### Added
- `feat(cpp/filters)`: Implementación de filtro de detección de bordes
  - Usa operador Sobel con umbrales configurables
  - Refs: MVP_02_CPP_FILTER, #42
```

## Proceso de Actualización

1. **Cada commit funcional** debe actualizar esta sección `[Unreleased]`
2. **Al hacer release**, mover `[Unreleased]` a una nueva sección con la versión
3. **Mantener orden cronológico**: Más reciente arriba
4. **Ser específico**: Incluir alcance y descripción clara

---

**Nota**: Este changelog se actualiza manualmente. Ver `GITFLOW.md` para más detalles sobre el proceso.

