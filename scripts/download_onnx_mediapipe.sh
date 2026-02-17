#!/usr/bin/env bash
# Descarga modelos ONNX para percepción (face, hands, pose).
# Ejecutar desde la raíz del repo: ./scripts/download_onnx_mediapipe.sh

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
MODEL_DIR="${REPO_ROOT}/onnx_models/mediapipe"
mkdir -p "$MODEL_DIR"

echo "Directorio de modelos: $MODEL_DIR"
echo ""

# Función para descargar con múltiples intentos
download_model() {
  local filename=$1
  shift
  local urls=("$@")
  
  if [[ -f "${MODEL_DIR}/${filename}" ]]; then
    local size=$(stat -f%z "${MODEL_DIR}/${filename}" 2>/dev/null || stat -c%s "${MODEL_DIR}/${filename}" 2>/dev/null || echo 0)
    if [[ $size -gt 1000 ]]; then
      echo "✅ Ya existe: ${filename} (${size} bytes)"
      return 0
    else
      echo "⚠️  ${filename} existe pero es muy pequeño (${size} bytes), reintentando..."
      rm -f "${MODEL_DIR}/${filename}"
    fi
  fi
  
  echo "Descargando ${filename}..."
  for url in "${urls[@]}"; do
    echo "  Intentando: ${url}"
    if command -v wget >/dev/null 2>&1; then
      if wget -q --timeout=10 -O "${MODEL_DIR}/${filename}.tmp" "${url}" 2>/dev/null; then
        local size=$(stat -f%z "${MODEL_DIR}/${filename}.tmp" 2>/dev/null || stat -c%s "${MODEL_DIR}/${filename}.tmp" 2>/dev/null || echo 0)
        if [[ $size -gt 1000 ]]; then
          mv "${MODEL_DIR}/${filename}.tmp" "${MODEL_DIR}/${filename}"
          echo "  ✅ Descargado: ${filename} (${size} bytes)"
          return 0
        else
          rm -f "${MODEL_DIR}/${filename}.tmp"
        fi
      fi
    elif command -v curl >/dev/null 2>&1; then
      if curl -sL --max-time 10 -o "${MODEL_DIR}/${filename}.tmp" "${url}" 2>/dev/null; then
        local size=$(stat -f%z "${MODEL_DIR}/${filename}.tmp" 2>/dev/null || stat -c%s "${MODEL_DIR}/${filename}.tmp" 2>/dev/null || echo 0)
        if [[ $size -gt 1000 ]]; then
          mv "${MODEL_DIR}/${filename}.tmp" "${MODEL_DIR}/${filename}"
          echo "  ✅ Descargado: ${filename} (${size} bytes)"
          return 0
        else
          rm -f "${MODEL_DIR}/${filename}.tmp"
        fi
      fi
    fi
  done
  
  echo "  ❌ No se pudo descargar ${filename} desde ninguna fuente"
  echo "     Puedes descargarlo manualmente y colocarlo en: ${MODEL_DIR}/${filename}"
  return 1
}

# Face: Modelos ONNX disponibles
# Nota: UltraFace es detección, no landmarks. Para landmarks reales necesitas convertir desde MediaPipe
download_model "face_landmark.onnx" \
  "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/ultraface/models/version-RFB-320.onnx" || true

echo ""
echo "⚠️  IMPORTANTE: El modelo UltraFace descargado es para DETECCIÓN de caras (bounding boxes),"
echo "   no para landmarks. Para landmarks faciales necesitas:"
echo "   1. Convertir modelos MediaPipe TFLite a ONNX"
echo "   2. Usar MediaPipe Python API y exportar a ONNX"
echo "   3. Descargar modelos pre-convertidos desde repositorios comunitarios"
echo ""

# Hands: Intentar desde repositorios conocidos
download_model "hand_landmark.onnx" \
  "https://github.com/google/mediapipe/raw/master/mediapipe/modules/hand_landmark/hand_landmark_full.tflite" \
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" || true

# Pose: Intentar desde repositorios conocidos  
download_model "pose_landmark.onnx" \
  "https://github.com/google/mediapipe/raw/master/mediapipe/modules/pose_landmark/pose_landmark_full.tflite" \
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task" || true

echo ""
echo "📝 Nota: Algunos modelos pueden estar en formato TFLite, no ONNX."
echo "   Para convertir TFLite a ONNX, puedes usar herramientas como:"
echo "   - onnx-tf (TensorFlow Lite to ONNX)"
echo "   - MediaPipe Python API para exportar a ONNX"
echo ""
echo "📦 Fuentes alternativas de modelos ONNX:"
echo "   1. ONNX Model Zoo: https://github.com/onnx/models"
echo "   2. HuggingFace: https://huggingface.co/models?library=onnx"
echo "   3. MediaPipe: https://developers.google.com/mediapipe/solutions/vision"
echo ""
echo "✅ Listo. Para usar desde cualquier directorio:"
echo "   export ONNX_MODELS_DIR=${MODEL_DIR}"
