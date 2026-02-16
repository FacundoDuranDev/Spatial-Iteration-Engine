# Modelos ONNX

Directorio para modelos optimizados (Style Encoder, Stylizer, detección persona/pose, segmentación).

- No versionar archivos `.onnx` pesados en git; usar `.gitignore` o LFS.
- Rutas configurables en `EngineConfig.neural` (por ejemplo `style_encoder_path`, `stylizer_path`).
- Instrucciones de export desde PyTorch/OpenVINO y descarga de artefactos: ver `docs/neural_architecture.md`.

Ejemplo de estructura esperada:

- `style_encoder.onnx`
- `stylizer.onnx`
- `flow_estimator.onnx` (opcional)
- `person_detection.onnx` (opcional)
- `silhouette_segmentation.onnx` (opcional)
