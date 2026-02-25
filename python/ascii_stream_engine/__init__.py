from .adapters.outputs import (
    AsciiFrameRecorder,
    FfmpegUdpOutput,
    NotebookPreviewSink,
    PreviewSink,
)
from .adapters.processors import (
    BaseAnalyzer,
    BaseFilter,
    BrightnessFilter,
    DetailBoostFilter,
    EdgeFilter,
    FaceHaarAnalyzer,
    InvertFilter,
)
from .adapters.renderers import AsciiRenderer, PassthroughRenderer
from .adapters.sources import OpenCVCameraSource
from .application import AnalyzerPipeline, FilterPipeline, StreamEngine
from .domain import (
    ConfigLoadError,
    EngineConfig,
    RenderFrame,
    get_predefined_profile,
    list_predefined_profiles,
    load_config_from_dict,
    load_config_from_file,
    load_config_from_profile,
    merge_configs,
    save_config_to_file,
)

# Nuevos módulos
from .infrastructure.event_bus import EventBus
from .infrastructure.plugins import PluginManager
from .ports import FrameRenderer, FrameSource, OutputSink
from .presentation import (
    build_control_panel,
    build_diagnostics_panel,
    build_engine_for_notebook,
    build_general_control_panel,
)

try:
    from .presentation import (  # noqa: F401
        build_advanced_diagnostics_panel,
        build_filter_designer_panel,
        build_full_dashboard,
        build_output_manager_panel,
        build_perception_control_panel,
        build_performance_monitor_panel,
        build_preset_manager_panel,
    )

    PRESENTATION_PANELS_AVAILABLE = True
except ImportError:
    PRESENTATION_PANELS_AVAILABLE = False


# Exportar nuevos módulos si están disponibles
try:
    from .adapters.trackers import (
        BaseTracker,
        KalmanTracker,
        MultiObjectTracker,
        OpenCVTracker,
    )
    from .application.pipeline import TrackingPipeline

    TRACKERS_AVAILABLE = True
except ImportError:
    TRACKERS_AVAILABLE = False

try:
    from .adapters.controllers import ControllerManager, MidiController, OscController

    CONTROLLERS_AVAILABLE = True
except ImportError:
    CONTROLLERS_AVAILABLE = False

try:
    from .adapters.sensors import AudioSensor, BaseSensor, DepthSensor, SensorFusion

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
    "PassthroughRenderer",
    "AsciiFrameRecorder",
    "FfmpegUdpOutput",
    "NotebookPreviewSink",
    "OutputSink",
    "PreviewSink",
    "build_control_panel",
    "build_diagnostics_panel",
    "build_engine_for_notebook",
    "build_general_control_panel",
    # Infrastructure
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

if PRESENTATION_PANELS_AVAILABLE:
    __all__.extend(
        [
            "build_advanced_diagnostics_panel",
            "build_filter_designer_panel",
            "build_full_dashboard",
            "build_output_manager_panel",
            "build_perception_control_panel",
            "build_performance_monitor_panel",
            "build_preset_manager_panel",
        ]
    )

if TRACKERS_AVAILABLE:
    __all__.extend(
        [
            "BaseTracker",
            "OpenCVTracker",
            "KalmanTracker",
            "MultiObjectTracker",
            "TrackingPipeline",
        ]
    )

if CONTROLLERS_AVAILABLE:
    __all__.extend(
        [
            "ControllerManager",
            "MidiController",
            "OscController",
        ]
    )

if SENSORS_AVAILABLE:
    __all__.extend(
        [
            "BaseSensor",
            "SensorFusion",
            "AudioSensor",
            "DepthSensor",
        ]
    )

if GENERATORS_AVAILABLE:
    __all__.extend(
        [
            "BaseContentGenerator",
            "PatternGenerator",
            "GeneratorSource",
        ]
    )
