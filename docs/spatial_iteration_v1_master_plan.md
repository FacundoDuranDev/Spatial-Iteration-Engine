# Plan Maestro V1: Spatial-Iteration-Engine

**Objetivo**: Implementación funcional mínima donde  
`stream de cámara → IA → motor → visual deformado en tiempo real`  
con performance usable en hardware integrado (Intel UHD 620, sin CUDA).

---

## 1. Arquitectura técnica detallada

### 1.1 Diagrama de alto nivel

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PYTHON (Control-Plane / IA)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│  [Fuente] → [Detección] → [Segmentación] → [Pose] → [Arte-Vector] → [Integrador] │
│     │            │              │            │            │              │       │
│     └────────────┴──────────────┴────────────┴────────────┴──────────────┘       │
│                                    │                                             │
│                          PercepciónIA (resultados)                               │
│                                    │                                             │
│                    ┌───────────────▼───────────────┐                             │
│                    │  Shared Memory / IPC Buffer   │                             │
│                    │  (FrameMetadata + Máscaras +  │                             │
│                    │   Vectores estéticos)         │                             │
│                    └───────────────┬───────────────┘                             │
└────────────────────────────────────┼────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────────┐
│                          C++ (Data-Plane / Render)                               │
├────────────────────────────────────┼────────────────────────────────────────────┤
│                                    ▼                                             │
│  [IO Ingest] → [ResourceManager] → [GraphScheduler] → [NodeExecutor] → [Output]  │
│                     │                    │                   │                   │
│                     └────────────────────┴───────────────────┘                   │
│                                    │                                             │
│                          GPU (Vulkan/OpenGL)                                      │
│                    warp · blur · feedback · deform                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Principios de diseño

| Principio | Aplicación |
|-----------|------------|
| **Python no procesa píxeles** | IA y orquestación en Python; buffers de video nunca cruzan el boundary |
| **C++ ejecuta el loop de frame** | Scheduler determinista, pools de texturas, dispatch GPU |
| **Percepción como metadata** | Detecciones, máscaras, vectores se pasan como estructuras compactas |
| **Zero-copy en ruta crítica** | Shared memory para metadata; FFmpeg/libav para ingest sin paso por Python |
| **GPU integrada friendly** | OpenGL ES 3.1 / Vulkan 1.1 mínimo; sin CUDA; texturas reutilizables |

### 1.3 Layout de directorios propuesto

```
/spatial_iteration_engine/           # Raíz del proyecto V1
├── python/                          # Control-plane + IA
│   ├── perception/                  # Módulos de percepción IA
│   │   ├── detection/               # Detección de personas (YOLO)
│   │   ├── segmentation/            # Segmentación de silueta
│   │   ├── pose/                    # Pose estimation
│   │   └── art_vector/              # Embeddings estilísticos
│   ├── integration/                 # Integrador percepción → motor
│   ├── orchestration/               # Orquestación y clock
│   └── bindings/                    # Cliente del puente Python↔C++
├── engine/                          # Runtime C++ (existente, evoluciona)
│   ├── core/                        # Scheduler, buffers, ejecución
│   ├── gpu/                         # Shaders warp, blur, feedback, deform
│   ├── io/                          # Ingest/egress FFmpeg
│   └── bindings/                    # pybind11 → Python
├── shared/                          # Estructuras compartidas Python↔C++
│   └── perception_protocol/         # Schemas de datos intercambiados
├── models/                          # Modelos ONNX (.onnx)
├── tests/
└── benchmarks/
```

---

## 2. Módulos con interfaces mínimas

### 2.1 Python: módulos de percepción

#### Módulo `detection`

| Elemento | Descripción |
|----------|-------------|
| **Input** | `np.ndarray` (H×W×3, RGB/BGR, uint8), resolución típica 320×240–640×480 |
| **Output** | `List[Detection]` donde `Detection = {bbox, class_id, confidence}` |
| **Interface** | `detect(frame: np.ndarray, config: DetectionConfig) -> List[Detection]` |
| **Dependencias** | `onnxruntime`, `numpy` |

```python
# Signature sugerida
def detect(frame: np.ndarray, config: DetectionConfig) -> List[Detection]:
    """Detecta personas en el frame. Retorna cajas y scores."""
```

#### Módulo `segmentation`

| Elemento | Descripción |
|----------|-------------|
| **Input** | `np.ndarray` (H×W×3), mismo rango de resolución |
| **Output** | `np.ndarray` (H×W) uint8, máscara de persona (0=bg, 255=fg) |
| **Interface** | `segment(frame: np.ndarray, config: SegConfig) -> np.ndarray` |
| **Dependencias** | `onnxruntime`, `numpy` |

