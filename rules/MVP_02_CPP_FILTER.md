# MVP 02 — One C++ Filter in Live Pipeline

Objetivo: Validar el bridge Python ↔ C++ en un flujo real.

Pipeline:
Camera
→ FilterPipeline (1 filtro C++)
→ PassthroughRenderer
→ PreviewSink

Requisitos:
./cpp/build.sh
PYTHONPATH=python:cpp/build

Script canónico:
run_preview.sh

Criterio de éxito:
- La imagen se ve
- El filtro C++ modifica el frame
- Al quitar el filtro, vuelve a la imagen original

Este MVP prueba que el backend de alto rendimiento es real.
