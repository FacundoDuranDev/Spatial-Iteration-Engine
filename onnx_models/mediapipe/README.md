# Modelos MediaPipe / ONNX para percepción (MVP_03)

Los módulos C++ de percepción (`perception_cpp`) cargan modelos ONNX desde este directorio.
Ruta por defecto: `onnx_models/mediapipe/` (relativa al directorio de trabajo al ejecutar Python).

Variables de entorno:
- **ONNX_MODELS_DIR**: ruta al directorio que contiene los `.onnx` (ej. absoluta: `/ruta/al/repo/onnx_models/mediapipe`).

## Archivos esperados

| Archivo               | Uso        | Landmarks |
|-----------------------|------------|-----------|
| `face_landmark.onnx`  | Cara       | 468 (o 6 en modelo Qualcomm) |
| `hand_landmark.onnx`  | Manos      | 21×2 (izq + der) |
| `pose_landmark.onnx`  | Pose       | 33 |

Si falta un archivo, ese detector devuelve vacío (no falla).

## Descargar modelos

Ejecutar desde la **raíz del repo**:

```bash
./scripts/download_onnx_mediapipe.sh
```

O manualmente:

1. **Cara (ejemplo para probar)** – Qualcomm Face Landmark (6 puntos):
   ```bash
   mkdir -p onnx_models/mediapipe
   wget -q -O onnx_models/mediapipe/face_landmark.onnx \
     "https://huggingface.co/qualcomm/MediaPipe-Face-Detection/resolve/main/MediaPipeFaceLandmarkDetector.onnx"
   ```

2. **Cara 468 puntos** – Luxonis (requiere registro en [models.luxonis.com](https://models.luxonis.com)) o exportar desde MediaPipe.

3. **Manos / Pose** – Buscar "MediaPipe hand landmarker ONNX" o "pose landmarker ONNX" y colocar como `hand_landmark.onnx` y `pose_landmark.onnx`.

## Requisitos C++

Para compilar con inferencia real (no stubs):

```bash
conda activate spatial-iteration-engine
conda install -c conda-forge onnxruntime-cpp
cd /ruta/al/repo && bash cpp/build.sh
```

Si no instalas `onnxruntime-cpp`, el módulo se compila igual pero devuelve arrays vacíos.
