# Fuentes Confiables Verificadas - Modelos ONNX

**Última actualización**: 2025-02-16  
**Cumple con**: `rules/SECURITY_MODEL_DOWNLOAD.md`

Este documento lista fuentes confiables verificadas para descargar modelos ONNX de face, hands y pose landmarks.

---

## 🔒 Fuentes de Alta Confiabilidad (Nivel 1)

### 1. ONNX Model Zoo (GitHub Oficial)

**Fuente**: `github.com/onnx/models`  
**Verificación**: ✅ Repositorio oficial de ONNX, mantenido por Microsoft y la comunidad ONNX  
**Licencia**: Varias (verificar por modelo)

#### Modelos Disponibles:

**Face Detection**:
- **UltraFace**: `https://github.com/onnx/models/raw/main/vision/body_analysis/ultraface/models/version-RFB-320.onnx`
  - Tamaño aproximado: ~1.2 MB
  - Uso: Detección de caras (bounding boxes)
  - Nota: No landmarks, solo detección

**Face Recognition**:
- **ArcFace**: `https://github.com/onnx/models/raw/main/vision/body_analysis/arcface/model/arcface_r100_v1.onnx`
  - Tamaño aproximado: ~248 MB
  - Uso: Reconocimiento facial (embeddings)
  - Nota: No landmarks, embeddings para reconocimiento

**Pose Estimation**:
- **YOLOv8 Pose**: Buscar en HuggingFace (más reciente)
- **MediaPipe Pose**: Ver sección de Google Research

---

### 2. HuggingFace Hub

**Fuente**: `huggingface.co`  
**Verificación**: ✅ Plataforma oficial, asociada con Microsoft Azure  
**Licencia**: Varias (verificar por modelo)

#### Modelos Recomendados:

**Face Landmarks**:
- Buscar: `https://huggingface.co/models?library=onnx&search=face+landmark`
- Modelos populares:
  - `onnx/face-detection-ultraface` (detección)
  - `onnx/face-recognition-arcface` (reconocimiento)

**Hand Landmarks**:
- Buscar: `https://huggingface.co/models?library=onnx&search=hand+landmark`
- Nota: Pocos modelos ONNX directos, mayoría son TFLite

**Pose Estimation**:
- Buscar: `https://huggingface.co/models?library=onnx&search=pose+estimation`
- Modelos populares:
  - `onnx/yolov8-pose` (YOLOv8 con pose)
  - `onnx/pose-estimation` (varios)

#### Cómo Descargar desde HuggingFace:

```bash
# Formato de URL para descarga directa:
https://huggingface.co/{model_id}/resolve/main/{filename}.onnx

# Ejemplo:
https://huggingface.co/onnx/face-detection-ultraface/resolve/main/model.onnx
```

---

### 3. Google Research / MediaPipe

**Fuente**: `github.com/google/mediapipe`  
**Verificación**: ✅ Repositorio oficial de Google  
**Licencia**: Apache 2.0

#### Modelos Disponibles:

**Nota Importante**: MediaPipe proporciona modelos principalmente en formato TFLite, NO ONNX directamente.

**Opciones**:
1. **Convertir TFLite a ONNX**: Usar `tf2onnx` o herramientas similares
2. **Buscar conversiones comunitarias**: Algunos usuarios han convertido modelos MediaPipe a ONNX

**Modelos TFLite de MediaPipe** (requieren conversión):
- Face Landmarks: `https://github.com/google/mediapipe/tree/master/mediapipe/modules/face_landmark`
- Hand Landmarks: `https://github.com/google/mediapipe/tree/master/mediapipe/modules/hand_landmark`
- Pose Landmarks: `https://github.com/google/mediapipe/tree/master/mediapipe/modules/pose_landmark`

---

## 🔍 Estrategia Recomendada

### Opción 1: Modelos ONNX Pre-convertidos (Recomendado)

1. **ONNX Model Zoo**: Para modelos de detección y reconocimiento facial
2. **HuggingFace**: Para modelos más recientes y variados
3. **Verificar checksums**: Cuando estén disponibles

