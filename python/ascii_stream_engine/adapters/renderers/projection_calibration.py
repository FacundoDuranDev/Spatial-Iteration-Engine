"""Auto-calibración de projection mapping con marcadores ChArUco.

Workflow operacional:

1. El operador apunta la cámara al proyector (físicamente).
2. La app pide al engine "modo calibración" → el renderer mete un patrón
   ChArUco fullscreen como output, sin warp.
3. El proyector tira el patrón sobre la superficie real.
4. La cámara captura ese patrón distorsionado por: (a) la perspectiva
   proyector-pared, (b) la perspectiva pared-cámara.
5. Detectamos los markers en el frame de cámara, computamos la homografía
   `proyector → cámara`, y la invertimos: los corners "compensados" que
   hacen que la imagen aparezca rectangular en la superficie son la
   inversa aplicada a las 4 esquinas del unit square en cámara.

Asunciones / limitaciones:
- La cámara debe estar en la posición desde donde queremos que se vea
  "correcto" — idealmente la del público.
- La superficie se modela como **plana** (homografía pura). Para
  superficies curvas o múltiples planos, esta calibración da una
  aproximación; el ajuste fino se hace con el mesh denso.
- Los 4 markers de las esquinas del board ChArUco deben quedar
  visibles y detectables (luz suficiente, sin oclusiones).

El módulo no tiene estado: las dos funciones (`generate_pattern_image`,
`detect_corners_normalized`) son puras. El bridge orquesta el modo
calibración.
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

# ChArUco board: 5 columnas × 4 filas de cuadrados (4 markers internos
# por chessboard). Diccionario 4x4 con 50 IDs alcanza para ese tamaño.
# Square length y marker length son arbitrarios — solo importa el ratio
# para la detección. La imagen final se reescala al output.
_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
_BOARD = cv2.aruco.CharucoBoard(
    size=(5, 4),
    squareLength=0.04,
    markerLength=0.024,
    dictionary=_DICTIONARY,
)
_DETECTOR_PARAMS = cv2.aruco.DetectorParameters()

# Cache de imágenes del patrón por (w, h) — generar una imagen ChArUco no
# es trivial y la pedimos en cada frame mientras estamos en modo calibración.
_PATTERN_CACHE: dict = {}


def generate_pattern_image(width: int, height: int) -> np.ndarray:
    """Devuelve la imagen del patrón ChArUco a tamaño `(height, width)`.

    Imagen RGB uint8 — directamente conectable al sink del engine como si
    fuera un render normal. El patrón se rellena al canvas con un margen
    blanco mínimo para que `detectMarkers` agarre las esquinas externas.
    """
    key = (int(width), int(height))
    cached = _PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    margin_px = 30
    inner_w = max(50, width - 2 * margin_px)
    inner_h = max(50, height - 2 * margin_px)
    inner = _BOARD.generateImage(
        outSize=(inner_w, inner_h),
        marginSize=0,
        borderBits=1,
    )
    # Pintar el board centrado en un canvas blanco (margen ayuda a detectar).
    canvas = np.full((height, width), 255, dtype=np.uint8)
    y0 = (height - inner_h) // 2
    x0 = (width - inner_w) // 2
    canvas[y0:y0 + inner_h, x0:x0 + inner_w] = inner
    rgb = cv2.cvtColor(canvas, cv2.COLOR_GRAY2RGB)
    _PATTERN_CACHE[key] = rgb
    return rgb


def detect_corners_normalized(
    captured_frame: np.ndarray,
) -> Tuple[Optional[list], Optional[str]]:
    """Detecta el patrón en el frame capturado y devuelve los corners.

    Returns:
        `(corners, error)` — corners es una lista de 4 `[x, y]`
        normalizados a [0, 1] en orden TL, TR, BR, BL listos para
        `region.set_corners(...)`. Si no se pudo detectar, corners es
        None y error es un string descriptivo.
    """
    if captured_frame is None:
        return None, "no hay frame de cámara disponible"
    if captured_frame.ndim == 3 and captured_frame.shape[2] == 3:
        gray = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = captured_frame
    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)

    h, w = gray.shape[:2]
    corners, ids, _ = cv2.aruco.detectMarkers(
        gray, _DICTIONARY, parameters=_DETECTOR_PARAMS
    )
    if ids is None or len(ids) < 4:
        return None, f"se detectaron solo {0 if ids is None else len(ids)} markers (mínimo 4)"

    # Estrategia simple: tomar el bounding box del conjunto de TODOS los
    # markers detectados como aproximación del rectángulo del patrón.
    # Para un quad con perspectiva real conviene refinar con
    # interpolateCornersCharuco — eso lo dejamos para v2.
    all_pts = np.concatenate(corners, axis=1).reshape(-1, 2)

    # Para cada esquina del bounding box, encontrar el punto detectado más
    # cercano — eso aproxima los 4 corners del patrón en el frame.
    bbox_corners = np.float32([
        [all_pts[:, 0].min(), all_pts[:, 1].min()],  # TL
        [all_pts[:, 0].max(), all_pts[:, 1].min()],  # TR
        [all_pts[:, 0].max(), all_pts[:, 1].max()],  # BR
        [all_pts[:, 0].min(), all_pts[:, 1].max()],  # BL
    ])
    detected = []
    for bc in bbox_corners:
        dists = np.linalg.norm(all_pts - bc, axis=1)
        idx = int(np.argmin(dists))
        detected.append(all_pts[idx])
    detected = np.float32(detected)

    # Normalizar a [0,1] del frame de cámara.
    detected_norm = detected.copy()
    detected_norm[:, 0] /= max(1.0, w - 1)
    detected_norm[:, 1] /= max(1.0, h - 1)

    # Computar la homografía proyector→cámara y su inversa.
    # En proyector-space, el patrón ocupa [0,1]² (rellenamos el output sin warp).
    src_projector = np.float32([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    H_proj_to_cam = cv2.getPerspectiveTransform(src_projector, detected_norm)
    try:
        H_cam_to_proj = np.linalg.inv(H_proj_to_cam)
    except np.linalg.LinAlgError:
        return None, "homografía degenerada — markers casi colineales"

    # Para que la imagen aparezca rectangular en la superficie, los corners
    # del frame source (en proyector-space) son: H⁻¹ aplicado a las 4
    # esquinas del unit square en coords cámara.
    target_in_camera = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]).reshape(-1, 1, 2)
    target_in_projector = cv2.perspectiveTransform(target_in_camera, H_cam_to_proj).reshape(-1, 2)
    # Clamp a [0, 1] — corners fuera de rango significarían "el proyector
    # no alcanza esa zona". El renderer también clampea por defensa.
    clamped = np.clip(target_in_projector, 0.0, 1.0)
    return [[float(x), float(y)] for (x, y) in clamped], None
