"""Renderer que delega la modificación de imagen al módulo C++ y empaqueta el resultado."""

from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer

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
    seg = analysis.get("silhouette_segmentation")
    if isinstance(seg, dict) and "person_mask" in seg:
        mask = seg["person_mask"]
        if isinstance(mask, np.ndarray) and mask.ndim == 2:
            return mask
    return None


def _numpy_to_pil_rgb(frame: np.ndarray) -> Image.Image:
    """Convierte frame numpy (BGR o RGB) a PIL Image RGB."""
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    elif frame.shape[2] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame)


class CppDeformedRenderer:
    """Renderer que usa el módulo C++ para modificar el frame y produce un RenderFrame.

    Si el bridge no está disponible, hace passthrough: convierte el frame a imagen
    (sin deformación) para no romper el pipeline.
    """

    def __init__(
        self,
        fallback_size: Optional[Tuple[int, int]] = None,
        use_mask: bool = True,
    ) -> None:
        self._fallback_size = fallback_size
        self._use_mask = use_mask
        self._bridge_available = _CPP_BRIDGE_AVAILABLE

    @property
    def bridge_available(self) -> bool:
        return self._bridge_available

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        if self._bridge_available and _render_bridge is not None:
            try:
                w, h = _render_bridge.get_output_shape()
                if w > 0 and h > 0:
                    return int(w), int(h)
            except Exception:
                pass
        if self._fallback_size:
            return self._fallback_size
        raw_w = getattr(config, "raw_width", None)
        raw_h = getattr(config, "raw_height", None)
        if raw_w and raw_h:
            return int(raw_w), int(raw_h)
        return 640, 360

    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> RenderFrame:
        if self._bridge_available and _render_bridge is not None:
            mask = _get_person_mask(analysis) if self._use_mask else None
            try:
                out = _render_bridge.render(frame, mask)
                if out is not None and isinstance(out, np.ndarray):
                    img = _numpy_to_pil_rgb(out)
                    return RenderFrame(image=img, metadata={"source": "cpp_bridge"})
            except Exception:
                pass
        # Fallback: passthrough del frame como imagen
        img = _numpy_to_pil_rgb(frame)
        if self._fallback_size:
            img = img.resize(
                (self._fallback_size[0], self._fallback_size[1]),
                Image.Resampling.LANCZOS,
            )
        return RenderFrame(image=img, metadata={"source": "passthrough"})
