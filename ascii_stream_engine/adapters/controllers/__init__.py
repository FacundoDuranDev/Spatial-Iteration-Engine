"""Módulo de controladores externos."""

from .base import BaseController
from .control_mapping import ControlMapping
from .controller_manager import ControllerManager

# Importar controladores con manejo de dependencias opcionales
try:
    from .midi_controller import MidiController
    MIDI_AVAILABLE = True
except ImportError:
    MIDI_AVAILABLE = False
    MidiController = None  # type: ignore

try:
    from .osc_controller import OscController
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False
    OscController = None  # type: ignore

__all__ = [
    "BaseController",
    "ControllerManager",
    "ControlMapping",
]

if MIDI_AVAILABLE:
    __all__.append("MidiController")

if OSC_AVAILABLE:
    __all__.append("OscController")

