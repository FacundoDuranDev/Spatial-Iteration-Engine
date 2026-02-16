"""Sistema de plugins para extensibilidad."""

from .plugin_interface import (
    AnalyzerPlugin,
    FilterPlugin,
    Plugin,
    RendererPlugin,
    TrackerPlugin,
)
from .plugin_loader import PluginLoader
from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry
from .plugin_metadata import PluginMetadata, extract_metadata_from_plugin

__all__ = [
    "Plugin",
    "FilterPlugin",
    "AnalyzerPlugin",
    "RendererPlugin",
    "TrackerPlugin",
    "PluginRegistry",
    "PluginManager",
    "PluginLoader",
    "PluginMetadata",
    "extract_metadata_from_plugin",
]

