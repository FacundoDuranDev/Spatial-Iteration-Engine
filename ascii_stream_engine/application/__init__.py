from .engine import StreamEngine
from .pipeline import AnalyzerPipeline, FilterPipeline

# Intentar importar TrackingPipeline si está disponible
try:
    from ..adapters.trackers import TrackingPipeline
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False

__all__ = ["StreamEngine", "AnalyzerPipeline", "FilterPipeline"]

if TRACKING_AVAILABLE:
    __all__.append("TrackingPipeline")
