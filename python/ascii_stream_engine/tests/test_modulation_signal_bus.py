"""Tests para SignalBus — pizarra compartida del ModulationEngine."""
from __future__ import annotations

import pytest

from ascii_stream_engine.application.modulation import SignalBus


# ── publish / get ─────────────────────────────────────────────────────


def test_get_unknown_returns_default():
    bus = SignalBus()
    assert bus.get("face.center.x") == 0.0
    assert bus.get("face.center.x", default=0.5) == 0.5


def test_publish_then_get_returns_last_value():
    bus = SignalBus()
    bus.publish("hands.right.palm.y", 0.3)
    bus.publish("hands.right.palm.y", 0.7)
    assert bus.get("hands.right.palm.y") == 0.7


def test_publish_coerces_to_float():
    bus = SignalBus()
    bus.publish("x", 1)  # int → float
    assert isinstance(bus.get("x"), float)
    assert bus.get("x") == 1.0


def test_has_only_after_publish():
    bus = SignalBus()
    assert not bus.has("y")
    bus.publish("y", 0.0)
    assert bus.has("y")


def test_publish_many_sets_all():
    bus = SignalBus()
    bus.publish_many({"a": 0.1, "b": 0.2, "c": 0.3})
    assert bus.get("a") == 0.1
    assert bus.get("b") == 0.2
    assert bus.get("c") == 0.3


# ── freeze-on-lost (no se llama a publish → último valor queda) ───────


def test_unpublished_frame_keeps_last_value():
    """Si una signal no se republica este frame, mantiene el valor anterior.
    Esto es freeze-on-lost natural — ningún source ni el bus tiene que
    'mantener' el valor explícitamente."""
    bus = SignalBus()
    bus.publish("face.center.x", 0.42)
    # Próximo "frame": face.center.x NO se publica
    assert bus.get("face.center.x") == 0.42  # sigue ahí


# ── history ───────────────────────────────────────────────────────────


def test_get_history_lazy_starts_with_current_value():
    bus = SignalBus()
    bus.publish("v", 1.0)
    h = bus.get_history("v")
    assert h == [1.0]  # bootstrap incluye el valor presente


def test_get_history_unknown_returns_empty():
    bus = SignalBus()
    assert bus.get_history("nope") == []


def test_get_history_appends_after_first_get():
    bus = SignalBus()
    bus.publish("v", 1.0)
    bus.get_history("v")  # arma el deque
    bus.publish("v", 2.0)
    bus.publish("v", 3.0)
    assert bus.get_history("v") == [1.0, 2.0, 3.0]


def test_get_history_truncates_to_n():
    bus = SignalBus(history_frames=5)
    bus.publish("v", 0.0)
    bus.get_history("v")
    for i in range(1, 10):
        bus.publish("v", float(i))
    h = bus.get_history("v")
    assert len(h) == 5
    assert h[-1] == 9.0
    assert h[0] == 5.0  # primeros 4 (0-4) cayeron por la deque maxlen


def test_get_history_n_arg_returns_last_n():
    bus = SignalBus(history_frames=10)
    bus.publish("v", 0.0)
    bus.get_history("v")
    for i in range(1, 6):
        bus.publish("v", float(i))
    assert bus.get_history("v", n=2) == [4.0, 5.0]


def test_history_is_lazy_per_signal():
    """No se reservan deques para signals que nadie pidió historia."""
    bus = SignalBus()
    bus.publish("a", 1.0)
    bus.publish("b", 2.0)
    bus.get_history("a")
    # internal: 'a' tiene history, 'b' no
    assert "a" in bus._history
    assert "b" not in bus._history


# ── snapshot / clear ──────────────────────────────────────────────────


def test_snapshot_returns_dict_copy():
    bus = SignalBus()
    bus.publish("a", 1.0)
    snap = bus.snapshot()
    assert snap == {"a": 1.0}
    snap["a"] = 99.0
    assert bus.get("a") == 1.0  # snapshot es copia, no rompe el bus


def test_clear_all():
    bus = SignalBus()
    bus.publish_many({"a": 1.0, "b": 2.0})
    n = bus.clear()
    assert n == 2
    assert not bus.has("a")
    assert not bus.has("b")


def test_clear_specific_names():
    bus = SignalBus()
    bus.publish_many({"a": 1.0, "b": 2.0, "c": 3.0})
    n = bus.clear(["a", "c"])
    assert n == 2
    assert not bus.has("a")
    assert bus.has("b")
    assert not bus.has("c")


# ── construcción ──────────────────────────────────────────────────────


def test_invalid_history_raises():
    with pytest.raises(ValueError):
        SignalBus(history_frames=0)
    with pytest.raises(ValueError):
        SignalBus(history_frames=-1)


def test_default_history_frames():
    bus = SignalBus()
    assert bus.history_frames == SignalBus.DEFAULT_HISTORY
