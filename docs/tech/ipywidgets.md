# ipywidgets

## Rol en el proyecto
Permite paneles de control en notebooks para ajustar config y filtros en vivo.

## Arquitectura basica
- Widget: objeto interactivo.
- observe(): conecta cambios a callbacks.
- display(): muestra el widget.

## Ejemplo minimo
```python
import ipywidgets as widgets
from IPython.display import display

slider = widgets.IntSlider(value=10, min=0, max=100)
slider.observe(lambda c: print(c["new"]), names="value")
display(slider)
```

## Buenas practicas
- Mantener callbacks simples.
- Actualizar config por lotes para evitar jitter.
- Usar tabs para agrupar controles.
