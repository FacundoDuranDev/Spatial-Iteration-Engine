"""Phase D · web_dashboard tests.

Decision #9: small set of focused tests that cover the security-critical
guardrails (op whitelist, value clamping, registry lookups). The full
end-to-end nav flow is exercised by the Playwright snap_v3_nav.py tool —
not pytest, because it needs a real engine + camera.
"""
from __future__ import annotations

import pytest

from ascii_stream_engine.adapters.outputs.web_dashboard import protocol, registry


# ── protocol.is_allowed_op ────────────────────────────────────────────


@pytest.mark.parametrize(
    "op,expected",
    [
        ("start", True),
        ("stop", True),
        ("toggle_filter", True),
        ("set_param", True),
        ("pong", True),
        ("flubber", False),
        ("", False),
        (None, False),
        (123, False),
        (["start"], False),
    ],
)
def test_is_allowed_op(op, expected):
    assert protocol.is_allowed_op(op) is expected


# ── protocol.clamp_float ──────────────────────────────────────────────


def test_clamp_float_in_range():
    assert protocol.clamp_float(0.5, 0.0, 1.0) == 0.5


def test_clamp_float_below_min():
    assert protocol.clamp_float(-5.0, 0.0, 1.0) == 0.0


def test_clamp_float_above_max():
    assert protocol.clamp_float(99.0, 0.0, 1.0) == 1.0


def test_clamp_float_bad_input_returns_default():
    assert protocol.clamp_float("not a number", 0.0, 1.0, default=0.42) == 0.42


def test_clamp_float_string_number_coerces():
    assert protocol.clamp_float("0.7", 0.0, 1.0) == 0.7


# ── protocol.clamp_int ────────────────────────────────────────────────


def test_clamp_int_snaps_to_step():
    # step=5, value=7.6 → snaps to 10
    assert protocol.clamp_int(7.6, 0, 100, step=5) == 10


def test_clamp_int_bad_returns_default():
    assert protocol.clamp_int(None, 0, 60, step=2, default=30) == 30


def test_clamp_int_clamps_within_bounds():
    assert protocol.clamp_int(1000, 0, 60, step=2) == 60
    assert protocol.clamp_int(-5, 0, 60, step=2) == 0


# ── protocol.coerce_bool ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("false", False),
        ("0", False),
        ("yes", True),  # any non-falsy string
        ("", False),
        (None, False),
    ],
)
def test_coerce_bool(raw, expected):
    assert protocol.coerce_bool(raw) is expected


# ── registry helpers ──────────────────────────────────────────────────


def test_registry_has_at_least_42_filters():
    # 44 wired minus the 2 redundant slit/chrono filters that were
    # collapsed into TemporalScan. Update this number consciously
    # when adding or removing filters; do not remove the test.
    assert len(registry.FILTERS) >= 42


def test_redundant_scan_filters_unregistered():
    # ChronoScanFilter + SlitScanFilter are explicitly NOT in the v3
    # registry — they were folded into TemporalScan. If you add them
    # back, justify it in the registry comment block.
    ids = {f["id"] for f in registry.FILTERS}
    assert "chrono_scan" not in ids
    assert "slit_scan" not in ids


def test_registry_core_filters_still_present():
    ids = {f["id"] for f in registry.FILTERS}
    for required in ("temporal_scan", "bc_cpp", "bloom", "chroma", "invert"):
        assert required in ids, f"core filter {required} missing"


def test_registry_ids_unique():
    ids = [f["id"] for f in registry.FILTERS]
    assert len(ids) == len(set(ids)), "duplicate filter ids in FILTERS"


def test_registry_has_4_categories():
    cat_ids = {c["id"] for c in registry.CATEGORIES}
    assert cat_ids == {"DISTORT", "COLOR", "GLITCH", "STYLIZE"}


def test_wired_filters_have_factory():
    # All 5 filters are now wired (chroma + invert promoted out of WIP).
    for fid in ("temporal_scan", "bc_cpp", "bloom", "chroma", "invert"):
        spec = registry.find_filter(fid)
        assert spec is not None
        assert spec.get("wip") is False
        assert callable(spec.get("factory"))


def test_no_filters_left_as_wip():
    # If you re-introduce a WIP stub, update this test consciously.
    wip = [f["id"] for f in registry.FILTERS if f.get("wip")]
    assert wip == [], f"unexpected WIP filters: {wip}"


def test_find_filter_unknown_returns_none():
    assert registry.find_filter("ghost") is None


def test_find_param_returns_dict_for_known():
    p = registry.find_param("bloom", "intensity")
    assert p is not None
    assert p["kind"] == "slider"
    assert p["min"] == 0.0
    assert p["max"] == 1.0


def test_find_param_unknown_returns_none():
    assert registry.find_param("bloom", "ghost_param") is None
    assert registry.find_param("ghost_filter", "intensity") is None


def test_default_params_returns_id_to_default_map():
    defaults = registry.default_params("bloom")
    assert defaults == {"intensity": 0.6, "threshold": 200, "audio_react": 1.0}


def test_default_params_invert_returns_empty():
    # Invert is wired but parameter-less (only the enabled toggle).
    assert registry.default_params("invert") == {}


def test_default_params_unknown_returns_empty():
    assert registry.default_params("ghost") == {}


# ── registry param spec sanity ────────────────────────────────────────


def test_every_wired_param_has_required_keys():
    required = {"id", "kind", "default", "label", "apply"}
    for spec in registry.FILTERS:
        if spec.get("wip"):
            continue
        for p in spec["params"]:
            missing = required - set(p)
            assert not missing, f"{spec['id']}.{p.get('id')} missing {missing}"


def test_slider_and_stepper_params_have_min_max_step():
    for spec in registry.FILTERS:
        if spec.get("wip"):
            continue
        for p in spec["params"]:
            if p["kind"] in ("slider", "stepper", "angle"):
                assert "min" in p, f"{spec['id']}.{p['id']} missing min"
                assert "max" in p, f"{spec['id']}.{p['id']} missing max"
                if p["kind"] != "angle":
                    assert "step" in p, f"{spec['id']}.{p['id']} missing step"


def test_select_params_have_options():
    for spec in registry.FILTERS:
        if spec.get("wip"):
            continue
        for p in spec["params"]:
            if p["kind"] == "select":
                assert isinstance(p.get("options"), list)
                assert p["default"] in p["options"]
