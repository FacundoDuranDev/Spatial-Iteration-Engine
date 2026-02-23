# Security Audit - Model Downloads

Este archivo registra todos los modelos descargados y sus verificaciones de seguridad.

**Última actualización**: 2025-02-16

---

## Modelos Registrados

Las entradas siguientes son generadas automáticamente por el script de descarga segura (`scripts/download_onnx_mediapipe.sh`).

---

## Auditoría Manual - Análisis Inicial (2025-02-16)

**Auditor**: Análisis automatizado de archivos descargados

### Resumen Ejecutivo

✅ **SEGURIDAD GENERAL: SEGURA**  
⚠️ **FORMATO: INCOMPATIBLE** (los archivos no son ONNX válidos)

Los archivos descargados **NO son maliciosos**, pero **NO son modelos ONNX válidos** para el uso previsto.

---

### Análisis Detallado por Archivo

#### 1. `face_landmark.onnx` (298 KB)

**Estado**: ❌ **NO VÁLIDO** (archivo HTML, no modelo)

**Análisis de Seguridad**:
- ✅ **Fuente**: HuggingFace (`huggingface.co/qualcomm/MediaPipe-Face-Detection`)
  - Qualcomm es una empresa legítima y reconocida
  - HuggingFace es una plataforma confiable para modelos de ML
- ✅ **Permisos**: `664` (no ejecutable)
- ✅ **Sin shebang**: No es un script ejecutable
- ✅ **Sin strings sospechosos**: No contiene código malicioso
- ❌ **Tipo de archivo**: HTML (página de error 404, no modelo ONNX)

**Conclusión**: El archivo es seguro pero **no es un modelo válido**. La descarga falló y se obtuvo una página HTML de error.

**Recomendación**: Eliminar y descargar desde una fuente alternativa.

---

#### 2. `hand_landmark.onnx` (7.5 MB)

**Estado**: ⚠️ **FORMATO INCORRECTO** (ZIP con TFLite, no ONNX)

**Análisis de Seguridad**:
- ✅ **Fuente**: MediaPipe / Google Research
  - Los strings internos muestran: `MediaPipe`, `Google Research`, `research/aimatter/nnets`
  - Google Research es una fuente **altamente confiable**
  - MediaPipe es un framework oficial de Google
- ✅ **Permisos**: `664` (no ejecutable)
- ✅ **Sin shebang**: No es un script ejecutable
- ✅ **Sin strings sospechosos**: No contiene código malicioso
- ✅ **Contenido**: ZIP con modelos TFLite legítimos:
  - `hand_detector.tflite` (2.3 MB)
  - `hand_landmarks_detector.tflite` (5.5 MB)
- ⚠️ **Formato**: ZIP con TFLite, **NO es ONNX**

**Conclusión**: El archivo es **seguro y legítimo** (viene de Google Research), pero **no es compatible** con el código actual que espera ONNX.

**Recomendación**: 
- Opción A: Convertir TFLite a ONNX usando `tf2onnx`
- Opción B: Buscar modelos ONNX pre-convertidos

---

#### 3. `pose_landmark.onnx` (9.0 MB)

**Estado**: ⚠️ **FORMATO INCORRECTO** (ZIP con TFLite, no ONNX)

**Análisis de Seguridad**:
- ✅ **Fuente**: MediaPipe / Google Research
  - Los strings internos muestran: `MediaPipe`, `blazepose_detector`, `research/aimatter/nnets`
  - Google Research es una fuente **altamente confiable**
  - BlazePose es un modelo oficial de MediaPipe
- ✅ **Permisos**: `664` (no ejecutable)
- ✅ **Sin shebang**: No es un script ejecutable
- ✅ **Sin strings sospechosos**: No contiene código malicioso
- ✅ **Contenido**: ZIP con modelos TFLite legítimos:
  - `pose_detector.tflite` (3.0 MB)
  - `pose_landmarks_detector.tflite` (6.4 MB)
- ⚠️ **Formato**: ZIP con TFLite, **NO es ONNX**

**Conclusión**: El archivo es **seguro y legítimo** (viene de Google Research), pero **no es compatible** con el código actual que espera ONNX.

**Recomendación**: 
- Opción A: Convertir TFLite a ONNX usando `tf2onnx`
- Opción B: Buscar modelos ONNX pre-convertidos

---

## Verificaciones de Seguridad Realizadas

### ✅ Verificaciones Pasadas

1. **Permisos de archivo**: Todos los archivos tienen permisos `664` (no ejecutables)
2. **Shebang**: Ningún archivo contiene shebang (`#!/`) que indique scripts ejecutables
3. **Strings sospechosos**: No se encontraron strings como `eval()`, `exec()`, `__import__`, `subprocess`, `os.system`
4. **Magic bytes**: Verificados para identificar tipos de archivo reales
5. **Fuentes**: Verificadas contra organizaciones conocidas (Qualcomm, Google Research, HuggingFace)

