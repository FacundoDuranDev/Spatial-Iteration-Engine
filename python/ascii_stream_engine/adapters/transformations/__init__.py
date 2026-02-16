"""Módulo de transformaciones espaciales."""

from .base import BaseSpatialTransform
from .blend_transformer import BlendTransformer
from .projection_mapper import ProjectionMapper
# TransformationPipeline se ha movido a application.pipeline
# Mantener import para compatibilidad hacia atrás
import warnings

try:
    from ...application.pipeline import TransformationPipeline
except ImportError:
    # Fallback al archivo local si no está disponible en application
    from .transformation_pipeline import TransformationPipeline
    warnings.warn(
        "Importar TransformationPipeline desde adapters.transformations está deprecado. "
        "Usa 'from ascii_stream_engine.application.pipeline import TransformationPipeline'.",
        DeprecationWarning,
        stacklevel=2,
    )
from .warp_transformer import WarpTransformer

__all__ = [
    "BaseSpatialTransform",
    "ProjectionMapper",
    "WarpTransformer",
    "BlendTransformer",
    "TransformationPipeline",
]

