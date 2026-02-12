# Plan Maestro V1 — Spatial-Iteration-Engine

**Objetivo V1**: Integrar percepción visual con IA liviana para generar vistas deformadas y arte reactivo usando cámaras en vivo.

**Hardware objetivo**: Laptop Intel UHD 620 (integrada, sin CUDA).

**Fecha**: Febrero 2025

---

## 1. ARQUITECTURA TÉCNICA DETALLADA

### 1.1 Visión general

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONTROL-PLANE (Python)                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Detección    │ │ Segmentación │ │ Arte-Vector  │ │ Integración  │            │
│  │ (personas)   │ │ (silueta)    │ │ (estética)   │ │ (percepciones│            │
│  │ ONNX         │ │ ONNX         │ │ ONNX         │ │ → parámetros)│            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
│         │                │                │                │                     │
│         └────────────────┴────────────────┴────────────────┘                     │
│                                    │                                              │
│                           PerceptionBuffer (shared)                               │
│                                    │                                              │
│         ParameterUpdate, FrameInputBinding (via RuntimeBinding)                    │
└────────────────────────────────────┼─────────────────────────────────────────────┘
                                     │ pybind11 / shared memory
┌────────────────────────────────────┼─────────────────────────────────────────────┐
│                         RUNTIME (C++)                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                              │
│  │ engine/io    │→│ engine/core  │→│ engine/gpu   │                              │
│  │ Camera Ingest│ │ Scheduler    │ │ Warp, Blur,  │                              │
│  │ FFmpeg       │ │ Buffers      │ │ Feedback,    │                              │
│  │              │ │ Tick/frame   │ │ Deformación  │                              │
│  └──────────────┘ └──────────────┘ └──────────────┘                              │
│                                    │                                              │
│                                    ▼                                              │
│                           Present / Output                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Roles Python vs C++

| Capa | Rol | Responsabilidades |
|------|-----|-------------------|
| **Python** | Control-plane, IA, orquestación | Cargar modelos ONNX, inferencia, analizar frames, producir parámetros y percepciones |
| **C++** | Runtime, render, geometría | Scheduler por frame, buffers GPU, shaders de deformación, presentación |
| **Regla crítica** | Sin píxeles en Python en ruta runtime | Python no procesa píxeles en el camino crítico: produce *percepciones* (bboxes, máscaras binarias, vectores); C++ aplica deformaciones sobre texturas GPU |

### 1.3 Módulos y ubicación

| Módulo | Ubicación | Lenguaje |
|--------|-----------|----------|
| Detección (personas) | `ascii_stream_engine/adapters/processors/analyzers/detection.py` | Python |
| Segmentación (silueta) | `ascii_stream_engine/adapters/processors/analyzers/segmentation.py` | Python |
| Arte-Vector | `ascii_stream_engine/adapters/processors/analyzers/art_vector.py` | Python |
| Integración percepciones | `ascii_stream_engine/application/services/perception_integrator.py` | Python |
| Runtime (scheduler, buffers) | `engine/core/` | C++ |
| Shaders (deformación) | `engine/gpu/` | C++ / GLSL |
| Ingest/Egress | `engine/io/` | C++ |
| Bindings Python↔C++ | `engine/bindings/` | pybind11 + C++ |

---

## 2. INTERFACES MÍNIMAS

### 2.1 Python — Módulo Detección

```python
# Port: ascii_stream_engine/ports/processors.py (extender Analyzer)
# Adapter: .../analyzers/detection.py

class PersonDetector(Protocol):
    name: str = "person_detector"
    enabled: bool = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict:
        """
        Returns:
            {
                "detections": [{"label": str, "confidence": float, "bbox": (x,y,w,h), "class_id": int}],
                "processing_time_ms": float,
            }
        """
        ...
```

**Signature sugerida para implementación ONNX**:
```python
def __init__(self, model_path: Path, input_size: Tuple[int,int] = (320,320), conf_threshold: float = 0.5) -> None
def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict
```

### 2.2 Python — Módulo Segmentación

```python
# Port: Analyzer
# Adapter: .../analyzers/segmentation.py

class SilhouetteSegmenter(Protocol):
    name: str = "silhouette_segmenter"
    enabled: bool = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict:
        """
        Returns:
            {
                "mask": np.ndarray,  # H×W, uint8, 0=bg, 255=fg
                "processing_time_ms": float,
            }
        """
        ...
```

