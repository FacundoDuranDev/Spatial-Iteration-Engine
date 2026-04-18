"""Tests for Gradio dashboard helpers (does not require Gradio installed)."""

import numpy as np
import pytest

from ascii_stream_engine.adapters.processors.filters import BloomFilter
from ascii_stream_engine.presentation.gradio_helpers import (
    MP3_CHAIN_ORDER,
    load_mp3_presets,
    order_mp3_filters,
)


class TestOrderMP3Filters:
    def test_correct_ordering(self):
        from ascii_stream_engine.adapters.processors.filters import (
            ColorGradingFilter,
            FilmGrainFilter,
            MotionBlurFilter,
            VignetteFilter,
        )

        filters = [
            VignetteFilter(),
            ColorGradingFilter(),
            MotionBlurFilter(),
            FilmGrainFilter(),
        ]
        ordered = order_mp3_filters(filters)
        names = [f.name for f in ordered]
        assert names.index("motion_blur") < names.index("color_grading")
        assert names.index("color_grading") < names.index("film_grain")
        assert names.index("film_grain") < names.index("vignette")

    def test_unknown_filters_go_last(self):
        from ascii_stream_engine.adapters.processors.filters import (
            BoidsFilter,
            VignetteFilter,
        )

        filters = [BoidsFilter(), VignetteFilter()]
        ordered = order_mp3_filters(filters)
        assert ordered[-1].name == "boids"


class TestLoadMP3Presets:
    def test_loads_5_presets(self):
        presets = load_mp3_presets()
        assert len(presets) == 5

    def test_preset_structure(self):
        presets = load_mp3_presets()
        for p in presets:
            assert "name" in p
            assert "filter_configs" in p
            assert isinstance(p["filter_configs"], list)
            assert len(p["filter_configs"]) > 0


class TestMP3ChainOrder:
    def test_chain_order_has_all_mp3_filters(self):
        expected = {
            "motion_blur", "depth_of_field", "bloom_cinematic", "lens_flare",
            "color_grading", "double_vision", "chromatic_aberration",
            "radial_blur", "glitch_block", "film_grain", "vignette",
            "kinetic_typography", "panel_compositor",
        }
        assert expected.issubset(set(MP3_CHAIN_ORDER))
