class BaseAnalyzer:
    name = "analyzer"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def analyze(self, frame, config):
        raise NotImplementedError("Implementar analyze en la subclase.")