**Signature sugerida**:
```python
def __init__(self, model_path: Path, input_size: Tuple[int,int] = (256,256)) -> None
def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict
```

### 2.3 Python — Módulo Arte-Vector

```python
# Port: Analyzer
# Adapter: .../analyzers/art_vector.py

class ArtVectorExtractor(Protocol):
    name: str = "art_vector_extractor"
    enabled: bool = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict:
        """
        Returns:
            {
                "vector": np.ndarray,  # shape (D,) float32, embeddings estilísticos
                "processing_time_ms": float,
            }
        """
        ...
```

**Signature sugerida**:
```python
def __init__(self, model_path: Path, vector_dim: int = 64) -> None
def analyze(self, frame: np.ndarray, config: EngineConfig) -> dict
```

### 2.4 Python — Integrador de Percepciones

```python
# Application layer
# ascii_stream_engine/application/services/perception_integrator.py

class PerceptionIntegrator(Protocol):
    def integrate(
        self,
        detection_result: dict,
        segmentation_result: dict,
        art_vector_result: dict,
        frame_index: int,
    ) -> Sequence[ParameterUpdate]:
        """
        Combina percepciones y produce ParameterUpdate para el nodo warp/deformación.
        """
        ...
```

**Signature sugerida**:
```python
def integrate(
    self,
    detections: List[Detection],
    mask: Optional[np.ndarray],
    art_vector: Optional[np.ndarray],
    frame_index: int,
) -> Sequence[ParameterUpdate]
```

### 2.5 C++ — Extensión del Runtime Graph

El grafo existente (`RuntimeGraphSpec`) se extiende con nodos que consumen percepciones:

- **Nodo `warp_perception`**: recibe parámetros vía `ParameterUpdate` (coeficientes de deformación derivados de bboxes, máscara, vectores).
- **Nodos existentes**: `warp`, `blur`, `feedback` — se mantienen.

**Nuevos parámetros por nodo** (ejemplo para `warp_perception`):

| Parámetro | Tipo | Origen |
|-----------|------|--------|
| `perspective_pts` | `[float x8]` | bbox principal + máscara |
| `intensity_factor` | `float` | art_vector[0..3] |
| `warp_strength` | `float` | confianza detección |

### 2.6 C++ — RuntimeBinding (sin cambios)

La interfaz `RuntimeBinding` existente ya soporta:
- `update_parameters(updates: Sequence[ParameterUpdate])`
- `push_inputs(inputs: Sequence[FrameInputBinding])`
- `tick(frame_index, frame_time_seconds)`

Se usa tal cual. Python envía `ParameterUpdate` por frame con los valores derivados de las percepciones.

---

## 3. COMUNICACIÓN PYTHON ↔ C++

### 3.1 Estrategia recomendada: **Buffers compartidos + ParameterUpdate**

| Dato | Mecanismo | Formato |
|------|-----------|---------|
| Parámetros (warp, blur, etc.) | `ParameterUpdate` via pybind11 | Struct serializable (node_id, param_name, value) |
| Frame de cámara | `FrameInputBinding` + buffer compartido o transferencia GPU | Ya contemplado en diseño actual |
| Máscara de segmentación | Buffer compartido (opcional) o downsampled | Si C++ necesita máscara: buffer `uint8 H×W` compartido |

### 3.2 Opciones de implementación

| Opción | Pros | Contras |
|--------|------|---------|
| **A. Solo ParameterUpdate** | Simple, sin nueva infra | Máscara debe reducirse a unos pocos coeficientes en Python |
| **B. Shared memory para máscara** | C++ puede deformar según silueta pixel-level | Más complejidad, sincronización |
| **C. Textura GPU compartida** | Mínimas copias si ambos acceden a GPU | Requiere OpenGL/Vulkan interop, más setup |

**Recomendación V1**: Opción A. Python resume la máscara en parámetros (centroide, área, bounding box aproximada, momento de inercia) y envía como `ParameterUpdate`. Esto mantiene latencia baja y evita buffers grandes.

### 3.3 Formato de datos intercambiados

