# Formatos Alternativos de Modelos - TFLite, NCNN, OpenVINO

**Fecha**: 2025-02-16  
**Basado en**: `rules/MVP_IA.md` - Tecnologías permitidas

Según las reglas del proyecto (`MVP_IA.md`), además de ONNX Runtime, se permiten:
- ✅ **NCNN**
- ✅ **TensorFlow Lite**
- ✅ **OpenVINO**

---

## 📋 Formatos Permitidos y Fuentes

### 1. TensorFlow Lite (TFLite)

**Runtime**: TensorFlow Lite C++  
**Fuentes confiables**:
- ✅ Google Research / MediaPipe (`github.com/google/mediapipe`)
- ✅ TensorFlow Hub (`tensorflow.org`)
- ✅ HuggingFace (modelos convertidos)

**Ventajas**:
- ✅ MediaPipe proporciona modelos TFLite oficiales
- ✅ Optimizado para móviles y edge devices
- ✅ Tamaños pequeños
- ✅ Buena documentación

**Desventajas**:
- ⚠️ Requiere TensorFlow Lite C++ (diferente de ONNX Runtime)
- ⚠️ Necesita conversión a ONNX si quieres usar ONNX Runtime

---

### 2. NCNN

**Runtime**: NCNN (Tencent)  
**Fuentes confiables**:
- ✅ Model Zoo de NCNN (`github.com/Tencent/ncnn`)
- ✅ Repositorios comunitarios verificados

**Ventajas**:
- ✅ Muy optimizado para CPU
- ✅ Tamaños pequeños
- ✅ Buena performance en tiempo real
- ✅ Creado por Tencent (empresa confiable)

**Desventajas**:
- ⚠️ Requiere NCNN runtime (diferente de ONNX Runtime)
- ⚠️ Menos modelos disponibles que ONNX

---

### 3. OpenVINO

**Runtime**: OpenVINO (Intel)  
**Fuentes confiables**:
- ✅ OpenVINO Model Zoo (`github.com/openvinotoolkit/open_model_zoo`)
- ✅ Intel AI Hub

**Ventajas**:
- ✅ Optimizado para hardware Intel
- ✅ Modelos oficiales de Intel
- ✅ Buena documentación

**Desventajas**:
- ⚠️ Requiere OpenVINO runtime
- ⚠️ Mejor performance en hardware Intel

---

## 🔍 Modelos TFLite Disponibles (MediaPipe)

### Face Landmarks

**Fuente**: Google Research / MediaPipe  
**Repositorio**: `https://github.com/google/mediapipe`

**Modelos disponibles**:
- Face Landmark Detector (468 puntos)
- Face Mesh (468 puntos con profundidad)

**Descarga**:
```bash
# Los modelos TFLite están en el repositorio de MediaPipe
# Requieren clonar el repo o descargar releases
```

---

### Hand Landmarks

**Fuente**: Google Research / MediaPipe  
**Modelos**:
- Hand Detector (detección de palmas)
- Hand Landmark Detector (21 puntos por mano)

**Ya tenemos**: `hand_landmark.onnx` contiene estos modelos TFLite en ZIP

---

### Pose Landmarks

**Fuente**: Google Research / MediaPipe  
**Modelos**:
- Pose Detector (detección de personas)
- Pose Landmark Detector (33 puntos de pose)

**Ya tenemos**: `pose_landmark.onnx` contiene estos modelos TFLite en ZIP

---

## 💡 Estrategias de Uso

### Opción 1: Usar TFLite Directamente (Recomendado para MediaPipe)

**Ventaja**: Modelos oficiales de Google, muy optimizados

**Implementación**:
1. Instalar TensorFlow Lite C++:
   ```bash
   conda install -c conda-forge tensorflow-lite
   ```
2. Crear módulo C++ similar a `onnx_runner.cpp` pero para TFLite
3. Usar los modelos TFLite que ya tenemos (en los ZIPs)

**Código necesario**:
- `cpp/src/perception/tflite_runner.cpp` (similar a `onnx_runner.cpp`)
- Actualizar `CMakeLists.txt` para incluir TensorFlow Lite

---

### Opción 2: Convertir TFLite a ONNX

**Ventaja**: Usar el código ONNX Runtime que ya tenemos

