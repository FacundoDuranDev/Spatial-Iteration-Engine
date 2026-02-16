"""Style: vectores artísticos y estilización neural.

Stubs para Style Encoder (artwork -> R64), Stylizer (Filter) y coherencia temporal.
"""

from .style_encoder import StyleEncoder
from .stylizer import NeuralStylizerFilter
from .temporal_coherence import TemporalCoherenceFilter

__all__ = [
    "StyleEncoder",
    "NeuralStylizerFilter",
    "TemporalCoherenceFilter",
]