- **ParameterUpdate**: `{node_id: str, param_name: str, value: ParamValue}` — ya definido.
- **ParamValue**: `Union[bool, int, float, str, Sequence[Scalar]]` — soporta listas de floats para `perspective_pts`, etc.
- **FrameInputBinding**: `{stream_id, resource_id, timestamp_seconds, frame_token}` — ya definido.

---

## 4. DEPENDENCIAS EXTERNAS

### 4.1 Python

| Paquete | Versión | Uso |
|---------|---------|-----|
| onnxruntime | ≥1.16 | Inferencia ONNX (CPU, ExecutionProvider recomendado) |
| numpy | ≥1.24 | Arrays |
| opencv-python | ≥4.8 | Preprocesamiento (resize, BGR→RGB) |
| (existentes) | — | opencv, numpy, pillow, pyyaml, etc. |

### 4.2 C++

| Dependencia | Versión | Uso |
|-------------|---------|-----|
| CMake | ≥3.18 | Build |
| OpenGL | 3.3+ o ES 3.0 | Render (Intel UHD 620 compatible) |
| Vulkan | 1.1+ (opcional) | Alternativa a OpenGL |
| FFmpeg | ≥5.0 | Ingest/Egress |
| pybind11 | ≥2.10 | Bindings Python↔C++ |

### 4.3 Compatibilidad Intel UHD 620

- OpenGL 4.5 compatible.
- Vulkan 1.1 soportado.
- Sin CUDA → ONNX Runtime en CPU (ExecutionProvider: `CPUExecutionProvider`).
- Resolución sugerida para 30 fps: 720p (1280×720) o 640×480 en modo bajo consumo.

---

## 5. PLAN DE TRABAJO (PASOS NUMERADOS)

### Fase 0 — Preparación
1. Crear rama `cursor/planificacion-inicial-v1-2d45` (ya existente).
2. Actualizar `requirements.txt` con `onnxruntime`.
3. Definir estructura de carpetas para modelos ONNX (`models/` o descarga bajo demanda).
4. Configurar CMake para engine C++ con OpenGL y pybind11.

### Fase 1 — Módulos de IA (Python)
5. Implementar `PersonDetector` con YOLO-nano ONNX (o similar).
6. Implementar `SilhouetteSegmenter` con modelo ONNX liviano.
7. Implementar `ArtVectorExtractor` con modelo de embeddings.
8. Tests unitarios por módulo (mock de frame, assert de formato de salida).
9. Benchmarks de latencia por modelo (objetivo: <15 ms cada uno en CPU, total <50 ms).

### Fase 2 — Integración de percepciones
10. Implementar `PerceptionIntegrator` que combine salidas de los 3 analizadores.
11. Mapeo percepciones → `ParameterUpdate` (fórmulas concretas para warp_strength, perspective_pts, etc.).
12. Integrar en pipeline existente (AnalyzerPipeline + nuevo stage de integración).
13. Tests de integración: pipeline con mocks de analizadores → verificar ParameterUpdate correctos.

### Fase 3 — Runtime C++
14. Implementar nodo `warp_perception` en engine/gpu que acepte parámetros de deformación.
15. Conectar `ParameterUpdate` desde Python al runtime vía bindings.
16. Validar flujo: Python tick → C++ tick → frame deformado.
17. Benchmark de latencia de tick completo (objetivo: <33 ms para 30 fps).

### Fase 4 — Pipeline completo
18. Conectar cámara → analizadores → integrador → runtime C++ → presentación.
19. Pruebas en hardware Intel UHD 620.
20. Ajustar resolución, frecuencia de inferencia (cada N frames) según performance.
21. Documentar configuración recomendada para V1.

### Fase 5 — Tests y benchmarks
22. Tests unitarios de cada módulo.
23. Test de integración end-to-end (stream simulado → salida deformada).
24. Benchmark report: latencia por etapa, FPS alcanzado, uso de CPU/GPU.
25. Documentar riesgos mitigados y limitaciones conocidas.

---

