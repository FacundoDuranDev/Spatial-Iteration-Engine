"""Definición de eventos del sistema para comunicación desacoplada entre módulos."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass(kw_only=True)
class BaseEvent:
    """Evento base con timestamp y metadata común."""

    timestamp: float = field(default_factory=time.time)
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class FrameCapturedEvent(BaseEvent):
    """Evento emitido cuando se captura un frame de la fuente."""

    frame: np.ndarray
    frame_id: str


@dataclass(kw_only=True)
class AnalysisCompleteEvent(BaseEvent):
    """Evento emitido cuando se completa el análisis de un frame."""

    frame_id: str
    results: Dict[str, Any]
    analysis_time: float = 0.0


@dataclass(kw_only=True)
class FilterAppliedEvent(BaseEvent):
    """Evento emitido cuando se aplica un filtro."""

    frame_id: str
    filter_name: str
    filter_time: float = 0.0


@dataclass(kw_only=True)
class RenderCompleteEvent(BaseEvent):
    """Evento emitido cuando se completa el renderizado de un frame."""

    frame_id: str
    render_time: float = 0.0
    output_size: Optional[tuple] = None


@dataclass(kw_only=True)
class FrameWrittenEvent(BaseEvent):
    """Evento emitido cuando se escribe un frame al output."""

    frame_id: str
    write_time: float = 0.0


@dataclass(kw_only=True)
class TrackingEvent(BaseEvent):
    """Evento emitido cuando se actualiza el tracking de objetos."""

    frame_id: str
    trajectories: Dict[str, Any]
    tracked_objects: int = 0


@dataclass(kw_only=True)
class SensorEvent(BaseEvent):
    """Evento emitido cuando un sensor lee nuevos datos."""

    sensor_name: str
    sensor_data: Dict[str, Any]
    sensor_type: str = "generic"


@dataclass(kw_only=True)
class ControlEvent(BaseEvent):
    """Evento emitido cuando se recibe un comando de control externo (MIDI/OSC)."""

    controller_name: str
    command: str
    params: Dict[str, Any]
    value: Optional[Any] = None


@dataclass(kw_only=True)
class ConfigChangeEvent(BaseEvent):
    """Evento emitido cuando cambia la configuración del engine."""

    changed_params: Dict[str, Any]
    old_values: Dict[str, Any]


@dataclass(kw_only=True)
class ErrorEvent(BaseEvent):
    """Evento emitido cuando ocurre un error en algún módulo."""

    error_type: str
    error_message: str
    module_name: str
    exception: Optional[Exception] = None
