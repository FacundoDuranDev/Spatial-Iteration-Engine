"""Módulo de pipelines - DEPRECADO.

Este módulo se mantiene solo para compatibilidad hacia atrás.
Los pipelines se han movido a application/pipeline/.

Por favor, actualiza tus imports:
- from ascii_stream_engine.application.pipeline import AnalyzerPipeline, FilterPipeline
"""

import warnings

from .pipeline import AnalyzerPipeline, FilterPipeline

warnings.warn(
    "Importar desde application.pipeline está deprecado. "
    "Usa 'from ascii_stream_engine.application.pipeline import ...' en su lugar.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["AnalyzerPipeline", "FilterPipeline"]
