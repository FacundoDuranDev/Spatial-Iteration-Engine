#!/usr/bin/env bash
# Descarga segura de modelos TFLite de MediaPipe desde fuentes oficiales
# Cumple con rules/SECURITY_MODEL_DOWNLOAD.md
# Ejecutar desde la raíz del repo: ./scripts/download_tflite_mediapipe.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
MODEL_DIR="${REPO_ROOT}/onnx_models/mediapipe/tflite"
TEMP_DIR="${REPO_ROOT}/onnx_models/.tmp"
AUDIT_FILE="${REPO_ROOT}/SECURITY_AUDIT.md"
mkdir -p "$MODEL_DIR" "$TEMP_DIR"

# Importar funciones de seguridad del script ONNX
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/download_onnx_mediapipe.sh" 2>/dev/null || {
    echo "ERROR: No se pudo cargar funciones de seguridad"
    exit 1
}

echo "=========================================="
echo "Descarga Segura de Modelos TFLite (MediaPipe)"
echo "Cumple con: rules/SECURITY_MODEL_DOWNLOAD.md"
echo "=========================================="
echo "Directorio de modelos: $MODEL_DIR"
echo ""

# Nota: MediaPipe TFLite se obtiene principalmente desde GitHub
# Los modelos están en el repositorio oficial de Google

echo "ℹ️  Modelos TFLite de MediaPipe:"
echo ""
echo "Los modelos TFLite oficiales de MediaPipe están en:"
echo "  https://github.com/google/mediapipe"
echo ""
echo "Para obtenerlos:"
echo "  1. Clonar el repositorio: git clone https://github.com/google/mediapipe.git"
echo "  2. Los modelos están en: mediapipe/modules/{face,hand,pose}_landmark/"
echo "  3. O descargar desde releases oficiales"
echo ""
echo "Ya tenemos modelos TFLite en los archivos ZIP:"
echo "  - hand_landmark.onnx (contiene hand_*.tflite)"
echo "  - pose_landmark.onnx (contiene pose_*.tflite)"
echo ""
echo "Para extraerlos:"
echo "  unzip onnx_models/mediapipe/hand_landmark.onnx"
echo "  unzip onnx_models/mediapipe/pose_landmark.onnx"
echo ""
echo "Luego puedes:"
echo "  1. Usar TFLite directamente (requiere TensorFlow Lite C++)"
echo "  2. Convertir a ONNX usando tf2onnx"
echo ""
echo "Ver: onnx_models/mediapipe/ALTERNATIVE_FORMATS.md para más información"

# Limpiar directorio temporal
rm -rf "$TEMP_DIR"

echo ""
echo "=========================================="
echo "Para más información sobre formatos alternativos:"
echo "  - onnx_models/mediapipe/ALTERNATIVE_FORMATS.md"
echo "  - rules/MVP_IA.md (tecnologías permitidas)"
echo "=========================================="