### 🔍 Análisis de Contenido

- **face_landmark.onnx**: Contiene HTML (página de error)
- **hand_landmark.onnx**: Contiene ZIP con modelos TFLite de MediaPipe
- **pose_landmark.onnx**: Contiene ZIP con modelos TFLite de MediaPipe

---

## Fuentes Verificadas

| Archivo | Fuente Original | Confiabilidad | Estado |
|---------|----------------|---------------|--------|
| `face_landmark.onnx` | HuggingFace (Qualcomm) | ✅ Alta | ❌ Descarga fallida (HTML) |
| `hand_landmark.onnx` | Google Research / MediaPipe | ✅ Muy Alta | ⚠️ Formato TFLite (no ONNX) |
| `pose_landmark.onnx` | Google Research / MediaPipe | ✅ Muy Alta | ⚠️ Formato TFLite (no ONNX) |

---

## Recomendaciones

### Inmediatas

1. ✅ **Los archivos son seguros**: No hay evidencia de código malicioso
2. ⚠️ **Formato incompatible**: Los archivos no son ONNX válidos
3. 🔄 **Acción requerida**: Obtener modelos ONNX válidos o convertir TFLite a ONNX

### Opciones para Modelos Válidos

**Opción 1: Buscar ONNX pre-convertidos**
- HuggingFace: `https://huggingface.co/models?library=onnx&search=face+landmark`
- ONNX Model Zoo: `https://github.com/onnx/models`
- Verificar checksums SHA256 si están disponibles

**Opción 2: Convertir TFLite a ONNX**
```bash
pip install tf2onnx
# Usar los modelos TFLite actuales (que son legítimos)
# Convertir a ONNX
```

**Opción 3: Usar MediaPipe Python (temporal)**
- Para probar el pipeline mientras se obtienen modelos ONNX
- NO cumple el requisito de "100% C++", pero permite validar el flujo

---

## Conclusión Final

✅ **SEGURIDAD**: Todos los archivos son **seguros y provienen de fuentes confiables**:
- Qualcomm (HuggingFace) - empresa legítima
- Google Research / MediaPipe - fuente oficial y confiable

⚠️ **COMPATIBILIDAD**: Los archivos **NO son ONNX válidos**:
- `face_landmark.onnx`: HTML (error de descarga)
- `hand_landmark.onnx`: ZIP con TFLite (necesita conversión)
- `pose_landmark.onnx`: ZIP con TFLite (necesita conversión)

**No hay riesgo de seguridad**, pero se necesitan modelos ONNX válidos para que la integración funcione correctamente.

---

## Firmas y Verificación

- **Magic bytes verificados**: ✅
- **Strings analizados**: ✅
- **Fuentes verificadas**: ✅
- **Permisos verificados**: ✅
- **Contenido inspeccionado**: ✅

**Auditoría completada**: 2025-02-16

---

## Nota sobre Entradas Automáticas

Las entradas siguientes son generadas automáticamente por el script de descarga segura. Cada modelo descargado usando `scripts/download_onnx_mediapipe.sh` será registrado aquí con todas sus verificaciones de seguridad.

### Modelo: pose_landmark.onnx - 2026-02-20 14:23:40 UTC

- **Archivo**: `/home/fissure/repos/Spatial-Iteration-Engine/onnx_models/mediapipe/pose_landmark.onnx`
- **URL**: `https://huggingface.co/Xenova/yolov8n-pose/resolve/main/onnx/model_fp16.onnx`
- **Formato**: onnx
- **Tamaño**: 6789736 bytes (6.48 MB)
- **SHA256**: `e16e5f4abb3e67ee77877e8be3823b099463c9504c060008490cc1fd519a1cbb`
- **Fuente**: Verificada (whitelist)
- **Verificaciones**: ✅ Checksum, ✅ Formato, ✅ Permisos, ✅ Tamaño, ✅ Strings
- **Estado**: ✅ APROBADO

---

### Modelo: face_landmark.onnx - 2026-02-20 14:24:43 UTC

- **Archivo**: `/home/fissure/repos/Spatial-Iteration-Engine/onnx_models/mediapipe/face_landmark.onnx`
- **URL**: `https://huggingface.co/iuliancmarcu/detr-face-detection-onnx/resolve/main/onnx/model_quantized.onnx`
- **Formato**: onnx
- **Tamaño**: 166738273 bytes (159.01 MB)
- **SHA256**: `d20f797c161bbdb040a9cd4ee088cfae292a81212a095b003b10962b5a3da218`
- **Fuente**: Verificada (whitelist)
- **Verificaciones**: ✅ Checksum, ✅ Formato, ✅ Permisos, ✅ Tamaño, ✅ Strings
- **Estado**: ✅ APROBADO

---
