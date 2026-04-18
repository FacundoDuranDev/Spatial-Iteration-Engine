"""RenderFrameCompositeNode — composes two RenderFrames via PIL alpha_composite."""

from typing import Any, Dict, List

from PIL import Image

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class RenderFrameCompositeNode(BaseNode):
    """Composes two RenderFrames into one.

    Uses PIL alpha_composite to blend images. Merges text, lines, and metadata
    from both inputs. B is composited on top of A.

    Inputs:
        render_in_a: Primary RenderFrame (required)
        render_in_b: Secondary RenderFrame (required)

    Output:
        render_out: Composited RenderFrame
    """

    name = "render_composite"

    def __init__(self, opacity: float = 1.0) -> None:
        super().__init__()
        self._opacity = max(0.0, min(1.0, opacity))

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("render_in_a", PortType.RENDER_FRAME),
            InputPort("render_in_b", PortType.RENDER_FRAME),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("render_out", PortType.RENDER_FRAME)]

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        rf_a = inputs["render_in_a"]
        rf_b = inputs["render_in_b"]

        # Import here to avoid circular imports at module level
        from ....domain.types import RenderFrame

        # Composite images
        img_a = rf_a.image.convert("RGBA")
        img_b = rf_b.image.convert("RGBA")

        # Resize B to match A if sizes differ
        if img_b.size != img_a.size:
            img_b = img_b.resize(img_a.size, Image.LANCZOS)

        # Apply opacity to B
        if self._opacity < 1.0:
            alpha = img_b.split()[3]
            alpha = alpha.point(lambda p: int(p * self._opacity))
            img_b.putalpha(alpha)

        composited = Image.alpha_composite(img_a, img_b)

        # Merge text
        text_parts = []
        if rf_a.text:
            text_parts.append(rf_a.text)
        if rf_b.text:
            text_parts.append(rf_b.text)
        merged_text = "\n".join(text_parts) if text_parts else None

        # Merge lines
        lines_a = rf_a.lines or []
        lines_b = rf_b.lines or []
        merged_lines = lines_a + lines_b if (lines_a or lines_b) else None

        # Merge metadata
        meta_a = rf_a.metadata or {}
        meta_b = rf_b.metadata or {}
        merged_meta = {**meta_a, **meta_b} if (meta_a or meta_b) else None

        result = RenderFrame(
            image=composited,
            text=merged_text,
            lines=merged_lines,
            metadata=merged_meta,
        )
        return {"render_out": result}
