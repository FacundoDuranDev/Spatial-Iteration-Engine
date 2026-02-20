# Resumen de Formatos y Modelos Disponibles

**Fecha**: 2025-02-16  
**Basado en**: `rules/MVP_IA.md` - Tecnologías permitidas

---

## 📊 Formatos Permitidos según MVP_IA.md

El proyecto permite los siguientes runtimes en C++:

1. ✅ **ONNX Runtime** (ya implementado)
2. ✅ **NCNN** (Tencent)
3. ✅ **TensorFlow Lite** (Google)
4. ✅ **OpenVINO** (Intel)

---

## ✅ Modelos Disponibles por Formato

### ONNX (Runtime Implementado) ✅

**Pose Estimation**:
- ✅ `pose_landmark.onnx` - 6.5 MB (YOLOv8 FP16)
  - Fuente: HuggingFace (`Xenova/yolov8n-pose`)
  - Estado: Descargado y verificado
  - Listo para usar

**Face Detection**:
- ✅ `face_landmark.onnx` - 159 MB (DETR Face Detection)
  - Fuente: HuggingFace (`iuliancmarcu/detr-face-detection-onnx`)
  - Estado: Descargado y verificado
  - ⚠️ Nota: Experimental (pocas descargas)

**Hand Detection**:
- ❌ No disponible en ONNX directamente
- 💡 Opción: Convertir TFLite → ONNX

---

### TFLite (Modelos Disponibles) ✅

**Hand Detection** (Extraídos de archivos ZIP):
- ✅ `hand_detector.tflite` - 2.23 MB
  - Fuente: Google Research / MediaPipe
  - Ubicación: `onnx_models/mediapipe/tflite/hand/`
  - Estado: Extraído y verificado

- ✅ `hand_landmarks_detector.tflite` - 5.23 MB
  - Fuente: Google Research / MediaPipe
  - Ubicación: `onnx_models/mediapipe/tflite/hand/`
  - Estado: Extraído y verificado

**Uso**:
- Opción 1: Convertir a ONNX (tf2onnx) - Recomendado
- Opción 2: Implementar soporte TFLite C++

**Fuentes adicionales**:
- Google Research / MediaPipe: `https://github.com/google/mediapipe`
- TensorFlow Hub: `https://tfhub.dev/`

---

### NCNN (Requiere Búsqueda) ⚠️

**Fuentes confiables**:
- Tencent NCNN Model Zoo: `https://github.com/Tencent/ncnn/tree/master/models`
- Conversión: ONNX → NCNN usando `onnx2ncnn`

**Ventajas**:
- Muy optimizado para CPU
- Tamaños pequeños
- Buena performance

**Estado**: No hay modelos descargados aún, requiere búsqueda o conversión

---

### OpenVINO (Requiere Búsqueda) ⚠️

**Fuentes confiables**:
- Intel OpenVINO Model Zoo: `https://github.com/openvinotoolkit/open_model_zoo`
- Intel AI Hub: `https://ai.intel.com/`

**Ventajas**:
- Optimizado para hardware Intel
- Modelos oficiales de Intel

**Estado**: No hay modelos descargados aún, requiere búsqueda o conversión

---

## 🔄 Estrategias de Conversión

### TFLite → ONNX (Recomendado para Hand)

```bash
# Instalar herramientas
pip install tf2onnx

# Convertir modelo
python -m tf2onnx.convert \
  --saved-model hand_landmarks_detector.tflite \
  --output hand_landmark.onnx
```

**Modelos listos para conversión**:
- ✅ `hand_detector.tflite` (2.23 MB)
- ✅ `hand_landmarks_detector.tflite` (5.23 MB)

---

### ONNX → NCNN

```bash
# Compilar herramienta de conversión
cd ncnn/tools
make onnx2ncnn

# Convertir
./onnx2ncnn model.onnx model.param model.bin
```

---

### ONNX → OpenVINO

```bash
# Usar Model Optimizer
mo --input_model model.onnx --output_dir output/
```

---

## 📋 Resumen de Modelos por Categoría

| Categoría | ONNX | TFLite | NCNN | OpenVINO |
|-----------|------|--------|------|----------|
| **Pose** | ✅ YOLOv8 (6.5 MB) | ⚠️ Buscar | ⚠️ Buscar/Convertir | ⚠️ Buscar/Convertir |
| **Face** | ✅ DETR (159 MB) | ⚠️ Buscar | ⚠️ Buscar/Convertir | ⚠️ Buscar/Convertir |
| **Hand** | ❌ No disponible | ✅ MediaPipe (2.23 + 5.23 MB) | ⚠️ Buscar/Convertir | ⚠️ Buscar/Convertir |

---

## 🎯 Recomendaciones

### Para Uso Inmediato (ONNX Runtime)
1. ✅ **Pose**: Usar `pose_landmark.onnx` (ya descargado)
2. ✅ **Face**: Usar `face_landmark.onnx` (ya descargado, verificar)
3. 🔄 **Hand**: Convertir `hand_landmarks_detector.tflite` → ONNX

### Para Máxima Performance
1. **NCNN**: Convertir modelos ONNX a NCNN para mejor performance en CPU
2. **TFLite C++**: Implementar soporte para usar modelos MediaPipe directamente

### Para Hardware Específico
1. **OpenVINO**: Si tienes hardware Intel, usar modelos OpenVINO optimizados

---

## 🔐 Verificación de Seguridad

Todos los modelos:
- ✅ Fuentes en whitelist (`rules/SECURITY_MODEL_DOWNLOAD.md`)
- ✅ Verificados y accesibles
- ✅ Formatos válidos
- ✅ Permisos correctos
- ✅ Registrados en auditoría

---

## 📚 Documentación Relacionada

- **Formatos alternativos**: `onnx_models/mediapipe/ALTERNATIVE_FORMATS.md`
- **Modelos disponibles**: `onnx_models/mediapipe/AVAILABLE_MODELS.md`
- **Modelos encontrados**: `onnx_models/mediapipe/MODELS_FOUND.md`
- **Fuentes confiables**: `onnx_models/mediapipe/TRUSTED_SOURCES.md`
- **Reglas de seguridad**: `rules/SECURITY_MODEL_DOWNLOAD.md`

