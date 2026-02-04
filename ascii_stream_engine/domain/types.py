from dataclasses import dataclass
from typing import Dict, List, Optional

from PIL import Image


@dataclass
class RenderFrame:
    image: Image.Image
    text: Optional[str] = None
    lines: Optional[List[str]] = None
    metadata: Optional[Dict[str, object]] = None
