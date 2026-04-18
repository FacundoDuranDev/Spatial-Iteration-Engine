"""CompoundSpatialSource — combines multiple spatial sources."""

from typing import List

from ...domain.types import ROI
from ...ports.spatial import SpatialSource


class CompoundSpatialSource:
    """Combines ROIs from multiple spatial sources.

    Example: face + hands simultaneously.
    """

    name: str = "compound"

    def __init__(self) -> None:
        self._sources: List[SpatialSource] = []

    def add_source(self, source: SpatialSource) -> None:
        """Add a spatial source to the compound."""
        self._sources.append(source)

    def remove_source(self, source: SpatialSource) -> None:
        """Remove a spatial source from the compound."""
        self._sources.remove(source)

    def extract(self, analysis_data: dict) -> List[ROI]:
        rois: List[ROI] = []
        for source in self._sources:
            rois.extend(source.extract(analysis_data))
        return rois
