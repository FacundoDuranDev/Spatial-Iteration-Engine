class BaseFilter:
    name = "filter"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def apply(self, frame, config, analysis=None):
        raise NotImplementedError("Implementar apply en la subclase.")
