"""Perception: detección de personas, pose y segmentación de silueta.

Módulos stub que implementan los ports de ascii_stream_engine (Analyzer)
para integrarse en el AnalyzerPipeline.
"""

from .person_detection import PersonDetectionAnalyzer
from .pose_estimation import PoseEstimationAnalyzer
from .silhouette_segmentation import SilhouetteSegmentationAnalyzer

__all__ = [
    "PersonDetectionAnalyzer",
    "PoseEstimationAnalyzer",
    "SilhouetteSegmentationAnalyzer",
]
