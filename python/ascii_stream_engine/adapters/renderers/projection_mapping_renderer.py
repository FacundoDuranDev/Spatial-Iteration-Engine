"""Renderer wrapper que aplica un warp de 4 corners para projection mapping.

Idea: el render del inner produce un frame rectangular; este wrapper lo
deforma con `cv2.warpPerspective` para que las 4 esquinas del rectángulo
caigan en 4 puntos arbitrarios dentro del canvas de salida. Útil cuando
el proyector apunta a una superficie no-rectangular (esquina, escultura,
pantalla inclinada) y querés que la imagen "encaje" físicamente.

Convención de corners: lista de 4 tuplas `(x, y)` en coordenadas
**normalizadas [0,1]** sobre el canvas de salida, en orden:

    0 = top-left, 1 = top-right, 2 = bottom-right, 3 = bottom-left

Identidad (sin deformación): `[(0,0), (1,0), (1,1), (0,1)]`. En ese caso
el render hace passthrough sin tocar el frame — costo cero.

El wrapper también implementa `OverlayCapable` (toggle on/off) para que
el bridge pueda apagarlo sin tener que reconstruir el chain de renderers.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer

# Identity quad — top-left, top-right, bottom-right, bottom-left in [0,1].
IDENTITY_CORNERS: Tuple[Tuple[float, float], ...] = (
    (0.0, 0.0),
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 1.0),
)


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


def _normalize_corners(corners: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float], ...]:
    if len(corners) != 4:
        raise ValueError(f"projection corners must be 4 points, got {len(corners)}")
    out: List[Tuple[float, float]] = []
    for i, pt in enumerate(corners):
        if len(pt) != 2:
            raise ValueError(f"corner {i} must be (x, y), got {pt!r}")
        out.append((_clamp01(pt[0]), _clamp01(pt[1])))
    return tuple(out)


class ProjectionMappingRenderer:
    """Aplica un warp de 4 corners al frame producido por el inner renderer.

    Cuando `enabled` es False o los corners son identidad, devuelve el
    frame sin tocar (costo cero). Cuando se activa con corners no-triviales,
    `cv2.warpPerspective` deforma el frame para que sus esquinas naturales
    caigan en las posiciones especificadas dentro del mismo canvas.
    """

    def __init__(
        self,
        inner: Optional[FrameRenderer] = None,
        corners: Optional[Sequence[Sequence[float]]] = None,
        enabled: bool = False,
    ) -> None:
        self._inner = inner
        self._corners: Tuple[Tuple[float, float], ...] = (
            _normalize_corners(corners) if corners is not None else IDENTITY_CORNERS
        )
        self._enabled: bool = bool(enabled)

    # --- composition -------------------------------------------------

    @property
    def inner(self) -> Optional[FrameRenderer]:
        return self._inner

    @inner.setter
    def inner(self, renderer: Optional[FrameRenderer]) -> None:
        self._inner = renderer

    # --- OverlayCapable-like toggle ---------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # Alias para que el bridge pueda usar el mismo Protocol que overlay.
    @property
    def overlay_enabled(self) -> bool:
        return self._enabled

    @overlay_enabled.setter
    def overlay_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # --- corners ----------------------------------------------------

    @property
    def corners_norm(self) -> List[Tuple[float, float]]:
        return list(self._corners)

    def set_corners(self, corners: Sequence[Sequence[float]]) -> None:
        self._corners = _normalize_corners(corners)

    def set_corner(self, idx: int, x: float, y: float) -> None:
        if not 0 <= idx < 4:
            raise IndexError(f"corner idx must be in [0,3], got {idx}")
        c = list(self._corners)
        c[idx] = (_clamp01(x), _clamp01(y))
        self._corners = tuple(c)

    def reset(self) -> None:
        self._corners = IDENTITY_CORNERS

    def is_identity(self) -> bool:
        # Tolerancia chica — cosas tipo `0.0000001` por floats no deberían
        # disparar el warp (ahorra una llamada a cv2 por frame).
        for (cx, cy), (ix, iy) in zip(self._corners, IDENTITY_CORNERS):
            if abs(cx - ix) > 1e-4 or abs(cy - iy) > 1e-4:
                return False
        return True

    # --- FrameRenderer protocol -------------------------------------

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        if self._inner is not None:
            return self._inner.output_size(config)
        return 640, 480

    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> RenderFrame:
        # Deferred import to avoid hard dependency at module load.
        if self._inner is not None:
            rendered = self._inner.render(frame, config, analysis)
        else:
            # Sin inner: convertimos BGR→RGB sin tocar nada más para que el
            # sink siga recibiendo PIL.Image como espera.
            arr = frame
            if arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
            rendered = RenderFrame(
                image=Image.fromarray(arr),
                metadata={"source": "projection_mapping_passthrough"},
            )

        if not self._enabled or self.is_identity():
            return rendered

        # Warp path. Trabajamos en numpy (más rápido que reabrir PIL).
        img = np.asarray(rendered.image)
        h, w = img.shape[:2]
        src = np.float32([
            [0.0, 0.0],
            [w, 0.0],
            [w, h],
            [0.0, h],
        ])
        dst = np.float32([(cx * w, cy * h) for (cx, cy) in self._corners])
        matrix = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(
            img,
            matrix,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        meta = dict(rendered.metadata) if rendered.metadata else {}
        meta["projection"] = "warped"
        meta["projection_corners_norm"] = list(self._corners)
        return RenderFrame(image=Image.fromarray(warped), metadata=meta)
