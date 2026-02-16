#!/usr/bin/env bash
# Cámara + filtros C++ + ventana (sin ASCII). Detener con Ctrl+C.
set -e
cd "$(dirname "$0")"
export PYTHONPATH="python:cpp/build"
# Pasar argumentos: ./run_preview_raw.sh 2  → usa cámara índice 2
python python/ascii_stream_engine/examples/stream_camera_cpp_preview.py "$@"
