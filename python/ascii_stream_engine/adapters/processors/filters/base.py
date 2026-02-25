class BaseFilter:
    name = "filter"

    # Temporal declarations (default: no temporal needs)
    required_input_history: int = 0
    needs_previous_output: bool = False
    needs_optical_flow: bool = False
    needs_delta_frame: bool = False

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def apply(self, frame, config, analysis=None):
        raise NotImplementedError("Implementar apply en la subclase.")
