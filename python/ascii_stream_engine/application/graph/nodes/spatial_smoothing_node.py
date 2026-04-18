"""SpatialSmoothingNode — temporal smoothing for spatial masks and control signals.

Smooths the mask and control outputs from a SpatialMapNode over time, and holds
the last known position when detection is lost for a configurable number of frames.

This eliminates jitter in hand/face/pose tracking and provides graceful falloff
when the tracked region temporarily disappears.
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class SpatialSmoothingNode(BaseNode):
    """Temporal smoothing for spatial data (mask + control signal).

    Inputs:
        mask_in (MASK, required): Binary mask from SpatialMapNode
        control_in (CONTROL_SIGNAL, required): Control dict from SpatialMapNode
        video_in (VIDEO_FRAME, optional): Passthrough video (forwarded unchanged)

    Outputs:
        mask_out (MASK): Temporally smoothed mask
        control_out (CONTROL_SIGNAL): Temporally smoothed control signal
        video_out (VIDEO_FRAME): Passthrough video (if connected)

    Parameters:
        smoothing: EMA alpha (0=no smoothing, 1=no memory). Default 0.4.
        hold_frames: Frames to hold last position after detection is lost. Default 15.
        fade_out: If True, fade the mask opacity during hold period. Default True.
    """

    name = "spatial_smoothing"

    def __init__(
        self,
        smoothing: float = 0.4,
        hold_frames: int = 15,
        fade_out: bool = True,
    ) -> None:
        super().__init__()
        self._smoothing = smoothing
        self._hold_frames = hold_frames
        self._fade_out = fade_out
        # State
        self._smooth_mask: Optional[np.ndarray] = None
        self._smooth_control: Optional[dict] = None
        self._last_valid_mask: Optional[np.ndarray] = None
        self._last_valid_control: Optional[dict] = None
        self._frames_since_lost = 0

    @property
    def smoothing(self) -> float:
        return self._smoothing

    @smoothing.setter
    def smoothing(self, value: float) -> None:
        self._smoothing = max(0.0, min(1.0, value))

    @property
    def hold_frames(self) -> int:
        return self._hold_frames

    @hold_frames.setter
    def hold_frames(self, value: int) -> None:
        self._hold_frames = max(0, value)

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("mask_in", PortType.MASK),
            InputPort("control_in", PortType.CONTROL_SIGNAL),
            InputPort("video_in", PortType.VIDEO_FRAME, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [
            OutputPort("mask_out", PortType.MASK),
            OutputPort("control_out", PortType.CONTROL_SIGNAL),
            OutputPort("video_out", PortType.VIDEO_FRAME),
        ]

    def reset(self) -> None:
        self._smooth_mask = None
        self._smooth_control = None
        self._last_valid_mask = None
        self._last_valid_control = None
        self._frames_since_lost = 0

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        mask = inputs["mask_in"]
        control = inputs["control_in"]
        video = inputs.get("video_in")

        detected = self._is_detected(control)

        if detected:
            # Fresh detection — smooth and store
            mask = self._smooth_mask_frame(mask)
            control = self._smooth_control_frame(control)
            self._last_valid_mask = mask.copy()
            self._last_valid_control = dict(control)
            self._frames_since_lost = 0
        elif self._last_valid_mask is not None and self._frames_since_lost < self._hold_frames:
            # Lost detection — hold last known, optionally fading
            self._frames_since_lost += 1
            mask = self._last_valid_mask
            control = self._last_valid_control

            if self._fade_out:
                fade = 1.0 - (self._frames_since_lost / self._hold_frames)
                mask = (mask.astype(np.float32) * fade).astype(np.uint8)
                control = dict(control)
                control["confidence"] = control.get("confidence", 1.0) * fade
        else:
            # No data and hold expired — reset to empty
            mask = np.zeros_like(mask)
            control = self._empty_control()

        outputs = {
            "mask_out": mask,
            "control_out": control,
        }
        if video is not None:
            outputs["video_out"] = video
        return outputs

    def _is_detected(self, control: Any) -> bool:
        """Check if the spatial source detected something this frame."""
        if isinstance(control, dict):
            return bool(control.get("detected", False))
        return False

    def _smooth_mask_frame(self, mask: np.ndarray) -> np.ndarray:
        """Apply exponential moving average to the mask."""
        alpha = self._smoothing
        mask_f = mask.astype(np.float32)
        if self._smooth_mask is None or self._smooth_mask.shape != mask.shape:
            self._smooth_mask = mask_f.copy()
        else:
            self._smooth_mask = alpha * mask_f + (1.0 - alpha) * self._smooth_mask
        return np.clip(self._smooth_mask, 0, 255).astype(np.uint8)

    def _smooth_control_frame(self, control: dict) -> dict:
        """Apply exponential moving average to numeric control values."""
        alpha = self._smoothing
        if self._smooth_control is None:
            self._smooth_control = dict(control)
            return dict(control)

        smoothed = {}
        for key, value in control.items():
            prev = self._smooth_control.get(key)
            if isinstance(value, (int, float)) and isinstance(prev, (int, float)):
                smoothed[key] = alpha * value + (1.0 - alpha) * prev
            else:
                smoothed[key] = value
        self._smooth_control = smoothed
        return dict(smoothed)

    def _empty_control(self) -> dict:
        return {
            "center_x": 0.5,
            "center_y": 0.5,
            "width": 0.0,
            "height": 0.0,
            "area": 0.0,
            "confidence": 0.0,
            "detected": False,
        }
