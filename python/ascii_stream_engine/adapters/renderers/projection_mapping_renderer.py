"""Renderer wrapper que aplica un warp configurable para projection mapping.

Soporta dos modos según la densidad del mesh:

- **2x2 (default)**: warp clásico de 4 corners. cv2.warpPerspective de una
  toma. Útil para superficies planas / aproximaciones rápidas.
- **NxM con N>=3 o M>=3**: mesh warp por triángulos. Cada celda del grid
  se subdivide en 2 triángulos y se aplica un warp afin por triángulo
  (vía un mapa de remapeo precomputado). Útil para superficies curvas
  o planas con detalle (ej. una pared con un saliente, una columna).

Convención de mesh_points: array `(rows, cols, 2)` en coordenadas
**normalizadas [0,1]** sobre el canvas de salida. `mesh_points[i,j]` es
dónde aterriza la esquina `(i,j)` del grid regular del frame source.

Identidad (sin deformación): grid regular igual al source. En ese caso
el render hace passthrough sin tocar el frame — costo cero.

El wrapper también expone `enabled` (toggle on/off) y un alias
`overlay_enabled` para que el bridge pueda usar el mismo Protocol que
otros renderers toggleables.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.renderers import FrameRenderer

# Identity quad — top-left, top-right, bottom-right, bottom-left en [0,1].
# Mantenido por compatibilidad con código que ya consumía la API 2x2.
IDENTITY_CORNERS: Tuple[Tuple[float, float], ...] = (
    (0.0, 0.0),
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 1.0),
)

# Densidades válidas — todas cuadradas. Más de 9x9 es overkill y rebuild
# del LUT empieza a doler (~50 ms a 1080p).
SUPPORTED_MESH_SIZES: Tuple[int, ...] = (2, 3, 5, 9)


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


def _identity_mesh(rows: int, cols: int) -> np.ndarray:
    """Mesh regular `(rows, cols, 2)` con valores normalizados [0,1]."""
    if rows < 2 or cols < 2:
        raise ValueError(f"mesh size must be >=2 in both dims, got {rows}x{cols}")
    ys = np.linspace(0.0, 1.0, rows, dtype=np.float32)
    xs = np.linspace(0.0, 1.0, cols, dtype=np.float32)
    out = np.zeros((rows, cols, 2), dtype=np.float32)
    out[..., 0] = xs[None, :]
    out[..., 1] = ys[:, None]
    return out


def _normalize_mesh(points, rows: int, cols: int) -> np.ndarray:
    """Acepta lista anidada o ndarray, valida shape, clampa a [0,1]."""
    arr = np.asarray(points, dtype=np.float32)
    if arr.shape != (rows, cols, 2):
        raise ValueError(
            f"mesh_points shape must be ({rows}, {cols}, 2), got {arr.shape}"
        )
    return np.clip(arr, 0.0, 1.0)


def _normalize_corners(corners: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float], ...]:
    """Convención legacy 4-corner: TL, TR, BR, BL."""
    if len(corners) != 4:
        raise ValueError(f"projection corners must be 4 points, got {len(corners)}")
    out: List[Tuple[float, float]] = []
    for i, pt in enumerate(corners):
        if len(pt) != 2:
            raise ValueError(f"corner {i} must be (x, y), got {pt!r}")
        out.append((_clamp01(pt[0]), _clamp01(pt[1])))
    return tuple(out)


def _corners_to_mesh(corners: Sequence[Sequence[float]]) -> np.ndarray:
    """Adaptador 4-corner → mesh 2x2 — orden TL,TR,BR,BL → grid[0,0]…grid[1,1]."""
    c = _normalize_corners(corners)
    return np.array([
        [list(c[0]), list(c[1])],   # row 0: TL, TR
        [list(c[3]), list(c[2])],   # row 1: BL, BR
    ], dtype=np.float32)


def _mesh_to_corners(mesh: np.ndarray) -> List[List[float]]:
    """Mesh 2x2 → lista 4-corner TL,TR,BR,BL para la API legacy."""
    if mesh.shape != (2, 2, 2):
        raise ValueError(f"_mesh_to_corners requires 2x2 mesh, got {mesh.shape}")
    return [
        list(mesh[0, 0]),
        list(mesh[0, 1]),
        list(mesh[1, 1]),
        list(mesh[1, 0]),
    ]


def _build_remap_lut(
    mesh: np.ndarray,
    width: int,
    height: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Construye los maps `(map_x, map_y)` para `cv2.remap` desde un mesh.

    Para cada celda del grid mesh — una esquina del rectángulo source —
    triangulamos en dos triángulos. Por cada triángulo de DESTINO calculamos
    la afín que lo manda al triángulo correspondiente de SOURCE (es la
    inversa de la deformación visual, que es lo que `cv2.remap` necesita).
    Después rasterizamos cada triángulo en sus pixeles, evaluando la afín.

    Pixeles fuera de cualquier triángulo se quedan en (0,0) — `cv2.remap`
    con `BORDER_CONSTANT` los pinta del color de borde (negro). Esto evita
    artefactos en zonas donde el mesh "metió" el frame hacia adentro.
    """
    rows, cols = mesh.shape[:2]
    # Inicializamos en -1 para que cv2.remap con BORDER_CONSTANT pinte el
    # borderValue (negro) en los pixeles que ningún triángulo cubrió.
    # Si dejáramos 0, cv2.remap leería img[0,0] (que NO es border) y
    # esos pixeles "no cubiertos" saldrían con un color cualquiera.
    map_x = np.full((height, width), -1.0, dtype=np.float32)
    map_y = np.full((height, width), -1.0, dtype=np.float32)
    mask = np.zeros((height, width), dtype=bool)

    # Source grid: posiciones regulares dentro del frame source en pixeles.
    src_xs = np.linspace(0.0, width - 1, cols, dtype=np.float32)
    src_ys = np.linspace(0.0, height - 1, rows, dtype=np.float32)

    # Destination grid: posiciones del mesh, escaladas a pixeles del output.
    dst_grid = mesh.copy()
    dst_grid[..., 0] *= (width - 1)
    dst_grid[..., 1] *= (height - 1)

    for i in range(rows - 1):
        for j in range(cols - 1):
            # Cuatro esquinas de la celda en source y dest.
            s00 = (src_xs[j],     src_ys[i])
            s01 = (src_xs[j + 1], src_ys[i])
            s10 = (src_xs[j],     src_ys[i + 1])
            s11 = (src_xs[j + 1], src_ys[i + 1])
            d00 = tuple(dst_grid[i,     j    ])
            d01 = tuple(dst_grid[i,     j + 1])
            d10 = tuple(dst_grid[i + 1, j    ])
            d11 = tuple(dst_grid[i + 1, j + 1])

            # Triángulos: (TL, TR, BR) y (TL, BR, BL). Diagonal compartida.
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
    """Rasteriza un triángulo dst y, para cada pixel, calcula el src equivalente.

    Usa coordenadas baricéntricas para el test de containment + interpolación
    bilineal de las coords source. Vectorizado en numpy para no recorrer
    pixel por pixel en Python.
    """
    # Bbox del triángulo destino, clipeado al frame.
    x0 = max(0, int(np.floor(dst_tri[:, 0].min())))
    x1 = min(width, int(np.ceil(dst_tri[:, 0].max())) + 1)
    y0 = max(0, int(np.floor(dst_tri[:, 1].min())))
    y1 = min(height, int(np.ceil(dst_tri[:, 1].max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return

    # Grid de coords pixel del bbox.
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)

    # Baricéntricas: (a, b, c) tal que P = a*V0 + b*V1 + c*V2, a+b+c=1.
    v0 = dst_tri[1] - dst_tri[0]
    v1 = dst_tri[2] - dst_tri[0]
    v2x = xs - dst_tri[0, 0]
    v2y = ys - dst_tri[0, 1]
    denom = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(denom) < 1e-9:
        return  # Triángulo degenerado.
    inv_denom = 1.0 / denom
    b = (v2x * v1[1] - v1[0] * v2y) * inv_denom
    c = (v0[0] * v2y - v2x * v0[1]) * inv_denom
    a = 1.0 - b - c

    inside = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
    if not np.any(inside):
        return

    # Source coords interpoladas con las mismas baricéntricas.
    src_x = a * src_tri[0, 0] + b * src_tri[1, 0] + c * src_tri[2, 0]
    src_y = a * src_tri[0, 1] + b * src_tri[1, 1] + c * src_tri[2, 1]

    # Escribir solo donde inside y aún no hay valor — los triángulos comparten
    # diagonal, queremos que gane el primero que llegue (no hay re-render).
    yy = ys[inside].astype(np.int32)
    xx = xs[inside].astype(np.int32)
    fresh = ~mask[yy, xx]
    yy = yy[fresh]; xx = xx[fresh]
    if yy.size == 0:
        return
    map_x[yy, xx] = src_x[inside][fresh]
    map_y[yy, xx] = src_y[inside][fresh]
    mask[yy, xx] = True


class ProjectionMappingRenderer:
    """Aplica un warp configurable al frame producido por el inner renderer.

    Cuando `enabled` es False o el mesh es identidad, devuelve el frame
    sin tocar (costo cero). Cuando se activa con mesh no-trivial:

    - mesh 2x2 → `cv2.warpPerspective` (path rápido, una operación).
    - mesh NxM (N o M >= 3) → `cv2.remap` con un LUT precomputado en
      cada cambio de mesh. La construcción del LUT es O(W*H) y corre
      una vez por calibración, no por frame.
    """

    def __init__(
        self,
        inner: Optional[FrameRenderer] = None,
        corners: Optional[Sequence[Sequence[float]]] = None,
        mesh_points=None,
        mesh_size: Tuple[int, int] = (2, 2),
        enabled: bool = False,
    ) -> None:
        self._inner = inner
        # `mesh_points` toma precedencia sobre `corners` (legacy).
        if mesh_points is not None:
            arr = np.asarray(mesh_points, dtype=np.float32)
            if arr.ndim != 3 or arr.shape[2] != 2:
                raise ValueError(f"mesh_points must be (rows, cols, 2), got shape {arr.shape}")
            self._mesh = np.clip(arr, 0.0, 1.0)
        elif corners is not None:
            self._mesh = _corners_to_mesh(corners)
        else:
            self._mesh = _identity_mesh(*mesh_size)
        self._enabled: bool = bool(enabled)
        # LUT cache para mesh NxM (N>=3 o M>=3). Invalidado en cada cambio
        # de mesh o de output_size. Tupla `(map_x, map_y, w, h, sig)`.
        self._lut_cache: Optional[Tuple[np.ndarray, np.ndarray, int, int, bytes]] = None

    # --- composition -------------------------------------------------

    @property
    def inner(self) -> Optional[FrameRenderer]:
        return self._inner

    @inner.setter
    def inner(self, renderer: Optional[FrameRenderer]) -> None:
        self._inner = renderer

    # --- toggle ------------------------------------------------------

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

    # --- mesh API ---------------------------------------------------

    @property
    def mesh_size(self) -> Tuple[int, int]:
        return (int(self._mesh.shape[0]), int(self._mesh.shape[1]))

    @property
    def mesh_points(self) -> List[List[List[float]]]:
        # Devuelve listas anidadas (JSON-friendly) en lugar de ndarray.
        return [[[float(v) for v in pt] for pt in row] for row in self._mesh]

    def set_mesh_size(self, rows: int, cols: int) -> None:
        """Reset al mesh identidad de la nueva densidad. Borra calibración."""
        if rows not in SUPPORTED_MESH_SIZES or cols not in SUPPORTED_MESH_SIZES:
            raise ValueError(
                f"mesh size {rows}x{cols} no soportado. "
                f"Densidades válidas: {SUPPORTED_MESH_SIZES}."
            )
        self._mesh = _identity_mesh(rows, cols)
        self._lut_cache = None

    def set_mesh_points(self, points) -> None:
        """Reescribe todos los puntos. Shape debe coincidir con mesh actual."""
        rows, cols = self.mesh_size
        self._mesh = _normalize_mesh(points, rows, cols)
        self._lut_cache = None

    def set_mesh_point(self, row: int, col: int, x: float, y: float) -> None:
        """Mueve un solo punto. Útil para drag fino sin reenviar todos."""
        rows, cols = self.mesh_size
        if not 0 <= row < rows:
            raise IndexError(f"row {row} out of [0, {rows})")
        if not 0 <= col < cols:
            raise IndexError(f"col {col} out of [0, {cols})")
        self._mesh[row, col] = (_clamp01(x), _clamp01(y))
        self._lut_cache = None

    def reset(self) -> None:
        rows, cols = self.mesh_size
        self._mesh = _identity_mesh(rows, cols)
        self._lut_cache = None

    def is_identity(self) -> bool:
        rows, cols = self.mesh_size
        ident = _identity_mesh(rows, cols)
        return bool(np.allclose(self._mesh, ident, atol=1e-4))

    # --- legacy 4-corner API (sigue funcionando con mesh 2x2) ------

    @property
    def corners_norm(self) -> List[Tuple[float, float]]:
        if self.mesh_size != (2, 2):
            # Cuando el mesh es más denso, devolvemos las 4 esquinas
            # extremas — sirve para la UI legacy pero no representa el
            # estado completo. Para mesh real usar `mesh_points`.
            return [
                (float(self._mesh[0,  0,  0]), float(self._mesh[0,  0,  1])),
                (float(self._mesh[0, -1,  0]), float(self._mesh[0, -1,  1])),
                (float(self._mesh[-1, -1, 0]), float(self._mesh[-1, -1, 1])),
                (float(self._mesh[-1, 0,  0]), float(self._mesh[-1, 0,  1])),
            ]
        return [
            (float(self._mesh[0, 0, 0]), float(self._mesh[0, 0, 1])),
            (float(self._mesh[0, 1, 0]), float(self._mesh[0, 1, 1])),
            (float(self._mesh[1, 1, 0]), float(self._mesh[1, 1, 1])),
            (float(self._mesh[1, 0, 0]), float(self._mesh[1, 0, 1])),
        ]

    def set_corners(self, corners: Sequence[Sequence[float]]) -> None:
        """Setea los 4 corners. Cambia el mesh a 2x2 si era más denso."""
        self._mesh = _corners_to_mesh(corners)
        self._lut_cache = None

    def set_corner(self, idx: int, x: float, y: float) -> None:
        """Mueve un corner por índice (0=TL, 1=TR, 2=BR, 3=BL)."""
        if not 0 <= idx < 4:
            raise IndexError(f"corner idx must be in [0,3], got {idx}")
        # Mapeo idx → (row, col) en el grid actual (2x2 o más).
        rows, cols = self.mesh_size
        rc = [
            (0, 0),                # TL
            (0, cols - 1),         # TR
            (rows - 1, cols - 1),  # BR
            (rows - 1, 0),         # BL
        ][idx]
        self._mesh[rc[0], rc[1]] = (_clamp01(x), _clamp01(y))
        self._lut_cache = None

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

        if not self._enabled or self.is_identity():
            return rendered

        img = np.asarray(rendered.image)
        h, w = img.shape[:2]

        if self.mesh_size == (2, 2):
            # Path rápido: warp perspectiva clásico.
            corners = self.corners_norm
            src = np.float32([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])
            dst = np.float32([(cx * w, cy * h) for (cx, cy) in corners])
            matrix = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(
                img, matrix, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0),
            )
        else:
            # Path mesh: cv2.remap con LUT cacheado.
            warped = self._render_mesh(img, w, h)

        meta = dict(rendered.metadata) if rendered.metadata else {}
        meta["projection"] = "warped"
        meta["projection_mesh_size"] = list(self.mesh_size)
        return RenderFrame(image=Image.fromarray(warped), metadata=meta)

    def _render_mesh(self, img: np.ndarray, w: int, h: int) -> np.ndarray:
        sig = self._mesh.tobytes()
        cache = self._lut_cache
        if cache is None or cache[2] != w or cache[3] != h or cache[4] != sig:
            map_x, map_y = _build_remap_lut(self._mesh, w, h)
            self._lut_cache = (map_x, map_y, w, h, sig)
        else:
            map_x, map_y = cache[0], cache[1]
        return cv2.remap(
            img, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