```python
def segment(frame: np.ndarray, config: SegConfig) -> np.ndarray:
    """Retorna máscara binaria/soft de silueta de persona."""
```

#### Módulo `pose`

| Elemento | Descripción |
|----------|-------------|
| **Input** | `np.ndarray` (H×W×3), opcionalmente recortado a persona |
| **Output** | `PoseResult`: lista de keypoints `[{x, y, confidence}, ...]` |
| **Interface** | `estimate_pose(frame: np.ndarray, config: PoseConfig) -> PoseResult` |
| **Dependencias** | `onnxruntime`, `numpy` |

```python
def estimate_pose(frame: np.ndarray, config: PoseConfig) -> PoseResult:
    """Retorna keypoints corporales (COCO/MPII style)."""
```

#### Módulo `art_vector`

| Elemento | Descripción |
|----------|-------------|
| **Input** | `np.ndarray` (H×W×3), frame o patch |
| **Output** | `np.ndarray` (D,) float32, embedding estilístico |
| **Interface** | `extract_style(frame: np.ndarray, config: ArtConfig) -> np.ndarray` |
| **Dependencias** | `onnxruntime`, `numpy` |

```python
def extract_style(frame: np.ndarray, config: ArtConfig) -> np.ndarray:
    """Extrae vector de estilo estético (D dims, ej. 128–256)."""
```

#### Módulo `integration`

| Elemento | Descripción |
|----------|-------------|
| **Input** | Resultados de detection, segmentation, pose, art_vector |
| **Output** | `PerceptionFrame` serializable para C++ |
| **Interface** | `integrate(det, seg, pose, art) -> PerceptionFrame` |

```python
def integrate(
    detections: List[Detection],
    mask: np.ndarray,
    pose: PoseResult,
    art_vector: np.ndarray,
    frame_id: int,
) -> PerceptionFrame:
    """Agrupa percepciones en estructura unificada para el motor."""
```

### 2.2 C++: interfaces del runtime

#### Core (`engine/core`)

| Componente | Responsabilidad | Interface C++ |
|------------|-----------------|---------------|
| `FrameRuntime` | Loop principal por frame | `void tick(PerceptionFrame const&)` |
| `GraphScheduler` | Orden topológico de nodos | `void schedule(GraphSpec const&)` |
| `ResourceManager` | Pools de texturas | `TextureHandle alloc(width, height)` |
| `NodeExecutor` | Dispatch de nodos GPU | `void execute(NodeSpec const&, Params const&)` |

#### GPU (`engine/gpu`)

| Nodo | Inputs | Output | Parámetros |
|------|--------|--------|------------|
| `warp` | tex_in | tex_out | transform 3×3, mask opcional |
| `blur` | tex_in | tex_out | radius, sigma |
| `feedback` | tex_in, tex_prev | tex_out | decay, mix |
| `deform` | tex_in, mask, pose | tex_out | intensity, kernel_size |

#### I/O (`engine/io`)

| Componente | Responsabilidad |
|------------|-----------------|
| `FfmpegInput` | Decode cámara → textura GPU (VAAPI/D3D11 si disponible) |
| `FfmpegOutput` | Encode textura → UDP/archivo |

### 2.3 Comunicación Python ↔ C++

#### Opción recomendada: Shared memory + pybind11

```
┌─────────────────────┐                    ┌─────────────────────┐
│ Python              │                    │ C++                 │
│                     │   Shared Memory    │                     │
│ PerceptionFrame ────┼───────────────────┼───► tick() consume   │
│ (struct layout)     │   (mmap / shm)     │                     │
│                     │                    │                     │
│ runtime.tick() ◄────┼─── return stats   │◄─── FrameRuntime     │
└─────────────────────┘                    └─────────────────────┘
```

**Formato de datos intercambiados:**

| Estructura | Uso |
|------------|-----|
| `PerceptionFrame` | Contenedor por frame: frame_id, timestamp, detections[], mask_handle, pose_keypoints[], art_vector[] |
| `Detection` | bbox[4], class_id, confidence |
| `PoseKeypoint` | x, y, confidence |
| `ArtVector` | float[D] |

**Opciones de implementación:**

