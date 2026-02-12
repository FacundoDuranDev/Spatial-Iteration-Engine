# Plan Maestro V1 — Spatial-Iteration-Engine

**Objetivo**: Integrar percepción visual con IA liviana para generar **vistas deformadas y arte reactivo** usando cámaras en vivo.

**GPU objetivo**: Intel UHD 620 / sin CUDA  
**Target FPS**: 30  
**Build system**: CMake  
**Stack**: ONNX Runtime, Vulkan/OpenGL, Python 3.10+, pybind11

---

## 1. ARQUITECTURA TÉCNICA DETALLADA

### 1.1 Principio rector

```
frameₙ → estado (IA + geometría) → frameₙ₊₁
```

- **Python**: IA (ONNX Runtime), orquestación, control-plane, parámetros.
- **C++**: Render en tiempo real, procesamiento de geometría, data-plane de píxeles.

### 1.2 Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON CONTROL-PLANE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  Capture (OpenCV)  │  Detección   │  Segmentación  │  Pose   │  Arte-Vector  │
│  frame → buffer    │  YOLO-nano   │  ONNX liviano  │  ONNX   │  Embeddings   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERCEPTION STATE (Python)                                  │
│  { detections, masks, keypoints, art_vector }  →  serializado a C++          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    shared memory / IPC / buffers zero-copy
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    C++ FRAME RUNTIME                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  GraphScheduler │ ResourceManager │ NodeExecutor (warp, deform, blend)      │
│  Input: frame + perception_state  →  Output: frame deformado                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GPU (Vulkan/OpenGL)                                       │
│  Nodos: warp_deform, silhouette_blend, art_feedback, output                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Módulos e interfaces mínimas

| Módulo | Lenguaje | Responsabilidad |
|--------|----------|-----------------|
| **PerceptionPipeline** | Python | Orquesta detección, segmentación, pose, arte-vector. |
| **DetectionModule** | Python | YOLO-nano → bounding boxes, clases. |
| **SegmentationModule** | Python | Segmentador ONNX → máscara binaria/silueta. |
| **PoseModule** | Python | Pose ONNX → keypoints (17/33). |
| **ArtVectorModule** | Python | Embeddings estilísticos desde frame/región. |
| **PerceptionState** | Python | Dataclass unificado para pasar a C++. |
| **PerceptionBridge** | pybind11 | Serializa state → C++ consumible. |
| **DeformEngine** | C++ | Aplica deformaciones usando perception_state. |
| **RenderNodes** | C++/GPU | warp_deform, silhouette_blend, feedback. |

### 1.4 Comunicación Python ↔ C++

**Opciones evaluadas:**

| Método | Pros | Contras | Decisión V1 |
|--------|------|---------|-------------|
| **Shared memory (mmap)** | Zero-copy, bajo latency | Sincronización manual | **Recomendado** |
| **Pybind11 paso directo** | Simple para prototipo | Copia implícita en cada frame | Fallback |
| **ZMQ/socket** | Desacoplado | Latencia extra | No para V1 |
| **Tensor/buffer numpy** | Interop fácil | Aún puede copiar | Alternativa |

**Propuesta V1:**
1. **Estructura fija en shared memory** (struct C-compatible) conteniendo:
   - `frame_id`, `timestamp`
   - arrays de detecciones (max N personas)
   - máscara downscaled (ej. 64×64 o 128×128)
   - keypoints (17×2 o 33×2)
   - art_vector (128 dims float32)

2. **Python** escribe en región mmap; **C++** lee en `tick()`.
3. **Semáforo o atomic** para sincronización producer/consumer.

**Firma sugerida (Python):**
```python
def write_perception_state(shm_name: str, state: PerceptionState) -> None
def get_shm_handle(shm_name: str) -> int  # para C++
```

**Firma sugerida (C++):**
```cpp
PerceptionState read_perception_state(const char* shm_name);
void apply_deformations(Texture& input, const PerceptionState& state, Texture& output);
```

---

## 2. ESPECIFICACIONES POR MÓDULO

### 2.1 Módulo de Detección (Python)

