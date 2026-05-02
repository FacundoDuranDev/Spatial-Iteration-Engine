"""Renderer wrapper que aplica projection mapping multi-región con mesh warping.

Modelo de datos:
- El renderer mantiene una **lista de regiones**. Una región es una pieza
  de superficie física (una pared, una cara de un cubo, un objeto) sobre
  la que querés que el output proyecte.
- Cada región tiene su propio **mesh NxM** (densidades soportadas:
  2x2 / 3x3 / 5x5 / 9x9), su propio enabled flag y su nombre.
- El default es **una sola región** identidad — comportamiento idéntico al
  pre-multi-región para clientes que no usen la nueva API.
- Una región a la vez es la **active**: la que el UI está editando con
  los métodos legacy `set_mesh_*` / `set_corner*`.

Render:
- Si hay solo 1 región habilitada, identidad → passthrough (costo cero).
- Si hay solo 1 región habilitada, mesh 2x2 → cv2.warpPerspective.
- Si hay solo 1 región habilitada, mesh NxM → cv2.remap con LUT cacheado.
- Si hay >1 región habilitada → composición sobre canvas negro: por cada
  región, warpear y pintar SOLO los pixeles cubiertos por algún triángulo
  (alpha mask del LUT). Las regiones más adelante en la lista pintan
  encima de las anteriores ("z-order = orden de la lista").

Convención de mesh_points: array `(rows, cols, 2)` en coordenadas
**normalizadas [0,1]** sobre el canvas de salida.

El wrapper expone `enabled` (toggle global on/off) y un alias
`overlay_enabled` para que el bridge pueda usar el mismo Protocol que
otros renderers toggleables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer

# Identity quad — top-left, top-right, bottom-right, bottom-left en [0,1].
IDENTITY_CORNERS: Tuple[Tuple[float, float], ...] = (
    (0.0, 0.0),
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 1.0),
)

# Densidades válidas — todas cuadradas. Más de 9x9 es overkill y rebuild
# del LUT empieza a doler (~50 ms a 1080p).
SUPPORTED_MESH_SIZES: Tuple[int, ...] = (2, 3, 5, 9)


# ---------------------------------------------------------------------------
# Helpers públicos / privados
# ---------------------------------------------------------------------------


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


def _identity_mesh(rows: int, cols: int) -> np.ndarray:
    if rows < 2 or cols < 2:
        raise ValueError(f"mesh size must be >=2 in both dims, got {rows}x{cols}")
    ys = np.linspace(0.0, 1.0, rows, dtype=np.float32)
    xs = np.linspace(0.0, 1.0, cols, dtype=np.float32)
    out = np.zeros((rows, cols, 2), dtype=np.float32)
    out[..., 0] = xs[None, :]
    out[..., 1] = ys[:, None]
    return out


def _normalize_mesh(points, rows: int, cols: int) -> np.ndarray:
    arr = np.asarray(points, dtype=np.float32)
    if arr.shape != (rows, cols, 2):
        raise ValueError(
            f"mesh_points shape must be ({rows}, {cols}, 2), got {arr.shape}"
        )
    return np.clip(arr, 0.0, 1.0)


def _normalize_corners(corners: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float], ...]:
    if len(corners) != 4:
        raise ValueError(f"projection corners must be 4 points, got {len(corners)}")
    out: List[Tuple[float, float]] = []
    for i, pt in enumerate(corners):
        if len(pt) != 2:
            raise ValueError(f"corner {i} must be (x, y), got {pt!r}")
        out.append((_clamp01(pt[0]), _clamp01(pt[1])))
    return tuple(out)


def _corners_to_mesh(corners: Sequence[Sequence[float]]) -> np.ndarray:
    """Adaptador 4-corner → mesh 2x2: TL,TR,BR,BL → grid[0..1][0..1]."""
    c = _normalize_corners(corners)
    return np.array([
        [list(c[0]), list(c[1])],   # row 0: TL, TR
        [list(c[3]), list(c[2])],   # row 1: BL, BR
    ], dtype=np.float32)


def _build_remap_lut(
    mesh: np.ndarray,
    width: int,
    height: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Construye `(map_x, map_y)` para `cv2.remap` desde un mesh.

    Pixeles fuera de cualquier triángulo del mesh se inicializan en
    `(-1, -1)`. cv2.remap con `BORDER_CONSTANT` los pinta del border
    value (negro), evitando leer img[0,0] basura.
    """
    rows, cols = mesh.shape[:2]
    map_x = np.full((height, width), -1.0, dtype=np.float32)
    map_y = np.full((height, width), -1.0, dtype=np.float32)
    mask = np.zeros((height, width), dtype=bool)

    src_xs = np.linspace(0.0, width - 1, cols, dtype=np.float32)
    src_ys = np.linspace(0.0, height - 1, rows, dtype=np.float32)

    dst_grid = mesh.copy()
    dst_grid[..., 0] *= (width - 1)
    dst_grid[..., 1] *= (height - 1)

    for i in range(rows - 1):
        for j in range(cols - 1):
            s00 = (src_xs[j],     src_ys[i])
            s01 = (src_xs[j + 1], src_ys[i])
            s10 = (src_xs[j],     src_ys[i + 1])
            s11 = (src_xs[j + 1], src_ys[i + 1])
            d00 = tuple(dst_grid[i,     j    ])
            d01 = tuple(dst_grid[i,     j + 1])
            d10 = tuple(dst_grid[i + 1, j    ])
            d11 = tuple(dst_grid[i + 1, j + 1])
            for src_tri, dst_tri in (
                ((s00, s01, s11), (d00, d01, d11)),
                ((s00, s11, s10), (d00, d11, d10)),
            ):
                _rasterize_triangle(
                    np.array(dst_tri, dtype=np.float32),
                    np.array(src_tri, dtype=np.float32),
                    map_x, map_y, mask, width, height,
                )
    return map_x, map_y


