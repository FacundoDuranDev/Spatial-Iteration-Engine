# Modelos ONNX Verificados y Accesibles

**Fecha de verificación**: 2025-02-16  
**Fuente**: HuggingFace (whitelist aprobada)  
**Estado**: ✅ URLs verificadas y accesibles

---

## ✅ Modelos Verificados

### Pose Estimation

#### 1. Xenova/yolov8n-pose (Recomendado - Pequeño y Rápido)

**Descripción**: YOLOv8 pose estimation, versión nano (pequeña y rápida)

**Archivos disponibles**:
- `onnx/model.onnx` - **12.9 MB** (recomendado para inicio)
  - URL: `https://huggingface.co/Xenova/yolov8n-pose/resolve/main/onnx/model.onnx`
  - ✅ Verificado y accesible
  
- `onnx/model_fp16.onnx` - **6.5 MB** (optimizado, FP16)
  - URL: `https://huggingface.co/Xenova/yolov8n-pose/resolve/main/onnx/model_fp16.onnx`
  - ✅ Verificado y accesible
  
- `onnx/model_int8.onnx` - **3.6 MB** (muy optimizado, INT8)
  - URL: `https://huggingface.co/Xenova/yolov8n-pose/resolve/main/onnx/model_int8.onnx`
  - ✅ Verificado y accesible

**Recomendación**: Usar `model_fp16.onnx` para balance entre precisión y tamaño.

---

#### 2. Xenova/yolov8x-pose (Alta Precisión)

**Descripción**: YOLOv8 pose estimation, versión extra large (más preciso pero más grande)

**Archivos disponibles**:
- `onnx/model.onnx` - **265 MB** (muy grande)
  - URL: `https://huggingface.co/Xenova/yolov8x-pose/resolve/main/onnx/model.onnx`
  - ✅ Verificado y accesible
  
- `onnx/model_fp16.onnx` - **132.7 MB** (optimizado, FP16)
  - URL: `https://huggingface.co/Xenova/yolov8x-pose/resolve/main/onnx/model_fp16.onnx`
  - ✅ Verificado y accesible
  
- `onnx/model_int8.onnx` - **66.8 MB** (muy optimizado, INT8)
  - URL: `https://huggingface.co/Xenova/yolov8x-pose/resolve/main/onnx/model_int8.onnx`
  - ✅ Verificado y accesible

**Recomendación**: Usar `model_fp16.onnx` si necesitas mayor precisión.

---

### Face Detection

⚠️ **Estado**: No se encontraron modelos ONNX directos con muchas descargas

**Alternativas**:
1. Usar modelos YOLO genéricos que detectan personas/caras
2. Convertir modelos TFLite de MediaPipe a ONNX
3. Buscar modelos específicos navegando HuggingFace manualmente

**Modelos encontrados (pocas descargas, requieren verificación)**:
- `iuliancmarcu/detr-face-detection-onnx`: 1 descarga
  - Tiene `onnx/model_quantized.onnx`
  - ⚠️ Muy pocas descargas, verificar antes de usar

---

### Hand Detection

⚠️ **Estado**: No se encontraron modelos ONNX directos

**Alternativas**:
1. Convertir modelos TFLite de MediaPipe a ONNX:
   - `qualcomm/MediaPipe-Hand-Detection` (289 descargas)
   - Formato: TFLite (requiere conversión)
   
2. Buscar modelos específicos navegando HuggingFace manualmente

---

## 📋 Recomendaciones por Uso

### Para Desarrollo/Pruebas (Rápido)
- **Pose**: `Xenova/yolov8n-pose` → `model_fp16.onnx` (6.5 MB)
- **Face**: Usar modelo YOLO genérico o convertir MediaPipe
- **Hand**: Convertir MediaPipe TFLite a ONNX

### Para Producción (Precisión)
- **Pose**: `Xenova/yolov8x-pose` → `model_fp16.onnx` (132.7 MB)
- **Face**: Buscar modelos específicos o convertir MediaPipe
- **Hand**: Convertir MediaPipe TFLite a ONNX

---

## 🔐 Verificación de Seguridad

✅ **Todas las URLs verificadas**:
- Fuente: HuggingFace (`huggingface.co`) - ✅ En whitelist
- Accesibilidad: ✅ Verificada con HTTP 200
- Tamaños: ✅ Verificados (razonables)
- Licencias: Verificar en página del modelo

---

## 📝 Notas de Uso

1. **Modelos YOLOv8**: Detectan múltiples personas/poses en una imagen
2. **Formatos optimizados**: FP16 e INT8 son más pequeños pero pueden tener menor precisión
3. **Conversión TFLite**: Para MediaPipe, usar `tf2onnx` o herramientas similares
4. **Tamaños**: Modelos grandes (>100MB) pueden requerir más memoria

---

## 🔄 Actualización

Este documento debe actualizarse cuando:
- Se encuentren nuevos modelos ONNX verificados
- URLs dejen de funcionar
- Se descubran modelos mejores

**Proceso**: Verificar con `curl -I {URL}` antes de usar.

