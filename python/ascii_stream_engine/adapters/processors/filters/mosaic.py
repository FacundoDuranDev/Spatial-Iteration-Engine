import cv2
import numpy as np

from .base import BaseFilter


class MosaicFilter(BaseFilter):
    """Pixelates the frame into a mosaic/block grid.

    Uses config.mosaic_block_size (float 0.01-0.3, default 0.05) to determine
    the relative size of each block as a fraction of the frame's shortest dimension.
    """

    name = "mosaic"

    def apply(self, frame, config, analysis=None):
        block_size = getattr(config, "mosaic_block_size", 0.05)
        block_size = max(0.01, min(0.3, float(block_size)))

        h, w = frame.shape[:2]
        min_dim = min(h, w)
        block_px = max(2, int(min_dim * block_size))

        small_w = max(1, w // block_px)
        small_h = max(1, h // block_px)

        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