| Campo | Valor |
|-------|-------|
| **Input** | `np.ndarray` uint8 H×W×3 (BGR) |
| **Output** | `List[Detection]` con `(x, y, w, h, class_id, confidence)` |
| **Formato** | Máximo 8 personas por frame (límite V1) |
| **Performance** | < 15 ms/frame en UHD 620 (objetivo) |
| **Pruebas** | Unit: mock frame → N detecciones; Benchmark: fps en 640×480 |

**Interface sugerida:**
```python
class Detection(NamedTuple):
    x: int
    y: int
    w: int
    h: int
    class_id: int
    confidence: float

class DetectionModule(Protocol):
    def detect(self, frame: np.ndarray) -> List[Detection]: ...
```

### 2.2 Módulo de Segmentación (Python)

| Campo | Valor |
|-------|-------|
| **Input** | `np.ndarray` uint8 H×W×3 |
| **Output** | `np.ndarray` float32 H×W (máscara 0–1) o uint8 binaria |
| **Resolución** | Downscaled a 64×64 o 128×128 para C++ (reducir IPC) |
| **Performance** | < 10 ms/frame |
| **Pruebas** | Unit: forma correcta; Benchmark: tiempo por resolución |

**Interface sugerida:**
```python
class SegmentationModule(Protocol):
    def segment(self, frame: np.ndarray) -> np.ndarray: ...
    def get_output_shape(self) -> Tuple[int, int]: ...
```

### 2.3 Módulo de Pose (Python)

| Campo | Valor |
|-------|-------|
| **Input** | `np.ndarray` o crop por detección |
| **Output** | `List[Pose]` con keypoints (x, y, confidence) × 17 o 33 |
| **Formato** | Coordenadas normalizadas [0,1] o absolutas |
| **Performance** | < 8 ms/frame para 1 persona (prioridad) |
| **Pruebas** | Unit: pose mock; Benchmark: latency por persona |

**Interface sugerida:**
```python
class Keypoint(NamedTuple):
    x: float
    y: float
    confidence: float

class Pose(NamedTuple):
    keypoints: List[Keypoint]

class PoseModule(Protocol):
    def estimate(self, frame: np.ndarray, bboxes: Optional[List[Detection]]) -> List[Pose]: ...
```

### 2.4 Módulo Arte-Vector (Python)

| Campo | Valor |
|-------|-------|
| **Input** | `np.ndarray` frame o región; opcional máscara |
| **Output** | `np.ndarray` float32 [128] o [256] (embedding) |
| **Uso** | Parámetros de deformación/color reactivos al estilo |
| **Performance** | < 5 ms/frame (modelo muy liviano) |
| **Pruebas** | Unit: embedding estable para mismo input; Benchmark: tiempo |

**Interface sugerida:**
```python
class ArtVectorModule(Protocol):
    def embed(self, frame: np.ndarray, mask: Optional[np.ndarray]) -> np.ndarray: ...
    def dim(self) -> int: ...
```

### 2.5 Módulo de Integración (PerceptionPipeline)

| Campo | Valor |
|-------|-------|
| **Input** | `np.ndarray` frame |
| **Output** | `PerceptionState` (dataclass serializable) |
| **Orden** | detect → segment, pose (por bbox) → art_vector |
| **Performance** | Pipeline total < 35 ms (aprox. 28 fps mínimo) |
| **Pruebas** | Integration: frame → state completo; Pipeline latency |

**Interface sugerida:**
```python
@dataclass
class PerceptionState:
    frame_id: int
    timestamp: float
    detections: List[Detection]
    mask: np.ndarray  # H×W float32, shape fijo
    poses: List[Pose]
    art_vector: np.ndarray  # float32

class PerceptionPipeline(Protocol):
    def process(self, frame: np.ndarray) -> PerceptionState: ...
```

### 2.6 Módulo de Render (C++)

| Campo | Valor |
|-------|-------|
| **Input** | Texture (frame) + PerceptionState (via shared mem) |
| **Output** | Texture (frame deformado) |
| **Nodos** | `warp_deform`, `silhouette_blend`, `feedback` |
| **Performance** | < 33 ms/frame (30 fps) |
| **Pruebas** | Unit: cada nodo con state mock; Benchmark: frame time |

