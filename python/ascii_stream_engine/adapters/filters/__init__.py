"""Módulo de filtros - DEPRECADO.

Este módulo se mantiene solo para compatibilidad hacia atrás.
Los filtros se han movido a adapters/processors/filters/.

Por favor, actualiza tus imports:
- from ascii_stream_engine.adapters.processors import BrightnessFilter, InvertFilter, ...
"""

import warnings

from ..processors.filters import (
    BaseFilter,
    BrightnessFilter,
    DetailBoostFilter,
    EdgeFilter,
    InvertFilter,
)

warnings.warn(
    "Importar desde adapters.filters está deprecado. "
    "Usa 'from ascii_stream_engine.adapters.processors import ...' en su lugar.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BaseFilter",
    "BrightnessFilter",
    "DetailBoostFilter",
    "EdgeFilter",
    "InvertFilter",
]

