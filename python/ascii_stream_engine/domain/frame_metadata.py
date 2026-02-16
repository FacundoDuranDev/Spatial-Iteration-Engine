"""Metadata extendida para frames con información de tracking y análisis."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class FrameMetadata:
    """Metadata completa para un frame con información de procesamiento."""

    frame_id: str
    timestamp: float
    source_id: Optional[str] = None
    frame_shape: Optional[tuple] = None
    frame_dtype: Optional[np.dtype] = None
    processing_time: float = 0.0
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    tracking_data: Dict[str, Any] = field(default_factory=dict)
    sensor_data: Dict[str, Any] = field(default_factory=dict)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la metadata a diccionario."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "source_id": self.source_id,
            "frame_shape": self.frame_shape,
            "frame_dtype": str(self.frame_dtype) if self.frame_dtype else None,
            "processing_time": self.processing_time,
            "analysis_results": self.analysis_results,
            "tracking_data": self.tracking_data,
            "sensor_data": self.sensor_data,
            "custom_metadata": self.custom_metadata,
        }

