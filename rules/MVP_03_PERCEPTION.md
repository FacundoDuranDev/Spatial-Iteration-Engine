# MVP_03 — Perception en C++ (Face, Hands, Pose)

## Objetivo

Agregar una capa de percepción en tiempo real al engine usando modelos de IA en C++, sin modificar todavía la imagen.

El pipeline debe poder detectar:

- Landmarks faciales (≈468 puntos)
- Landmarks de manos (21 por mano)
- Pose corporal (33 joints)

Y exponerlos al engine como `analysis`, accesible por filtros y renderers.

La imagen original NO debe cambiar en este MVP.


---

## Pipeline objetivo

CameraSource  
→ AnalyzerPipeline([FaceLandmarkAnalyzer, HandLandmarkAnalyzer, PoseLandmarkAnalyzer])  
→ FilterPipeline  
→ PassthroughRenderer  
→ PreviewSink  

Los puntos se dibujan como overlay (solo visualización, no filtro).


---

## Stack técnico obligatorio

Toda la inferencia se ejecuta en C++.

| Componente | Tecnología |
|-----------|-----------|
| Inferencia | ONNX Runtime C++ |
| Modelos | MediaPipe ONNX |
| Preprocesado | OpenCV |
| Postprocesado | C++ |
| Bridge Python | pybind11 |


---

## Modelos ONNX

Se deben descargar y colocar en:

onnx_models/mediapipe/


Modelos requeridos:

- face_landmark.onnx  
- hand_landmark.onnx  
- pose_landmark.onnx  

Formato esperado:
- Input: imagen RGB (float32 o uint8 normalizado)
- Output: tensores de landmarks normalizados (0–1)


---

## C++ — estructura nueva

Agregar:



cpp/src/perception/
face_landmarks.cpp
hand_landmarks.cpp
pose_landmarks.cpp
perception_common.hpp


Cada módulo debe exponer una función:

```cpp
std::vector<float> run_<type>(uint8_t* image, int width, int height)


Que devuelve landmarks normalizados:

Face: [x1,y1, x2,y2, ..., x468,y468]

Hand: [x1,y1 ... x21,y21]

Pose: [x1,y1 ... x33,y33]

pybind11 bridge

Exponer en filters_cpp (o nuevo módulo perception_cpp):

py::array_t<float> detect_face(np.ndarray frame)
py::array_t<float> detect_hands(np.ndarray frame)
py::array_t<float> detect_pose(np.ndarray frame)


Entrada: frame uint8 (H,W,3)
Salida: numpy float32 (N,2) en coordenadas normalizadas (0..1)

Python — nuevos adapters

Crear:

python/ascii_stream_engine/adapters/perception/
    face.py
    hands.py
    pose.py


Cada uno implementa Analyzer:

class FaceLandmarkAnalyzer(Analyzer):
    def analyze(self, frame, analysis):
        analysis.face.points = perception_cpp.detect_face(frame.image)


Idem para manos y pose.

Si perception_cpp no existe:

No fallar

Dejar analysis vacío

Domain — estructuras

Agregar en:

domain/frame_analysis.py

class FaceAnalysis:
    points: np.ndarray  # (468,2)

class HandAnalysis:
    left: np.ndarray   # (21,2)
    right: np.ndarray  # (21,2)

class PoseAnalysis:
    joints: np.ndarray # (33,2)


Y colgarlo de FrameAnalysis.

Visualización (overlay)

Crear un renderer auxiliar o modificar PreviewRenderer para:

Si analysis.face existe:

Dibujar puntos verdes

Si analysis.hands existe:

Izquierda rojo, derecha azul

Si analysis.pose existe:

Joints amarillos, líneas simples

Script de prueba

Crear:

python/ascii_stream_engine/examples/stream_with_landmarks.py


Que ejecute:

Camera
→ AnalyzerPipeline([FaceLandmarkAnalyzer, HandLandmarkAnalyzer, PoseLandmarkAnalyzer])
→ PassthroughRenderer
→ PreviewSink

Debe abrir ventana con puntos encima del video.

Criterios de éxito

MVP_03 es válido cuando:

La cámara se ve en tiempo real

Cara, manos y cuerpo tienen puntos que siguen al usuario

No se aplica ningún filtro a la imagen base

Si C++ no está compilado, el pipeline no se rompe (solo no hay puntos)

Prohibiciones

No usar Python para inferencia

No modificar la imagen aún

No mezclar percepción con filtros

No romper MVP_01 ni MVP_02

No crear nuevas capas fuera de ARCHITECTURE.md

Resultado esperado

Una capa de percepción en C++ industrial que alimente el motor con información geométrica del humano en tiempo real, habilitando los próximos MVPs de deformación, puppeteering y warping.


---

Esto es exactamente cómo se construyen los motores de **Snap, TikTok y Unreal Live Link Face**.

Cuando esto esté andando, lo siguiente es:
**MVP_04 — Deformación geométrica por landmarks.**

Y ahí empieza lo realmente poderoso.
