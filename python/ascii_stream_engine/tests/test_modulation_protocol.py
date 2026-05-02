"""Tests del validator de payloads para `add_modulation` y persistencia JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ascii_stream_engine.adapters.outputs.web_dashboard import protocol, registry
from ascii_stream_engine.application.modulation import Modulation, curves


VALID_SIGNALS = frozenset({
    "face.center.x", "hands.right.palm.y", "hands.distance",
})
VALID_CURVES = frozenset(curves.CURVE_NAMES)


def _payload(**overrides):
    base = {
        "signal": "hands.right.palm.y",
        "filter": "bloom",
        "param": "intensity",
    }
    base.update(overrides)
    return base


# ── happy path ────────────────────────────────────────────────────────


def test_validate_minimal_payload_uses_defaults():
    out, err = protocol.validate_modulation_payload(
        _payload(), VALID_SIGNALS, registry, VALID_CURVES
    )
    assert err is None
    assert out["signal"] == "hands.right.palm.y"
    assert out["filter_id"] == "bloom"
    assert out["param_id"] == "intensity"
    assert out["in_min"] == 0.0 and out["in_max"] == 1.0
    assert out["out_min"] == 0.0 and out["out_max"] == 1.0
    assert out["curve"] == "linear"
    assert out["smoothing"] == 0.3
    assert out["enabled"] is True


def test_validate_full_payload_keeps_values():
    out, err = protocol.validate_modulation_payload(
        _payload(
            in_min=0.1, in_max=0.9, out_min=10.0, out_max=20.0,
            curve="invert", smoothing=0.7, enabled=False,
        ),
        VALID_SIGNALS, registry, VALID_CURVES,
    )
    assert err is None
    assert out["in_min"] == pytest.approx(0.1)
    assert out["in_max"] == pytest.approx(0.9)
    assert out["out_max"] == pytest.approx(20.0)
    assert out["curve"] == "invert"
    assert out["smoothing"] == pytest.approx(0.7)
    assert out["enabled"] is False


def test_normalized_dict_constructs_valid_modulation():
    """El dict normalizado se puede pasar directo a Modulation(**out)."""
    out, _ = protocol.validate_modulation_payload(
        _payload(), VALID_SIGNALS, registry, VALID_CURVES
    )
    m = Modulation(**out)
    assert m.signal == "hands.right.palm.y"


# ── rejecciones ───────────────────────────────────────────────────────


def test_reject_non_dict_payload():
    out, err = protocol.validate_modulation_payload(
        "not a dict", VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out is None
    assert "object" in err


def test_reject_unknown_signal():
    out, err = protocol.validate_modulation_payload(
        _payload(signal="moon.phase"), VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out is None
    assert "signal" in err


def test_reject_missing_signal():
    p = _payload(); del p["signal"]
    out, err = protocol.validate_modulation_payload(
        p, VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out is None and "signal" in err


def test_reject_unknown_filter():
    out, err = protocol.validate_modulation_payload(
        _payload(filter="not_a_real_filter"),
        VALID_SIGNALS, registry, VALID_CURVES,
    )
    assert out is None
    assert "filter" in err


def test_reject_unknown_param():
    out, err = protocol.validate_modulation_payload(
        _payload(filter="bloom", param="not_a_real_param"),
        VALID_SIGNALS, registry, VALID_CURVES,
    )
    assert out is None
    assert "param" in err


def test_reject_unknown_curve():
    out, err = protocol.validate_modulation_payload(
        _payload(curve="quantum_easing"),
        VALID_SIGNALS, registry, VALID_CURVES,
    )
    assert out is None
    assert "curve" in err


# ── clamping silencioso ──────────────────────────────────────────────


def test_smoothing_clamped_to_unit_range():
    out, _ = protocol.validate_modulation_payload(
        _payload(smoothing=5.0), VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out["smoothing"] == 1.0
    out, _ = protocol.validate_modulation_payload(
        _payload(smoothing=-0.5), VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out["smoothing"] == 0.0


def test_in_out_ranges_clamped_to_safe_bounds():
    """No deberíamos aceptar inf/nan/±1e10 — el bus se llenaría de garbage."""
    out, _ = protocol.validate_modulation_payload(
        _payload(in_max=1e20), VALID_SIGNALS, registry, VALID_CURVES
    )
    assert out["in_max"] == 1e6  # clamped


# ── persistencia round-trip ──────────────────────────────────────────


def test_modulation_json_round_trip(tmp_path: Path):
    """JSON del bridge → re-load → Modulation idéntico."""
    m = Modulation(
        signal="face.center.x", filter_id="bloom", param_id="intensity",
        in_min=0.2, in_max=0.8, out_min=0.0, out_max=1.5,
        curve="ease_in_out", smoothing=0.6, enabled=False,
    )
    file = tmp_path / "modulations.json"
    data = {"version": 1, "mappings": [m.to_dict()]}
    file.write_text(json.dumps(data, indent=2))

    loaded = json.loads(file.read_text())
    assert loaded["version"] == 1
    assert len(loaded["mappings"]) == 1
    m2 = Modulation.from_dict(loaded["mappings"][0])
    assert m == m2


def test_load_tolerates_extra_keys_in_persisted_entry():
    """Versión futura con campos extra no rompe la load (ignora extras)."""
    entry = {
        "signal": "x", "filter_id": "f", "param_id": "p",
        "future_field_v2": 42,  # ← debería ignorarse
    }
    m = Modulation.from_dict(entry)
    assert m.signal == "x"
