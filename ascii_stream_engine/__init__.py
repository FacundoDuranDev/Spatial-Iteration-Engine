from .application import AnalyzerPipeline, FilterPipeline, StreamEngine
from .domain import (
    EngineConfig,
    RenderFrame,
    ConfigLoadError,
    get_predefined_profile,
    list_predefined_profiles,
    load_config_from_dict,
    load_config_from_file,
    load_config_from_profile,
    merge_configs,
    save_config_to_file,
)
from .ports import FrameRenderer, FrameSource, OutputSink
from .adapters.analyzers import BaseAnalyzer, FaceHaarAnalyzer
from .adapters.filters import (
    BaseFilter,
    BrightnessFilter,
    DetailBoostFilter,
    EdgeFilter,
    InvertFilter,
)
from .adapters.outputs import AsciiFrameRecorder, FfmpegUdpOutput
from .adapters.renderers import AsciiRenderer
from .adapters.sources import OpenCVCameraSource
from .presentation import build_control_panel, build_general_control_panel

# Nuevos módulos
from .infrastructure.event_bus import EventBus
from .infrastructure.plugins import PluginManager

# Exportar nuevos módulos si están disponibles
try:
    from .adapters.trackers import (
        BaseTracker,
        KalmanTracker,
        MultiObjectTracker,
        OpenCVTracker,
        TrackingPipeline,
    )
    TRACKERS_AVAILABLE = True
except ImportError:
    TRACKERS_AVAILABLE = False

try:
    from .adapters.controllers import ControllerManager
    from .adapters.controllers import MidiController, OscController
    CONTROLLERS_AVAILABLE = True
except ImportError:
    CONTROLLERS_AVAILABLE = False

try:
    from .adapters.sensors import BaseSensor, SensorFusion
    from .adapters.sensors import AudioSensor, DepthSensor
    SENSORS_AVAILABLE = True
except ImportError:
    SENSORS_AVAILABLE = False

try:
    from .adapters.generators import (
        BaseContentGenerator,
        GeneratorSource,
        PatternGenerator,
    )
    GENERATORS_AVAILABLE = True
except ImportError:
    GENERATORS_AVAILABLE = False

__all__ = [
    "EngineConfig",
    "StreamEngine",
    "AnalyzerPipeline",
    "FilterPipeline",
    "RenderFrame",
    "FrameSource",
    "OpenCVCameraSource",
    "BaseAnalyzer",
    "FaceHaarAnalyzer",
    "BaseFilter",
    "BrightnessFilter",
    "DetailBoostFilter",
    "EdgeFilter",
    "InvertFilter",
    "AsciiRenderer",
    "FrameRenderer",
    "AsciiFrameRecorder",
    "FfmpegUdpOutput",
    "OutputSink",
    "build_control_panel",
    "build_general_control_panel",
    # Nuevos módulos
    "EventBus",
    "PluginManager",
    # Sistema de configuración
    "ConfigLoadError",
    "get_predefined_profile",
    "list_predefined_profiles",
    "load_config_from_dict",
    "load_config_from_file",
    "load_config_from_profile",
    "merge_configs",
    "save_config_to_file",
]

if TRACKERS_AVAILABLE:
    __all__.extend([
        "BaseTracker",
        "OpenCVTracker",
        "KalmanTracker",
        "MultiObjectTracker",
        "TrackingPipeline",
    ])

if CONTROLLERS_AVAILABLE:
    __all__.extend([
        "ControllerManager",
        "MidiController",
        "OscController",
    ])

if SENSORS_AVAILABLE:
    __all__.extend([
        "BaseSensor",
        "SensorFusion",
        "AudioSensor",
        "DepthSensor",
    ])

if GENERATORS_AVAILABLE:
    __all__.extend([
        "BaseContentGenerator",
        "PatternGenerator",
        "GeneratorSource",
    ])
