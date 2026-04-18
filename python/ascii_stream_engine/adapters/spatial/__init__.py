"""Spatial source adapters — extract ROIs from various analysis data."""

from .compound_source import CompoundSpatialSource
from .face_source import FaceSpatialSource
from .hand_frame_source import HandFrameSpatialSource
from .hands_source import HandsSpatialSource
from .manual_source import ManualRegionSource
from .object_source import ObjectSpatialSource
from .pose_source import PoseSpatialSource

__all__ = [
    "FaceSpatialSource",
    "HandFrameSpatialSource",
    "HandsSpatialSource",
    "PoseSpatialSource",
    "ObjectSpatialSource",
    "ManualRegionSource",
    "CompoundSpatialSource",
]
