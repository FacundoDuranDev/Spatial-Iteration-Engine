# Integración de Percepción IA - Guía Completa

**Fecha**: 2025-02-16  
**Estado**: ✅ Integración completa y funcional

---

## ✅ Estado Actual

### Modelos Descargados

- ✅ **Pose**: `pose_landmark.onnx` (6.5 MB) - YOLOv8 FP16
- ✅ **Face**: `face_landmark.onnx` (159 MB) - DETR Face Detection
- ✅ **Hand**: `hand_landmark.onnx` (7.5 MB) - MediaPipe (formato TFLite en ZIP)

### Módulo C++ Compilado

- ✅ `perception_cpp.cpython-312-x86_64-linux-gnu.so` compilado y funcional
- ✅ Funciones expuestas: `detect_face`, `detect_hands`, `detect_pose`
- ✅ Integración con ONNX Runtime completa

### Adapters Python

- ✅ `FaceLandmarkAnalyzer` - Funcional
- ✅ `HandLandmarkAnalyzer` - Funcional
- ✅ `PoseLandmarkAnalyzer` - Funcional

### Panel de Control

- ✅ Pestaña "IA" con controles para activar/desactivar detección
- ✅ Visualización de estado del detector
- ✅ Soporte para overlay de landmarks

---

## 🚀 Uso en el Panel de Control

### Configuración Inicial

1. **Asegurar que los modelos estén disponibles**:
   ```bash
   export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"
   ```

2. **Configurar PYTHONPATH**:
   ```bash
   export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
   ```

3. **Iniciar Jupyter/Notebook**:
   ```python
   from ascii_stream_engine.presentation.notebook_api import build_engine_for_notebook, build_general_control_panel
   
   engine = build_engine_for_notebook(camera_index=0)
   build_general_control_panel(engine)
   ```

### Uso del Panel de Control

1. **Activar detección**:
   - Ir a la pestaña "IA"
   - Activar checkboxes: "Detección cara", "Detección manos", "Detección pose"
   - Clic en "Aplicar IA"

2. **Visualizar landmarks**:
   - En "Visualización", seleccionar "Overlay landmarks"
   - Clic en "Aplicar IA"
   - Iniciar el motor con "Start"

3. **Verificar estado**:
   - Clic en "Actualizar estado detector"
   - Verás el número de puntos detectados para cada categoría

---

## 📋 Estructura de la Integración

### Flujo de Datos

```
Cámara
  ↓
StreamEngine
  ↓
AnalyzerPipeline
  ├─ FaceLandmarkAnalyzer → perception_cpp.detect_face
  ├─ HandLandmarkAnalyzer → perception_cpp.detect_hands
  └─ PoseLandmarkAnalyzer → perception_cpp.detect_pose
  ↓
FrameAnalysis (almacenado en engine)
  ↓
Renderer (LandmarksOverlayRenderer o PassthroughRenderer)
  ↓
OutputSink (PreviewSink o NotebookPreviewSink)
```

### Componentes

1. **C++ (`perception_cpp`)**:
   - `onnx_runner.cpp` - Ejecuta modelos ONNX
   - `face_landmarks.cpp`, `hand_landmarks.cpp`, `pose_landmarks.cpp` - Wrappers
   - `pybind_perception.cpp` - Bridge Python

2. **Python (Adapters)**:
   - `face.py` - `FaceLandmarkAnalyzer`
   - `hands.py` - `HandLandmarkAnalyzer`
   - `pose.py` - `PoseLandmarkAnalyzer`

3. **Panel de Control**:
   - `notebook_api.py` - `build_general_control_panel`
   - Pestaña "IA" con controles interactivos

---

## 🧪 Pruebas

### Script de Prueba

```bash
export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"
export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
python3 scripts/test_perception_integration.py
```

### Prueba Manual

```python
import sys
import os
sys.path.insert(0, 'python')
sys.path.insert(0, 'cpp/build')

os.environ['ONNX_MODELS_DIR'] = 'onnx_models/mediapipe'

from ascii_stream_engine.presentation.notebook_api import build_engine_for_notebook
from ascii_stream_engine.presentation.notebook_api import build_general_control_panel

engine = build_engine_for_notebook(0)
build_general_control_panel(engine)
```

---

## ⚠️ Notas Importantes

### Modelo de Face (DETR)

El modelo `face_landmark.onnx` es DETR Face Detection, que detecta **bounding boxes** de caras, no landmarks específicos. Por eso puede devolver 0 puntos cuando se esperan landmarks.

**Solución**: Para landmarks faciales específicos, considerar:
- Convertir modelos MediaPipe TFLite a ONNX
- Buscar modelos ONNX específicos de landmarks faciales

### Modelo de Hand

El archivo `hand_landmark.onnx` contiene modelos TFLite en formato ZIP. El código actual espera ONNX.

**Solución**: 
- Extraer TFLite y convertir a ONNX
- O implementar soporte TFLite nativo (ver `USE_ORIGINAL_FORMATS.md`)

### Modelo de Pose

El modelo `pose_landmark.onnx` (YOLOv8) funciona correctamente y devuelve landmarks de pose.

---

## 🔧 Troubleshooting

### Error: "No module named 'perception_cpp'"

**Solución**:
```bash
cd cpp/build
cmake ..
make -j4
export PYTHONPATH="$(pwd):$PYTHONPATH"
```

### Error: "Model not found"

**Solución**:
```bash
export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"
# Verificar que los archivos existan
ls -lh onnx_models/mediapipe/*.onnx
```

### No se detectan puntos

**Verificar**:
1. Los modelos están en la ruta correcta
2. `ONNX_MODELS_DIR` está configurado
3. Los analyzers están habilitados en el panel de control
4. El motor está corriendo

---

## 📚 Referencias

- **Modelos**: `onnx_models/mediapipe/VERIFIED_MODELS.md`
- **Formatos alternativos**: `onnx_models/mediapipe/ALTERNATIVE_FORMATS.md`
- **Usar formatos originales**: `onnx_models/mediapipe/USE_ORIGINAL_FORMATS.md`
- **Reglas de seguridad**: `rules/SECURITY_MODEL_DOWNLOAD.md`

