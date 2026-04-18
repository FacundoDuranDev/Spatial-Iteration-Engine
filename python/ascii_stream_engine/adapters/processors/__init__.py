"""Procesadores de frames (filters y analyzers)."""

# Re-exportar desde subdirectorios para mantener compatibilidad
from .analyzers import BaseAnalyzer, FaceHaarAnalyzer
from .filters import (
    ALL_FILTERS,
    BaseFilter,
    BrightnessFilter,
    CppBrightnessContrastFilter,
    CppChannelSwapFilter,
    CppGrayscaleFilter,
    CppImageModifierFilter,
    CppInvertFilter,
    DetailBoostFilter,
    EdgeFilter,
    InvertFilter,
    deserialize_filter,
    get_filter_params,
    serialize_filter,
    set_filter_params,
)

__all__ = [
    # Analyzers
    "BaseAnalyzer",
    "FaceHaarAnalyzer",
    # Filters
    "BaseFilter",
    "BrightnessFilter",
    "CppBrightnessContrastFilter",
    "CppChannelSwapFilter",
    "CppGrayscaleFilter",
    "CppImageModifierFilter",
    "CppInvertFilter",
    "DetailBoostFilter",
    "EdgeFilter",
    "InvertFilter",
    # Registry utilities
    "ALL_FILTERS",
    "get_filter_params",
    "set_filter_params",
    "serialize_filter",
    "deserialize_filter",
]
