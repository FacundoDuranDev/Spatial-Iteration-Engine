"""Estructuras para datos de tracking de objetos."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TrajectoryPoint:
    """Punto en una trayectoria de tracking."""

    x: float
    y: float
    timestamp: float
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    """Trayectoria completa de un objeto siendo trackeado."""

    object_id: str
    label: Optional[str] = None
    points: List[TrajectoryPoint] = field(default_factory=list)
    bbox: Optional[tuple] = None  # (x, y, width, height)
    velocity: Optional[tuple] = None  # (vx, vy)
    age: int = 0  # Número de frames desde la primera detección
    lost: bool = False  # Si el objeto se perdió
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_point(self, x: float, y: float, timestamp: float, confidence: float = 1.0) -> None:
        """Agrega un punto a la trayectoria."""
        self.points.append(TrajectoryPoint(x, y, timestamp, confidence))
        self.age += 1

    def get_latest_point(self) -> Optional[TrajectoryPoint]:
        """Obtiene el punto más reciente de la trayectoria."""
        return self.points[-1] if self.points else None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la trayectoria a diccionario."""
        return {
            "object_id": self.object_id,
            "label": self.label,
            "points": [
                {
                    "x": p.x,
                    "y": p.y,
                    "timestamp": p.timestamp,
                    "confidence": p.confidence,
                    "metadata": p.metadata,
                }
                for p in self.points
            ],
            "bbox": self.bbox,
            "velocity": self.velocity,
            "age": self.age,
            "lost": self.lost,
            "metadata": self.metadata,
        }


@dataclass
class TrackingData:
    """Datos completos de tracking para un frame."""

    frame_id: str
    timestamp: float
    trajectories: Dict[str, Trajectory] = field(default_factory=dict)
    active_objects: int = 0
    lost_objects: int = 0
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_trajectory(self, trajectory: Trajectory) -> None:
        """Agrega una trayectoria al conjunto de tracking."""
        self.trajectories[trajectory.object_id] = trajectory
        if trajectory.lost:
            self.lost_objects += 1
        else:
            self.active_objects += 1

    def get_trajectory(self, object_id: str) -> Optional[Trajectory]:
        """Obtiene una trayectoria por ID."""
        return self.trajectories.get(object_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte los datos de tracking a diccionario."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "trajectories": {obj_id: traj.to_dict() for obj_id, traj in self.trajectories.items()},
            "active_objects": self.active_objects,
            "lost_objects": self.lost_objects,
            "processing_time": self.processing_time,
            "metadata": self.metadata,
        }