### Opción 2: Conversión desde TFLite

Si necesitas específicamente modelos MediaPipe:

1. Descargar modelos TFLite desde Google Research
2. Convertir a ONNX usando `tf2onnx`:
   ```bash
   pip install tf2onnx
   python -m tf2onnx.convert --saved-model model.tflite --output model.onnx
   ```
3. Validar el modelo convertido

### Opción 3: Modelos Alternativos

Para landmarks específicos, considerar:

1. **YOLOv8-Pose**: Pose estimation moderna
2. **RetinaFace**: Face detection con landmarks
3. **OpenPose**: Pose estimation (puede tener versiones ONNX)

---

## ✅ Proceso de Búsqueda Segura

### Cómo Encontrar URLs Válidas

**IMPORTANTE**: Las URLs específicas pueden cambiar. Sigue este proceso para encontrar URLs válidas:

#### 1. ONNX Model Zoo

1. Visitar: `https://github.com/onnx/models`
2. Navegar a: `vision/body_analysis/` para modelos de detección
3. Verificar estructura del repositorio (puede cambiar)
4. Usar URL raw de GitHub: `https://github.com/onnx/models/raw/main/{ruta}/{archivo}.onnx`
5. Verificar que la URL responde con `curl -I {URL}`

#### 2. HuggingFace

1. Buscar modelos: `https://huggingface.co/models?library=onnx&search={término}`
2. Seleccionar modelo confiable (verificar autor y descargas)
3. Ir a la pestaña "Files and versions"
4. Copiar URL de descarga directa: `https://huggingface.co/{model_id}/resolve/main/{filename}.onnx`
5. Verificar que el modelo tiene licencia clara

#### 3. Verificación de Seguridad

Antes de usar cualquier URL:
```bash
# 1. Verificar que la URL está en whitelist
# 2. Verificar accesibilidad
curl -I {URL}

# 3. Verificar tamaño (no descargar si es sospechoso)
# 4. Verificar formato después de descargar
```

---

## ⚠️ URLs No Verificadas (Requieren Verificación Manual)

**NOTA**: Las siguientes URLs fueron encontradas en documentación pero NO han sido verificadas como accesibles:

### ONNX Model Zoo (Estructura puede variar)

- Face Detection: `github.com/onnx/models/vision/body_analysis/ultraface/`
- Face Recognition: `github.com/onnx/models/vision/body_analysis/arcface/`
- Pose Estimation: `github.com/onnx/models/vision/body_analysis/` (buscar modelos de pose)

**Proceso**: Navegar manualmente al repositorio y verificar URLs actuales.

---

## ⚠️ Limitaciones Conocidas

1. **Landmarks específicos**: Pocos modelos ONNX proporcionan landmarks directos (x,y coordenadas)
2. **MediaPipe**: Principalmente TFLite, requiere conversión
3. **Tamaños grandes**: Algunos modelos pueden ser >100MB

---

## 🔐 Verificación de Seguridad

Todas las fuentes listadas:
- ✅ Están en la whitelist de `rules/SECURITY_MODEL_DOWNLOAD.md`
- ✅ Son repositorios oficiales o plataformas certificadas
- ✅ Tienen documentación pública
- ✅ Son mantenidos activamente

---

## 📝 Notas de Uso

1. **Verificar licencias**: Cada modelo tiene su propia licencia
2. **Checksums**: Verificar cuando estén disponibles
3. **Tamaños**: Algunos modelos son grandes, considerar LFS o descarga bajo demanda
4. **Compatibilidad**: Verificar que los modelos sean compatibles con ONNX Runtime C++

---

## 🔄 Actualización de URLs

Este documento debe actualizarse cuando:
- Se encuentren nuevas fuentes confiables
- URLs dejen de funcionar
- Se descubran modelos mejores o más recientes

**Proceso**: Actualizar este archivo y el script `download_onnx_mediapipe.sh` con nuevas URLs verificadas.

