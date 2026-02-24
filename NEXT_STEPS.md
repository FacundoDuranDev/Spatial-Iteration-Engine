# Próximos Pasos - Integración ONNX

## ✅ Completado

1. ✅ ONNX Runtime instalado y configurado
2. ✅ Módulo `perception_cpp` compilado con ONNX Runtime (100% C++)
3. ✅ Adapters Python funcionando (solo wrappers, delegan en C++)
4. ✅ Script de descarga de modelos mejorado
5. ✅ Documentación de arquitectura creada
6. ✅ Commits realizados en `feature/integracion-ONNX`

## 📋 Siguientes Pasos (en orden)

### 1. Obtener Modelos ONNX Válidos (PRIORITARIO)

**Estado actual**: Los modelos descargados no son compatibles:
- `face_landmark.onnx`: UltraFace (detección, no landmarks) - puede funcionar parcialmente
- `hand_landmark.onnx`: Formato TFLite/Task - necesita conversión
- `pose_landmark.onnx`: Formato TFLite/Task - necesita conversión

**Opciones**:

**A) Buscar modelos ONNX pre-convertidos**:
```bash
# Buscar en HuggingFace
# https://huggingface.co/models?library=onnx&search=face+landmark
# https://huggingface.co/models?library=onnx&search=hand+landmark
# https://huggingface.co/models?library=onnx&search=pose+landmark
```

**B) Convertir TFLite a ONNX**:
```bash
pip install tf2onnx
# Descargar modelos TFLite desde MediaPipe
# Convertir usando tf2onnx
```

**C) Probar con modelo actual** (UltraFace):
- Aunque es detección, puede usarse para verificar que la inferencia funciona

### 2. Probar el Pipeline Completo

Una vez tengas modelos válidos (o para probar con UltraFace):

```bash
# Activar entorno
conda activate spatial-iteration-engine

# Configurar PYTHONPATH
export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
export ONNX_MODELS_DIR="$(pwd)/onnx_models/mediapipe"

# Ejecutar ejemplo
python python/ascii_stream_engine/examples/stream_with_landmarks.py
```

**Verificar**:
- ✅ El módulo `perception_cpp` se importa correctamente
- ✅ Los modelos ONNX se cargan sin errores
- ✅ La inferencia devuelve resultados (aunque sean 0 puntos si el modelo no es compatible)
- ✅ El pipeline no se rompe si no hay modelos

### 3. Verificar Visualización de Landmarks

Si los modelos funcionan y devuelven landmarks:
- Verificar que `LandmarksOverlayRenderer` dibuja los puntos correctamente
- Ajustar colores/tamaños si es necesario

### 4. Commit Final y Merge

```bash
# Desde feature/integracion-ONNX
git add .  # Solo archivos relevantes (no cpp/build/)
git commit -m "feat: complete ONNX integration with working models"

# Mergear a develop
git checkout develop
git pull origin develop
git merge feature/integracion-ONNX
git push origin develop
```

### 5. Opcional: Crear Ejemplo Funcional

Si todo funciona, crear un ejemplo más completo que demuestre:
- Múltiples analizadores funcionando simultáneamente
- Integración con filtros
- Uso en notebooks

## 🎯 Prioridad

1. **ALTA**: Obtener modelos ONNX válidos (sin esto, la integración no funciona completamente)
2. **MEDIA**: Probar el pipeline end-to-end
3. **BAJA**: Mejoras y optimizaciones

## 📝 Notas

- Los archivos en `cpp/build/` no deben committearse (están en .gitignore)
- Los modelos ONNX grandes no deben committearse (están en .gitignore)
- La integración técnica está completa; solo faltan modelos válidos para probarla

