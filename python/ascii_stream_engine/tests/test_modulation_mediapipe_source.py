"""Tests para MediaPipeSignalSource — analysis dict → señales del bus."""
from __future__ import annotations

import math

import numpy as np
import pytest

from ascii_stream_engine.application.modulation import (
    MediaPipeSignalSource,
    SignalBus,
    SignalSource,
)


@pytest.fixture
def bus() -> SignalBus:
    return SignalBus()


@pytest.fixture
def src() -> MediaPipeSignalSource:
    return MediaPipeSignalSource()


# ── Protocol contract ────────────────────────────────────────────────


def test_satisfies_signal_source_protocol(src):
    assert isinstance(src, SignalSource)


def test_declared_signals_is_static_and_returns_15():
    declared = MediaPipeSignalSource.declared_signals()
    assert isinstance(declared, list)
    assert len(declared) == 15
    # Tiene que devolver una copia — modificarla no rompe el catálogo.
    declared.append("intruder")
    assert "intruder" not in MediaPipeSignalSource.declared_signals()


def test_declared_signals_use_dotted_namespace(src):
    declared = src.declared_signals()
    for name in declared:
        assert "." in name, f"{name!r} no usa namespace dotted"
        head = name.split(".")[0]
        assert head in {"face", "hands"}, f"{name!r} fuera de namespace conocido"


# ── face.* ────────────────────────────────────────────────────────────


def test_publish_with_no_face_publishes_count_zero(src, bus):
    src.publish({"face": {"faces": []}}, bus)
    assert bus.get("face.count") == 0.0
    assert not bus.has("face.center.x")  # no hay cara → no se publica el resto


def test_publish_face_center_and_scale(src, bus):
    analysis = {
        "face": {
            "faces": [{"bbox": [0.2, 0.3, 0.4, 0.5], "confidence": 0.9}],
        }
    }
    src.publish(analysis, bus)
    assert bus.get("face.count") == 1.0
    assert bus.get("face.center.x") == pytest.approx(0.4)  # 0.2 + 0.4/2
    assert bus.get("face.center.y") == pytest.approx(0.55)  # 0.3 + 0.5/2
    assert bus.get("face.bbox.scale") == pytest.approx(0.5)  # max(w, h)
    assert bus.get("face.confidence") == pytest.approx(0.9)


def test_face_uses_first_detected(src, bus):
    """Cuando hay varias caras, el sujeto = la primera (asumimos orden de
    confidence desc del detector)."""
    analysis = {
        "face": {
            "faces": [
                {"bbox": [0.1, 0.1, 0.2, 0.2], "confidence": 0.99},
                {"bbox": [0.7, 0.7, 0.1, 0.1], "confidence": 0.5},
            ]
        }
    }
    src.publish(analysis, bus)
    assert bus.get("face.count") == 2.0
    assert bus.get("face.center.x") == pytest.approx(0.2)  # primera cara


# ── hands.* ───────────────────────────────────────────────────────────


def _hand21(palm_xy=(0.5, 0.5), tip_xy=(0.6, 0.4)) -> np.ndarray:
    """Construye un ndarray(21, 2) con palm[0] y tip_index[8] dados, resto cero."""
    arr = np.zeros((21, 2), dtype=np.float32)
    arr[0] = palm_xy
    arr[8] = tip_xy
    return arr


def test_hands_count_zero_when_no_hands(src, bus):
    src.publish({"hands": {"left": None, "right": None}}, bus)
    assert bus.get("hands.count") == 0.0


def test_hands_publishes_left_only(src, bus):
    src.publish({"hands": {"left": _hand21((0.3, 0.7), (0.35, 0.65)), "right": None}}, bus)
    assert bus.get("hands.count") == 1.0
    assert bus.get("hands.left.palm.x") == pytest.approx(0.3)
    assert bus.get("hands.left.palm.y") == pytest.approx(0.7)
    assert bus.get("hands.left.tip_index.x") == pytest.approx(0.35)
    assert bus.get("hands.left.tip_index.y") == pytest.approx(0.65)
    # right NO se publica
    assert not bus.has("hands.right.palm.x")
    # distance NO se publica si solo hay una mano
    assert not bus.has("hands.distance")


def test_hands_distance_when_both_present(src, bus):
    left = _hand21((0.2, 0.5), (0.25, 0.45))
    right = _hand21((0.8, 0.5), (0.75, 0.45))
    src.publish({"hands": {"left": left, "right": right}}, bus)
    assert bus.get("hands.count") == 2.0
    # Distancia palm a palm: hypot(0.6, 0)
    assert bus.get("hands.distance") == pytest.approx(0.6)


def test_hands_distance_diagonal(src, bus):
    left = _hand21((0.0, 0.0))
    right = _hand21((0.3, 0.4))
    src.publish({"hands": {"left": left, "right": right}}, bus)
    assert bus.get("hands.distance") == pytest.approx(math.hypot(0.3, 0.4))


def test_empty_ndarray_treated_as_no_hand(src, bus):
    """Algunas runs de MediaPipe devuelven array vacío en vez de None."""
    src.publish({"hands": {"left": np.zeros((0, 2)), "right": _hand21()}}, bus)
    assert bus.get("hands.count") == 1.0
    assert not bus.has("hands.left.palm.x")
    assert bus.has("hands.right.palm.x")


# ── freeze-on-lost integration ────────────────────────────────────────


def test_freeze_on_lost_keeps_last_value(src, bus):
    """Si la mano desaparece este frame, su última posición queda en el bus."""
    # Frame 1: ambas manos
    src.publish({"hands": {"left": _hand21((0.4, 0.6)), "right": _hand21((0.7, 0.3))}}, bus)
    assert bus.get("hands.right.palm.x") == pytest.approx(0.7)
    # Frame 2: derecha desaparece (MediaPipe perdió tracking)
    src.publish({"hands": {"left": _hand21((0.4, 0.6)), "right": None}}, bus)
    # La derecha NO se reescribe → último valor queda
    assert bus.get("hands.right.palm.x") == pytest.approx(0.7)
    assert bus.get("hands.count") == 1.0  # pero el contador SÍ refleja la realidad


# ── robustez ─────────────────────────────────────────────────────────


def test_publish_empty_analysis_is_safe(src, bus):
    """analysis={} (analyzer NO corrió) → freeze-on-lost: nada se publica."""
    src.publish({}, bus)
    assert bus.snapshot() == {}


def test_publish_hands_present_but_empty_publishes_zero_count(src, bus):
    """hands presente con dict vacío (analyzer corrió, vio 0 manos) → count=0."""
    src.publish({"hands": {}}, bus)
    assert bus.get("hands.count") == 0.0
    assert not bus.has("face.count")  # face no estaba en el dict


def test_publish_garbage_analysis_is_safe(src, bus):
    src.publish({"face": "not a dict", "hands": 42}, bus)
    assert bus.snapshot() == {}


def test_publish_missing_bbox_is_safe(src, bus):
    """face sin bbox válido — debería publicar count pero no center."""
    src.publish({"face": {"faces": [{"confidence": 0.5}]}}, bus)
    assert bus.get("face.count") == 1.0
    assert bus.get("face.confidence") == pytest.approx(0.5)
    assert not bus.has("face.center.x")
