"""ModulationEngine — aplica mappings señal→param una vez por frame.

Diseño concurrente:
- `_mappings: List[Modulation]` se actualiza con copy-on-write (lock solo
  para escritores, lectores acceden el snapshot por rebind atómico).
- `tick()` corre en el thread del GraphScheduler, sin lock.
- `add/remove/clear` corre desde el WS handler (~1 Hz), toma `_lock`
  brevemente para rebindear la lista.

Smoothing: low-pass EMA con `smoothing` ∈ [0, 1] como peso del pasado.
    smoothing = 0.0   → sin smoothing (la señal pasa directa)
    smoothing = 0.3   → default razonable, lag chico
    smoothing = 0.95  → muy lento, tipo "sigue al cuerpo con inercia"
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from . import curves
from .mapping import Modulation
from .signal_bus import SignalBus

logger = logging.getLogger("modulation.engine")

# Tipo del callback que aplica el valor al filtro real (delegado al bridge).
ParamSetter = Callable[[str, str, Any], bool]


class ModulationEngine:
    """Mantiene una lista de mappings y los aplica por frame al engine.

    No depende del bridge directamente: el `setter` (callable que sabe
    cómo mutar un (fid, pid) en el StreamEngine) se inyecta en `tick()`.
    Esto preserva la dirección de dependencia hexagonal: application no
    importa adapters/web_dashboard.
    """

    def __init__(self, signal_bus: SignalBus) -> None:
        self._bus = signal_bus
        # Copy-on-write: tick() lee `self._mappings` sin lock; writers
        # crean lista nueva y rebindean atómicamente.
        self._mappings: List[Modulation] = []
        # Estado de smoothing per-mapping (key = índice estable mientras
        # no se removan mappings antes; clear en remove para evitar drift).
        self._smooth_state: Dict[int, float] = {}
        self._lock = threading.Lock()

    # ── public API: management ────────────────────────────────────────

    def add(self, m: Modulation) -> int:
        """Agrega un mapping. Devuelve el índice asignado."""
        with self._lock:
            new = list(self._mappings)
            new.append(m)
            self._mappings = new
            return len(new) - 1

    def remove(self, idx: int) -> bool:
        """Borra el mapping por índice. Devuelve True si existía."""
        with self._lock:
            if idx < 0 or idx >= len(self._mappings):
                return False
            new = list(self._mappings)
            new.pop(idx)
            self._mappings = new
            # Borrar todos los estados de smoothing — los índices cambian
            # tras un remove. Re-bootstrap al primer tick. Es un mini
            # hiccup aceptable (1 frame de salto) en ops de UI a 1 Hz.
            self._smooth_state.clear()
            return True

    def clear(self) -> int:
        """Borra todos los mappings. Devuelve count borrado."""
        with self._lock:
            n = len(self._mappings)
            self._mappings = []
            self._smooth_state.clear()
            return n

    def list(self) -> List[Modulation]:
        """Snapshot de la lista actual (lectura sin lock — atómica)."""
        return list(self._mappings)

    def has_mappings(self) -> bool:
        return bool(self._mappings)

    def modulated_params(self) -> set:
        """Set de (filter_id, param_id) tuplas de mappings ENABLED.

        Lo usa el bridge.snapshot() para marcar params modulados → la UI
        los renderiza disabled (evita el "fight" con el slider a 30 Hz).
        """
        out = set()
        for m in self._mappings:
            if m.enabled:
                out.add((m.filter_id, m.param_id))
        return out

    # ── hot path: tick ────────────────────────────────────────────────

    def tick(self, setter: ParamSetter) -> int:
        """Aplica todos los mappings activos. Devuelve count de params updated.

        Llamado desde el GraphScheduler una vez por frame, después de los
        analyzers (analysis ya está en el SignalBus) y antes del primer
        ProcessorNode (filtros).
        """
        mappings = self._mappings  # snapshot atómico
        if not mappings:
            return 0
        n = 0
        for i, m in enumerate(mappings):
            if not m.enabled:
                continue
            if not self._bus.has(m.signal):
                continue  # freeze-on-lost: signal no publicada → no hacemos nada
            raw = self._bus.get(m.signal)
            value = self._compute(m, raw)
            value = self._smooth(i, m.smoothing, value)
            try:
                if setter(m.filter_id, m.param_id, value):
                    n += 1
            except Exception:
                logger.exception(
                    "modulation %d → %s.%s failed", i, m.filter_id, m.param_id
                )
        return n

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _compute(m: Modulation, raw: float) -> float:
        """Normaliza, aplica curva y escala a out_range."""
        if m.in_max == m.in_min:
            t = 0.0
        else:
            t = (raw - m.in_min) / (m.in_max - m.in_min)
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        t = curves.apply(m.curve, t)
        return m.out_min + t * (m.out_max - m.out_min)

    def _smooth(self, idx: int, smoothing: float, value: float) -> float:
        """EMA low-pass. smoothing alto = más lento; 0 = sin filtro."""
        if smoothing <= 0.0:
            self._smooth_state[idx] = value
            return value
        if smoothing >= 1.0:
            # Edge case: 1.0 = nunca cambia. Bootstrap con el primer valor.
            prev = self._smooth_state.setdefault(idx, value)
            return prev
        prev = self._smooth_state.get(idx, value)  # bootstrap = sin salto
        new = smoothing * prev + (1.0 - smoothing) * value
        self._smooth_state[idx] = new
        return new
