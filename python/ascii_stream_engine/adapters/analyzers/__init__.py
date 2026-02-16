"""Módulo de analizadores - DEPRECADO.

Este módulo se mantiene solo para compatibilidad hacia atrás.
Los analizadores se han movido a adapters/processors/analyzers/.

Por favor, actualiza tus imports:
- from ascii_stream_engine.adapters.processors import BaseAnalyzer, FaceHaarAnalyzer
"""

import warnings

from ..processors.analyzers import BaseAnalyzer, FaceHaarAnalyzer

warnings.warn(
    "Importar desde adapters.analyzers está deprecado. "
    "Usa 'from ascii_stream_engine.adapters.processors import ...' en su lugar.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["BaseAnalyzer", "FaceHaarAnalyzer"]