| Método | Pros | Contras |
|--------|------|---------|
| **Shared memory (POSIX / mmap)** | Sin copia, baja latencia | Sincronización manual, multiplataforma con cuidado |
| **pybind11 + struct packed** | Simple, portable | Copia por llamada; aceptable si struct < ~100 KB |
| **ZeroMQ / IPC** | Desacopla procesos | Latencia y overhead para 30 fps |
| **Memoria compartida con semáforos** | Determinista | Más complejidad |

**Recomendación V1:** Empezar con **pybind11 + structs compactos** (PerceptionFrame serializado). Si la copia resulta costosa en benchmarks, migrar a shared memory con layout fijo.

**API de binding sugerida:**

```cpp
// C++ expuesto a Python
class RuntimeBinding {
public:
    void set_graph(GraphSpec const& spec);
    void update_params(ParamUpdates const& updates);
    void set_perception(PerceptionFrame const& frame);
    ExecutionStats tick();
};
```

```python
# Python
runtime = RuntimeBinding()
runtime.set_perception(perception_frame)
stats = runtime.tick()
```

---

## 3. Especificaciones por módulo

### 3.1 Módulo Detección

| Aspecto | Especificación |
|---------|----------------|
| **Input** | np.ndarray (H,W,3) uint8, BGR o RGB según modelo |
| **Output** | `List[Detection]`, cada uno: `bbox=(x1,y1,x2,y2)`, `class_id`, `confidence` |
| **Formato bbox** | Coordenadas absolutas en píxeles (frame original) |
| **Performance** | < 15 ms por frame en Intel UHD 620 @ 320×240 |
| **Límites** | Máx. 10 detecciones por frame (top-N por confidence) |
| **Pruebas unitarias** | Frame sintético con cuadrado → 1 detección; frame vacío → 0 |

### 3.2 Módulo Segmentación

| Aspecto | Especificación |
|---------|----------------|
| **Input** | np.ndarray (H,W,3) uint8 |
| **Output** | np.ndarray (H,W) uint8, valores 0 (background) o 255 (persona) |
| **Resolución** | Puede ser menor que input (ej. 160×120); upsample opcional |
| **Performance** | < 20 ms por frame @ 320×240 |
| **Límites** | Máscara compacta; si se pasa a C++, formato raw o RLE |
| **Pruebas unitarias** | Frame con persona centrada → máscara no vacía; frame vacío → máscara ceros |

### 3.3 Módulo Pose

| Aspecto | Especificación |
|---------|----------------|
| **Input** | np.ndarray (H,W,3), idealmente recortado a bbox de persona |
| **Output** | `PoseResult`: 17 keypoints (COCO) o 33 (MediaPipe), cada uno `(x, y, conf)` |
| **Coordenadas** | Absolutas respecto al frame de entrada |
| **Performance** | < 10 ms por persona @ 256×256 |
| **Límites** | 1 persona por frame (la de mayor confidence en detección) |
| **Pruebas unitarias** | Pose conocido en imagen sintética → keypoints dentro de tolerancia |

### 3.4 Módulo Arte-Vector

| Aspecto | Especificación |
|---------|----------------|
| **Input** | np.ndarray (H,W,3), puede ser frame completo o patch |
| **Output** | np.ndarray (D,) float32, D fijo (ej. 128) |
| **Performance** | < 25 ms por frame @ 224×224 |
| **Límites** | Normalización L2 para consistencia |
| **Pruebas unitarias** | Frames similares → distancia euclidiana baja; frames distintos → mayor |

### 3.5 Módulo Integración

| Aspecto | Especificación |
|---------|----------------|
| **Input** | Salidas de detection, segmentation, pose, art_vector |
| **Output** | `PerceptionFrame` serializable, < 100 KB típico |
| **Responsabilidad** | Alinear máscaras con coordenadas de detección; validar y rellenar faltantes |
| **Pruebas unitarias** | Integración de mocks → PerceptionFrame bien formado |

### 3.6 Módulo Render (C++/GPU)

| Aspecto | Especificación |
|---------|----------------|
| **Input** | Textura de cámara, PerceptionFrame (mask, pose, art_vector) |
| **Output** | Textura deformada lista para display/stream |
| **Nodos** | warp (afectado por pose), blur, feedback, deform (usa mask) |
| **Performance** | Pipeline completo < 33 ms (30 fps) en Intel UHD 620 |
| **Pruebas** | Benchmarks de cada nodo; test de integración con percepción mock |

---

## 4. Modelos IA y ONNX Runtime

### 4.1 Tabla de modelos

