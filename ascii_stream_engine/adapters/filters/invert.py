from .base import BaseFilter


class InvertFilter(BaseFilter):
    name = "invert"

    def apply(self, frame, config, analysis=None):
        if not getattr(config, "invert", False):
            return frame
        return 255 - frame
