#!/usr/bin/env bash
# Build de los módulos C++ (filters_cpp, render_bridge).
# Requiere: cmake en PATH y un compilador C++ (g++, clang++, etc.).
#
# Opción 1 – Usar el venv actual (con pip install cmake):
#   source .venv/bin/activate   # o el path de tu venv
#   ./cpp/build.sh
#
# Opción 2 – Usar conda env (tiene cmake + compilers):
#   conda activate spatial-iteration-engine
#   ./cpp/build.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
echo "Build listo. Módulos en: ${BUILD_DIR}"
ls -la *.so 2>/dev/null || true
