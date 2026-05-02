"""SignalSource Protocol — contrato para productores del SignalBus."""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class SignalSource(Protocol):
    """Adaptador que extrae señales de un analysis dict y las publica al bus.

    Los signals declarados son ESTÁTICOS — los conoce la clase, no la
    instancia. Eso permite armar el catálogo de "señales mapeables" del
    UI sin tener que esperar a que MediaPipe detecte algo.

    Convención de nombres: dotted, namespace por dominio.
        face.center.x       hands.left.palm.x       body.head.yaw  (futuro)
        face.bbox.scale     hands.distance          audio.bpm      (futuro)
    """

    @classmethod
    def declared_signals(cls) -> List[str]:
        """Lista exhaustiva y ESTÁTICA de signals que esta source puede publicar.

        Convocada antes de que la cámara abra para poblar el wizard de
        creación de mappings en la UI.
        """
        ...

    def publish(self, analysis: Dict[str, Any], bus: "SignalBus") -> None:  # noqa: F821
        """Por frame: mira el analysis dict y publica las señales que pueda
        derivar al bus. Debe ser barato (microsegundos) — corre en el hot path.

        Comportamiento ante "perdí la detección este frame": NO publicar
        (freeze-on-lost natural — el bus mantiene el último valor). Si la
        source quiere semántica distinta, que llame `bus.publish(name, 0)`
        o `bus.clear([name])` explícito.
        """
        ...
