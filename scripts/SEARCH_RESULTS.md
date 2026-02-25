# Resultados de Búsqueda - Modelos ONNX

**Fecha**: 2025-02-16  
**Proceso**: Búsqueda segura siguiendo `rules/SECURITY_MODEL_DOWNLOAD.md`

---

## 🔍 Proceso Ejecutado

1. ✅ Ejecutado `find_onnx_models.sh` - Proceso documentado
2. ✅ Buscado en HuggingFace API - Modelos encontrados
3. ✅ Verificado URLs - Algunas requieren autenticación
4. ✅ Documentado resultados

---

## 📊 Modelos Encontrados

### Face Detection

**Modelos encontrados en HuggingFace**:
- `iuliancmarcu/detr-face-detection-onnx`: 1 descarga
  - ⚠️ Muy pocas descargas (puede ser experimental)
  - ✅ Fuente confiable (HuggingFace)
  - ⚠️ Requiere verificación manual de URL

- `ayusrjn/optimized_face_detection_onnx`: 0 descargas
  - ⚠️ Sin descargas (muy nuevo o no verificado)
  - ✅ Fuente confiable (HuggingFace)
  - ⚠️ Requiere verificación manual

### Hand Landmarks

- ❌ No se encontraron modelos ONNX directos
- 💡 **Alternativa**: Convertir modelos TFLite de MediaPipe

### Pose Estimation

- ❌ No se encontraron modelos ONNX directos con búsqueda básica
- 💡 **Alternativa**: Buscar YOLOv8-Pose o convertir MediaPipe

---

## ⚠️ Observaciones Importantes

### 1. URLs Requieren Verificación Manual

Las URLs de HuggingFace pueden:
- Requerir autenticación (401)
- Cambiar estructura (404)
- Necesitar navegación manual en el sitio

### 2. Modelos con Pocas Descargas

Los modelos encontrados tienen muy pocas descargas, lo que sugiere:
- Pueden ser experimentales
- Pueden no estar completamente probados
- Requieren verificación adicional antes de usar en producción

### 3. Estrategia Recomendada

**Opción A: Búsqueda Manual en HuggingFace**
1. Visitar: `https://huggingface.co/models?library=onnx&search=face+detection`
2. Filtrar por: Más descargas, mejor documentación
3. Verificar licencia y documentación
4. Obtener URL de descarga desde la interfaz web

**Opción B: Usar Modelos TFLite y Convertir**
1. Descargar modelos TFLite desde Google Research/MediaPipe
2. Convertir a ONNX usando `tf2onnx`
3. Validar modelo convertido

**Opción C: Modelos de ONNX Model Zoo**
1. Navegar manualmente: `https://github.com/onnx/models`
2. Verificar estructura actual del repositorio
3. Obtener URLs raw de GitHub

---

## ✅ Próximos Pasos

1. **Búsqueda manual en HuggingFace**: Encontrar modelos con más descargas
2. **Verificar URLs manualmente**: Usar navegador para obtener URLs correctas
3. **Considerar conversión TFLite**: Para modelos MediaPipe específicos
4. **Actualizar script**: Agregar URLs verificadas cuando se encuentren

---

## 🔐 Verificación de Seguridad

Todos los modelos encontrados:
- ✅ Provienen de fuentes en whitelist (HuggingFace)
- ⚠️ Requieren verificación adicional (pocas descargas)
- ⚠️ URLs necesitan verificación manual (estructura puede variar)

**Recomendación**: Usar modelos con >100 descargas y documentación completa.

