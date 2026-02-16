#!/usr/bin/env bash
# Ejecuta el ejemplo basic_stream con PYTHONPATH correcto (python + cpp/build).
# Uso: ./run_basic_stream.sh   (o: bash run_basic_stream.sh)
set -e
cd "$(dirname "$0")"
export PYTHONPATH="python:cpp/build"
python python/ascii_stream_engine/examples/basic_stream.py "$@"
