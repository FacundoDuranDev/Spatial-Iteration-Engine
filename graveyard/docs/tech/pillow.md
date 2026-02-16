# Pillow (PIL)

## Rol en el proyecto
- Render ASCII a imagen RGB.
- Manejo de fuentes y texto monoespaciado.

## Arquitectura basica
- Image: contenedor de pixeles.
- ImageDraw: dibuja texto.
- ImageFont: carga fuentes TTF.

## Ejemplo minimo
```python
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (320, 180), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()
draw.text((0, 0), "ASCII", fill=(255, 255, 255), font=font)
```

## Buenas practicas
- Usar fuente monoespaciada para grilla uniforme.
- Evitar recrear la fuente en cada frame.
- Convertir a RGB antes de enviar a ffmpeg.
