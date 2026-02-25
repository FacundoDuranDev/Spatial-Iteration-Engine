"""Estructuras tipadas para resultados de análisis."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Detection:
    """Resultado de detección de un objeto."""

    label: str
    confidence: float
    bbox: tuple  # (x, y, width, height)
    class_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Resultado completo de análisis de un frame."""

    analyzer_name: str
    detections: List[Detection] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    timestamp: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el resultado a diccionario."""
        return {
            "analyzer_name": self.analyzer_name,
            "detections": [
                {
                    "label": d.label,
                    "confidence": d.confidence,
                    "bbox": d.bbox,
                    "class_id": d.class_id,
                    "metadata": d.metadata,
                }
                for d in self.detections
            ],
            "raw_data": self.raw_data,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message,
        }
