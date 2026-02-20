# Estado Actual de la Percepción IA

**Fecha**: 2025-02-20  
**Última actualización**: Después de agregar post-procesamiento YOLOv8

---

## ✅ Funcionando Correctamente

### Pose Estimation (YOLOv8)

**Estado**: ✅ **FUNCIONANDO**

- **Modelo**: `pose_landmark.onnx` (6.5 MB) - YOLOv8 FP16
- **Puntos detectados**: ~17 keypoints (correcto)
- **Post-procesamiento**: ✅ Implementado y funcionando
- **Resultado**: De 156800 puntos → 17 keypoints válidos

**Uso en panel de control**:
1. Activar "Detección pose" en la pestaña IA
2. Clic en "Aplicar IA"
3. Iniciar el motor
4. Verás ~17 puntos de pose detectados

---

## ⚠️ Problemas Conocidos

### Face Detection (DETR)

**Estado**: ⚠️ **NO FUNCIONA** (0 puntos)

**Causa**: El modelo puede no estar cargándose correctamente o ser incompatible

**Modelo**: `face_landmark.onnx` (159 MB) - DETR Face Detection
- Fuente: `iuliancmarcu/detr-face-detection-onnx`
- ⚠️ Experimental (solo 1 descarga en HuggingFace)
- Puede requerir formato de entrada diferente

**Soluciones**:
1. **Verificar carga del modelo**: Ejecutar diagnóstico
   ```bash
   python3 scripts/diagnose_perception.py
   ```
2. **Buscar modelo alternativo**: Modelos con más descargas y mejor soporte
3. **Convertir MediaPipe TFLite**: Usar modelos oficiales de Google

**Trabajo temporal**: Desactivar detección de cara hasta resolver

---

### Hand Detection (MediaPipe)

**Estado**: ❌ **NO FUNCIONA** (0 puntos)

**Causa**: ❌ **El archivo NO es un modelo ONNX válido**

**Problema**: `hand_landmark.onnx` es un archivo ZIP que contiene:
- `hand_detector.tflite` (2.3 MB)
- `hand_landmarks_detector.tflite` (5.5 MB)

**Verificación**:
```bash
file onnx_models/mediapipe/hand_landmark.onnx
# Resultado: ZIP archive
unzip -l onnx_models/mediapipe/hand_landmark.onnx
```

**Soluciones**:

#### Opción 1: Convertir TFLite → ONNX (Recomendado)
```bash
# Extraer TFLite
unzip onnx_models/mediapipe/hand_landmark.onnx -d onnx_models/mediapipe/tflite/

# Convertir
pip install tf2onnx
python -m tf2onnx.convert \
  --saved-model onnx_models/mediapipe/tflite/hand_landmarks_detector.tflite \
  --output onnx_models/mediapipe/hand_landmark.onnx
```

#### Opción 2: Implementar soporte TFLite
- Ver: `onnx_models/mediapipe/USE_ORIGINAL_FORMATS.md`
- Crear `TfliteRunner` similar a `OnnxRunner`

#### Opción 3: Buscar modelo ONNX alternativo
- Buscar en HuggingFace modelos ONNX de hand landmarks
- Ver: `onnx_models/mediapipe/TRUSTED_SOURCES.md`

**Trabajo temporal**: Desactivar detección de manos hasta convertir o implementar TFLite

---

## 📊 Resumen por Detector

| Detector | Estado | Puntos Detectados | Acción Requerida |
|----------|--------|-------------------|------------------|
| **Pose** | ✅ Funcionando | ~17 keypoints | ✅ Listo para usar |
| **Face** | ⚠️ No funciona | 0 puntos | 🔄 Buscar modelo alternativo |
| **Hands** | ❌ No funciona | 0 puntos | 🔄 Convertir TFLite → ONNX |

---

## 🎯 Uso Recomendado Actual

### Para Producción/Pruebas

**Usar solo Pose**:
1. Activar solo "Detección pose" en el panel de control
2. Desactivar Face y Hands hasta resolver los problemas
3. El detector de pose funciona correctamente y devuelve ~17 keypoints

### Para Desarrollo

**Resolver problemas de Face y Hands**:
1. **Face**: Buscar modelo alternativo o verificar compatibilidad del DETR
2. **Hands**: Convertir TFLite → ONNX o implementar soporte TFLite

---

## 🔧 Comandos de Diagnóstico

### Diagnóstico completo
```bash
export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"
export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
python3 scripts/diagnose_perception.py
```

### Probar solo pose
```python
import perception_cpp
import numpy as np

frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
result = perception_cpp.detect_pose(frame)
print(f"Puntos detectados: {result.shape[0]}")
# Debería mostrar ~17 puntos
```

---

## 📚 Documentación Relacionada

- **Troubleshooting**: `docs/PERCEPTION_TROUBLESHOOTING.md`
- **Integración**: `docs/PERCEPTION_INTEGRATION.md`
- **Modelos verificados**: `onnx_models/mediapipe/VERIFIED_MODELS.md`
- **Formatos alternativos**: `onnx_models/mediapipe/ALTERNATIVE_FORMATS.md`

