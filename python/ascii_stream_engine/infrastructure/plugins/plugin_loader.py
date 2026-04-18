"""Cargador seguro de plugins desde archivos externos."""

import importlib.util
import inspect
import logging
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple, Type

from .plugin_interface import Plugin
from .plugin_metadata import PluginMetadata, extract_metadata_from_plugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """Cargador de plugins con validación."""

    def __init__(self) -> None:
        """Inicializa el cargador."""
        self._loaded_modules: dict = {}

    def load_from_file(
        self, file_path: str, plugin_class_name: Optional[str] = None
    ) -> Optional[Plugin]:
        """
        Carga un plugin desde un archivo Python.

        Args:
            file_path: Ruta al archivo del plugin
            plugin_class_name: Nombre de la clase del plugin (se infiere si no se proporciona)

        Returns:
            Instancia del plugin o None si falla
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            logger.error(f"Archivo de plugin no encontrado: {file_path}")
            return None

        if not file_path.suffix == ".py":
            logger.error(f"El archivo debe ser un módulo Python (.py): {file_path}")
            return None

        try:
            # Intentar cargar metadatos desde archivo JSON asociado
            metadata_file = file_path.with_suffix(".json")
            metadata = None
            if metadata_file.exists():
                metadata = PluginMetadata.from_file(str(metadata_file))
                if metadata:
                    logger.debug(f"Metadatos cargados desde: {metadata_file}")

            # Cargar módulo
            module_name = f"plugin_{file_path.stem}_{id(file_path)}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)

            if spec is None or spec.loader is None:
                logger.error(f"No se pudo crear spec para: {file_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Buscar clase del plugin
            if plugin_class_name:
                plugin_class = getattr(module, plugin_class_name, None)
            else:
                # Buscar automáticamente clases que hereden de Plugin
                plugin_class = self._find_plugin_class(module)

            if plugin_class is None:
                logger.error(f"No se encontró clase de plugin en: {file_path}")
                return None

            # Instanciar plugin
            plugin = plugin_class()
            if not isinstance(plugin, Plugin):
                logger.error(f"La clase no es una instancia de Plugin: {file_path}")
                return None

            # Aplicar metadatos si se cargaron
            if metadata:
                plugin.metadata = metadata.to_dict()
                # Actualizar atributos básicos si están en metadatos
                if metadata.name and (not hasattr(plugin, "name") or not plugin.name):
                    plugin.name = metadata.name
                if metadata.version and (not hasattr(plugin, "version") or not plugin.version):
                    plugin.version = metadata.version
                if metadata.description:
                    plugin.description = metadata.description
                if metadata.author:
                    plugin.author = metadata.author

            if not plugin.validate():
                logger.error(f"Plugin no válido: {plugin.name}")
                return None

            logger.info(f"Plugin cargado exitosamente: {plugin.name} desde {file_path}")
            return plugin

        except Exception as e:
            logger.error(f"Error cargando plugin desde {file_path}: {e}", exc_info=True)
            return None

    def load_from_file_with_metadata(
        self, file_path: str, plugin_class_name: Optional[str] = None
    ) -> Optional[Tuple[Plugin, PluginMetadata]]:
        """
        Carga un plugin y sus metadatos desde un archivo.

        Args:
            file_path: Ruta al archivo del plugin
            plugin_class_name: Nombre de la clase del plugin (se infiere si no se proporciona)

        Returns:
            Tupla (plugin, metadata) o None si falla
        """
        plugin = self.load_from_file(file_path, plugin_class_name)
        if plugin is None:
            return None

        metadata = extract_metadata_from_plugin(plugin)
        metadata.loaded_from = str(file_path)
        metadata.load_time = time.time()

        return (plugin, metadata)

    def load_from_directory(self, directory: str, recursive: bool = False) -> List[Plugin]:
        """
        Carga todos los plugins de un directorio.

        Args:
            directory: Directorio a escanear
            recursive: Si buscar recursivamente en subdirectorios

        Returns:
            Lista de plugins cargados
        """
        directory = Path(directory).resolve()

        if not directory.exists() or not directory.is_dir():
            logger.error(f"Directorio no encontrado: {directory}")
            return []

        plugins = []
        pattern = "**/*.py" if recursive else "*.py"

        for file_path in directory.glob(pattern):
            # Saltar __init__.py y archivos de test
            if file_path.name.startswith("__") or "test" in file_path.name.lower():
                continue

            plugin = self.load_from_file(str(file_path))
            if plugin:
                plugins.append(plugin)

        logger.info(f"Cargados {len(plugins)} plugins desde {directory}")
        return plugins

    def load_from_module(self, module_name: str, plugin_class_name: str) -> Optional[Plugin]:
        """
        Carga un plugin desde un módulo Python instalado.

        Args:
            module_name: Nombre del módulo
            plugin_class_name: Nombre de la clase del plugin

        Returns:
            Instancia del plugin o None si falla
        """
        try:
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, plugin_class_name, None)

            if plugin_class is None:
                logger.error(f"Clase '{plugin_class_name}' no encontrada en módulo '{module_name}'")
                return None

            plugin = plugin_class()
            if not isinstance(plugin, Plugin):
                logger.error(
                    f"La clase no es una instancia de Plugin: {module_name}.{plugin_class_name}"
                )
                return None

            if not plugin.validate():
                logger.error(f"Plugin no válido: {plugin.name}")
                return None

            logger.info(f"Plugin cargado desde módulo: {module_name}.{plugin_class_name}")
            return plugin

        except Exception as e:
            logger.error(f"Error cargando plugin desde módulo '{module_name}': {e}", exc_info=True)
            return None

    @staticmethod
    def _find_plugin_class(module) -> Optional[Type[Plugin]]:
        """Busca automáticamente una clase de plugin en un módulo."""
        from .plugin_interface import Plugin

        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj is not Plugin
                and not inspect.isabstract(obj)
            ):
                return obj
        return None
