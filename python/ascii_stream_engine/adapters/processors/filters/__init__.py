from .ascii import AsciiFilter
from .base import BaseFilter
from .bloom import BloomFilter
from .chrono_scan import ChronoScanFilter
from .chromatic_trails import ChromaticTrailsFilter
from .feedback_loop import FeedbackLoopFilter
from .bloom_cinematic import BloomCinematicFilter
from .boids import BoidsFilter
from .brightness import BrightnessFilter
from .chromatic_aberration import ChromaticAberrationFilter
from .color_grading import ColorGradingFilter
from .cpp_brightness_contrast import CppBrightnessContrastFilter
from .cpp_channel_swap import CppChannelSwapFilter
from .cpp_grayscale import CppGrayscaleFilter
from .cpp_invert import CppInvertFilter
from .cpp_modifier import CppImageModifierFilter
from .cpp_physarum import CppPhysarumFilter
from .crt_glitch import CRTGlitchFilter
from .depth_of_field import DepthOfFieldFilter
from .detail import DetailBoostFilter
from .double_vision import DoubleVisionFilter
from .edge_smooth import EdgeSmoothFilter
from .edges import EdgeFilter
from .film_grain import FilmGrainFilter
from .glitch_block import GlitchBlockFilter
from .geometric_patterns import GeometricPatternFilter
from .hand_frame import HandFrameFilter
from .hand_spatial_warp import HandSpatialWarpFilter
from .infrared import InfraredFilter
from .invert import InvertFilter
from .kaleidoscope import KaleidoscopeFilter
from .kinetic_typography import KineticTypographyFilter
from .lens_flare import LensFlareFilter
from .kuwahara import KuwaharaFilter
from .mosaic import MosaicFilter
from .motion_blur import MotionBlurFilter
from .optical_flow_particles import OpticalFlowParticlesFilter
from .panel_compositor import PanelCompositorFilter
from .physarum import PhysarumFilter
from .radial_blur import RadialBlurFilter
from .radial_collapse import RadialCollapseFilter
from .slit_scan import SlitScanFilter
from .stippling import StipplingFilter
from .toon_shading import ToonShadingFilter
from .uv_displacement import UVDisplacementFilter
from .vignette import VignetteFilter
from ._registry import (
    ALL_FILTERS,
    _ensure_registry,
    deserialize_filter,
    get_filter_params,
    serialize_filter,
    set_filter_params,
)

# Build the registry now that all filter classes are imported.
_ensure_registry()

__all__ = [
    "AsciiFilter",
    "BaseFilter",
    "BloomFilter",
    "BloomCinematicFilter",
    "BoidsFilter",
    "BrightnessFilter",
    "ChromaticAberrationFilter",
    "ChromaticTrailsFilter",
    "ChronoScanFilter",
    "ColorGradingFilter",
    "CppBrightnessContrastFilter",
    "CppChannelSwapFilter",
    "CppGrayscaleFilter",
    "CppImageModifierFilter",
    "CppInvertFilter",
    "CppPhysarumFilter",
    "CRTGlitchFilter",
    "DepthOfFieldFilter",
    "DetailBoostFilter",
    "DoubleVisionFilter",
    "EdgeFilter",
    "EdgeSmoothFilter",
    "FilmGrainFilter",
    "GeometricPatternFilter",
    "GlitchBlockFilter",
    "HandFrameFilter",
    "HandSpatialWarpFilter",
    "InfraredFilter",
    "InvertFilter",
    "KaleidoscopeFilter",
    "KineticTypographyFilter",
    "LensFlareFilter",
    "KuwaharaFilter",
    "MosaicFilter",
    "MotionBlurFilter",
    "OpticalFlowParticlesFilter",
    "PanelCompositorFilter",
    "PhysarumFilter",
    "RadialBlurFilter",
    "RadialCollapseFilter",
    "SlitScanFilter",
    "StipplingFilter",
    "ToonShadingFilter",
    "UVDisplacementFilter",
    "VignetteFilter",
    # Registry utilities
    "ALL_FILTERS",
    "get_filter_params",
    "set_filter_params",
    "serialize_filter",
    "deserialize_filter",
]