| Modelo | Tarea | Formato ONNX | Input | Output | Uso en motor |
|--------|-------|--------------|-------|--------|--------------|
| **YOLO-nano / YOLOv8-n** | Detección personas | .onnx | (1,3,H,W) FP32, H=W=320 o 416 | (1,N,6) [x,y,w,h,conf,class] | Bboxes para segmentación y pose |
| **Portrait/Person seg.** | Segmentación silueta | .onnx | (1,3,H,W) FP32 | (1,1,H,W) o (1,C,H,W) | Máscara para deformación |
| **MoveNet / MediaPipe Pose** | Pose estimation | .onnx | (1,3,256,256) FP32 | (1,17,3) keypoints | Deformaciones dirigidas por extremidades |
| **Arte (custom / CLIP-style)** | Embedding estético | .onnx | (1,3,224,224) FP32 | (1,D) FP32 | Parámetros de estilo (color, brush) |

### 4.2 Ejecución con ONNX Runtime

```python
# Patrón común
import onnxruntime as ort

session = ort.InferenceSession(
    "model.onnx",
    providers=["CPUExecutionProvider"],  # Intel UHD 620: CPU o DML/DirectML si Win
)
input_name = session.get_inputs()[0].name
output = session.run(None, {input_name: input_tensor})
```

**Consideraciones para Intel UHD 620:**
- `CPUExecutionProvider` es la opción más estable.
- `DmlExecutionProvider` (Windows) puede dar aceleración en GPU integrada; probar.
- Evitar `CUDAExecutionProvider` (no aplica).
- Inputs en FP32; algunos modelos pueden usar FP16 pero ONNX Runtime en CPU suele ser FP32.

### 4.3 Formatos de salida esperados

| Modelo | Formato raw ONNX | Post-procesamiento |
|--------|------------------|---------------------|
| YOLO | `(1, N, 6)` o `(1, 84, 8400)` (formato ultralytics) | NMS, filtrar class_id=0 (person), top-K |
| Segmentador | `(1, 1, H, W)` logits o `(1, C, H, W)` | Argmax/sigmoid → máscara uint8 |
| Pose | `(1, 17, 3)` o `(1, 51)` | Rescale a coordenadas originales |
| Arte | `(1, D)` | L2-normalize opcional |

### 4.4 Cómo alimentan al motor

```
PerceptionFrame {
  frame_id, timestamp
  detections[]     → C++: regiones de interés, selección de persona
  mask (handle)    → C++: texto de máscara o índice en pool compartido
  pose_keypoints[] → C++: uniforms para shaders de deformación
  art_vector[]     → C++: parámetros de color/estilo en shaders
}
```

El motor C++ lee `PerceptionFrame` cada tick y ajusta parámetros de nodos (warp, deform) según pose y máscara; art_vector modula paleta o intensidad.

---

## 5. Dependencias externas

### 5.1 Python

| Paquete | Versión | Uso |
|---------|---------|-----|
| Python | 3.10+ | Base |
| onnxruntime | 1.16+ | Modelos IA |
| numpy | 1.24+ | Arrays |
| opencv-python | 4.8+ | Captura cámara (alternativa a FFmpeg en Python) |
| pybind11 | 2.11+ | Bindings |
| PyYAML | 6.0+ | Configuración |

### 5.2 C++

| Dependencia | Versión | Uso |
|-------------|---------|-----|
| CMake | 3.20+ | Build |
| C++17 | - | Estándar mínimo |
| pybind11 | 2.11+ | Bindings |
| Vulkan SDK | 1.1+ | Render (o OpenGL 3.3) |
| FFmpeg (libav*) | 5.x+ | Ingest/egress |
| GLFW o SDL2 | - | Ventana y contexto |

### 5.3 Compatibilidad

| Componente | Intel UHD 620 | Notas |
|------------|---------------|-------|
| Vulkan | 1.1 | Drivers Intel recientes |
| OpenGL | 4.5 | Fallback si Vulkan falla |
| ONNX Runtime | CPU | DML opcional en Windows |
| FFmpeg | VAAPI (Linux) | Decode hardware si disponible |

---

## 6. Plan de trabajo numerado

### Fase 0: Preparación (1–2 semanas)

1. Crear estructura de directorios V1.
2. Configurar CMake con pybind11, Vulkan/OpenGL, FFmpeg.
3. Definir `PerceptionFrame` y estructuras compartidas (Python + C++).
4. Implementar binding mínimo: `RuntimeBinding.tick()` stub que retorna stats.

### Fase 1: Percepción IA en Python (2–3 semanas)

