"""Tests para las 5 curvas puras de modulación."""
from __future__ import annotations

import pytest

from ascii_stream_engine.application.modulation import curves


# ── linear (la trivial) ──────────────────────────────────────────────


def test_linear_identity():
    for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
        assert curves.linear(t) == t


# ── ease_in_out (smooth-step) ────────────────────────────────────────


def test_ease_in_out_endpoints():
    assert curves.ease_in_out(0.0) == 0.0
    assert curves.ease_in_out(1.0) == 1.0


def test_ease_in_out_clamps_outside_range():
    assert curves.ease_in_out(-0.5) == 0.0
    assert curves.ease_in_out(1.5) == 1.0


def test_ease_in_out_midpoint():
    # Smooth-step en 0.5 = 0.5 (simétrica).
    assert curves.ease_in_out(0.5) == pytest.approx(0.5)


def test_ease_in_out_monotonic():
    """Cualquier t < t' implica f(t) < f(t')."""
    samples = [i / 20.0 for i in range(21)]
    out = [curves.ease_in_out(t) for t in samples]
    for a, b in zip(out, out[1:]):
        assert a <= b


# ── ease_in / ease_out ───────────────────────────────────────────────


def test_ease_in_starts_slower_than_linear():
    assert curves.ease_in(0.25) < 0.25
    assert curves.ease_in(0.5) == pytest.approx(0.25)


def test_ease_out_ends_slower_than_linear():
    assert curves.ease_out(0.5) == pytest.approx(0.75)
    assert curves.ease_out(0.25) > 0.25  # acelera al inicio


def test_easings_endpoints():
    for fn in (curves.ease_in, curves.ease_out):
        assert fn(0.0) == 0.0
        assert fn(1.0) == 1.0


# ── invert ───────────────────────────────────────────────────────────


def test_invert_mirrors():
    assert curves.invert(0.0) == 1.0
    assert curves.invert(1.0) == 0.0
    assert curves.invert(0.3) == pytest.approx(0.7)


# ── apply (dispatch) ─────────────────────────────────────────────────


def test_apply_known_curve_uses_correct_function():
    assert curves.apply("invert", 0.2) == pytest.approx(0.8)
    assert curves.apply("linear", 0.4) == 0.4


def test_apply_unknown_curve_falls_back_to_linear():
    """Defensivo: name del JSON viejo no rompe el sistema."""
    assert curves.apply("nonexistent", 0.42) == 0.42
    assert curves.apply("", 0.7) == 0.7


def test_curve_names_matches_dict():
    assert set(curves.CURVE_NAMES) == set(curves.CURVES.keys())
    assert len(curves.CURVE_NAMES) == 5
