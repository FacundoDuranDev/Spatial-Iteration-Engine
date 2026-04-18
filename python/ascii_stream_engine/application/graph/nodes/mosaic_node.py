"""MosaicFilterNode — standalone graph node for pixelation with control signal input."""

from typing import Any, Dict, List

import cv2
import numpy as np

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class MosaicFilterNode(BaseNode):
    """Pixelates a video frame into a mosaic block grid.

    Standalone graph node (not wrapping the adapter) with a CONTROL_SIGNAL
    input for dynamic block_size control.

    Inputs:
        video_in: Video frame (required)
        block_size: Optional control signal (float 0.01-0.3, default 0.05)

    Output:
        video_out: Pixelated frame
    """

    name = "mosaic_filter"

    def __init__(self, default_block_size: float = 0.05) -> None:
        super().__init__()
        self._default_block_size = max(0.01, min(0.3, default_block_size))

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in", PortType.VIDEO_FRAME),
            InputPort("block_size", PortType.CONTROL_SIGNAL, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        block_size = inputs.get("block_size", self._default_block_size)
        if block_size is None:
            block_size = self._default_block_size
        block_size = float(max(0.01, min(0.3, block_size)))

        h, w = frame.shape[:2]
        min_dim = min(h, w)
        block_px = max(2, int(min_dim * block_size))

        small_w = max(1, w // block_px)
        small_h = max(1, h // block_px)

        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        result = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        return {"video_out": result}
