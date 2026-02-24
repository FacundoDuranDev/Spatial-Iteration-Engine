"""Pipelines para procesamiento de frames."""

from .analyzer_pipeline import AnalyzerPipeline
from .filter_pipeline import FilterPipeline
from .processor_pipeline import ProcessorPipeline
from .tracking_pipeline import TrackingPipeline
from .transformation_pipeline import TransformationPipeline

__all__ = [
    "ProcessorPipeline",
    "AnalyzerPipeline",
    "FilterPipeline",
    "TransformationPipeline",
    "TrackingPipeline",
]
