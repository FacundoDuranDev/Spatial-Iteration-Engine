"""SpatialMapNode — converts analysis data to spatial masks and control signals."""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType
from ....domain.types import ROI
from ....ports.spatial import SpatialSource


class SpatialMapNode(BaseNode):
    """Receives video + analysis, delegates to a SpatialSource strategy,
    and produces masks, control signals, and optional ROI crops.

    The source strategy can be swapped at runtime via set_source()
    without rebuilding the graph.

    Inputs:
        video_in (VIDEO_FRAME, required): Source frame for mask/crop generation
        analysis_in (ANALYSIS_DATA, required): Analysis dict from upstream analyzers
        region_in (CONTROL_SIGNAL, optional): Override ROI from interactive input

    Outputs:
        video_out (VIDEO_FRAME): Passthrough of input frame
        mask_out (MASK): Binary mask (255 inside ROI, 0 outside), optional Gaussian blur
        control_out (CONTROL_SIGNAL): Dict with center, size, confidence, detected flag
        roi_video_out (VIDEO_FRAME): Cropped ROI region resized to original frame size
    """

    name = "spatial_map"

    def __init__(
        self,
        source: Optional[SpatialSource] = None,
        roi_index: int = 0,
        blur_mask: bool = False,
        blur_radius: int = 21,
        produce_crop: bool = False,
        resize_crop: bool = True,
    ) -> None:
        super().__init__()
        self._source = source
        self._roi_index = roi_index
        self._blur_mask = blur_mask
        self._blur_radius = blur_radius | 1  # must be odd
        self._produce_crop = produce_crop
        self._resize_crop = resize_crop

    @property
    def source(self) -> Optional[SpatialSource]:
        return self._source

    def set_source(self, source: SpatialSource) -> None:
        """Swap the spatial source strategy at runtime."""
        self._source = source

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in", PortType.VIDEO_FRAME),
            InputPort("analysis_in", PortType.ANALYSIS_DATA),
            InputPort("region_in", PortType.CONTROL_SIGNAL, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("mask_out", PortType.MASK),
            OutputPort("control_out", PortType.CONTROL_SIGNAL),
            OutputPort("roi_video_out", PortType.VIDEO_FRAME),
        ]

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        analysis = inputs.get("analysis_in", {})
        region_override = inputs.get("region_in")

        h, w = frame.shape[:2]

        # Extract ROIs
        roi = self._resolve_roi(analysis, region_override)

        # Generate outputs
        mask = self._generate_mask(h, w, roi)
        control = self._generate_control(roi)
        crop = self._generate_crop(frame, h, w, roi) if self._produce_crop else frame

        return {
            "video_out": frame,
            "mask_out": mask,
            "control_out": control,
            "roi_video_out": crop,
        }

    def _resolve_roi(self, analysis: dict, region_override: Any) -> Optional[ROI]:
        """Get the active ROI from override, source, or None."""
        # Interactive override takes precedence
        if region_override is not None and isinstance(region_override, dict):
            x = float(region_override.get("x", 0))
            y = float(region_override.get("y", 0))
            rw = float(region_override.get("w", 0))
            rh = float(region_override.get("h", 0))
            if rw > 0 and rh > 0:
                return ROI(x=x, y=y, w=rw, h=rh)

        if self._source is None:
            return None

        rois = self._source.extract(analysis)
        if not rois or self._roi_index >= len(rois):
            return None
        return rois[self._roi_index]

    def _generate_mask(self, h: int, w: int, roi: Optional[ROI]) -> np.ndarray:
        """Generate binary mask for the ROI."""
        mask = np.zeros((h, w), dtype=np.uint8)
        if roi is None:
            return mask

        x1, y1, x2, y2 = roi.to_pixel_rect(h, w)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255

        if self._blur_mask and self._blur_radius > 1:
            mask = cv2.GaussianBlur(mask, (self._blur_radius, self._blur_radius), 0)

        return mask

    def _generate_control(self, roi: Optional[ROI]) -> dict:
        """Generate control signal dict from ROI."""
        if roi is None:
            return {
                "center_x": 0.5,
                "center_y": 0.5,
                "width": 0.0,
                "height": 0.0,
                "area": 0.0,
                "confidence": 0.0,
                "detected": False,
            }
        cx, cy = roi.center
        return {
            "center_x": cx,
            "center_y": cy,
            "width": roi.w,
            "height": roi.h,
            "area": roi.area,
            "confidence": roi.confidence,
            "detected": True,
        }

    def _generate_crop(
        self, frame: np.ndarray, h: int, w: int, roi: Optional[ROI]
    ) -> np.ndarray:
        """Crop the ROI region, optionally resizing to original frame dimensions."""
        if roi is None:
            return frame

        x1, y1, x2, y2 = roi.to_pixel_rect(h, w)
        if x2 <= x1 or y2 <= y1:
            return frame

        crop = frame[y1:y2, x1:x2].copy()
        if self._resize_crop:
            return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
        return crop
