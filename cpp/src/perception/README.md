# Módulo de Percepción C++ (ONNX Runtime)

## Arquitectura: 100% C++

**Toda la inferencia de IA se ejecuta en C++**, sin dependencias de Python para el procesamiento.

### Flujo de Datos

```
Python (Frame numpy array)
    ↓
pybind11 bridge (pybind_perception.cpp)
    ↓
C++ perception::run_face/hands/pose()
    ↓
C++ OnnxRunner::run() [ONNX Runtime C++]
    ↓
Modelo ONNX (cargado en memoria C++)
    ↓
Resultados (vector<float> landmarks)
    ↓
pybind11 → numpy array
    ↓
Python (solo recibe resultados)
```

### Componentes C++

1. **`onnx_runner.cpp`**: Motor de inferencia ONNX
   - Carga modelos ONNX
   - Preprocesa imágenes (resize, normalize, NCHW)
   - Ejecuta inferencia con ONNX Runtime C++
   - Postprocesa resultados (extrae x,y de landmarks)

2. **`face_landmarks.cpp`**: Wrapper para landmarks faciales
   - Llama a `OnnxRunner` con modelo `face_landmark.onnx`

3. **`hand_landmarks.cpp`**: Wrapper para landmarks de manos
   - Llama a `OnnxRunner` con modelo `hand_landmark.onnx`

4. **`pose_landmarks.cpp`**: Wrapper para pose corporal
   - Llama a `OnnxRunner` con modelo `pose_landmark.onnx`

5. **`pybind_perception.cpp`**: Bridge Python ↔ C++
   - Expone funciones `detect_face()`, `detect_hands()`, `detect_pose()`
   - Convierte numpy arrays ↔ buffers C++

### Python (Solo Wrappers)

Los adapters en `python/ascii_stream_engine/adapters/perception/`:
- **NO hacen inferencia**
- **Solo llaman a `perception_cpp.detect_*()`**
- Convierten resultados a formato del pipeline

### Tecnologías

- **ONNX Runtime C++**: Inferencia de modelos
- **C++17**: Lenguaje base
- **pybind11**: Bridge Python (solo para interfaz)
- **Sin Python**: No hay dependencias de PyTorch, TensorFlow, MediaPipe Python, etc.

### Requisitos

- ONNX Runtime C++ instalado (`onnxruntime-cpp`)
- Modelos ONNX en `onnx_models/mediapipe/`
- Compilación con `USE_ONNXRUNTIME=1`

### Verificación

Para confirmar que todo está en C++:

```bash
# Buscar imports de IA en Python (debe estar vacío)
grep -r "import.*onnx\|import.*torch\|import.*tensorflow" python/

# Verificar que los adapters solo llaman a C++
grep -A 5 "perception_cpp" python/ascii_stream_engine/adapters/perception/*.py
```

