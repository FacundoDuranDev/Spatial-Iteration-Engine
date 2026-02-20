# Troubleshooting - Percepción IA

**Fecha**: 2025-02-16  
**Problema**: No se detectan puntos aunque los modelos estén activados

---

## 🔍 Problemas Identificados

### 1. Pose: Demasiados Puntos (156800 puntos)

**Síntoma**: El detector de pose devuelve 156800 puntos en lugar de ~17-33 keypoints.

**Causa**: El modelo YOLOv8 está funcionando correctamente, pero devuelve toda la salida del modelo sin filtrar. YOLOv8 devuelve múltiples detecciones con formato:
- `(num_detections, 4+1+num_keypoints*3)` donde:
  - 4 valores: bbox (x, y, w, h)
  - 1 valor: confidence
  - num_keypoints*3: keypoints (x, y, confidence) para cada keypoint

**Solución**: ✅ **IMPLEMENTADO** - Post-procesamiento agregado en `onnx_runner.cpp`
- Filtra detecciones con confidence > 0.5
- Extrae solo keypoints válidos (confidence > 0.3)
- Devuelve solo la primera detección válida

**Verificación**:
```bash
python3 scripts/diagnose_perception.py
```

---

### 2. Face: Cero Puntos

**Síntoma**: El detector de cara devuelve 0 puntos.

**Causas posibles**:
1. **Modelo no se carga**: El archivo `face_landmark.onnx` (159 MB) puede no ser compatible
2. **Formato incompatible**: El modelo DETR puede requerir formato de entrada diferente
3. **Modelo experimental**: El modelo tiene pocas descargas y puede no funcionar correctamente

**Diagnóstico**:
```bash
# Verificar que el modelo existe
ls -lh onnx_models/mediapipe/face_landmark.onnx

# Probar carga directa
python3 scripts/diagnose_perception.py
```

**Soluciones**:
1. **Verificar carga del modelo**: El modelo puede no estar cargándose correctamente
2. **Buscar modelo alternativo**: Considerar modelos con más descargas
3. **Convertir MediaPipe TFLite**: Usar modelos oficiales de MediaPipe

---

### 3. Hands: Cero Puntos

**Síntoma**: El detector de manos devuelve 0 puntos.

**Causa**: ❌ **El archivo `hand_landmark.onnx` NO es un modelo ONNX válido**
- Es un archivo ZIP que contiene modelos TFLite:
  - `hand_detector.tflite` (2.3 MB)
  - `hand_landmarks_detector.tflite` (5.5 MB)

**Verificación**:
```bash
file onnx_models/mediapipe/hand_landmark.onnx
unzip -l onnx_models/mediapipe/hand_landmark.onnx
```

**Soluciones**:

#### Opción 1: Convertir TFLite → ONNX (Recomendado)
```bash
# Extraer TFLite del ZIP
unzip onnx_models/mediapipe/hand_landmark.onnx -d onnx_models/mediapipe/tflite/

# Convertir usando tf2onnx
pip install tf2onnx
python -m tf2onnx.convert \
  --saved-model onnx_models/mediapipe/tflite/hand_landmarks_detector.tflite \
  --output onnx_models/mediapipe/hand_landmark.onnx
```

#### Opción 2: Implementar soporte TFLite
- Ver: `onnx_models/mediapipe/USE_ORIGINAL_FORMATS.md`
- Implementar `TfliteRunner` similar a `OnnxRunner`

#### Opción 3: Buscar modelo ONNX alternativo
- Buscar en HuggingFace modelos ONNX de hand landmarks
- Ver: `onnx_models/mediapipe/TRUSTED_SOURCES.md`

---

## 🛠️ Soluciones Implementadas

### Post-procesamiento YOLOv8

Se agregó función `postprocess_yolov8_pose()` en `onnx_runner.cpp` que:
1. Detecta formato YOLOv8 por el tamaño de la salida
2. Filtra detecciones con confidence > 0.5
3. Extrae keypoints válidos (confidence > 0.3)
4. Devuelve solo la primera detección válida

**Resultado esperado**: De 156800 puntos → ~17-33 keypoints válidos

---

## 📋 Checklist de Verificación

### Modelos
- [ ] `pose_landmark.onnx` existe y es ONNX válido ✅
- [ ] `face_landmark.onnx` existe (159 MB) ⚠️ Verificar compatibilidad
- [ ] `hand_landmark.onnx` es ZIP/TFLite ❌ Necesita conversión

### Módulo C++
- [ ] `perception_cpp` compilado correctamente
- [ ] ONNX Runtime disponible en el sistema
- [ ] `ONNX_MODELS_DIR` configurado correctamente

### Pruebas
- [ ] Ejecutar `scripts/diagnose_perception.py`
- [ ] Verificar que pose devuelve ~17-33 puntos (no 156800)
- [ ] Verificar que face/hands muestran mensajes de error claros

---

## 🔧 Comandos de Diagnóstico

### Diagnóstico completo
```bash
export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"
export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
python3 scripts/diagnose_perception.py
```

### Verificar modelos
```bash
ls -lh onnx_models/mediapipe/*.onnx
file onnx_models/mediapipe/*.onnx
```

### Probar detección
```python
import perception_cpp
import numpy as np

frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
result = perception_cpp.detect_pose(frame)
print(f"Puntos: {result.shape[0] if hasattr(result, 'shape') else 0}")
```

---

## 📚 Referencias

- **Modelos**: `onnx_models/mediapipe/VERIFIED_MODELS.md`
- **Formatos alternativos**: `onnx_models/mediapipe/ALTERNATIVE_FORMATS.md`
- **Usar formatos originales**: `onnx_models/mediapipe/USE_ORIGINAL_FORMATS.md`
- **Integración**: `docs/PERCEPTION_INTEGRATION.md`