5. Integrar YOLO-nano/v8-n ONNX para detección de personas.
6. Integrar segmentador ONNX (silueta).
7. Integrar pose estimation ONNX.
8. Integrar modelo de arte/embedding ONNX.
9. Implementar módulo `integration` que produce `PerceptionFrame`.
10. Tests unitarios por modelo y para `integration`.

### Fase 2: Runtime C++ básico (2–3 semanas)

11. Implementar `ResourceManager` y pools de texturas.
12. Implementar `GraphScheduler` (DAG simple).
13. Implementar nodos GPU: warp, blur, feedback.
14. Implementar nodo `deform` que consume máscara y pose.
15. Implementar `FrameRuntime.tick(PerceptionFrame)`.
16. Conectar ingest FFmpeg a textura de entrada.

### Fase 3: Integración end-to-end (1–2 semanas)

17. Conectar Python perception loop a C++ via binding.
18. Sincronizar clock: Python produce PerceptionFrame a 30 fps; C++ consume.
19. Implementar salida (display + opcional UDP).
20. Tests de integración y benchmarks.

### Fase 4: Optimización y estabilidad (1 semana)

21. Perfil y optimizar cuellos de botella (ONNX, copias, GPU).
22. Ajustar resolución y calidad para 30 fps en UHD 620.
23. Documentar configuración y uso.

---

## 7. Riesgos técnicos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| ONNX en CPU demasiado lento para 30 fps | Alta | Alto | Reducir resolución de modelos; ejecutar perception cada 2 frames; modelos más pequeños |
| Vulkan inestable en Intel UHD 620 | Media | Alto | Fallback a OpenGL 3.3; probar drivers actualizados |
| Latencia de copia Python↔C++ | Media | Medio | Empezar con struct pequeño; migrar a shared memory si necesario |
| Modelo de arte no disponible | Media | Medio | Usar CLIP o similar exportado a ONNX; o placeholder con histograma de color |
| FFmpeg GPU decode no disponible | Baja | Medio | Decode CPU; priorizar que el render sea GPU |
| Memoria limitada en laptop | Media | Medio | Limitar tamaño de pools; resolución máx 1280×720 |

---

## 8. Pruebas y benchmarks

### 8.1 Pruebas unitarias

| Módulo | Tipo | Criterio |
|--------|------|----------|
| detection | Unit | Frame sintético → detección esperada |
| segmentation | Unit | Máscara formato correcto, no vacía cuando hay persona |
| pose | Unit | Keypoints en rango, orden correcto |
| art_vector | Unit | Dimensión correcta, normalización |
| integration | Unit | PerceptionFrame válido con mocks |
| RuntimeBinding | Unit | tick() sin crash, stats no vacíos |

### 8.2 Benchmarks

| Métrica | Objetivo | Herramienta |
|---------|----------|-------------|
| Latencia detección | < 15 ms | `time.perf_counter()` por invocación |
| Latencia segmentación | < 20 ms | Idem |
| Latencia pose | < 10 ms | Idem |
| Latencia art_vector | < 25 ms | Idem |
| Latencia total percepción | < 50 ms | Suma o pipeline paralelizable |
| Latencia tick C++ | < 33 ms | Para 30 fps |
| FPS end-to-end | ≥ 30 | Contador de frames en 60 s |

### 8.3 Perfiles sugeridos

- **Python**: cProfile o py-spy en el loop de percepción.
- **C++**: Tracy, optick o perf para el tick.
- **GPU**: RenderDoc para verificar que no haya stalls.

---

## 9. Resumen de entregables V1

| Entregable | Descripción |
|------------|-------------|
| **Arquitectura** | Documento (este plan) + diagramas |
| **Interfaces** | Signatures Python (perception, integration) y C++ (RuntimeBinding, nodos) |
| **Módulos Python** | detection, segmentation, pose, art_vector, integration |
| **Runtime C++** | core (scheduler, pools), gpu (warp, blur, feedback, deform), io |
| **Binding** | pybind11 para PerceptionFrame y tick |
| **Modelos** | Al menos 3: detección, segmentación, pose; arte como bonus |
| **Tests** | Unitarios por módulo; integración end-to-end |
| **Benchmarks** | Scripts de latencia y FPS |

---

## 10. Próximos pasos (post-confirmación)

1. Revisar y ajustar este plan según feedback.
2. Confirmar modelos concretos (links a ONNX, fuentes).
3. Crear repositorio/rama y estructura de carpetas.
4. Iniciar Fase 0 según el plan numerado.

---

*Documento: Plan Maestro V1 — Spatial-Iteration-Engine*  
*Versión: 1.0 — Febrero 2025*
