"""Style Encoder: convierte imagen de referencia (artwork) en vector de estilo R64."""

from typing import Optional

import numpy as np


class StyleEncoder:
    """Convierte una imagen RGB (artwork) en un vector de estilo de 64 dimensiones.

    Stub: devuelve vector de ceros. Luego cargar ONNX desde config.neural.style_encoder_path.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path
        # TODO: cargar ONNX/OpenVINO cuando model_path esté definido

    def encode(self, image_rgb: np.ndarray) -> np.ndarray:
        """Codifica la imagen a vector de estilo en R^64.

        Args:
            image_rgb: Imagen RGB (H, W, 3), uint8 o float.

        Returns:
            Vector de estilo shape (64,) float32.
        """
        # Stub: vector de ceros
        # TODO: inferencia ONNX cuando modelo esté disponible
        return np.zeros(64, dtype=np.float32)