**Proceso**:
```bash
# Instalar herramientas de conversión
pip install tf2onnx

# Extraer TFLite de los ZIPs que tenemos
unzip hand_landmark.onnx
# (contiene hand_detector.tflite y hand_landmarks_detector.tflite)

# Convertir a ONNX
python -m tf2onnx.convert \
  --saved-model hand_landmarks_detector.tflite \
  --output hand_landmark.onnx
```

**Nota**: La conversión puede requerir ajustes según el modelo.

---

### Opción 3: Usar NCNN (Para Performance)

**Ventaja**: Muy rápido en CPU, optimizado por Tencent

**Modelos disponibles**:
- Buscar en: `https://github.com/Tencent/ncnn/tree/master/models`
- O convertir desde ONNX usando `onnx2ncnn`

**Implementación**:
1. Instalar NCNN:
   ```bash
   git clone https://github.com/Tencent/ncnn.git
   cd ncnn && mkdir build && cd build
   cmake .. && make -j4
   ```
2. Crear módulo C++ para NCNN
3. Convertir modelos ONNX a NCNN si es necesario

---

## 🔐 Verificación de Seguridad para Formatos Alternativos

### TFLite

**Verificaciones**:
- ✅ Magic bytes: `TFL3` o formato FlatBuffers
- ✅ Fuente: Google Research / MediaPipe (muy confiable)
- ✅ Tamaño: Verificar razonable
- ✅ Permisos: No ejecutable

**Fuentes permitidas**:
- `github.com/google/mediapipe` ✅
- `tensorflow.org` ✅
- `huggingface.co` (con verificación) ✅

---

### NCNN

**Verificaciones**:
- ✅ Magic bytes: Formato NCNN específico
- ✅ Fuente: Tencent NCNN Model Zoo (confiable)
- ✅ Tamaño: Verificar razonable
- ✅ Permisos: No ejecutable

**Fuentes permitidas**:
- `github.com/Tencent/ncnn` ✅
- Repositorios verificados de la comunidad

---

### OpenVINO

**Verificaciones**:
- ✅ Formato: IR (Intermediate Representation) de OpenVINO
- ✅ Fuente: Intel OpenVINO Model Zoo (confiable)
- ✅ Tamaño: Verificar razonable
- ✅ Permisos: No ejecutable

**Fuentes permitidas**:
- `github.com/openvinotoolkit/open_model_zoo` ✅
- `ai.intel.com` ✅

---

## 📊 Comparación de Formatos

| Formato | Runtime | Performance | Tamaño | Disponibilidad Modelos | Facilidad |
|---------|---------|-------------|--------|------------------------|-----------|
| **ONNX** | ONNX Runtime | ⭐⭐⭐⭐ | Medio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **TFLite** | TensorFlow Lite | ⭐⭐⭐⭐⭐ | Pequeño | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **NCNN** | NCNN | ⭐⭐⭐⭐⭐ | Muy Pequeño | ⭐⭐⭐ | ⭐⭐⭐ |
| **OpenVINO** | OpenVINO | ⭐⭐⭐⭐⭐* | Medio | ⭐⭐⭐⭐ | ⭐⭐⭐ |

*Mejor en hardware Intel

---

## 🎯 Recomendación por Caso de Uso

### Para MediaPipe Específicamente
**Recomendado**: **TFLite** (formato nativo de MediaPipe)
- Modelos oficiales disponibles
- Muy optimizados
- Requiere agregar soporte TFLite al código C++

### Para Máxima Compatibilidad
**Recomendado**: **ONNX** (ya implementado)
- Más modelos disponibles
- Código ya implementado
- Convertir TFLite → ONNX si es necesario

### Para Máxima Performance en CPU
**Recomendado**: **NCNN**
- Muy rápido
- Optimizado por Tencent
- Requiere implementar soporte NCNN

---

## 📝 Próximos Pasos

1. **Decidir formato**: ¿TFLite, NCNN, o convertir a ONNX?
2. **Implementar runtime**: Si se elige TFLite o NCNN, agregar soporte en C++
3. **Actualizar reglas de seguridad**: Incluir formatos alternativos en whitelist
4. **Crear scripts de descarga**: Para formatos alternativos

---

## 🔗 Enlaces Útiles

- **MediaPipe TFLite**: https://github.com/google/mediapipe
- **NCNN Model Zoo**: https://github.com/Tencent/ncnn/tree/master/models
- **OpenVINO Model Zoo**: https://github.com/openvinotoolkit/open_model_zoo
- **TensorFlow Lite C++**: https://www.tensorflow.org/lite/guide/build_cmake

