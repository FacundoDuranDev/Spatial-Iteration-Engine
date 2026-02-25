# Modelos Disponibles por Formato

**Última actualización**: 2025-02-16  
**Formato**: Lista completa de modelos disponibles en diferentes formatos

---

## ✅ Modelos ONNX (Ya Descargados)

### Pose Estimation
- ✅ `pose_landmark.onnx` - **6.5 MB** (YOLOv8 FP16)
  - Modelo: `Xenova/yolov8n-pose`
  - Fuente: HuggingFace ✅
  - Estado: Descargado y verificado

### Face Detection
- ✅ `face_landmark.onnx` - **159 MB** (DETR Face Detection)
  - Modelo: `iuliancmarcu/detr-face-detection-onnx`
  - Fuente: HuggingFace ✅
  - Estado: Descargado y verificado
  - ⚠️ Nota: Pocas descargas (experimental)

---

## ✅ Modelos TFLite (Extraídos de Archivos ZIP)

### Hand Detection
- ✅ `hand_detector.tflite` - **2.23 MB**
  - Fuente: Google Research / MediaPipe ✅
  - Ubicación: `onnx_models/mediapipe/tflite/hand/hand_detector.tflite`
  - Estado: Extraído y verificado

- ✅ `hand_landmarks_detector.tflite` - **5.23 MB**
  - Fuente: Google Research / MediaPipe ✅
  - Ubicación: `onnx_models/mediapipe/tflite/hand/hand_landmarks_detector.tflite`
  - Estado: Extraído y verificado

**Uso**:
- Opción 1: Usar con TensorFlow Lite C++ (requiere implementar soporte)
- Opción 2: Convertir a ONNX usando `tf2onnx`

---

## 📋 Modelos Disponibles desde Fuentes Oficiales

### TFLite (MediaPipe - Google Research)

**Repositorio**: `https://github.com/google/mediapipe`

**Modelos disponibles**:
- **Face Landmarks**: `mediapipe/modules/face_landmark/face_landmark.tflite`
- **Hand Landmarks**: `mediapipe/modules/hand_landmark/hand_landmark.tflite`
- **Pose Landmarks**: `mediapipe/modules/pose_landmark/pose_landmark.tflite`

**Descarga**:
```bash
# Clonar repositorio
git clone https://github.com/google/mediapipe.git

# O descargar desde releases oficiales
# Los modelos están en el repositorio
```

**Ya tenemos**: Hand models extraídos de archivos ZIP ✅

---

### NCNN (Tencent)

**Repositorio**: `https://github.com/Tencent/ncnn`  
**Model Zoo**: `https://github.com/Tencent/ncnn/tree/master/models`

**Modelos disponibles**:
- Face detection: Varios modelos optimizados
- Hand/Pose: Menos comunes, pero disponibles
- Conversión: ONNX → NCNN usando `onnx2ncnn`

**Descarga**:
```bash
# Clonar repositorio NCNN
git clone https://github.com/Tencent/ncnn.git
cd ncnn/models
# Ver modelos disponibles
```

---

### OpenVINO (Intel)

**Repositorio**: `https://github.com/openvinotoolkit/open_model_zoo`

**Modelos disponibles**:
- Face detection: Varios modelos
- Pose estimation: Modelos optimizados para Intel
- Formato: IR (.xml + .bin)

**Descarga**:
```bash
# Usar OpenVINO Model Downloader
pip install openvino-dev
omz_downloader --name <model_name>
```

---

## 🔄 Estrategias de Conversión

### TFLite → ONNX

```bash
# Instalar herramientas
pip install tf2onnx

# Convertir modelo
python -m tf2onnx.convert \
  --saved-model model.tflite \
  --output model.onnx
```

**Modelos listos para conversión**:
- ✅ `hand_detector.tflite` (2.23 MB)
- ✅ `hand_landmarks_detector.tflite` (5.23 MB)

---

### ONNX → NCNN

```bash
# Compilar onnx2ncnn (herramienta de NCNN)
cd ncnn/tools
make onnx2ncnn

# Convertir
./onnx2ncnn model.onnx model.param model.bin
```

---

### ONNX → OpenVINO

```bash
# Usar Model Optimizer de OpenVINO
mo --input_model model.onnx --output_dir output/
```

---

## 📊 Comparación de Formatos Disponibles

| Formato | Modelos Disponibles | Estado | Acción Requerida |
|---------|---------------------|--------|------------------|
| **ONNX** | Pose ✅, Face ✅ | ✅ Listo | Usar directamente |
| **TFLite** | Hand ✅ (extraído) | ✅ Disponible | Convertir a ONNX o implementar TFLite C++ |
| **NCNN** | Varios (buscar) | ⚠️ Requiere búsqueda | Buscar modelos o convertir ONNX |
| **OpenVINO** | Varios (buscar) | ⚠️ Requiere búsqueda | Buscar modelos o convertir ONNX |

---

## 🎯 Recomendación

### Para Uso Inmediato
1. **Pose**: Usar `pose_landmark.onnx` (ya descargado) ✅
2. **Face**: Usar `face_landmark.onnx` (ya descargado, verificar funcionamiento) ✅
3. **Hand**: Convertir `hand_landmarks_detector.tflite` a ONNX

### Para Máxima Compatibilidad
- Convertir todos los TFLite a ONNX
- Usar el código ONNX Runtime que ya está implementado

### Para Máxima Performance
- Considerar NCNN para modelos críticos de performance
- Implementar soporte TFLite C++ para usar modelos MediaPipe directamente

---

## 📝 Notas

- Los modelos TFLite de MediaPipe son **oficiales de Google** y muy confiables
- La conversión TFLite → ONNX puede requerir ajustes según el modelo
- NCNN y OpenVINO requieren implementar soporte en C++ (similar a ONNX Runtime)

---

## 🔗 Referencias

- **MediaPipe TFLite**: https://github.com/google/mediapipe
- **NCNN Model Zoo**: https://github.com/Tencent/ncnn/tree/master/models
- **OpenVINO Model Zoo**: https://github.com/openvinotoolkit/open_model_zoo
- **Conversión TFLite→ONNX**: Ver `ALTERNATIVE_FORMATS.md`

