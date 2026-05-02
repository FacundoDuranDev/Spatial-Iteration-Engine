"""Modulation engine: tracking signals → filter param mutations.

Subsystem dentro de `application/` que cumple el rol "MIDI controller hecho
con el cuerpo": cualquier señal del SignalBus (cara, manos, futuro Kinect)
puede modular cualquier parámetro de cualquier filtro registrado, vía
mappings declarativos (`Modulation`) que el `ModulationEngine` aplica una
vez por frame entre Analyzers y Filters.

Componentes (introducidos por fases):
    Phase 1: SignalBus + SignalSource Protocol + MediaPipeSignalSource
    Phase 2: ModulationEngine + curves
    Phase 3: WS protocol + persistencia
    Phase 4: UI mobile

Ver plan en `.claude/plans/hagmos-un-plan-de-reflective-stonebraker.md`.
"""

from . import curves
from .engine import ModulationEngine, ParamSetter
from .mapping import Modulation
from .signal_bus import SignalBus
from .sources.base import SignalSource
from .sources.mediapipe_source import MediaPipeSignalSource

__all__ = [
    "SignalBus",
    "SignalSource",
    "MediaPipeSignalSource",
    "ModulationEngine",
    "ParamSetter",
    "Modulation",
    "curves",
]
