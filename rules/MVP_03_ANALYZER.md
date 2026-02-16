# MVP 03 — Analyzer in the Loop

Objetivo: Integrar percepción sin afectar render ni estabilidad.

Pipeline:
Camera
→ AnalyzerPipeline (1 analizador)
→ FilterPipeline
→ PassthroughRenderer
→ PreviewSink

El analizador puede ser:
- Haar face detector
- O un stub que devuelva un bounding box

Criterio de éxito:
- El preview sigue funcionando
- El analizador se ejecuta por frame
- No rompe FPS ni estabilidad

Este MVP valida la capa de percepción.