def _rasterize_triangle(
    dst_tri: np.ndarray,
    src_tri: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
    mask: np.ndarray,
    width: int,
    height: int,
) -> None:
    x0 = max(0, int(np.floor(dst_tri[:, 0].min())))
    x1 = min(width, int(np.ceil(dst_tri[:, 0].max())) + 1)
    y0 = max(0, int(np.floor(dst_tri[:, 1].min())))
    y1 = min(height, int(np.ceil(dst_tri[:, 1].max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return

    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)

    v0 = dst_tri[1] - dst_tri[0]
    v1 = dst_tri[2] - dst_tri[0]
    v2x = xs - dst_tri[0, 0]
    v2y = ys - dst_tri[0, 1]
    denom = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(denom) < 1e-9:
        return
    inv_denom = 1.0 / denom
    b = (v2x * v1[1] - v1[0] * v2y) * inv_denom
    c = (v0[0] * v2y - v2x * v0[1]) * inv_denom
    a = 1.0 - b - c

    inside = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
    if not np.any(inside):
        return

    src_x = a * src_tri[0, 0] + b * src_tri[1, 0] + c * src_tri[2, 0]
    src_y = a * src_tri[0, 1] + b * src_tri[1, 1] + c * src_tri[2, 1]

    yy = ys[inside].astype(np.int32)
    xx = xs[inside].astype(np.int32)
    fresh = ~mask[yy, xx]
    yy = yy[fresh]; xx = xx[fresh]
    if yy.size == 0:
        return
    map_x[yy, xx] = src_x[inside][fresh]
    map_y[yy, xx] = src_y[inside][fresh]
    mask[yy, xx] = True


# ---------------------------------------------------------------------------
# Region — un trozo de superficie física con su propio mesh
# ---------------------------------------------------------------------------


@dataclass
class Region:
    """Una superficie de proyección con su propio mesh warp.

    El mesh es una grilla NxM de puntos normalizados [0,1] que indican
    dónde aterriza la esquina (i,j) del rectángulo source dentro del canvas
    de salida. Densidad y puntos son independientes entre regiones.
    """

    name: str = "Región"
    enabled: bool = True
    _mesh: np.ndarray = field(default_factory=lambda: _identity_mesh(2, 2))

    @property
    def mesh(self) -> np.ndarray:
        return self._mesh

    @property
    def mesh_size(self) -> Tuple[int, int]:
        return (int(self._mesh.shape[0]), int(self._mesh.shape[1]))

    @property
    def mesh_points(self) -> List[List[List[float]]]:
        return [[[float(v) for v in pt] for pt in row] for row in self._mesh]

    @property
    def corners_norm(self) -> List[Tuple[float, float]]:
        m = self._mesh
        return [
            (float(m[0,  0,  0]), float(m[0,  0,  1])),
            (float(m[0, -1,  0]), float(m[0, -1,  1])),
            (float(m[-1, -1, 0]), float(m[-1, -1, 1])),
            (float(m[-1, 0,  0]), float(m[-1, 0,  1])),
        ]

    def set_mesh_size(self, rows: int, cols: int) -> None:
        if rows not in SUPPORTED_MESH_SIZES or cols not in SUPPORTED_MESH_SIZES:
            raise ValueError(
                f"mesh size {rows}x{cols} no soportado. "
                f"Densidades válidas: {SUPPORTED_MESH_SIZES}."
            )
        self._mesh = _identity_mesh(rows, cols)

    def set_mesh_points(self, points) -> None:
        rows, cols = self.mesh_size
        self._mesh = _normalize_mesh(points, rows, cols)

    def set_mesh_point(self, row: int, col: int, x: float, y: float) -> None:
        rows, cols = self.mesh_size
        if not 0 <= row < rows:
            raise IndexError(f"row {row} out of [0, {rows})")
        if not 0 <= col < cols:
            raise IndexError(f"col {col} out of [0, {cols})")
        self._mesh[row, col] = (_clamp01(x), _clamp01(y))

    def set_corners(self, corners: Sequence[Sequence[float]]) -> None:
        self._mesh = _corners_to_mesh(corners)

    def set_corner(self, idx: int, x: float, y: float) -> None:
        if not 0 <= idx < 4:
            raise IndexError(f"corner idx must be in [0,3], got {idx}")
        rows, cols = self.mesh_size
        rc = [
            (0, 0),                # TL
            (0, cols - 1),         # TR
            (rows - 1, cols - 1),  # BR
            (rows - 1, 0),         # BL
        ][idx]
        self._mesh[rc[0], rc[1]] = (_clamp01(x), _clamp01(y))

    def reset(self) -> None:
        rows, cols = self.mesh_size
        self._mesh = _identity_mesh(rows, cols)

    def is_identity(self) -> bool:
        rows, cols = self.mesh_size
        return bool(np.allclose(self._mesh, _identity_mesh(rows, cols), atol=1e-4))

    def to_dict(self) -> Dict[str, Any]:
        rows, cols = self.mesh_size
        return {
            "name": self.name,
            "enabled": bool(self.enabled),
            "mesh_size": [rows, cols],
            "mesh_points": self.mesh_points,
        }


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class ProjectionMappingRenderer:
    """Aplica projection mapping multi-región sobre el frame del inner renderer.

    Por default arranca con UNA región identidad; el `enabled` global empieza
    en False, así que no toca nada hasta que el usuario calibre algo.

    Métodos legacy (`set_mesh_*`, `set_corner*`, `corners_norm`) operan sobre
    la **active region**. Eso preserva back-compat con el código que usaba
    el renderer single-region.
    """

    def __init__(
        self,
        inner: Optional[FrameRenderer] = None,
        corners: Optional[Sequence[Sequence[float]]] = None,
        mesh_points=None,
        mesh_size: Tuple[int, int] = (2, 2),
        enabled: bool = False,
        regions: Optional[List[Region]] = None,
    ) -> None:
        self._inner = inner

        if regions is not None:
            if not regions:
                raise ValueError("regions list must contain at least one Region")
            self._regions: List[Region] = list(regions)
        else:
            # Construir una región default a partir de los args legacy.
            r = Region(name="Región 1")
            if mesh_points is not None:
                arr = np.asarray(mesh_points, dtype=np.float32)
                if arr.ndim != 3 or arr.shape[2] != 2:
                    raise ValueError(
                        f"mesh_points must be (rows, cols, 2), got shape {arr.shape}"
                    )
                r._mesh = np.clip(arr, 0.0, 1.0)
            elif corners is not None:
                r._mesh = _corners_to_mesh(corners)
            else:
                r._mesh = _identity_mesh(*mesh_size)
            self._regions = [r]

        self._active: int = 0
        self._enabled: bool = bool(enabled)
        # LUT cache por región. Cada entry: (map_x, map_y, w, h, sig).
        self._lut_caches: List[Optional[Tuple[np.ndarray, np.ndarray, int, int, bytes]]] = (
            [None] * len(self._regions)
        )

    # --- composition -------------------------------------------------

    @property
    def inner(self) -> Optional[FrameRenderer]:
        return self._inner

    @inner.setter
    def inner(self, renderer: Optional[FrameRenderer]) -> None:
        self._inner = renderer

    # --- toggle global ----------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    @property
    def overlay_enabled(self) -> bool:
        return self._enabled

    @overlay_enabled.setter
    def overlay_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # --- regiones ----------------------------------------------------

    @property
    def regions(self) -> List[Region]:
        return list(self._regions)

    @property
    def active_region_index(self) -> int:
        return self._active

    @property
    def active_region(self) -> Region:
        return self._regions[self._active]

    def set_active_region(self, idx: int) -> None:
        if not 0 <= idx < len(self._regions):
            raise IndexError(
                f"region idx {idx} out of [0, {len(self._regions)})"
            )
        self._active = idx

    def add_region(self, name: Optional[str] = None) -> int:
        """Suma una región identidad al final de la lista. La hace active."""
        nm = name or f"Región {len(self._regions) + 1}"
        self._regions.append(Region(name=nm))
        self._lut_caches.append(None)
        self._active = len(self._regions) - 1
        return self._active

    def remove_region(self, idx: int) -> None:
        """Borra la región. No permite quedar con cero — al menos 1 siempre."""
        if not 0 <= idx < len(self._regions):
            raise IndexError(
                f"region idx {idx} out of [0, {len(self._regions)})"
            )
        if len(self._regions) == 1:
            raise ValueError("no se puede borrar la última región — siempre debe haber al menos 1")
        self._regions.pop(idx)
        self._lut_caches.pop(idx)
        # Mantener el active válido (clampeado).
        if self._active >= len(self._regions):
            self._active = len(self._regions) - 1

    def rename_region(self, idx: int, name: str) -> None:
        if not 0 <= idx < len(self._regions):
            raise IndexError(f"region idx {idx} out of [0, {len(self._regions)})")
        self._regions[idx].name = str(name)

    def set_region_enabled(self, idx: int, on: bool) -> None:
        if not 0 <= idx < len(self._regions):
            raise IndexError(f"region idx {idx} out of [0, {len(self._regions)})")
        self._regions[idx].enabled = bool(on)

    # --- proxies legacy: actúan sobre la active region --------------

    @property
    def mesh_size(self) -> Tuple[int, int]:
        return self.active_region.mesh_size

    @property
    def mesh_points(self) -> List[List[List[float]]]:
        return self.active_region.mesh_points

    @property
    def corners_norm(self) -> List[Tuple[float, float]]:
        return self.active_region.corners_norm

    def set_mesh_size(self, rows: int, cols: int) -> None:
        self.active_region.set_mesh_size(rows, cols)
        self._lut_caches[self._active] = None

    def set_mesh_points(self, points) -> None:
        self.active_region.set_mesh_points(points)
        self._lut_caches[self._active] = None

    def set_mesh_point(self, row: int, col: int, x: float, y: float) -> None:
        self.active_region.set_mesh_point(row, col, x, y)
        self._lut_caches[self._active] = None

    def set_corners(self, corners: Sequence[Sequence[float]]) -> None:
        self.active_region.set_corners(corners)
        self._lut_caches[self._active] = None

    def set_corner(self, idx: int, x: float, y: float) -> None:
        self.active_region.set_corner(idx, x, y)
        self._lut_caches[self._active] = None

    def reset(self) -> None:
        """Reset SOLO de la active region — no afecta otras."""
        self.active_region.reset()
        self._lut_caches[self._active] = None

    def reset_all(self) -> None:
        """Reset de todas las regiones a identidad."""
        for r in self._regions:
            r.reset()
        self._lut_caches = [None] * len(self._regions)

    def is_identity(self) -> bool:
        """True si todas las regiones habilitadas están en identidad.

        Si NINGUNA región está habilitada, también es trivial → identity.
        """
        any_enabled = False
        for r in self._regions:
            if r.enabled:
                any_enabled = True
                if not r.is_identity():
                    return False
        return True if not any_enabled else True

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
        if self._inner is not None:
            rendered = self._inner.render(frame, config, analysis)
        else:
            arr = frame
            if arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
            rendered = RenderFrame(
                image=Image.fromarray(arr),
                metadata={"source": "projection_mapping_passthrough"},
            )

        # Path corto: warp global apagado o no hay nada que warpear.
        if not self._enabled or self.is_identity():
            return rendered

        img = np.asarray(rendered.image)
        h, w = img.shape[:2]

        enabled_regions = [
            (i, r) for i, r in enumerate(self._regions) if r.enabled
        ]
        if not enabled_regions:
            return rendered

        if len(enabled_regions) == 1:
            idx, region = enabled_regions[0]
            if region.mesh_size == (2, 2):
                warped = self._render_perspective(img, w, h, region)
            else:
                warped = self._render_mesh_single(img, w, h, idx, region)
        else:
            warped = self._render_composite(img, w, h, enabled_regions)

        meta = dict(rendered.metadata) if rendered.metadata else {}
        meta["projection"] = "warped"
        meta["projection_regions_total"] = len(self._regions)
        meta["projection_regions_active"] = len(enabled_regions)
        return RenderFrame(image=Image.fromarray(warped), metadata=meta)

    # --- render paths -----------------------------------------------

    def _render_perspective(
        self, img: np.ndarray, w: int, h: int, region: Region
    ) -> np.ndarray:
        corners = region.corners_norm
        src = np.float32([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])
        dst = np.float32([(cx * w, cy * h) for (cx, cy) in corners])
        matrix = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(
            img, matrix, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def _get_or_build_lut(
        self, idx: int, region: Region, w: int, h: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        sig = region.mesh.tobytes()
        cache = self._lut_caches[idx]
        if cache is None or cache[2] != w or cache[3] != h or cache[4] != sig:
            map_x, map_y = _build_remap_lut(region.mesh, w, h)
            self._lut_caches[idx] = (map_x, map_y, w, h, sig)
            return map_x, map_y
        return cache[0], cache[1]

    def _render_mesh_single(
        self, img: np.ndarray, w: int, h: int, idx: int, region: Region
    ) -> np.ndarray:
        map_x, map_y = self._get_or_build_lut(idx, region, w, h)
        return cv2.remap(
            img, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def _render_composite(
        self, img: np.ndarray, w: int, h: int,
        enabled_regions: List[Tuple[int, Region]],
    ) -> np.ndarray:
        """Composición multi-región sobre canvas negro con masks por región.

        Para cada región: warpear → calcular su mask de cobertura (pixeles
        dentro de algún triángulo) → escribir SOLO esos pixeles al canvas.
        Las regiones más adelante en la lista pintan encima de las anteriores.
        """
        canvas = np.zeros((h, w, img.shape[2] if img.ndim == 3 else 1), dtype=img.dtype)
        if img.ndim == 2:
            canvas = canvas[..., 0]

        for idx, region in enabled_regions:
            if region.mesh_size == (2, 2):
                # Path rápido: warp perspectiva + mask del cuadrilátero.
                warped = self._render_perspective(img, w, h, region)
                mask = self._perspective_mask(region, w, h)
            else:
                # Mesh: el LUT ya tiene -1 en pixeles fuera de cualquier
                # triángulo; usamos eso como mask.
                map_x, map_y = self._get_or_build_lut(idx, region, w, h)
                warped = cv2.remap(
                    img, map_x, map_y,
                    interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=(0, 0, 0),
                )
                mask = map_x >= 0
            if canvas.ndim == 3 and mask.ndim == 2:
                canvas[mask] = warped[mask]
            else:
                canvas[mask] = warped[mask]
        return canvas

    def _perspective_mask(
        self, region: Region, w: int, h: int
    ) -> np.ndarray:
        """Mask boolean de pixeles cubiertos por el cuadrilátero de un mesh 2x2."""
        corners = region.corners_norm
        # Convertir a polígono pixel-space, en orden TL,TR,BR,BL.
        poly = np.int32([[cx * w, cy * h] for (cx, cy) in corners])
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillConvexPoly(mask, poly, 255)
        return mask.astype(bool)
