from typing import Optional, Protocol

import numpy as np


class FrameSource(Protocol):
    def open(self) -> None: ...

    def read(self) -> Optional[np.ndarray]: ...

    def close(self) -> None: ...
