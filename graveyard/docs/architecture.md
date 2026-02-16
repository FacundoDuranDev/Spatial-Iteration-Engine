# Arquitectura hexagonal (Ports & Adapters)

Para el **flujo conceptual del pipeline V1** (Source → Perception → Semantic/Transformations → Visual Modifiers → Renderer → Output), ver [pipeline_architecture_v1.md](pipeline_architecture_v1.md).

## Objetivo
- Separar el core de negocio de dependencias externas.
- Facilitar pruebas y reemplazo de tecnología.
- Mantener límites claros entre capas.
- Proporcionar un motor de video modular y extensible.

## Estructura de Capas

### 1. Domain (Modelos Puros)
**Ubicación**: `ascii_stream_engine/domain/`

Contiene los modelos de dominio sin dependencias externas:
- `config.py`: Configuración del engine (EngineConfig)
- `types.py`: Tipos de datos (RenderFrame, etc.)
- `events.py`: Eventos del sistema
- `tracking_data.py`: Datos de tracking
- `frame_metadata.py`: Metadata de frames

**Regla**: No depende de ninguna otra capa.

### 2. Ports (Interfaces/Protocols)
**Ubicación**: `ascii_stream_engine/ports/`

Define los contratos (protocols) que debe implementar cada tipo de componente:
- `sources.py`: FrameSource
- `renderers.py`: FrameRenderer
- `outputs.py`: OutputSink
- `processors.py`: FrameProcessor, Filter, Analyzer, ProcessorPipeline
- `trackers.py`: ObjectTracker
- `transformations.py`: SpatialTransform
- `controllers.py`: Controller
- `sensors.py`: Sensor

**Regla**: Solo depende de `domain`.

### 3. Application (Casos de Uso y Orquestación)
**Ubicación**: `ascii_stream_engine/application/`

Contiene la lógica de negocio y orquestación:

#### 3.1 Engine Principal
- `engine.py`: StreamEngine - Motor principal que orquesta todo

#### 3.2 Pipelines
**Ubicación**: `application/pipeline/`
- `processor_pipeline.py`: Pipeline genérico reutilizable
- `analyzer_pipeline.py`: Pipeline de analizadores
- `filter_pipeline.py`: Pipeline de filtros
- `transformation_pipeline.py`: Pipeline de transformaciones espaciales
- `tracking_pipeline.py`: Pipeline de trackers

#### 3.3 Orquestación
**Ubicación**: `application/orchestration/`
- `pipeline_orchestrator.py`: Orquesta el flujo completo del pipeline
- `stage_executor.py`: Ejecuta cada etapa del pipeline con manejo de errores

#### 3.4 Servicios
**Ubicación**: `application/services/`
- `error_handler.py`: Manejo centralizado de errores
- `retry_manager.py`: Gestión de reintentos y reconexiones
- `frame_buffer.py`: Gestión de buffer de frames

**Regla**: Depende de `domain` y `ports`.

### 4. Adapters (Implementaciones Concretas)
**Ubicación**: `ascii_stream_engine/adapters/`

Implementaciones concretas de los protocols:

- `sources/`: Implementaciones de FrameSource (OpenCVCameraSource, etc.)
- `renderers/`: Implementaciones de FrameRenderer (AsciiRenderer, etc.)
- `outputs/`: Implementaciones de OutputSink (FfmpegUdpOutput, NDI, RTSP, WebRTC, etc.)
- `processors/`: Procesadores de frames
  - `filters/`: Filtros (BrightnessFilter, EdgeFilter, etc.)
  - `analyzers/`: Analizadores (FaceHaarAnalyzer, etc.)
- `trackers/`: Implementaciones de ObjectTracker
- `transformations/`: Implementaciones de SpatialTransform
- `controllers/`: Controladores externos (MIDI, OSC)
- `sensors/`: Sensores (Audio, Depth, etc.)
- `generators/`: Generadores de contenido

**Regla**: Depende de `ports` y `domain`.

### 5. Infrastructure (Servicios Transversales)
**Ubicación**: `ascii_stream_engine/infrastructure/`

Servicios compartidos:
- `event_bus.py`: Sistema de eventos
- `plugins.py`: Gestor de plugins
- `metrics.py`: Métricas del engine
- `profiling.py`: Profiling de performance
- `logging.py`: Configuración de logging
- `message_queue.py`: Cola de mensajes
- `performance/`: Optimizaciones de performance

### 6. Presentation (UI y Notebooks)
**Ubicación**: `ascii_stream_engine/presentation/`

Interfaces de usuario:
- `notebook_api.py`: API para notebooks Jupyter

## Flujo de Datos

```
FrameSource → PipelineOrchestrator → StageExecutor
    ↓
    ├─→ AnalyzerPipeline → análisis
    ├─→ TransformationPipeline → transformación espacial
    ├─→ FilterPipeline → filtrado
    ├─→ TrackingPipeline → tracking
    ├─→ FrameRenderer → renderizado
    └─→ OutputSink → salida
```

## Reglas de Dependencias

```
domain
  ↑
  ├── ports
  │     ↑
  │     ├── application
  │     │     ↑
  │     │     └── adapters
  │     │
  │     └── adapters
  │
  └── infrastructure
        ↑
        └── application
```

1. **domain** no depende de nadie.
2. **ports** depende solo de **domain**.
3. **application** depende de **domain** y **ports**.
4. **adapters** depende de **ports** y **domain**.
5. **infrastructure** puede ser usado por **application**.
6. **presentation** depende de **application** y **adapters** (o solo public API).

## Ventajas de esta Arquitectura

1. **Modularidad**: Cada componente tiene responsabilidades claras.
2. **Extensibilidad**: Fácil agregar nuevos procesadores, renderers, outputs.
3. **Testabilidad**: Componentes pueden testearse de forma aislada.
4. **Mantenibilidad**: Cambios tecnológicos localizados en adapters.
5. **Separación de Concerns**: Lógica de negocio separada de implementaciones.

## Ejemplo de Extensión

### Agregar un nuevo filtro:

1. Crear clase que implemente el protocolo `Filter` en `adapters/processors/filters/`:
```python
from ...ports.processors import Filter
from ...domain.config import EngineConfig
import numpy as np

class MyCustomFilter:
    name = "my_custom_filter"
    enabled = True
    
    def apply(self, frame: np.ndarray, config: EngineConfig, 
              analysis: Optional[dict] = None) -> np.ndarray:
        # Implementar lógica del filtro
        return processed_frame
```

2. Usar en el engine:
```python
from ascii_stream_engine.adapters.processors import MyCustomFilter
from ascii_stream_engine.application import FilterPipeline

filters = FilterPipeline([MyCustomFilter()])
engine = StreamEngine(..., filters=filters)
```

### Agregar un nuevo output:

1. Crear clase que implemente `OutputSink` en `adapters/outputs/`:
```python
from ...ports.outputs import OutputSink
from ...domain.config import EngineConfig
from ...domain.types import RenderFrame

class MyCustomOutput:
    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        # Inicializar output
        pass
    
    def write(self, frame: RenderFrame) -> None:
        # Escribir frame
        pass
    
    def close(self) -> None:
        # Cerrar output
        pass
```

2. Usar en el engine:
```python
from ascii_stream_engine.adapters.outputs import MyCustomOutput

output = MyCustomOutput()
engine = StreamEngine(..., sink=output)
```

## Empaquetado

- Exponer en `ascii_stream_engine/__init__.py` los elementos de uso público.
- Mantener paths internos para desarrollo y tests.
- Usar deprecation warnings para cambios de API.
