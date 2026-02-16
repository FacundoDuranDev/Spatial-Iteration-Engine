#!/usr/bin/env bash
# Preview sin cámara: patrón animado + 1 filtro C++. Para probar cuando la cámara falla.
set -e
cd "$(dirname "$0")"
export PYTHONPATH="python:cpp/build"
python python/ascii_stream_engine/examples/stream_preview_pattern.py "$@"
