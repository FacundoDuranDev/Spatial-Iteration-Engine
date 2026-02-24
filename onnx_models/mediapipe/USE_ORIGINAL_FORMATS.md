# Usar Modelos en su Formato Original (Sin Conversión)

**Respuesta corta**: ✅ **SÍ, puedes usar los modelos en su formato original** sin necesidad de conversión.

Solo necesitas implementar soporte para el runtime correspondiente, similar a como ya está implementado ONNX Runtime.

---

## 🏗️ Arquitectura Actual (ONNX Runtime)

El proyecto ya tiene una arquitectura modular que permite agregar nuevos runtimes:

### Estructura Actual

```
cpp/src/perception/
├── onnx_runner.cpp      # Implementación de ONNX Runtime
├── onnx_runner.hpp      # Interfaz del runner
├── face_landmarks.cpp   # Usa OnnxRunner
├── hand_landmarks.cpp   # Usa OnnxRunner
└── pose_landmarks.cpp   # Usa OnnxRunner
```

**Cómo funciona**:
1. `OnnxRunner` encapsula toda la lógica de ONNX Runtime
2. Los módulos de landmarks (`face_landmarks.cpp`, etc.) usan `OnnxRunner`
3. CMakeLists.txt busca ONNX Runtime opcionalmente
4. Si no encuentra ONNX Runtime, usa stubs (no hace nada, pero no falla)

---

## ✅ Opción 1: Usar TFLite Directamente (Sin Conversión)

### Lo que necesitas hacer:

#### 1. Crear `TfliteRunner` (similar a `OnnxRunner`)

**Archivo**: `cpp/src/perception/tflite_runner.cpp`
```cpp
#include "perception/tflite_runner.hpp"

#ifdef USE_TFLITE
#include <tensorflow/lite/interpreter.h>
#include <tensorflow/lite/kernels/register.h>
#include <tensorflow/lite/model.h>
// ... implementación similar a onnx_runner.cpp
#endif
```

**Archivo**: `cpp/include/perception/tflite_runner.hpp`
```cpp
namespace perception {
class TfliteRunner {
  // Interfaz similar a OnnxRunner
  bool load(const std::string& model_path);
  std::vector<float> run(const std::uint8_t* image, int width, int height);
};
}
```

#### 2. Actualizar `CMakeLists.txt` para buscar TensorFlow Lite

```cmake
# Buscar TensorFlow Lite
find_path(TFLITE_INCLUDE_DIR 
  tensorflow/lite/interpreter.h
  HINTS ${CONDA_PREFIX}/include
)
find_library(TFLITE_LIB 
  tensorflowlite
  HINTS ${CONDA_PREFIX}/lib
)

if(TFLITE_INCLUDE_DIR AND TFLITE_LIB)
  set(USE_TFLITE 1)
  target_include_directories(perception_cpp PRIVATE ${TFLITE_INCLUDE_DIR})
  target_link_libraries(perception_cpp PRIVATE ${TFLITE_LIB})
  target_compile_definitions(perception_cpp PRIVATE USE_TFLITE=1)
endif()
```

#### 3. Actualizar módulos de landmarks para usar TFLite

**Ejemplo**: `cpp/src/perception/hand_landmarks.cpp`
```cpp
#ifdef USE_TFLITE
#include "perception/tflite_runner.hpp"
static TfliteRunner runner;
#else
#include "perception/onnx_runner.hpp"
static OnnxRunner runner;
#endif

// Usar runner igual que antes
```

#### 4. Instalar TensorFlow Lite C++

```bash
# Opción 1: Desde conda
conda install -c conda-forge tensorflow-lite

# Opción 2: Compilar desde fuente
# Ver: https://www.tensorflow.org/lite/guide/build_cmake
```

---

## ✅ Opción 2: Usar NCNN Directamente

### Lo que necesitas hacer:

#### 1. Crear `NcnnRunner` (similar a `OnnxRunner`)

**Archivo**: `cpp/src/perception/ncnn_runner.cpp`
```cpp
#include "perception/ncnn_runner.hpp"

#ifdef USE_NCNN
#include <ncnn/net.h>
// ... implementación usando NCNN API
#endif
```

#### 2. Actualizar `CMakeLists.txt` para buscar NCNN

```cmake
# Buscar NCNN
find_path(NCNN_INCLUDE_DIR ncnn/net.h)
find_library(NCNN_LIB ncnn)

if(NCNN_INCLUDE_DIR AND NCNN_LIB)
  set(USE_NCNN 1)
  # ... configurar
endif()
```

#### 3. Instalar NCNN

```bash
git clone https://github.com/Tencent/ncnn.git
cd ncnn
mkdir build && cd build
cmake .. && make -j4
# Instalar o usar directamente
```

---

## ✅ Opción 3: Usar OpenVINO Directamente

### Lo que necesitas hacer:

