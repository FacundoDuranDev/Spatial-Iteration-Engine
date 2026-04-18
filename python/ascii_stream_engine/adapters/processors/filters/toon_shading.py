import cv2
import numpy as np

from .base import BaseFilter


class ToonShadingFilter(BaseFilter):
    """Cel/toon shading filter that quantizes colors and overlays detected edges.

    Produces a cartoon-like effect by reducing the color palette to discrete levels
    and drawing bold edges. Optionally uses bilateral filtering for smoother regions
    and increases detail around detected faces when perception data is available.

    Parameters via config attributes:
        toon_color_levels (int 2-16, default 6): number of quantization levels per channel.
        toon_edge_thickness (int 1-3, default 1): dilation iterations for edge lines.
        toon_edge_color (tuple BGR, default (0,0,0)): color used for edge overlay.
        toon_smooth (bool, default True): apply bilateral pre-smoothing.
    """

    name = "toon_shading"

    def apply(self, frame, config, analysis=None):
        if not self.enabled:
            return frame

        # Read parameters from config with defaults
        color_levels = getattr(config, "toon_color_levels", 6)
        color_levels = max(2, min(16, int(color_levels)))

        edge_thickness = getattr(config, "toon_edge_thickness", 1)
        edge_thickness = max(1, min(3, int(edge_thickness)))

        edge_color = getattr(config, "toon_edge_color", (0, 0, 0))
        smooth = getattr(config, "toon_smooth", True)

        # No-op guard: 1 level would be meaningless, return original ref
        if color_levels < 2:
            return frame

        # Work on a copy — never mutate the source frame
        out = frame.copy(order="C")
        h, w = out.shape[:2]

        # --- Optional bilateral pre-smoothing ---
        if smooth:
            out = cv2.bilateralFilter(out, d=7, sigmaColor=75, sigmaSpace=75)

        # --- Color quantization ---
        div = 256.0 / color_levels
        half = div / 2.0
        out = (np.floor(out.astype(np.float32) / div) * div + half).astype(np.uint8)

        # --- Edge detection ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Dilate edges for thickness control
        if edge_thickness > 1:
            kernel = np.ones((2, 2), dtype=np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=edge_thickness - 1)

        # --- Optional face-region detail enhancement ---
        if analysis is not None:
            face_data = analysis.get("face")
            if face_data is not None:
                faces = face_data.get("faces")
                if faces:
                    for face in faces:
                        bbox = face.get("bbox")
                        if bbox is None or len(bbox) < 4:
                            continue
                        x, y, fw, fh = bbox
                        # Coordinates are normalised 0-1
                        x1 = max(0, int(x * w))
                        y1 = max(0, int(y * h))
                        x2 = min(w, int((x + fw) * w))
                        y2 = min(h, int((y + fh) * h))
                        if x2 <= x1 or y2 <= y1:
                            continue
                        # Re-quantize face region with double the levels for more detail
                        face_levels = min(16, color_levels * 2)
                        fdiv = 256.0 / face_levels
                        fhalf = fdiv / 2.0
                        roi = frame[y1:y2, x1:x2].astype(np.float32)
                        if smooth:
                            roi_smooth = cv2.bilateralFilter(
                                roi.astype(np.uint8), d=7, sigmaColor=50, sigmaSpace=50
                            )
                            roi = roi_smooth.astype(np.float32)
                        out[y1:y2, x1:x2] = (
                            np.floor(roi / fdiv) * fdiv + fhalf
                        ).astype(np.uint8)

        # --- Overlay edges ---
        edge_mask = edges > 0
        out[edge_mask] = edge_color

        return np.ascontiguousarray(out, dtype=np.uint8)
