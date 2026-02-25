#!/usr/bin/env bash
# Script auxiliar para buscar modelos ONNX desde fuentes confiables
# Ayuda a encontrar URLs válidas siguiendo las reglas de seguridad
# Uso: ./scripts/find_onnx_models.sh [face|hands|pose]

set -euo pipefail

SEARCH_TERM="${1:-face}"

echo "=========================================="
echo "Búsqueda Segura de Modelos ONNX"
echo "Cumple con: rules/SECURITY_MODEL_DOWNLOAD.md"
echo "=========================================="
echo ""

echo "🔍 Buscando modelos para: $SEARCH_TERM"
echo ""

# 1. HuggingFace (API)
echo "=== 1. HuggingFace Hub ==="
echo "Buscando en: https://huggingface.co/models?library=onnx&search=$SEARCH_TERM"
echo ""
echo "Para encontrar modelos:"
echo "  1. Visita: https://huggingface.co/models?library=onnx&search=$SEARCH_TERM"
echo "  2. Selecciona un modelo con muchas descargas y buena documentación"
echo "  3. Ve a 'Files and versions'"
echo "  4. Copia la URL de descarga directa"
echo "  5. Verifica que cumple con rules/SECURITY_MODEL_DOWNLOAD.md"
echo ""

# 2. ONNX Model Zoo
echo "=== 2. ONNX Model Zoo (GitHub) ==="
echo "Repositorio: https://github.com/onnx/models"
echo ""
echo "Para encontrar modelos:"
echo "  1. Visita: https://github.com/onnx/models"
echo "  2. Navega a: vision/body_analysis/ para modelos de detección"
echo "  3. Busca modelos relacionados con: $SEARCH_TERM"
echo "  4. Usa URL raw: https://github.com/onnx/models/raw/main/{ruta}/{archivo}.onnx"
echo "  5. Verifica accesibilidad con: curl -I {URL}"
echo ""

# 3. Google Research / MediaPipe
echo "=== 3. Google Research / MediaPipe ==="
echo "Repositorio: https://github.com/google/mediapipe"
echo ""
echo "NOTA: MediaPipe proporciona principalmente modelos TFLite"
echo "Para convertir a ONNX:"
echo "  1. Descarga modelo TFLite desde: https://github.com/google/mediapipe"
echo "  2. Convierte usando: pip install tf2onnx"
echo "  3. python -m tf2onnx.convert --saved-model model.tflite --output model.onnx"
echo ""

# 4. Verificación
echo "=== 4. Verificación de Seguridad ==="
echo "Antes de usar cualquier URL, verifica:"
echo "  ✅ Fuente está en whitelist (rules/SECURITY_MODEL_DOWNLOAD.md)"
echo "  ✅ URL es accesible (curl -I {URL})"
echo "  ✅ Modelo tiene licencia clara"
echo "  ✅ Documentación disponible"
echo "  ✅ Checksum disponible (si es posible)"
echo ""

# 5. Uso del script de descarga
echo "=== 5. Descargar con Script Seguro ==="
echo "Una vez tengas una URL válida, puedes:"
echo "  1. Editar scripts/download_onnx_mediapipe.sh"
echo "  2. Agregar la URL a la función download_with_verification"
echo "  3. Ejecutar: ./scripts/download_onnx_mediapipe.sh"
echo ""
echo "O descargar manualmente y validar:"
echo "  ./scripts/download_onnx_mediapipe.sh  # Validará el archivo si existe"
echo ""

echo "=========================================="
echo "Para más información, ver:"
echo "  - onnx_models/mediapipe/TRUSTED_SOURCES.md"
echo "  - rules/SECURITY_MODEL_DOWNLOAD.md"
echo "=========================================="

