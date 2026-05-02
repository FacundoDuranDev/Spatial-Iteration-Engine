"""Tests del ModulationEngine + Modulation dataclass.

FakeBridge captura las llamadas al setter para verificar comportamiento sin
montar el bridge real ni el engine completo.
"""
from __future__ import annotations

from typing import Any, List, Tuple

import pytest

from ascii_stream_engine.application.modulation import (
    Modulation,
    ModulationEngine,
    SignalBus,
)


class FakeBridge:
    """Captura los (fid, pid, value) que el ModulationEngine escribe."""

    def __init__(self, succeed: bool = True) -> None:
        self.calls: List[Tuple[str, str, Any]] = []
        self.succeed = succeed

    def set_param(self, fid: str, pid: str, value: Any) -> bool:
        self.calls.append((fid, pid, value))
        return self.succeed


# ── Modulation dataclass ──────────────────────────────────────────────


def test_modulation_defaults():
    m = Modulation(signal="x", filter_id="f", param_id="p")
    assert m.in_min == 0.0 and m.in_max == 1.0
    assert m.out_min == 0.0 and m.out_max == 1.0
    assert m.curve == "linear"
    assert m.smoothing == 0.3
    assert m.enabled is True


def test_modulation_to_dict_round_trip():
    m = Modulation(
        signal="hands.right.palm.y",
        filter_id="bloom",
        param_id="intensity",
        in_min=0.1,
        in_max=0.9,
        out_min=0.2,
        out_max=1.5,
        curve="ease_in_out",
        smoothing=0.6,
        enabled=False,
    )
    d = m.to_dict()
    m2 = Modulation.from_dict(d)
    assert m == m2


def test_from_dict_tolerates_missing_keys():
    """Versión vieja del schema sin curve/smoothing → defaults."""
    m = Modulation.from_dict({"signal": "x", "filter_id": "f", "param_id": "p"})
    assert m.curve == "linear"
    assert m.smoothing == 0.3


def test_from_dict_ignores_unknown_keys():
    """Versión nueva del schema con keys extra → no rompe."""
    m = Modulation.from_dict({
        "signal": "x", "filter_id": "f", "param_id": "p",
        "future_field": "ignored",
    })
    assert m.signal == "x"


# ── add / remove / list / has_mappings ───────────────────────────────


def test_engine_starts_empty():
    eng = ModulationEngine(SignalBus())
    assert not eng.has_mappings()
    assert eng.list() == []


def test_add_returns_index():
    eng = ModulationEngine(SignalBus())
    idx0 = eng.add(Modulation("a", "f1", "p1"))
    idx1 = eng.add(Modulation("b", "f2", "p2"))
    assert idx0 == 0
    assert idx1 == 1
    assert eng.has_mappings()
    assert len(eng.list()) == 2


def test_remove_by_index():
    eng = ModulationEngine(SignalBus())
    eng.add(Modulation("a", "f1", "p1"))
    eng.add(Modulation("b", "f2", "p2"))
    assert eng.remove(0) is True
    assert len(eng.list()) == 1
    assert eng.list()[0].signal == "b"


def test_remove_invalid_index_returns_false():
    eng = ModulationEngine(SignalBus())
    eng.add(Modulation("a", "f1", "p1"))
    assert eng.remove(99) is False
    assert eng.remove(-1) is False


def test_clear_returns_count():
    eng = ModulationEngine(SignalBus())
    eng.add(Modulation("a", "f1", "p1"))
    eng.add(Modulation("b", "f2", "p2"))
    assert eng.clear() == 2
    assert not eng.has_mappings()


def test_list_returns_copy():
    """Mutar la lista devuelta no afecta el engine."""
    eng = ModulationEngine(SignalBus())
    eng.add(Modulation("a", "f1", "p1"))
    snapshot = eng.list()
    snapshot.clear()
    assert eng.has_mappings()  # engine intacto


def test_modulated_params_only_includes_enabled():
    eng = ModulationEngine(SignalBus())
    eng.add(Modulation("a", "f1", "p1"))
    eng.add(Modulation("b", "f2", "p2", enabled=False))
    assert eng.modulated_params() == {("f1", "p1")}


# ── tick: pipeline completa ──────────────────────────────────────────


def test_tick_no_mappings_is_noop():
    eng = ModulationEngine(SignalBus())
    bridge = FakeBridge()
    assert eng.tick(bridge.set_param) == 0
    assert bridge.calls == []


def test_tick_freeze_on_lost_skips_unpublished_signal():
    """Si la señal no está en el bus, el mapping no se aplica."""
    bus = SignalBus()
    eng = ModulationEngine(bus)
    eng.add(Modulation("hands.right.palm.y", "bloom", "intensity"))
    bridge = FakeBridge()
    assert eng.tick(bridge.set_param) == 0
    assert bridge.calls == []


def test_tick_linear_passthrough():
    bus = SignalBus()
    bus.publish("x", 0.5)
    eng = ModulationEngine(bus)
    eng.add(Modulation(
        "x", "f", "p",
        in_min=0.0, in_max=1.0, out_min=0.0, out_max=1.0,
        curve="linear", smoothing=0.0,
    ))
    bridge = FakeBridge()
    n = eng.tick(bridge.set_param)
    assert n == 1
    assert bridge.calls == [("f", "p", 0.5)]


