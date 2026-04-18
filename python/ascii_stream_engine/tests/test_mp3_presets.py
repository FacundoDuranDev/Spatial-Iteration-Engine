"""Tests for Max Payne 3 preset loading and filter deserialization."""

import json
import os

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters import (
    ALL_FILTERS,
    deserialize_filter,
    serialize_filter,
)
from ascii_stream_engine.domain.config import EngineConfig


# Find project root (contains data/ directory).
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_TEST_DIR, "..", "..", ".."))
PRESETS_PATH = os.path.join(_PROJECT_ROOT, "data", "presets", "mp3_presets.json")


@pytest.fixture
def mp3_presets():
    with open(PRESETS_PATH) as f:
        return json.load(f)


class TestMP3PresetsFile:
    def test_file_exists(self):
        assert os.path.isfile(PRESETS_PATH), f"Preset file not found: {PRESETS_PATH}"

    def test_is_valid_json(self):
        with open(PRESETS_PATH) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 5

    def test_preset_names(self, mp3_presets):
        names = {p["name"] for p in mp3_presets}
        expected = {"Favela Sun", "Drunk Bar", "Bullet Time", "Trauma Flash", "Noir Flashback"}
        assert names == expected


class TestPresetFilterDiscovery:
    def test_all_filter_names_exist_in_registry(self, mp3_presets):
        for preset in mp3_presets:
            for fc in preset["filter_configs"]:
                assert fc["name"] in ALL_FILTERS, (
                    f"Preset '{preset['name']}' references unknown filter: {fc['name']}"
                )

    def test_all_filters_deserialize(self, mp3_presets):
        for preset in mp3_presets:
            for fc in preset["filter_configs"]:
                instance = deserialize_filter(fc)
                assert instance.name == fc["name"]
                assert instance.enabled == fc.get("enabled", True)


class TestPresetRoundTrip:
    def test_serialize_deserialize_round_trip(self, mp3_presets):
        for preset in mp3_presets:
            for fc in preset["filter_configs"]:
                instance = deserialize_filter(fc)
                data = serialize_filter(instance)
                restored = deserialize_filter(data)
                assert restored.name == instance.name
                assert type(restored) is type(instance)


class TestPresetFilterExecution:
    def test_all_preset_filters_process_frame(self, mp3_presets):
        """Every filter from every preset should process a frame without error."""
        config = EngineConfig()
        frame = np.full((240, 320, 3), 120, dtype=np.uint8)
        frame[100:140, 140:180] = 250  # Bright spot for bloom/flare.

        for preset in mp3_presets:
            for fc in preset["filter_configs"]:
                instance = deserialize_filter(fc)
                result = instance.apply(frame, config)
                assert result.shape == frame.shape, (
                    f"Filter {fc['name']} in preset '{preset['name']}' broke shape"
                )
                assert result.dtype == np.uint8
