"""Filtro que delega la modificación de imagen al módulo C++ (render_bridge)."""

from typing import Optional

import numpy as np

from ....domain.config import EngineConfig
from .base import BaseFilter

try:
    import render_bridge as _render_bridge

    _CPP_BRIDGE_AVAILABLE = True
except ImportError:
    _render_bridge = None
    _CPP_BRIDGE_AVAILABLE = False


def _get_person_mask(analysis: Optional[dict]) -> Optional[np.ndarray]:
    """Extrae la máscara de persona del resultado de análisis."""
    if not analysis:
        return None
    # SilhouetteSegmentationAnalyzer pone su resultado bajo su nombre
    seg = analysis.get("silhouette_segmentation")
    if isinstance(seg, dict) and "person_mask" in seg:
        mask = seg["person_mask"]
        if isinstance(mask, np.ndarray) and mask.ndim == 2:
            return mask
    return None


class CppImageModifierFilter(BaseFilter):
    """Filtro que modifica el frame usando el módulo C++ (deformación/composición por máscara).

    Si el bridge no está compilado o no está instalado, devuelve el frame sin cambios.
    Usa la máscara de segmentación de persona (analysis['silhouette_segmentation']['person_mask'])
    si está disponible.
    """

    name = "cpp_image_modifier"
    enabled = True

    def __init__(self, enabled: bool = True, use_mask: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._use_mask = use_mask
        self._bridge_available = _CPP_BRIDGE_AVAILABLE

    @property
    def bridge_available(self) -> bool:
        return self._bridge_available

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        if not self._bridge_available or _render_bridge is None:
            return frame.copy()

        mask = _get_person_mask(analysis) if self._use_mask else None
        # Bridge espera frame C-contiguous; opcionalmente RGB/BGR según contrato
        out = _render_bridge.render(frame, mask)
        if out is None or not isinstance(out, np.ndarray):
            return frame.copy()
        return out
