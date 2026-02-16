"""Re-export de TrackingPipeline desde application.pipeline.

La implementación única está en ascii_stream_engine.application.pipeline.
Preferir: from ascii_stream_engine.application.pipeline import TrackingPipeline
"""

from ...application.pipeline import TrackingPipeline

__all__ = ["TrackingPipeline"]
