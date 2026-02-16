#!/usr/bin/env bash
# MVP_02: cámara → 1 filtro C++ → PassthroughRenderer → PreviewSink. Requiere ./cpp/build.sh.
set -e
cd "$(dirname "$0")"
export PYTHONPATH="python:cpp/build"
python python/ascii_stream_engine/examples/stream_with_preview.py "$@"
