"""Gestor principal de plugins con hot-reload."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
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

from .plugin_interface import Plugin
from .plugin_loader import PluginLoader
from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginFileHandler(FileSystemEventHandler):
    """Manejador de eventos del sistema de archivos para hot-reload de plugins."""

    def __init__(self, manager: "PluginManager", debounce_seconds: float = 0.5) -> None:
        """
        Inicializa el manejador.
        
        Args:
            manager: Instancia del PluginManager
            debounce_seconds: Tiempo de espera antes de recargar (evita múltiples recargas)
        """
        super().__init__()
        self._manager = manager
        self._debounce_seconds = debounce_seconds
        self._pending_reloads: Dict[str, float] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Se llama cuando se modifica un archivo."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return
        
        # Debounce: esperar un poco antes de recargar
        current_time = time.time()
        with self._lock:
            last_reload = self._pending_reloads.get(str(file_path), 0)
            if current_time - last_reload < self._debounce_seconds:
                return
            self._pending_reloads[str(file_path)] = current_time
        
        logger.info(f"Archivo modificado detectado: {file_path}, recargando plugin...")
        self._manager._reload_plugin_file(str(file_path))

    def on_created(self, event: FileSystemEvent) -> None:
        """Se llama cuando se crea un nuevo archivo."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return
        
        logger.info(f"Nuevo archivo detectado: {file_path}, cargando plugin...")
        self._manager.load_from_file(str(file_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Se llama cuando se elimina un archivo."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not file_path.suffix == ".py":
            return
        
        # Intentar desregistrar el plugin si estaba cargado
        logger.info(f"Archivo eliminado detectado: {file_path}, desregistrando plugin...")
        # Buscar el plugin por ruta (esto requeriría tracking adicional)
        # Por ahora solo logueamos


class PluginManager:
    """Gestor que coordina carga, registro y uso de plugins con hot-reload."""

    def __init__(
        self,
        plugin_paths: Optional[List[str]] = None,
        enable_hot_reload: bool = False,
        hot_reload_debounce: float = 0.5,
    ) -> None:
        """
        Inicializa el gestor de plugins.

        Args:
            plugin_paths: Lista de rutas donde buscar plugins
            enable_hot_reload: Si habilitar hot-reload automático
            hot_reload_debounce: Tiempo de espera antes de recargar (segundos)
        """
        self._registry = PluginRegistry()
        self._loader = PluginLoader()
        self._plugin_paths = plugin_paths or []
        self._enable_hot_reload = enable_hot_reload and WATCHDOG_AVAILABLE
        self._hot_reload_debounce = hot_reload_debounce
        
        # Tracking de archivos cargados para hot-reload
        self._file_to_plugin: Dict[str, str] = {}  # file_path -> plugin_name
        
        # Sistema de hot-reload
        self._observer: Optional[Observer] = None
        self._hot_reload_lock = threading.Lock()

        # Cargar plugins automáticamente si hay rutas
        if self._plugin_paths:
            self.load_all()
        
        # Iniciar hot-reload si está habilitado
        if self._enable_hot_reload:
            self.start_hot_reload()

    def _reload_plugin_file(self, file_path: str) -> bool:
        """
        Recarga un plugin desde un archivo (usado por hot-reload).
        
        Args:
            file_path: Ruta al archivo del plugin
            
        Returns:
            True si se recargó exitosamente
        """
        with self._hot_reload_lock:
            # Buscar el plugin asociado a este archivo
            plugin_name = self._file_to_plugin.get(file_path)
            
            if plugin_name:
                # Desregistrar el plugin anterior
                self._registry.unregister(plugin_name)
                logger.debug(f"Plugin '{plugin_name}' desregistrado para recarga")
            
            # Cargar el plugin nuevamente
            result = self.load_from_file(file_path)
            
            if result and plugin_name:
                # Actualizar el mapeo
                new_plugin = self._registry.get(plugin_name)
                if new_plugin:
                    self._file_to_plugin[file_path] = new_plugin.name
                    logger.info(f"Plugin '{plugin_name}' recargado exitosamente")
            
            return result

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
        """
        Carga un plugin desde un archivo.

        Args:
            file_path: Ruta al archivo
            plugin_class_name: Nombre de la clase (opcional)

        Returns:
            True si se cargó y registró exitosamente
        """
        file_path = str(Path(file_path).resolve())
        plugin = self._loader.load_from_file(file_path, plugin_class_name)
        if plugin:
            success = self._registry.register(plugin)
            if success:
                # Trackear el archivo para hot-reload
                self._file_to_plugin[file_path] = plugin.name
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
        """Obtiene el registro de plugins."""
        return self._registry

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

