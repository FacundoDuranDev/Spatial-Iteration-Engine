# Dependencias (requirements.txt)

Este archivo describe cada dependencia y su uso dentro del proyecto.

## opencv-python
Uso:
- Captura de camara con cv2.VideoCapture.
- Conversion de color (BGR a GRAY/RGB).
- Resize eficiente para grillas ASCII.
- Filtros basicos y detectores (edge, face).

Ejemplo minimo:
```python
import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
cap.release()
```

## numpy
Uso:
- Representacion de frames como arrays.
- Operaciones vectorizadas para filtros.

Ejemplo minimo:
```python
import numpy as np

frame = np.zeros((10, 10), dtype=np.uint8)
```

## pillow
Uso:
- Render ASCII a imagen RGB.
- Manejo de fonts con ImageFont.

Ejemplo minimo:
```python
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (120, 60), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()
draw.text((0, 0), "ASCII", fill=(255, 255, 255), font=font)
```

## ipywidgets
Uso:
- UI interactiva en notebooks (sliders, botones, tabs).

Ejemplo minimo:
```python
import ipywidgets as widgets
from IPython.display import display

slider = widgets.IntSlider(value=10, min=0, max=100)
display(slider)
```

## ipython
Uso:
- display() para mostrar widgets en notebooks.
- Runtime interactivo en Jupyter.

Ejemplo minimo:
```python
from IPython.display import display
import ipywidgets as widgets

btn = widgets.Button(description="Click")
display(btn)
```

## Notas de instalacion
Instalar todo:
```
python -m pip install -r ascii_stream_engine/requirements.txt
```