**Nodos GPU sugeridos:**
- `warp_deform`: aplica deformación basada en poses/keypoints.
- `silhouette_blend`: mezcla frame con máscara para efecto de silueta.
- `art_feedback`: modula color/feedback según art_vector.
- `output`: salida final.

---

## 3. MODELOS IA Y RUNTIME

### 3.1 Detección: YOLO-nano / variante ONNX

| Atributo | Valor |
|----------|-------|
| **Modelo** | YOLOv8-nano o YOLOv5n ONNX, o NanoDet |
| **Input** | 320×320 o 640×640 |
| **Output** | (N, 6) [x, y, w, h, conf, class] |
| **Ejecución** | `ort.InferenceSession` con `ExecutionProvider.CPU` o `DmlExecutionProvider` (DirectML, Intel) |
| **Alimenta motor** | Bounding boxes → selección persona principal → crop para pose/segmentación |

**Cómo ejecutar con ONNX Runtime:**
```python
session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
outputs = session.run(None, {"images": preprocessed_tensor})
# Post-procesar NMS, decodificar boxes
```

### 3.2 Segmentación: modelo liviano

| Atributo | Valor |
|----------|-------|
| **Modelo** | MODNet (lite), U²-Net (small), o BiSeNet V2 Lite ONNX |
| **Input** | 256×256 o 320×320 |
| **Output** | (1, 1, H, W) float32 máscara |
| **Ejecución** | ONNX Runtime CPU |
| **Alimenta motor** | Máscara → texture/alpha para silhouette_blend |

### 3.3 Pose estimation

| Atributo | Valor |
|----------|-------|
| **Modelo** | MoveNet Lightning/Thunder o LiteHRNet ONNX |
| **Input** | 192×192 (Lightning) o 256×256 |
| **Output** | (1, 17, 3) o (1, 33, 3) [x, y, conf] |
| **Ejecución** | ONNX Runtime CPU |
| **Alimenta motor** | Keypoints → control de deformación (ej. atracción/repulsión por extremidades) |

### 3.4 Modelo de arte (embeddings estilísticos)

| Atributo | Valor |
|----------|-------|
| **Modelo** | Encoder pequeño ONNX (ej. ResNet-18 truncated, o custom VAE encoder) |
| **Entrenamiento** | Pre-entrenado sobre dataset de obras de arte (WikiArt, etc.) |
| **Input** | 224×224 RGB |
| **Output** | (1, 128) o (1, 256) float32 |
| **Ejecución** | ONNX Runtime CPU |
| **Alimenta motor** | Vector → parámetros de color/feedback/deformación (mapeo heurístico o lookup) |

---

## 4. DEPENDENCIAS EXTERNAS

| Dependencia | Versión | Rol |
|-------------|---------|-----|
| Python | 3.10+ | Control-plane |
| ONNX Runtime | 1.16+ | Inferencia IA |
| OpenCV | 4.8+ | Capture, preproceso |
| NumPy | 1.24+ | Arrays |
| Vulkan SDK / OpenGL | - | Render |
| CMake | 3.20+ | Build |
| pybind11 | 2.11+ | Bindings |
| FFmpeg | - | I/O opcional |

**Compatibilidad Intel UHD 620:**
- Vulkan 1.1 soportado.
- DirectML (Windows) como provider alternativo para ONNX.
- OpenGL 4.5 como fallback si Vulkan falla.

---

## 5. PLAN DE TRABAJO EN PASOS

### Fase 0 — Preparación (Semana 1)
1. Crear estructura de directorios para `perception/`, `engine/core`, `engine/gpu`, `engine/bindings`.
2. Configurar CMake + pybind11 para módulo Python importable.
3. Definir `PerceptionState` y struct C equivalente en header compartido.
4. Crear stub de shared memory (Python escribe, C++ lee) sin IA aún.

