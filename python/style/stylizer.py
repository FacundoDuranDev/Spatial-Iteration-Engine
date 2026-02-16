"""Neural Stylizer: Filter que aplica vector de estilo al frame."""

from typing import Optional

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig


class NeuralStylizerFilter:
    """Filtro que aplica estilo al frame usando un vector de estilo (R64).

    Implementa el protocolo Filter. Recibe style_vector de analysis o config.
    Stub: devuelve el frame sin cambios.
    """

    name = "neural_stylizer"
    enabled = True

    def __init__(self, style_encoder=None, enabled: bool = True) -> None:
        self.enabled = enabled
        self._style_encoder = style_encoder  # opcional, para encode on-demand

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        """Aplica el estilo al frame. Stub: retorna frame sin cambios."""
        # TODO: usar analysis.get("style_vector") o config.neural y modelo ONNX
        return frame.copy()
