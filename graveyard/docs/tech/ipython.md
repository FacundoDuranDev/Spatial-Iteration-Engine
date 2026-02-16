# IPython

## Rol en el proyecto
Se usa junto con ipywidgets para mostrar controles en notebooks
(IPython.display.display).

## Ejemplo minimo
```python
from IPython.display import display
import ipywidgets as widgets

btn = widgets.Button(description="Click")
display(btn)
```

## Buenas practicas
- Importar solo cuando se usa en notebooks.
- En librerias, encapsular import dentro de funciones con try/except.
