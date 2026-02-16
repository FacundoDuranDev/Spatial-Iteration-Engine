#!/usr/bin/env bash
# Descarga modelos ONNX para percepción (face; hands/pose si hay URL pública).
# Ejecutar desde la raíz del repo: ./scripts/download_onnx_mediapipe.sh

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
MODEL_DIR="${REPO_ROOT}/onnx_models/mediapipe"
mkdir -p "$MODEL_DIR"

echo "Directorio de modelos: $MODEL_DIR"

# Face: Qualcomm MediaPipe Face Landmark Detector (6 puntos; útil para probar el pipeline)
if [[ ! -f "${MODEL_DIR}/face_landmark.onnx" ]]; then
  echo "Descargando face_landmark.onnx (Qualcomm, 6 puntos)..."
  wget -q -O "${MODEL_DIR}/face_landmark.onnx" \
    "https://huggingface.co/qualcomm/MediaPipe-Face-Detection/resolve/main/MediaPipeFaceLandmarkDetector.onnx" \
    || curl -sL -o "${MODEL_DIR}/face_landmark.onnx" \
    "https://huggingface.co/qualcomm/MediaPipe-Face-Detection/resolve/main/MediaPipeFaceLandmarkDetector.onnx"
  echo "  OK: face_landmark.onnx"
else
  echo "Ya existe: face_landmark.onnx"
fi

# Hands y pose: no hay URL pública estándar; el usuario puede colocar aquí hand_landmark.onnx y pose_landmark.onnx
if [[ ! -f "${MODEL_DIR}/hand_landmark.onnx" ]]; then
  echo "hand_landmark.onnx no descargado (añadir URL o colocar manualmente)."
fi
if [[ ! -f "${MODEL_DIR}/pose_landmark.onnx" ]]; then
  echo "pose_landmark.onnx no descargado (añadir URL o colocar manualmente)."
fi

echo "Listo. Para usar desde cualquier directorio, exporta: export ONNX_MODELS_DIR=$MODEL_DIR"
