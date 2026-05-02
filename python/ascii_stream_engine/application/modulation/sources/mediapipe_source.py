"""MediaPipeSignalSource — traduce face/hands analysis a señales modulables.

Lee el dict producido por `FaceLandmarkAnalyzer` y `HandLandmarkAnalyzer`
(ver `adapters/perception/{face,hands}.py`) y publica 15 señales con
nombres dotted estables. Cuando sumemos MoveNet o Kinect, sus sources
publicarán al MISMO bus con namespace `body.*` — el resto del sistema no
se entera.

Schema esperado del analysis dict:
    analysis["face"] = {
        "faces": [{"bbox": [x, y, w, h], "confidence": float, "points": ndarray}],
        "points": ndarray  # concatenado, no usado acá
    }
    analysis["hands"] = {
        "left":  ndarray(21, 2) | empty,    # MediaPipe convention: "Left"
        "right": ndarray(21, 2) | empty,    # se refiere al lado del SUJETO,
                                            # NO al espejado del viewer
    }

Todos los valores normalizados 0-1 (ya vienen así de los analyzers).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from ..signal_bus import SignalBus

# Índices canónicos de MediaPipe Hands (21 landmarks por mano).
_PALM = 0       # wrist / palm base
_TIP_INDEX = 8  # punta del índice — el "puntero" más usable


class MediaPipeSignalSource:
    """Productor del SignalBus a partir de face + hands analysis.

    Statless — solo recibe analysis y publica al bus. La detección efímera
    (cara perdida un frame) NO se publica → freeze-on-lost natural.
    """

    # Catálogo estático — esto poblará el wizard de la UI.
    _SIGNALS: List[str] = [
        "face.center.x",
        "face.center.y",
        "face.bbox.scale",
        "face.confidence",
        "face.count",
        "hands.left.palm.x",
        "hands.left.palm.y",
        "hands.left.tip_index.x",
        "hands.left.tip_index.y",
        "hands.right.palm.x",
        "hands.right.palm.y",
        "hands.right.tip_index.x",
        "hands.right.tip_index.y",
        "hands.distance",
        "hands.count",
    ]

    @classmethod
    def declared_signals(cls) -> List[str]:
        return list(cls._SIGNALS)

    def publish(self, analysis: Dict[str, Any], bus: SignalBus) -> None:
        # Distinguimos "analyzer NO corrió" (key ausente → freeze-on-lost,
        # no publicamos nada) de "analyzer corrió y no encontró" (key
        # presente con lista vacía → publicamos count=0).
        face = analysis.get("face") if "face" in analysis else None
        hands = analysis.get("hands") if "hands" in analysis else None
        faces_list = face.get("faces") if isinstance(face, dict) else None
        if isinstance(faces_list, list):
            bus.publish("face.count", float(len(faces_list)))
            if faces_list:
                primary = faces_list[0]  # primera cara = "el sujeto"
                bbox = primary.get("bbox")
                if isinstance(bbox, (list, tuple, np.ndarray)) and len(bbox) >= 4:
                    bx, by, bw, bh = (float(bbox[0]), float(bbox[1]),
                                      float(bbox[2]), float(bbox[3]))
                    bus.publish("face.center.x", bx + bw * 0.5)
                    bus.publish("face.center.y", by + bh * 0.5)
                    # Scale = max(w, h) — robusto a aspect raros de caras de perfil.
                    bus.publish("face.bbox.scale", max(bw, bh))
                conf = primary.get("confidence")
                if conf is not None:
                    bus.publish("face.confidence", float(conf))

        # hands.* — count + posiciones por mano. Distance solo si ambas
        # presentes. Si la key 'hands' no estaba (analyzer apagado) caemos
        # acá con hands=None y no publicamos nada → freeze-on-lost.
        if isinstance(hands, dict):
            left = self._as_array(hands.get("left"))
            right = self._as_array(hands.get("right"))
            present = 0
            if left is not None:
                present += 1
                self._publish_hand(bus, "hands.left", left)
            if right is not None:
                present += 1
                self._publish_hand(bus, "hands.right", right)
            bus.publish("hands.count", float(present))
            if left is not None and right is not None:
                lp = self._safe_landmark(left, _PALM)
                rp = self._safe_landmark(right, _PALM)
                if lp is not None and rp is not None:
                    dx = float(lp[0]) - float(rp[0])
                    dy = float(lp[1]) - float(rp[1])
                    bus.publish("hands.distance", math.hypot(dx, dy))

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _as_array(value: Any) -> Optional[np.ndarray]:
        """Devuelve ndarray con landmarks o None si está vacío / inválido."""
        if value is None:
            return None
        try:
            arr = np.asarray(value)
        except Exception:
            return None
        if arr.size == 0 or arr.ndim < 2 or arr.shape[-1] < 2:
            return None
        return arr

    @staticmethod
    def _safe_landmark(arr: np.ndarray, idx: int) -> Optional[np.ndarray]:
        if idx < 0 or idx >= arr.shape[0]:
            return None
        return arr[idx]

    def _publish_hand(self, bus: SignalBus, prefix: str, arr: np.ndarray) -> None:
        palm = self._safe_landmark(arr, _PALM)
        if palm is not None:
            bus.publish(f"{prefix}.palm.x", float(palm[0]))
            bus.publish(f"{prefix}.palm.y", float(palm[1]))
        tip = self._safe_landmark(arr, _TIP_INDEX)
        if tip is not None:
            bus.publish(f"{prefix}.tip_index.x", float(tip[0]))
            bus.publish(f"{prefix}.tip_index.y", float(tip[1]))
