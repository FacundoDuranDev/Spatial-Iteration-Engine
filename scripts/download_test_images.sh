#!/usr/bin/env bash
# Genera imágenes de prueba para testing interno de percepción IA
# Usa OpenCV para generar imágenes sintéticas (más confiable que descargar)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
TEST_IMAGES_DIR="${REPO_ROOT}/test_images"
mkdir -p "$TEST_IMAGES_DIR"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Generación de Imágenes de Prueba para IA"
echo "Método: OpenCV (imágenes sintéticas)"
echo "=========================================="
echo "Directorio: $TEST_IMAGES_DIR"
echo ""

# Verificar que Python y OpenCV estén disponibles
if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}ERROR: python3 no encontrado${NC}" >&2
  exit 1
fi

# Generar imágenes usando Python + OpenCV
python3 << 'PYTHON_SCRIPT'
import cv2
import numpy as np
from pathlib import Path
import sys

repo_root = Path(__file__).parent.parent if '__file__' in globals() else Path.cwd()
test_images_dir = repo_root / "test_images"
test_images_dir.mkdir(exist_ok=True)

print("Generando imágenes sintéticas...")
print()

# 1. Imagen de pose (persona completa de pie)
print("1. Generando test_pose.jpg (persona completa)...")
img_pose = np.zeros((480, 640, 3), dtype=np.uint8)
img_pose.fill(50)  # Fondo gris oscuro

# Cabeza (círculo)
cv2.circle(img_pose, (320, 80), 40, (220, 200, 180), -1)
# Torso (rectángulo)
cv2.rectangle(img_pose, (280, 120), (360, 280), (200, 180, 160), -1)
# Brazos
cv2.rectangle(img_pose, (240, 140), (280, 220), (200, 180, 160), -1)  # Izquierdo
cv2.rectangle(img_pose, (360, 140), (400, 220), (200, 180, 160), -1)  # Derecho
# Piernas
cv2.rectangle(img_pose, (300, 280), (320, 400), (180, 160, 140), -1)  # Izquierda
cv2.rectangle(img_pose, (340, 280), (360, 400), (180, 160, 140), -1)  # Derecha

cv2.imwrite(str(test_images_dir / "test_pose.jpg"), img_pose)
print(f"   ✅ Guardado: {test_images_dir / 'test_pose.jpg'}")

# 2. Imagen de cara (rostro centrado)
print("2. Generando test_face.jpg (rostro)...")
img_face = np.zeros((480, 640, 3), dtype=np.uint8)
img_face.fill(50)

# Cara (círculo grande)
cv2.circle(img_face, (320, 240), 120, (220, 200, 180), -1)
# Ojos
cv2.circle(img_face, (290, 220), 15, (50, 50, 50), -1)  # Izquierdo
cv2.circle(img_face, (350, 220), 15, (50, 50, 50), -1)  # Derecho
# Nariz (triángulo)
pts_nose = np.array([[320, 240], [310, 260], [330, 260]], np.int32)
cv2.fillPoly(img_face, [pts_nose], (200, 180, 160))
# Boca (arco)
cv2.ellipse(img_face, (320, 270), (40, 20), 0, 0, 180, (150, 100, 100), 3)

cv2.imwrite(str(test_images_dir / "test_face.jpg"), img_face)
print(f"   ✅ Guardado: {test_images_dir / 'test_face.jpg'}")

# 3. Imagen de manos (manos visibles)
print("3. Generando test_hands.jpg (manos)...")
img_hands = np.zeros((480, 640, 3), dtype=np.uint8)
img_hands.fill(50)

# Mano izquierda (palma abierta)
# Palma
cv2.ellipse(img_hands, (200, 240), (60, 80), 30, 0, 360, (220, 200, 180), -1)
# Dedos
for i, offset in enumerate([-30, -15, 0, 15, 30]):
    cv2.ellipse(img_hands, (200 + offset, 180), (8, 40), 0, 0, 360, (220, 200, 180), -1)

# Mano derecha (palma abierta)
cv2.ellipse(img_hands, (440, 240), (60, 80), -30, 0, 360, (220, 200, 180), -1)
for i, offset in enumerate([-30, -15, 0, 15, 30]):
    cv2.ellipse(img_hands, (440 + offset, 180), (8, 40), 0, 0, 360, (220, 200, 180), -1)

cv2.imwrite(str(test_images_dir / "test_hands.jpg"), img_hands)
print(f"   ✅ Guardado: {test_images_dir / 'test_hands.jpg'}")

print()
print("✅ Todas las imágenes generadas correctamente")
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
  echo ""
  echo "=========================================="
  echo "Generación completada"
  echo "=========================================="
  echo "Imágenes guardadas en: $TEST_IMAGES_DIR"
  echo ""
  echo "Para usar en tests internos:"
  echo "  python3 scripts/test_with_images.py"
else
  echo -e "${RED}ERROR: Fallo al generar imágenes${NC}" >&2
  exit 1
fi

