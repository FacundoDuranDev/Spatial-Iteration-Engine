"""SpatialSource protocol — extracts ROIs from analysis data."""

from typing import List

from typing_extensions import Protocol, runtime_checkable

from ..domain.types import ROI


@runtime_checkable
class SpatialSource(Protocol):
    """Strategy that extracts regions of interest from analysis data.

    Implementations receive the full analysis dict (keyed by analyzer name)
    and return a list of ROIs in normalized 0-1 coordinates.
    """

    name: str

    def extract(self, analysis_data: dict) -> List[ROI]:
        """Extract ROIs from analysis data.

        Args:
            analysis_data: Dict keyed by analyzer name, e.g.
                {"face": {...}, "hands": {...}}

        Returns:
            List of ROI objects in normalized coordinates.
        """
        ...
