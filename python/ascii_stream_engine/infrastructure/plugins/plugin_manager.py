"""Plugin manager with hot-reload, dependency resolution, and batch reload."""

import logging
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Crear clases dummy para evitar errores
    class Observer:
        pass

    class FileSystemEventHandler:
        pass

    class FileSystemEvent:
        pass


from .plugin_dependency import PluginDependencyResolver
from .plugin_interface import Plugin
from .plugin_loader import PluginLoader
from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

# Maximum number of pending reload entries to prevent unbounded growth
_MAX_PENDING_RELOADS = 100


class PluginFileHandler(FileSystemEventHandler):
    """File system event handler for plugin hot-reload with batch collection."""

    def __init__(self, manager: "PluginManager", debounce_seconds: float = 0.5) -> None:
        """Initialize the handler.

        Args:
            manager: PluginManager instance.
            debounce_seconds: Time to wait before triggering reload (debounce).
        """
        super().__init__()
        self._manager = manager
        self._debounce_seconds = debounce_seconds
        self._pending_reloads: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Called when a file is modified."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return

        # Debounce using perf_counter for accurate timing
        current_time = time.perf_counter()
        with self._lock:
            last_reload = self._pending_reloads.get(str(file_path), 0)
            if current_time - last_reload < self._debounce_seconds:
                return
            self._pending_reloads[str(file_path)] = current_time
            # Bound pending reloads to prevent unbounded growth
            while len(self._pending_reloads) > _MAX_PENDING_RELOADS:
                self._pending_reloads.popitem(last=False)

        logger.info(f"Modified file detected: {file_path}, reloading plugin...")
        self._manager._reload_plugin_file(str(file_path))

    def on_created(self, event: FileSystemEvent) -> None:
        """Called when a new file is created."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return

        logger.info(f"New file detected: {file_path}, loading plugin...")
        self._manager.load_from_file(str(file_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Called when a file is deleted."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return

        logger.info(f"Deleted file detected: {file_path}, unregistering plugin...")
        self._manager._handle_file_deleted(str(file_path))


class PluginManager:
    """Plugin manager with loading, registration, hot-reload, and dependency resolution."""

    def __init__(
        self,
        plugin_paths: Optional[List[str]] = None,
        enable_hot_reload: bool = False,
        hot_reload_debounce: float = 0.5,
    ) -> None:
        """Initialize the plugin manager.

        Args:
            plugin_paths: List of paths to search for plugins.
            enable_hot_reload: Whether to enable automatic hot-reload.
            hot_reload_debounce: Time to wait before reloading (seconds).
        """
        self._registry = PluginRegistry()
        self._loader = PluginLoader()
        self._plugin_paths = plugin_paths or []
        self._enable_hot_reload = enable_hot_reload and WATCHDOG_AVAILABLE
        self._hot_reload_debounce = hot_reload_debounce

        # Tracking loaded files for hot-reload
        self._file_to_plugin: Dict[str, str] = {}  # file_path -> plugin_name

        # Hot-reload system
        self._observer: Optional[Observer] = None
        self._hot_reload_lock = threading.Lock()

        # Dependency resolution
        self._dependency_resolver = PluginDependencyResolver()

        # Reload statistics
        self._reload_count = 0
        self._total_reload_time = 0.0
        self._last_reload_at: Optional[float] = None

        # Load plugins automatically if paths are provided
        if self._plugin_paths:
            self.load_all()

        # Start hot-reload if enabled
        if self._enable_hot_reload:
            self.start_hot_reload()

    def _reload_plugin_file(self, file_path: str) -> bool:
        """Reload a plugin from a file (used by hot-reload).

        Also reloads all plugins that depend on the changed plugin
        in dependency order.

        Args:
            file_path: Path to the plugin file.

        Returns:
            True if reload was successful.
        """
        start_time = time.perf_counter()
        with self._hot_reload_lock:
            # Find the plugin associated with this file
            plugin_name = self._file_to_plugin.get(file_path)

            # Determine reload order: this plugin + all dependents
            reload_names = [plugin_name] if plugin_name else []
            if plugin_name and self._dependency_resolver.has_plugin(plugin_name):
                dependents = self._dependency_resolver.get_dependents(plugin_name)
                reload_names.extend(sorted(dependents))

            # Unregister all plugins to be reloaded
            for name in reload_names:
                if name and self._registry.get(name):
                    self._registry.unregister(name)
                    logger.debug(f"Plugin '{name}' unregistered for reload")

            # Reload the primary file
            result = self.load_from_file(file_path)

            if result and plugin_name:
                new_plugin = self._registry.get(plugin_name)
                if new_plugin:
                    self._file_to_plugin[file_path] = new_plugin.name
                    logger.info(f"Plugin '{plugin_name}' reloaded successfully")

            # Reload dependent plugins from their tracked files
            for name in reload_names[1:]:  # Skip the primary (already reloaded)
                dep_file = None
                for fp, pn in self._file_to_plugin.items():
                    if pn == name:
                        dep_file = fp
                        break
                if dep_file:
                    try:
                        self.load_from_file(dep_file)
                        logger.info(f"Dependent plugin '{name}' reloaded")
                    except Exception as e:
                        logger.error(f"Failed to reload dependent plugin '{name}': {e}")

            # Update reload stats
            reload_duration = time.perf_counter() - start_time
            self._reload_count += 1
            self._total_reload_time += reload_duration
            self._last_reload_at = time.perf_counter()

            return result

    def _handle_file_deleted(self, file_path: str) -> None:
        """Handle a deleted plugin file by unregistering its plugin.

        Args:
            file_path: Path to the deleted file.
        """
        with self._hot_reload_lock:
            file_path_resolved = str(Path(file_path).resolve())
            plugin_name = self._file_to_plugin.pop(file_path_resolved, None)
            if plugin_name:
                self._registry.unregister(plugin_name)
                self._dependency_resolver.remove_plugin(plugin_name)
                logger.info(f"Plugin '{plugin_name}' unregistered (file deleted)")

    def reload_stats(self) -> Dict[str, object]:
        """Return reload statistics.

        Returns:
            Dict with reload_count, avg_reload_time_ms, last_reload_at.
        """
        with self._hot_reload_lock:
            avg_ms = 0.0
            if self._reload_count > 0:
                avg_ms = (self._total_reload_time / self._reload_count) * 1000.0
            return {
                "reload_count": self._reload_count,
                "avg_reload_time_ms": avg_ms,
                "last_reload_at": self._last_reload_at,
            }

    def load_all(self) -> int:
        """
        Carga todos los plugins desde las rutas configuradas.

        Returns:
            Número de plugins cargados
        """
        loaded_count = 0
        for path in self._plugin_paths:
            path_obj = Path(path)
            if path_obj.is_file():
                plugin = self._loader.load_from_file(path)
                if plugin and self._registry.register(plugin):
                    loaded_count += 1
            elif path_obj.is_dir():
                plugins = self._loader.load_from_directory(path, recursive=True)
                for plugin in plugins:
                    if self._registry.register(plugin):
                        loaded_count += 1
            else:
                logger.warning(f"Ruta de plugin no válida: {path}")

        logger.info(f"Total de plugins cargados: {loaded_count}")
        return loaded_count

    def load_from_file(self, file_path: str, plugin_class_name: Optional[str] = None) -> bool:
        """Load a plugin from a file.

        Args:
            file_path: Path to the file.
            plugin_class_name: Class name (optional).

        Returns:
            True if loaded and registered successfully.
        """
        file_path = str(Path(file_path).resolve())
        plugin = self._loader.load_from_file(file_path, plugin_class_name)
        if plugin:
            success = self._registry.register(plugin)
            if success:
                # Track the file for hot-reload
                self._file_to_plugin[file_path] = plugin.name
                # Register dependencies if plugin has metadata
                deps = getattr(plugin, "dependencies", [])
                if not deps:
                    metadata = getattr(plugin, "metadata", None)
                    if hasattr(metadata, "dependencies"):
                        deps = metadata.dependencies or []
                self._dependency_resolver.add_plugin(plugin.name, deps)
            return success
        return False

    def load_from_directory(self, directory: str, recursive: bool = False) -> int:
        """
        Carga plugins desde un directorio.

        Args:
            directory: Directorio a escanear
            recursive: Si buscar recursivamente

        Returns:
            Número de plugins cargados
        """
        plugins = self._loader.load_from_directory(directory, recursive)
        loaded_count = 0
        for plugin in plugins:
            if self._registry.register(plugin):
                loaded_count += 1
        return loaded_count

    def load_from_module(self, module_name: str, plugin_class_name: str) -> bool:
        """
        Carga un plugin desde un módulo Python.

        Args:
            module_name: Nombre del módulo
            plugin_class_name: Nombre de la clase

        Returns:
            True si se cargó exitosamente
        """
        plugin = self._loader.load_from_module(module_name, plugin_class_name)
        if plugin:
            return self._registry.register(plugin)
        return False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Obtiene un plugin por nombre.

        Args:
            name: Nombre del plugin

        Returns:
            Instancia del plugin o None
        """
        return self._registry.get(name)

    def get_all_plugins(self, plugin_type: Optional[str] = None) -> List[Plugin]:
        """
        Obtiene todos los plugins.

        Args:
            plugin_type: Tipo de plugin (opcional)

        Returns:
            Lista de plugins
        """
        return self._registry.get_all(plugin_type)

    def unregister(self, name: str) -> bool:
        """
        Desregistra un plugin.

        Args:
            name: Nombre del plugin

        Returns:
            True si se desregistró exitosamente
        """
        return self._registry.unregister(name)

    def add_plugin_path(self, path: str) -> None:
        """
        Agrega una ruta para buscar plugins.

        Args:
            path: Ruta a agregar
        """
        if path not in self._plugin_paths:
            self._plugin_paths.append(path)
            logger.debug(f"Ruta de plugin agregada: {path}")

    def get_plugin_paths(self) -> List[str]:
        """Obtiene todas las rutas de plugins configuradas."""
        return self._plugin_paths.copy()

    @property
    def registry(self) -> PluginRegistry:
        """Get the plugin registry."""
        return self._registry

    @property
    def dependency_resolver(self) -> PluginDependencyResolver:
        """Get the dependency resolver."""
        return self._dependency_resolver

    def start_hot_reload(self) -> bool:
        """
        Inicia el sistema de hot-reload.

        Returns:
            True si se inició exitosamente
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog no está disponible, hot-reload deshabilitado")
            return False

        if self._observer is not None:
            logger.warning("Hot-reload ya está activo")
            return False

        try:
            self._observer = Observer()
            handler = PluginFileHandler(self, self._hot_reload_debounce)

            # Observar todos los directorios de plugins
            for path_str in self._plugin_paths:
                path = Path(path_str)
                if path.is_dir():
                    self._observer.schedule(handler, str(path), recursive=True)
                    logger.info(f"Hot-reload activo para: {path}")
                elif path.is_file():
                    # Observar el directorio padre del archivo
                    parent_dir = path.parent
                    if parent_dir.is_dir():
                        self._observer.schedule(handler, str(parent_dir), recursive=False)
                        logger.info(f"Hot-reload activo para directorio: {parent_dir}")

            self._observer.start()
            logger.info("Sistema de hot-reload iniciado")
            return True
        except Exception as e:
            logger.error(f"Error iniciando hot-reload: {e}", exc_info=True)
            return False

    def stop_hot_reload(self) -> None:
        """Detiene el sistema de hot-reload."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Sistema de hot-reload detenido")

    def is_hot_reload_active(self) -> bool:
        """Verifica si el hot-reload está activo."""
        return self._observer is not None and self._observer.is_alive()

    def clear(self) -> None:
        """Limpia todos los plugins."""
        # Detener hot-reload si está activo
        if self._observer is not None:
            self.stop_hot_reload()

        self._registry.clear()
        self._file_to_plugin.clear()
        logger.debug("Todos los plugins han sido limpiados")

    def __del__(self) -> None:
        """Asegura que el observer se detenga al destruir el objeto."""
        if self._observer is not None:
            try:
                self.stop_hot_reload()
            except Exception:
                pass
