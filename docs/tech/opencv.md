# OpenCV (opencv-python)

## Rol en el proyecto
- Captura de frames desde camara con cv2.VideoCapture.
- Conversion de color (BGR a GRAY/RGB).
- Resize eficiente para grillas ASCII.
- Filtros basicos y detectores.

## Arquitectura basica
1. VideoCapture abre el device.
2. read() devuelve (ret, frame).
3. Procesamiento con funciones cv2.
4. Liberar recurso con release().

## Ejemplo minimo
```python
import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
cap.release()
```

## Buenas practicas
- Usar CAP_PROP_BUFFERSIZE bajo para baja latencia.
- Validar ret y frame.
- Convertir BGR a RGB antes de usar Pillow.
- Evitar resize multiples en el mismo frame.