#### 1. Crear `OpenVINORunner` (similar a `OnnxRunner`)

**Archivo**: `cpp/src/perception/openvino_runner.cpp`
```cpp
#include "perception/openvino_runner.hpp"

#ifdef USE_OPENVINO
#include <openvino/openvino.hpp>
// ... implementación usando OpenVINO API
#endif
```

#### 2. Actualizar `CMakeLists.txt` para buscar OpenVINO

```cmake
# Buscar OpenVINO
find_package(OpenVINO)
# ... configurar
```

---

## 📊 Comparación: Conversión vs. Runtime Nativo

| Aspecto | Conversión (TFLite→ONNX) | Runtime Nativo (TFLite) |
|---------|-------------------------|-------------------------|
| **Complejidad** | ⭐ Fácil (solo ejecutar script) | ⭐⭐⭐ Requiere implementar código |
| **Performance** | ⭐⭐⭐ Buena (ONNX optimizado) | ⭐⭐⭐⭐ Excelente (nativo) |
| **Tamaño modelo** | Puede aumentar ligeramente | Original (más pequeño) |
| **Mantenimiento** | ⭐⭐ Dos formatos | ⭐ Un formato |
| **Tiempo** | ⭐ Rápido (minutos) | ⭐⭐⭐ Horas de desarrollo |

---

## 🎯 Recomendación

### Para Desarrollo Rápido
**Usar conversión TFLite → ONNX**:
- ✅ Ya tienes código ONNX funcionando
- ✅ Solo necesitas ejecutar `tf2onnx`
- ✅ Funciona inmediatamente

### Para Producción / Máxima Performance
**Implementar soporte TFLite nativo**:
- ✅ Mejor performance (modelos optimizados por Google)
- ✅ Tamaños más pequeños
- ✅ Un solo formato (TFLite) para todos los modelos MediaPipe

### Para Flexibilidad Máxima
**Soporte múltiple (ONNX + TFLite)**:
- ✅ El código ya está preparado para esto (modular)
- ✅ Puedes usar ONNX cuando esté disponible
- ✅ Puedes usar TFLite cuando sea mejor

---

## 💡 Ventajas de Usar Formatos Originales

1. **Performance**: Los modelos están optimizados para su runtime nativo
2. **Tamaño**: No hay overhead de conversión
3. **Actualizaciones**: Puedes usar modelos actualizados directamente
4. **Compatibilidad**: Mejor compatibilidad con modelos oficiales (MediaPipe)

---

## 🔧 Ejemplo: Implementar TFLite Runner

### Paso 1: Crear estructura básica

```cpp
// cpp/include/perception/tflite_runner.hpp
namespace perception {
class TfliteRunner {
 public:
  TfliteRunner();
  ~TfliteRunner();
  bool load(const std::string& model_path);
  std::vector<float> run(const std::uint8_t* image, int width, int height);
 private:
  std::unique_ptr<tflite::FlatBufferModel> model_;
  std::unique_ptr<tflite::Interpreter> interpreter_;
  bool loaded_ = false;
};
}
```

### Paso 2: Implementar carga y ejecución

```cpp
// cpp/src/perception/tflite_runner.cpp
bool TfliteRunner::load(const std::string& model_path) {
  model_ = tflite::FlatBufferModel::BuildFromFile(model_path.c_str());
  if (!model_) return false;
  
  tflite::ops::builtin::BuiltinOpResolver resolver;
  tflite::InterpreterBuilder builder(*model_, resolver);
  builder(&interpreter_);
  
  if (!interpreter_) return false;
  interpreter_->AllocateTensors();
  loaded_ = true;
  return true;
}

std::vector<float> TfliteRunner::run(const std::uint8_t* image, int width, int height) {
  // Preprocesar imagen (similar a onnx_runner.cpp)
  // Ejecutar inferencia
  // Postprocesar resultados
}
```

### Paso 3: Integrar en CMakeLists.txt

```cmake
# Agregar tflite_runner.cpp a PERCEPTION_SOURCES
set(PERCEPTION_SOURCES
  src/perception/face_landmarks.cpp
  src/perception/hand_landmarks.cpp
  src/perception/pose_landmarks.cpp
  src/perception/onnx_runner.cpp
  src/perception/tflite_runner.cpp  # Nuevo
)
```

---

## 📝 Conclusión

**NO es necesario convertir** si implementas soporte para el runtime correspondiente. La arquitectura del proyecto ya está preparada para esto (modular, con stubs opcionales).

**Ventajas de usar formatos originales**:
- ✅ Mejor performance
- ✅ Tamaños más pequeños
- ✅ Compatibilidad directa con modelos oficiales

**Desventajas**:
- ⚠️ Requiere implementar código adicional
- ⚠️ Más tiempo de desarrollo

**Recomendación**: Para desarrollo rápido, usa conversión. Para producción, considera implementar soporte nativo.

