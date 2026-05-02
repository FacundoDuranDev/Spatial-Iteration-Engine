"""Modulation — un mapping de señal-del-bus a parámetro-de-filtro.

Es inmutable (frozen dataclass): para "modificar" un mapping se borra el
viejo y se crea uno nuevo. Esto encaja con el copy-on-write del engine y
evita locks.

Persistencia: `to_dict()` / `from_dict()` para schema versionado en
`~/.ascii_stream_engine/modulations.json`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Modulation:
    """Conexión declarativa señal → param.

    El flujo en `tick()`:
        raw = bus.get(signal)
        t   = clamp((raw - in_min) / (in_max - in_min))   # normalizar
        t   = curve(t)                                     # aplicar curva
        v   = out_min + t * (out_max - out_min)            # escalar a out_range
        v   = ema(v, prev, smoothing)                      # suavizar
        bridge_setter(filter_id, param_id, v)              # aplicar al filtro
    """

    signal: str
    filter_id: str
    param_id: str
    in_min: float = 0.0
    in_max: float = 1.0
    out_min: float = 0.0
    out_max: float = 1.0
    curve: str = "linear"
    smoothing: float = 0.3       # 0 = sin smoothing, 1 = nunca cambia
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Modulation":
        # Tolerante: keys faltantes usan default. Keys extra se ignoran.
        kwargs = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**kwargs)