### Fase 1 — Módulos IA en Python (Semanas 2–3)
5. Integrar YOLO-nano ONNX: descarga modelo, preproceso, inferencia, NMS.
6. Integrar segmentador ONNX (MODNet/BiSeNet).
7. Integrar pose ONNX (MoveNet).
8. Integrar (o stub) modelo arte-vector.
9. Implementar `PerceptionPipeline` que une los cuatro.
10. Tests unitarios por módulo; benchmark de latencia.

### Fase 2 — Bridge Python → C++ (Semana 4)
11. Implementar región shared memory con struct fijo.
12. Serializar `PerceptionState` → bytes en formato C.
13. Binding pybind11: `write_perception_state`, `create_shm`.
14. C++: `read_perception_state` desde shm.
15. Test roundtrip Python → C++.

### Fase 3 — Render C++/GPU (Semanas 5–6)
16. Inicializar Vulkan (o OpenGL) en `engine/core`.
17. Nodo `warp_deform`: leer keypoints, aplicar mapeo de coordenadas.
18. Nodo `silhouette_blend`: texture + máscara alpha.
19. Nodo `art_feedback`: parámetros desde art_vector.
20. Integrar con `RuntimeGraphSpec` existente (nodos nuevos).

### Fase 4 — Integración E2E (Semana 7)
21. Loop: cámara → `PerceptionPipeline` → shm → C++ tick → output.
22. Ajustar resolución y calidad para 30 fps en UHD 620.
23. Tests de integración y benchmark FPS.
24. Documentar uso y configuración.

### Fase 5 — Estabilización (Semana 8)
25. Manejo de errores (modelo fallido, cámara desconectada).
26. Fallbacks: sin IA → warp genérico; sin GPU → path CPU legacy.
27. Profiling y optimización final.

---

## 6. RIESGOS TÉCNICOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| ONNX en UHD 620 lento | Media | Alto | Reducir input size; usar CPU si GPU empeora; modelo más pequeño |
| Latencia total > 33 ms | Media | Alto | Pipeline asíncrono (IA 1 frame atrás); reducir resolución percepción |
| Shared memory cross-platform | Baja | Medio | Usar `multiprocessing.shared_memory` (Python 3.8+); POSIX/Windows compatible |
| Vulkan no disponible | Baja | Medio | Fallback OpenGL 4.5 |
| Modelo arte no disponible | Media | Bajo | Stub con vector aleatorio o PCA de colores del frame |

---

## 7. PRUEBAS Y BENCHMARKS

### Pruebas unitarias
- Cada módulo IA: mock input → output shape/range correcto.
- `PerceptionState` serialización/deserialización idempotente.
- Nodos C++ con state mock: output no vacío, sin crash.

### Benchmarks
- **IA pipeline**: ms por frame (target < 35 ms).
- **C++ tick**: ms por frame (target < 33 ms).
- **E2E FPS**: en 640×480 y 1280×720.

### Criterios de aceptación V1
- Stream cámara → IA → motor → visual deformado en tiempo real.
- ≥ 28 FPS estables en 640×480 en Intel UHD 620.
- Al menos detección + segmentación funcionales; pose y arte pueden ser stub mejorado después.

---

## 8. RESUMEN DE ENTREGABLES

| Entregable | Descripción |
|------------|-------------|
| Arquitectura | Documento (este plan) + diagramas |
| Interfaces | Signatures en Python (Protocol) y C++ (headers) |
| Módulos IA | Detection, Segmentation, Pose, ArtVector en Python |
| Bridge | Shared memory + pybind11 |
| Render | Nodos warp_deform, silhouette_blend, art_feedback en C++ |
| Tests | Unit + integration + benchmark |
| Docs | Uso, configuración, troubleshooting |

---

## 9. PRÓXIMOS PASOS

1. **Confirmar este plan** antes de generar código.
2. Validar disponibilidad de modelos ONNX (YOLOv8-nano, MODNet/BiSeNet, MoveNet).
3. Decidir resolución de máscara para IPC (64×64 vs 128×128).
4. Priorizar: ¿pose antes que arte-vector o viceversa?

---

*Documento: Plan Maestro V1 — Spatial-Iteration-Engine*  
*Versión: 1.0 | Fecha: 2025-02-12*
