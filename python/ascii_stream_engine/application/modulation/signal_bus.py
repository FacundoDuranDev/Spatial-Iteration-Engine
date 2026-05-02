"""SignalBus — pizarra compartida de señales tracking → modulación.

Productores (SignalSources) escriben señales por frame; consumidores
(ModulationEngine) leen el último valor o un buffer corto de historia.

Diseño explícitamente single-thread en el hot path: tanto las publicaciones
como las lecturas viven en el thread del GraphScheduler. El `_lock` es solo
para snapshots desde el WS handler (1 Hz vs 30 Hz, contention nula).

Freeze-on-lost no vive acá: es decisión del SignalSource. Si una señal no
se publica en este frame, su último valor queda en el bus tal cual — los
mappings ven "cara congelada" en vez de cero.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional


class SignalBus:
    """Thread-safe bag of `name → float` con history buffer per-signal.

    El history es lazy: solo se asigna deque cuando se llama `get_history`
    para esa señal por primera vez. Evita reservar 30 frames × 50 signals
    por defecto cuando casi nadie usa derivadas.
    """

    DEFAULT_HISTORY: int = 30

    def __init__(self, history_frames: int = DEFAULT_HISTORY) -> None:
        if history_frames < 1:
            raise ValueError(f"history_frames must be >= 1, got {history_frames}")
        self._history_frames = int(history_frames)
        self._values: Dict[str, float] = {}
        self._history: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def history_frames(self) -> int:
        return self._history_frames

    def publish(self, name: str, value: float) -> None:
        """Escribe `value` en `name`. Si hay history activo para esa señal,
        appendea (deque autotrunca a `history_frames`).
        """
        v = float(value)
        self._values[name] = v
        # Lazy history — solo se actualiza si alguien lo está rastreando.
        h = self._history.get(name)
        if h is not None:
            h.append(v)

    def publish_many(self, items: Dict[str, float]) -> None:
        """Atajo: publica varios pares en un solo call."""
        for k, v in items.items():
            self.publish(k, v)

    def get(self, name: str, default: float = 0.0) -> float:
        """Último valor publicado, o `default` si nunca se publicó."""
        return self._values.get(name, float(default))

    def has(self, name: str) -> bool:
        """True si la señal fue publicada al menos una vez."""
        return name in self._values

    def get_history(self, name: str, n: Optional[int] = None) -> List[float]:
        """Devuelve hasta los últimos `n` valores (default = todos los disponibles).

        La primera llamada para `name` "arma" el deque y empieza a guardar.
        Por eso la primera lectura puede traer 1 elemento (el actual) — eso
        es esperable. Para velocidades estables esperá unos frames antes
        de derivar.
        """
        h = self._history.get(name)
        if h is None:
            # Bootstrap: arrancá guardando desde ahora.
            h = deque(maxlen=self._history_frames)
            if name in self._values:
                h.append(self._values[name])
            self._history[name] = h
        if n is None or n >= len(h):
            return list(h)
        return list(h)[-n:]

    def snapshot(self) -> Dict[str, float]:
        """Copia thread-safe del dict actual — para debug / UI."""
        with self._lock:
            return dict(self._values)

    def names(self) -> List[str]:
        """Nombres de todas las señales que alguna vez se publicaron."""
        return list(self._values.keys())

    def clear(self, names: Optional[Iterable[str]] = None) -> int:
        """Borra señales. Sin args borra todo. Devuelve count borrado.

        Útil cuando un SignalSource quiere "olvidar" señales perdidas en
        vez de freeze-on-lost (anti-default — evitar a menos que sepas
        por qué). Más típico: nadie llama esto y el bus crece monotónico.
        """
        with self._lock:
            if names is None:
                n = len(self._values)
                self._values.clear()
                self._history.clear()
                return n
            n = 0
            for nm in names:
                if self._values.pop(nm, None) is not None:
                    n += 1
                self._history.pop(nm, None)
            return n
