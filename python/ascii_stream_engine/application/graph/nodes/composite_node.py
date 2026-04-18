"""CompositeNode — blends two video frames with configurable blend modes."""

from typing import Any, Dict, List

import cv2
import numpy as np

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class CompositeNode(BaseNode):
    """Blends two video frames using a configurable blend mode.

    Inputs:
        video_in_a: Primary video frame (required)
        video_in_b: Secondary video frame (required)
        mask_in: Optional mask (MASK) — white=B, black=A
        opacity: Optional control signal (CONTROL_SIGNAL) — float 0-1, default 1.0

    Output:
        video_out: Blended result

    Blend modes: alpha, additive, multiply, screen, overlay, mask
    """

    name = "composite"

    BLEND_MODES = ("alpha", "additive", "multiply", "screen", "overlay", "mask")

    def __init__(self, mode: str = "alpha", opacity: float = 1.0) -> None:
        super().__init__()
        if mode not in self.BLEND_MODES:
            raise ValueError(f"Unknown blend mode {mode!r}, expected one of {self.BLEND_MODES}")
        self._mode = mode
        self._default_opacity = opacity

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in_a", PortType.VIDEO_FRAME),
            InputPort("video_in_b", PortType.VIDEO_FRAME),
            InputPort("mask_in", PortType.MASK, required=False),
            InputPort("opacity", PortType.CONTROL_SIGNAL, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs["video_in_a"]
        b = inputs["video_in_b"]
        opacity = inputs.get("opacity", self._default_opacity)
        if opacity is None:
            opacity = self._default_opacity
        opacity = float(max(0.0, min(1.0, opacity)))

        mask = inputs.get("mask_in")

        # Resize b to match a if shapes differ
        if a.shape[:2] != b.shape[:2]:
            b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_LINEAR)

        result = self._blend(a, b, opacity, mask)
        return {"video_out": result}

    def _blend(
        self, a: np.ndarray, b: np.ndarray, opacity: float, mask: Any
    ) -> np.ndarray:
        """Apply the configured blend mode."""
        if self._mode == "mask" and mask is not None:
            return self._blend_mask(a, b, mask)

        a_f = a.astype(np.float32)
        b_f = b.astype(np.float32)

        if self._mode == "alpha":
            out = a_f * (1.0 - opacity) + b_f * opacity
        elif self._mode == "additive":
            out = a_f + b_f * opacity
        elif self._mode == "multiply":
            out = a_f * (b_f / 255.0) * opacity + a_f * (1.0 - opacity)
        elif self._mode == "screen":
            inv = 255.0 - (255.0 - a_f) * (255.0 - b_f) / 255.0
            out = a_f * (1.0 - opacity) + inv * opacity
        elif self._mode == "overlay":
            # Overlay: multiply where a<128, screen where a>=128
            low = 2.0 * a_f * b_f / 255.0
            high = 255.0 - 2.0 * (255.0 - a_f) * (255.0 - b_f) / 255.0
            overlay = np.where(a_f < 128, low, high)
            out = a_f * (1.0 - opacity) + overlay * opacity
        elif self._mode == "mask":
            # Mask mode without a mask — fall back to alpha blend
            out = a_f * (1.0 - opacity) + b_f * opacity
        else:
            out = a_f

        return np.clip(out, 0, 255).astype(np.uint8)

    def _blend_mask(
        self, a: np.ndarray, b: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        """Blend using a mask: white=B, black=A."""
        if mask.shape[:2] != a.shape[:2]:
            mask = cv2.resize(mask, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_LINEAR)

        if mask.ndim == 2:
            alpha = mask.astype(np.float32) / 255.0
            alpha = alpha[:, :, np.newaxis]
        else:
            alpha = mask[:, :, :1].astype(np.float32) / 255.0

        a_f = a.astype(np.float32)
        b_f = b.astype(np.float32)
        out = a_f * (1.0 - alpha) + b_f * alpha
        return np.clip(out, 0, 255).astype(np.uint8)
