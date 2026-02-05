# Testing

Estrategia:
- Tests unitarios para domain y application.
- Tests con mocks para cv2 y ffmpeg.
- Skips condicionales si faltan dependencias.

Ejecutar tests:
```
python -m unittest discover -s ascii_stream_engine/tests
```

Buenas practicas:
- Mockear cv2.VideoCapture para evitar acceso a camara.
- Mockear subprocess.Popen en outputs UDP.
- Validar que los pipelines respetan el orden.
- Probar update_config con valores validos e invalidos.
