import numpy as np
from .base import BaseFilter


class InvertFilter(BaseFilter):
    name = "invert"

    def apply(self, frame, config, analysis=None):
        if not getattr(config, "invert", False):
            return frame
        # Optimización: usar np.subtract en lugar de operador - para mejor control
        # Nota: Esto aún crea una copia, pero es necesario porque no queremos modificar el frame original
        # La optimización real está en el early return arriba
        if hasattr(frame, 'dtype'):
            # Frame es un array numpy
            return np.subtract(255, frame, dtype=frame.dtype)
        else:
            # Frame es un escalar (para compatibilidad con tests)
            return 255 - frame