## 6. RIESGOS TÉCNICOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Intel UHD 620 no alcanza 30 fps | Media | Alto | Resolución 640×480, inferencia cada 2–3 frames, shaders simples |
| Latencia ONNX CPU excesiva | Media | Alto | Modelos ultra-livianos (nano), quantización int8, input size pequeño |
| Pybind11 + buffers complejos | Baja | Medio | Empezar solo con ParameterUpdate; buffers compartidos en iteración posterior |
| Modelo de arte no disponible | Alta | Medio | Fallback: vector constante o extracción por color/histograma |
| Incompatibilidad OpenGL/Vulkan en Linux | Baja | Alto | Tener path OpenGL como default; Vulkan como opcional |
| Segmentación demasiado lenta | Media | Medio | Usar modelo muy pequeño (MobileNet-Seg) o saltear frames |

---

## 7. INDICACIONES DE PRUEBAS Y BENCHMARKS

### 7.1 Tests unitarios

- **PersonDetector**: Frame fijo con persona → assert `detections` no vacío, bbox dentro de imagen.
- **SilhouetteSegmenter**: Frame con silueta clara → assert `mask` shape correcto, valores 0/255.
- **ArtVectorExtractor**: Cualquier frame → assert `vector` shape (D,), dtype float32.
- **PerceptionIntegrator**: Entrada mock → assert `ParameterUpdate` con keys esperados.

### 7.2 Benchmarks

- **Por modelo**: tiempo de inferencia (p50, p99) en CPU, 100 iteraciones.
- **Pipeline completo**: frame → análisis completo → ParameterUpdate en ms.
- **Runtime C++**: `tick()` time en ms, FPS medido.
- **End-to-end**: cámara live → salida, FPS y latencia visual.

### 7.3 Criterios de aceptación V1

- [ ] Flujo funcional: cámara → IA → motor → visual deformado.
- [ ] ≥25 fps en 720p en Intel UHD 620 (30 fps en 640×480).
- [ ] Latencia total <100 ms desde captura hasta frame mostrado.
- [ ] Tests unitarios pasando.
- [ ] Documentación de configuración y límites.

---

## 8. ESPECIFICACIONES POR MÓDULO

### 8.1 Módulo Detección

| Campo | Especificación |
|-------|----------------|
| **Input** | `np.ndarray` H×W×3, BGR, uint8 |
| **Output** | `dict` con `detections: List[{label, confidence, bbox, class_id}]`, `processing_time_ms` |
| **Formato bbox** | `(x, y, width, height)` en píxeles, origen esquina superior izquierda |
| **Performance** | <20 ms por frame en CPU (Intel i5 típico) |
| **Límites** | Máximo 10 detecciones por frame; class_id persona = 0 (definido por modelo) |
| **Pruebas** | Test con imagen COCO/visión con persona; test con imagen sin persona |

### 8.2 Módulo Segmentación

| Campo | Especificación |
|-------|----------------|
| **Input** | `np.ndarray` H×W×3, BGR, uint8 |
| **Output** | `dict` con `mask: np.ndarray` H×W uint8 (0/255), `processing_time_ms` |
| **Resolución máscara** | Puede ser menor que input (ej. 128×128); upscale en Python si se requiere |
| **Performance** | <15 ms por frame en CPU |
| **Límites** | Máscara binaria (foreground/background) |
| **Pruebas** | Test con persona centrada; assert shape; test performance |

### 8.3 Módulo Arte-Vector

| Campo | Especificación |
|-------|----------------|
| **Input** | `np.ndarray` H×W×3, BGR, uint8 |
| **Output** | `dict` con `vector: np.ndarray` shape (D,) float32, `processing_time_ms` |
| **Dimensión D** | 32–128 (configurable) |
| **Performance** | <15 ms por frame en CPU |
| **Límites** | Vector normalizado (opcional) |
| **Pruebas** | Assert shape y dtype; test que frames similares den vectores cercanos (opcional) |

### 8.4 Módulo Integración

| Campo | Especificación |
|-------|----------------|
| **Input** | `detections`, `mask`, `art_vector`, `frame_index` |
| **Output** | `Sequence[ParameterUpdate]` |
| **Lógica** | Mapear bbox principal → perspective_pts; mask → warp_strength/intensity; art_vector → color/estilo |
| **Performance** | <1 ms (solo cálculos ligeros) |
| **Pruebas** | Assert ParameterUpdate para nodo warp; tests con edge cases (sin detecciones, máscara vacía) |

### 8.5 Módulo Render (C++)

