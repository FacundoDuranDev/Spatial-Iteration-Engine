"""Coherencia temporal (opcional): suavizado entre frames estilizados."""

from typing import Optional

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig


class TemporalCoherenceFilter:
    """Filtro opcional que suaviza el resultado en el tiempo (optical flow / blending).

    Stub: devuelve el frame sin cambios.
    """

    name = "temporal_coherence"
    enabled = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._previous_frame: Optional[np.ndarray] = None

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        """Aplica suavizado temporal. Stub: retorna frame sin cambios."""
        # TODO: FastFlowNet + blending con _previous_frame
        self._previous_frame = frame.copy()
        return frame.copy()
