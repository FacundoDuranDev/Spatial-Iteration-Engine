"""Tests for the filter registry and serialization utilities."""

import pytest

from ascii_stream_engine.adapters.processors.filters import (
    ALL_FILTERS,
    BaseFilter,
    BloomFilter,
    ChromaticAberrationFilter,
    deserialize_filter,
    get_filter_params,
    serialize_filter,
    set_filter_params,
)


class TestAllFiltersRegistry:
    def test_registry_is_populated(self):
        assert len(ALL_FILTERS) > 0

    def test_registry_contains_known_filters(self):
        expected = {"bloom", "chromatic_aberration", "brightness", "edges", "invert"}
        for name in expected:
            assert name in ALL_FILTERS, f"Missing filter: {name}"

    def test_all_values_are_base_filter_subclasses(self):
        for name, cls in ALL_FILTERS.items():
            assert issubclass(cls, BaseFilter), f"{name} -> {cls} is not a BaseFilter"

    def test_registry_excludes_base_filter(self):
        assert BaseFilter not in ALL_FILTERS.values()


class TestGetFilterParams:
    def test_bloom_params(self):
        f = BloomFilter(threshold=180, blur_size=21, intensity=0.8)
        params = get_filter_params(f)
        assert params["threshold"] == 180
        assert params["blur_size"] == 21
        assert params["intensity"] == 0.8

    def test_chromatic_aberration_params(self):
        f = ChromaticAberrationFilter(strength=5.0, center_x=0.3)
        params = get_filter_params(f)
        assert params["strength"] == 5.0
        assert params["center_x"] == 0.3
        assert "radial" in params


class TestSetFilterParams:
    def test_set_params_updates_attributes(self):
        f = BloomFilter()
        set_filter_params(f, {"threshold": 150, "intensity": 0.4})
        assert f._threshold == 150
        assert f._intensity == 0.4

    def test_set_ignores_unknown_params(self):
        f = BloomFilter()
        set_filter_params(f, {"nonexistent": 42})
        assert not hasattr(f, "_nonexistent")


class TestSerializeDeserialize:
    def test_round_trip_bloom(self):
        original = BloomFilter(threshold=190, blur_size=25, intensity=0.7)
        original.enabled = False
        data = serialize_filter(original)
        restored = deserialize_filter(data)
        assert restored.name == "bloom"
        assert restored._threshold == 190
        assert restored._blur_size == 25
        assert restored._intensity == 0.7
        assert restored.enabled is False

    def test_round_trip_chromatic_aberration(self):
        original = ChromaticAberrationFilter(strength=6.0, radial=False)
        data = serialize_filter(original)
        restored = deserialize_filter(data)
        assert restored._strength == 6.0
        assert restored._radial is False

    def test_deserialize_unknown_filter_raises(self):
        with pytest.raises(KeyError, match="Unknown filter"):
            deserialize_filter({"name": "nonexistent_filter_xyz"})

    def test_all_filters_can_round_trip(self):
        """Every registered filter must survive serialize -> deserialize."""
        for name, cls in ALL_FILTERS.items():
            try:
                instance = cls()
            except TypeError:
                continue  # Skip filters with required args
            data = serialize_filter(instance)
            restored = deserialize_filter(data)
            assert restored.name == name
            assert type(restored) is cls