| Campo | Especificación |
|-------|----------------|
| **Input** | Textura de cámara, ParameterUpdate (perspective_pts, warp_strength, etc.) |
| **Output** | Textura deformada para presentación |
| **Performance** | <10 ms por frame para warp + blur + feedback en 720p |
| **Límites** | Shaders GLSL 330+ compatibles con Intel UHD 620 |
| **Pruebas** | Test de render con parámetros fijos; benchmark de tick |

---

## 9. MODELOS IA Y RUNTIME

### 9.1 Detección — YOLO-nano / variante liviana

| Atributo | Valor |
|----------|-------|
| **Modelo** | YOLOv8-nano ONNX o YOLOv5-nano (export ONNX) |
| **Input** | 320×320 o 640×640 (menor = más rápido) |
| **Output** | Boxes (x,y,w,h), scores, class_ids |
| **Ejecución** | `ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])` |
| **Preproceso** | Resize, BGR→RGB, normalize [0,1], NCHW |
| **Postproceso** | NMS en Python (opcional cv2.dnn.NMSBoxes) |
| **Alimenta motor** | bbox principal → `perspective_pts`, `warp_strength` por confianza |

### 9.2 Segmentación — Segmentador liviano

| Atributo | Valor |
|----------|-------|
| **Modelo** | DeepLabV3-MobileNet o similar ONNX, o segmentación de persona (segformer-b0) |
| **Alternativa** | SAM Tiny (si disponible ONNX) o modelo custom entrenado |
| **Input** | 256×256 o 512×512 |
| **Output** | Logits o máscara H×W |
| **Ejecución** | ONNX Runtime CPU |
| **Postproceso** | Argmax o threshold → máscara binaria uint8 |
| **Alimenta motor** | Centroide, área normalizada → `ParameterUpdate` |

### 9.3 Pose estimation

| Atributo | Valor |
|----------|-------|
| **Modelo** | MoveNet Lightning o MediaPipe Pose (export ONNX) |
| **Input** | 192×192 típico |
| **Output** | Keypoints (x,y,confidence) por persona |
| **Uso en V1** | Opcional: keypoints pueden guiar deformación (ej. manos, cabeza) |
| **Prioridad** | Secundaria si hay tiempo; puede omitirse en MVP |

### 9.4 Modelo de arte (embeddings estilísticos)

| Atributo | Valor |
|----------|-------|
| **Modelo** | Red pequeña (MLP/CNN) entrenada en embeddings de obras de arte |
| **Fallback** | Si no hay modelo: histograma de color, promedios por región, o vector constante |
| **Input** | Frame redimensionado (224×224 típico para CNN) |
| **Output** | Vector (D,) float32 |
| **Alimenta motor** | `intensity_factor`, `color_tint`, etc. desde componentes del vector |

### 9.5 Resumen de ejecución ONNX

```python
import onnxruntime as ort

session = ort.InferenceSession(
    "model.onnx",
    providers=["CPUExecutionProvider"],
    sess_options=ort.SessionOptions(),
)
session.set_providers(["CPUExecutionProvider"])

# Inferencia
outputs = session.run(None, {"images": input_tensor})
```

---

## 10. HERRAMIENTAS Y CONFIGURACIÓN

- **Build C++**: CMake, compilador GCC/Clang.
- **Python**: venv con Python 3.10+.
- **Configuración**: YAML/JSON para paths de modelos, resoluciones, umbrales (extender `EngineConfig` o crear `PerceptionConfig`).
- **Logging**: Usar infraestructura existente (`ascii_stream_engine/infrastructure/logging.py`).
- **Métricas**: Extender `metrics.py` para tiempos de inferencia y FPS.

---

## 11. RESUMEN EJECUTIVO

La V1 integra:

1. **Tres analizadores Python** (detección, segmentación, arte-vector) con ONNX Runtime en CPU.
2. **Un integrador** que traduce percepciones en `ParameterUpdate` para el runtime C++.
3. **Runtime C++** existente extendido con nodo `warp_perception` que aplica deformaciones según parámetros.
4. **Comunicación** vía `ParameterUpdate` (pybind11) sin buffers de píxeles grandes en el camino crítico.
5. **Objetivo**: 30 fps en Intel UHD 620 con flujo cámara → IA → motor → visual deformado.

**Próximo paso**: Confirmar este plan antes de generar código. Ajustes sugeridos o preguntas pueden documentarse como comentarios en este archivo.