def test_tick_clamps_to_in_range():
    bus = SignalBus()
    bus.publish("x", 1.5)  # above in_max
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", in_max=1.0, out_max=10.0, smoothing=0.0))
    bridge = FakeBridge()
    eng.tick(bridge.set_param)
    assert bridge.calls[0][2] == pytest.approx(10.0)  # clamped → max out


def test_tick_maps_in_range_to_out_range():
    bus = SignalBus()
    bus.publish("x", 0.5)
    eng = ModulationEngine(bus)
    # in [0, 1] → out [10, 20], midpoint debería ser 15
    eng.add(Modulation("x", "f", "p", out_min=10.0, out_max=20.0, smoothing=0.0))
    bridge = FakeBridge()
    eng.tick(bridge.set_param)
    assert bridge.calls[0][2] == pytest.approx(15.0)


def test_tick_applies_invert_curve():
    bus = SignalBus()
    bus.publish("x", 0.2)
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", curve="invert", smoothing=0.0))
    bridge = FakeBridge()
    eng.tick(bridge.set_param)
    assert bridge.calls[0][2] == pytest.approx(0.8)


def test_tick_disabled_mapping_skipped():
    bus = SignalBus()
    bus.publish("x", 0.5)
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", enabled=False, smoothing=0.0))
    bridge = FakeBridge()
    assert eng.tick(bridge.set_param) == 0


def test_tick_setter_failure_doesnt_crash_other_mappings():
    bus = SignalBus()
    bus.publish("x", 0.5)
    bus.publish("y", 0.7)
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f1", "p1", smoothing=0.0))
    eng.add(Modulation("y", "f2", "p2", smoothing=0.0))

    calls = []
    def setter(fid, pid, v):
        calls.append((fid, pid, v))
        if fid == "f1":
            raise RuntimeError("boom")
        return True

    eng.tick(setter)
    # f1 falló, f2 igual se aplicó
    assert ("f2", "p2", pytest.approx(0.7)) in calls


# ── smoothing (EMA) ──────────────────────────────────────────────────


def test_smoothing_zero_is_passthrough():
    bus = SignalBus()
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", smoothing=0.0))
    bridge = FakeBridge()
    bus.publish("x", 0.0); eng.tick(bridge.set_param)
    bus.publish("x", 1.0); eng.tick(bridge.set_param)
    assert bridge.calls[0][2] == pytest.approx(0.0)
    assert bridge.calls[1][2] == pytest.approx(1.0)  # sin lag


def test_smoothing_high_lags_value():
    bus = SignalBus()
    eng = ModulationEngine(bus)
    # smoothing=0.9 → mantiene 90% del pasado, agrega 10% del nuevo
    eng.add(Modulation("x", "f", "p", smoothing=0.9))
    bridge = FakeBridge()
    bus.publish("x", 0.0); eng.tick(bridge.set_param)
    bus.publish("x", 1.0); eng.tick(bridge.set_param)
    # primer tick bootstrap = 0.0
    assert bridge.calls[0][2] == pytest.approx(0.0)
    # segundo tick: 0.9*0.0 + 0.1*1.0 = 0.1
    assert bridge.calls[1][2] == pytest.approx(0.1)


def test_smoothing_one_freezes_on_first_value():
    bus = SignalBus()
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", smoothing=1.0))
    bridge = FakeBridge()
    bus.publish("x", 0.3); eng.tick(bridge.set_param)
    bus.publish("x", 0.9); eng.tick(bridge.set_param)
    # smoothing 1.0 = nunca cambia tras bootstrap
    assert bridge.calls[0][2] == pytest.approx(0.3)
    assert bridge.calls[1][2] == pytest.approx(0.3)


def test_smoothing_state_resets_on_remove():
    """Después de remove, los índices de smoothing se borran (mini hiccup
    aceptable, evita usar el smoothing 'fantasma' del mapping anterior)."""
    bus = SignalBus()
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f", "p", smoothing=0.9))
    bridge = FakeBridge()
    bus.publish("x", 0.5); eng.tick(bridge.set_param)
    bus.publish("x", 0.5); eng.tick(bridge.set_param)
    # smooth state existe
    assert eng._smooth_state
    eng.remove(0)
    assert eng._smooth_state == {}


# ── copy-on-write para concurrencia ──────────────────────────────────


def test_add_during_tick_doesnt_affect_current_tick():
    """Simulamos que tick() y add() ocurren en threads distintos.
    Acá no podemos forzar timing real pero sí verificar que el snapshot
    de tick() es estable: agregamos otro mapping dentro del setter y
    confirmamos que NO se usó en este mismo tick."""
    bus = SignalBus()
    bus.publish("x", 0.5)
    eng = ModulationEngine(bus)
    eng.add(Modulation("x", "f1", "p1", smoothing=0.0))

    calls = []
    def setter(fid, pid, v):
        calls.append((fid, pid, v))
        # Se mete uno nuevo durante el tick — pero NO debería verse en este tick.
        if len(calls) == 1:
            eng.add(Modulation("x", "f2", "p2", smoothing=0.0))
        return True

    eng.tick(setter)
    # solo el original se aplicó en este tick
    assert len(calls) == 1
    # el siguiente tick sí ve los dos
    eng.tick(setter)
    assert len(calls) == 3
