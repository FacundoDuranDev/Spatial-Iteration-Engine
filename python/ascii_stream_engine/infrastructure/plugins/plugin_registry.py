"""Registro de plugins disponibles."""

import logging
from typing import Dict, List, Optional, Type

try:
    from importlib.metadata import EntryPoint, entry_points
except ImportError:
    # Python < 3.8 fallback
    from importlib_metadata import entry_points, EntryPoint

from .plugin_interface import Plugin
from .plugin_metadata import PluginMetadata, extract_metadata_from_plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registro central de plugins cargados con auto-descubrimiento."""

    def __init__(self, enable_auto_discovery: bool = True) -> None:
        """
        Inicializa el registro.

        Args:
            enable_auto_discovery: Si habilitar auto-descubrimiento de plugins
        """
        self._plugins: Dict[str, Plugin] = {}
        self._plugins_by_type: Dict[str, List[str]] = {
            "filter": [],
            "analyzer": [],
            "renderer": [],
            "tracker": [],
        }
        self._metadata: Dict[str, PluginMetadata] = {}
        self._entry_points: Dict[str, EntryPoint] = {}
        self._enable_auto_discovery = enable_auto_discovery

        # Auto-descubrir plugins al inicializar
        if enable_auto_discovery:
            self.discover_plugins()

    def register(
        self,
        plugin: Plugin,
        plugin_type: Optional[str] = None,
        metadata: Optional[PluginMetadata] = None,
    ) -> bool:
        """
        Registra un plugin con metadatos.

        Args:
            plugin: Instancia del plugin
            plugin_type: Tipo del plugin (se infiere si no se proporciona)
            metadata: Metadatos del plugin (se extraen si no se proporcionan)

        Returns:
            True si se registró exitosamente
        """
        if not plugin.validate():
            logger.error(f"Plugin '{plugin.name}' no es válido")
            return False

        # Inferir tipo si no se proporciona
        if plugin_type is None:
            plugin_type = self._infer_plugin_type(plugin)

        if plugin_type not in self._plugins_by_type:
            logger.error(f"Tipo de plugin desconocido: {plugin_type}")
            return False

        # Extraer o usar metadatos proporcionados
        if metadata is None:
            metadata = extract_metadata_from_plugin(plugin, plugin_type)
        else:
            # Asegurar que el tipo sea correcto
            metadata.plugin_type = plugin_type

        # Verificar que no exista otro plugin con el mismo nombre
        if plugin.name in self._plugins:
            logger.warning(f"Plugin '{plugin.name}' ya está registrado, reemplazando")
            self.unregister(plugin.name)

        self._plugins[plugin.name] = plugin
        self._metadata[plugin.name] = metadata
        if plugin.name not in self._plugins_by_type[plugin_type]:
            self._plugins_by_type[plugin_type].append(plugin.name)

        logger.info(
            f"Plugin '{plugin.name}' (tipo: {plugin_type}, versión: {metadata.version}) registrado"
        )
        return True

    def unregister(self, plugin_name: str) -> bool:
        """
        Desregistra un plugin.

        Args:
            plugin_name: Nombre del plugin

        Returns:
            True si se desregistró exitosamente
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin '{plugin_name}' no está registrado")
            return False

        plugin = self._plugins[plugin_name]
        plugin_type = self._infer_plugin_type(plugin)

        del self._plugins[plugin_name]
        if plugin_name in self._metadata:
            del self._metadata[plugin_name]
        if plugin_name in self._entry_points:
            del self._entry_points[plugin_name]
        if plugin_name in self._plugins_by_type[plugin_type]:
            self._plugins_by_type[plugin_type].remove(plugin_name)

        logger.info(f"Plugin '{plugin_name}' desregistrado")
        return True

    def get(self, plugin_name: str) -> Optional[Plugin]:
        """
        Obtiene un plugin por nombre.

        Args:
            plugin_name: Nombre del plugin

        Returns:
            Instancia del plugin o None si no existe
        """
        return self._plugins.get(plugin_name)

    def get_all(self, plugin_type: Optional[str] = None) -> List[Plugin]:
        """
        Obtiene todos los plugins, opcionalmente filtrados por tipo.

        Args:
            plugin_type: Tipo de plugin (None para todos)

        Returns:
            Lista de plugins
        """
        if plugin_type:
            if plugin_type not in self._plugins_by_type:
                return []
            return [
                self._plugins[name]
                for name in self._plugins_by_type[plugin_type]
                if name in self._plugins
            ]
        return list(self._plugins.values())

    def get_names(self, plugin_type: Optional[str] = None) -> List[str]:
        """
        Obtiene los nombres de todos los plugins.

        Args:
            plugin_type: Tipo de plugin (None para todos)

        Returns:
            Lista de nombres
        """
        if plugin_type:
            return self._plugins_by_type.get(plugin_type, [])
        return list(self._plugins.keys())

    def has(self, plugin_name: str) -> bool:
        """
        Verifica si un plugin está registrado.

        Args:
            plugin_name: Nombre del plugin

        Returns:
            True si está registrado
        """
        return plugin_name in self._plugins

    def get_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """
        Obtiene los metadatos de un plugin.

        Args:
            plugin_name: Nombre del plugin

        Returns:
            Metadatos del plugin o None si no existe
        """
        return self._metadata.get(plugin_name)

    def get_all_metadata(self) -> Dict[str, PluginMetadata]:
        """Obtiene todos los metadatos de plugins registrados."""
        return self._metadata.copy()

    def discover_plugins(self, group: str = "ascii_stream_engine.plugins") -> int:
        """
        Descubre plugins automáticamente usando entry points de Python.

        Args:
            group: Nombre del grupo de entry points a buscar

        Returns:
            Número de plugins descubiertos
        """
        if not self._enable_auto_discovery:
            return 0

        discovered_count = 0
        try:
            # Obtener entry points del grupo especificado
            eps = entry_points(group=group)

            for ep in eps:
                try:
                    # Cargar el plugin desde el entry point
                    plugin_class = ep.load()
                    plugin = plugin_class()

                    if isinstance(plugin, Plugin):
                        # Registrar el plugin
                        if self.register(plugin):
                            self._entry_points[plugin.name] = ep
                            discovered_count += 1
                            logger.debug(f"Plugin descubierto desde entry point: {ep.name}")
                except Exception as e:
                    logger.warning(f"Error cargando plugin desde entry point '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"No se encontraron entry points en grupo '{group}': {e}")

        if discovered_count > 0:
            logger.info(f"Descubiertos {discovered_count} plugins automáticamente")

        return discovered_count

    def clear(self) -> None:
        """Limpia todos los plugins registrados."""
        self._plugins.clear()
        self._metadata.clear()
        self._entry_points.clear()
        for plugin_list in self._plugins_by_type.values():
            plugin_list.clear()
        logger.debug("Registro de plugins limpiado")

    def count(self, plugin_type: Optional[str] = None) -> int:
        """
        Cuenta el número de plugins registrados.

        Args:
            plugin_type: Tipo de plugin (None para total)

        Returns:
            Número de plugins
        """
        if plugin_type:
            return len(self._plugins_by_type.get(plugin_type, []))
        return len(self._plugins)

    @staticmethod
    def _infer_plugin_type(plugin: Plugin) -> str:
        """Infiere el tipo de plugin basándose en su clase."""
        from .plugin_interface import (
            AnalyzerPlugin,
            FilterPlugin,
            RendererPlugin,
            TrackerPlugin,
        )

        if isinstance(plugin, FilterPlugin):
            return "filter"
        elif isinstance(plugin, AnalyzerPlugin):
            return "analyzer"
        elif isinstance(plugin, RendererPlugin):
            return "renderer"
        elif isinstance(plugin, TrackerPlugin):
            return "tracker"
        else:
            return "unknown"
