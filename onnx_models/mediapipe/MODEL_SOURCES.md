# Fuentes de Modelos ONNX para Percepción

## Estado Actual

Los modelos descargados automáticamente pueden no ser compatibles directamente:
- **face_landmark.onnx**: UltraFace (detección, no landmarks) - 1.3MB
- **hand_landmark.onnx**: TFLite/Task format - 7.5MB  
- **pose_landmark.onnx**: TFLite/Task format - 9.0MB

## Soluciones Recomendadas

### Opción 1: Convertir MediaPipe TFLite a ONNX

MediaPipe proporciona modelos en formato TFLite. Para convertirlos a ONNX:

```bash
# Instalar herramientas de conversión
pip install tf2onnx onnx-tf

# Descargar modelos TFLite desde MediaPipe
# Luego convertir usando tf2onnx o herramientas similares
```

### Opción 2: Usar MediaPipe Python API

MediaPipe Python puede exportar resultados que luego puedes usar:

```python
import mediapipe as mp

# Usar MediaPipe directamente y obtener landmarks
# Luego adaptar el código para usar esos landmarks
```

### Opción 3: Modelos ONNX Pre-convertidos

Buscar en:
- **HuggingFace**: https://huggingface.co/models?library=onnx&search=face+landmark
- **ONNX Model Zoo**: https://github.com/onnx/models
- **Repositorios comunitarios**: GitHub search "mediapipe onnx face landmark"

### Opción 4: Modelos Alternativos Compatibles

Para probar la integración mientras buscas modelos MediaPipe:

1. **Face Detection** (ya descargado - UltraFace):
   - Funciona pero devuelve bounding boxes, no landmarks
   - Puede usarse para detectar presencia de cara

2. **Modelos de landmarks alternativos**:
   - Buscar "facial landmarks ONNX" en HuggingFace
   - Modelos de 68 puntos o 468 puntos

## Nota sobre el Código Actual

El código en `cpp/src/perception/onnx_runner.cpp` espera:
- **Input**: RGB image (uint8), se redimensiona automáticamente
- **Output**: Array de floats con landmarks (x,y) o (x,y,z) normalizados 0-1

Cualquier modelo ONNX que cumpla estos requisitos debería funcionar.

## Próximos Pasos

1. Probar con el modelo UltraFace actual (aunque sea detección, verifica que la inferencia funciona)
2. Buscar modelos de landmarks específicos en HuggingFace
3. Considerar usar MediaPipe Python como fallback si no hay modelos ONNX disponibles

