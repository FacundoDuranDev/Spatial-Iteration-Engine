"""ManualRegionSource — user-defined fixed ROIs."""

from typing import List

from ...domain.types import ROI


class ManualRegionSource:
    """Provides manually set ROIs, ignoring analysis data.

    Use set_region() for a single region or set_regions() for multiple.
    """

    name: str = "manual"

    def __init__(self) -> None:
        self._regions: List[ROI] = []

    def set_region(self, x: float, y: float, w: float, h: float, label: str = "") -> None:
        """Set a single region, replacing any existing regions."""
        self._regions = [ROI(x=x, y=y, w=w, h=h, confidence=1.0, label=label)]

    def set_regions(self, regions: List[ROI]) -> None:
        """Set multiple regions, replacing any existing regions."""
        self._regions = list(regions)

    def clear(self) -> None:
        """Remove all regions."""
        self._regions = []

    def extract(self, analysis_data: dict) -> List[ROI]:
        return list(self._regions)
