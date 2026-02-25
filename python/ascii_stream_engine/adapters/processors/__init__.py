"""Procesadores de frames (filters y analyzers)."""

# Re-exportar desde subdirectorios para mantener compatibilidad
from .analyzers import BaseAnalyzer, FaceHaarAnalyzer
from .filters import (
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
]
