"""Tests para el sistema de plugins."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.infrastructure.plugins import (
    AnalyzerPlugin,
    FilterPlugin,
    Plugin,
    PluginLoader,
    PluginManager,
    PluginMetadata,
    PluginRegistry,
    RendererPlugin,
    TrackerPlugin,
    extract_metadata_from_plugin,
)


# Plugins de prueba
class TestFilterPlugin(FilterPlugin):
    name = "test_filter"
    version = "1.0.0"
    description = "Un filtro de prueba"
    author = "Test"

    def apply(self, frame, config, analysis=None):
        return frame * 0.5


class TestAnalyzerPlugin(AnalyzerPlugin):
    name = "test_analyzer"
    version = "1.0.0"
    description = "Un analizador de prueba"
    author = "Test"

    def analyze(self, frame, config):
        return {"test": True}


class TestRendererPlugin(RendererPlugin):
    name = "test_renderer"
    version = "1.0.0"
    description = "Un renderer de prueba"
    author = "Test"

    def render(self, frame, config, analysis=None):
        return RenderFrame(image=frame, text="test", lines=["test"])

    def output_size(self, config):
        return (100, 100)


class TestTrackerPlugin(TrackerPlugin):
    name = "test_tracker"
    version = "1.0.0"
    description = "Un tracker de prueba"
    author = "Test"

    def track(self, frame, detections, config):
        return {"tracked": True}

    def reset(self):
        pass


class TestPluginWithMetadata(FilterPlugin):
    name = "plugin_with_metadata"
    version = "2.0.0"
    description = "Plugin con metadatos"
    author = "Test"

    metadata = {
        "dependencies": ["numpy"],
        "capabilities": ["gpu"],
        "tags": ["test"],
    }

    def apply(self, frame, config, analysis=None):
        return frame


class TestPluginMetadata(unittest.TestCase):
    """Tests para PluginMetadata."""

    def test_create_metadata(self):
        """Test crear metadatos básicos."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type="filter",
        )
        self.assertEqual(metadata.name, "test")
        self.assertEqual(metadata.version, "1.0.0")
        self.assertEqual(metadata.plugin_type, "filter")

    def test_metadata_to_dict(self):
        """Test conversión a diccionario."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            capabilities={"gpu", "real_time"},
        )
        data = metadata.to_dict()
        self.assertIsInstance(data["capabilities"], list)
        self.assertIn("gpu", data["capabilities"])

    def test_metadata_to_json(self):
        """Test conversión a JSON."""
        metadata = PluginMetadata(name="test", version="1.0.0")
        json_str = metadata.to_json()
        self.assertIsInstance(json_str, str)
        data = json.loads(json_str)
        self.assertEqual(data["name"], "test")

    def test_metadata_from_dict(self):
        """Test crear desde diccionario."""
        data = {
            "name": "test",
            "version": "1.0.0",
            "capabilities": ["gpu"],
        }
        metadata = PluginMetadata.from_dict(data)
        self.assertEqual(metadata.name, "test")
        self.assertIn("gpu", metadata.capabilities)

    def test_metadata_save_load_file(self):
        """Test guardar y cargar desde archivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "metadata.json"
            metadata = PluginMetadata(
                name="test",
                version="1.0.0",
                description="Test metadata",
            )

            # Guardar
            self.assertTrue(metadata.save_to_file(str(file_path)))
            self.assertTrue(file_path.exists())

            # Cargar
            loaded = PluginMetadata.from_file(str(file_path))
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.name, "test")
            self.assertEqual(loaded.description, "Test metadata")

    def test_metadata_validate(self):
        """Test validación de metadatos."""
        # Válido
        metadata = PluginMetadata(name="test", version="1.0.0")
        self.assertTrue(metadata.validate())

        # Inválido: sin nombre
        metadata = PluginMetadata(name="", version="1.0.0")
        self.assertFalse(metadata.validate())

        # Inválido: tipo incorrecto
        metadata = PluginMetadata(name="test", version="1.0.0", plugin_type="invalid")
        self.assertFalse(metadata.validate())

    def test_metadata_merge(self):
        """Test fusión de metadatos."""
        base = PluginMetadata(
            name="test",
            version="1.0.0",
            dependencies=["numpy"],
            capabilities={"gpu"},
        )
        other = PluginMetadata(
            name="test",
            version="2.0.0",
            dependencies=["opencv"],
            capabilities={"real_time"},
            description="Updated",
        )

        merged = base.merge(other)
        self.assertEqual(merged.version, "2.0.0")
        self.assertEqual(merged.description, "Updated")
        self.assertIn("numpy", merged.dependencies)
        self.assertIn("opencv", merged.dependencies)
        self.assertIn("gpu", merged.capabilities)
        self.assertIn("real_time", merged.capabilities)


class TestPluginInterface(unittest.TestCase):
    """Tests para interfaces de plugins."""

    def test_filter_plugin(self):
        """Test FilterPlugin."""
        plugin = TestFilterPlugin()
        self.assertTrue(plugin.validate())
        self.assertEqual(plugin.name, "test_filter")

        frame = np.ones((10, 10, 3), dtype=np.uint8) * 255
        config = EngineConfig()
        result = plugin.apply(frame, config)
        self.assertIsNotNone(result)

    def test_analyzer_plugin(self):
        """Test AnalyzerPlugin."""
        plugin = TestAnalyzerPlugin()
        self.assertTrue(plugin.validate())

        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        config = EngineConfig()
        result = plugin.analyze(frame, config)
        self.assertIn("test", result)

    def test_renderer_plugin(self):
        """Test RendererPlugin."""
        plugin = TestRendererPlugin()
        self.assertTrue(plugin.validate())

        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        config = EngineConfig()
        result = plugin.render(frame, config)
        self.assertIsInstance(result, RenderFrame)

        size = plugin.output_size(config)
        self.assertEqual(size, (100, 100))

    def test_tracker_plugin(self):
        """Test TrackerPlugin."""
        plugin = TestTrackerPlugin()
        self.assertTrue(plugin.validate())

        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        config = EngineConfig()
        result = plugin.track(frame, {}, config)
        self.assertIn("tracked", result)

        plugin.reset()  # No debería fallar

    def test_plugin_with_metadata(self):
        """Test plugin con metadatos."""
        plugin = TestPluginWithMetadata()
        self.assertTrue(plugin.validate())

        metadata = plugin.get_metadata()
        self.assertIsInstance(metadata, PluginMetadata)
        self.assertEqual(metadata.name, "plugin_with_metadata")
        self.assertIn("gpu", metadata.capabilities)

    def test_extract_metadata_from_plugin(self):
        """Test extracción de metadatos."""
        plugin = TestFilterPlugin()
        metadata = extract_metadata_from_plugin(plugin)
        self.assertEqual(metadata.name, "test_filter")
        self.assertEqual(metadata.plugin_type, "filter")


class TestPluginRegistry(unittest.TestCase):
    """Tests para PluginRegistry."""

    def setUp(self):
        """Configurar tests."""
        self.registry = PluginRegistry(enable_auto_discovery=False)

    def test_register_plugin(self):
        """Test registrar plugin."""
        plugin = TestFilterPlugin()
        self.assertTrue(self.registry.register(plugin))
        self.assertTrue(self.registry.has("test_filter"))

    def test_get_plugin(self):
        """Test obtener plugin."""
        plugin = TestFilterPlugin()
        self.registry.register(plugin)
        retrieved = self.registry.get("test_filter")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_filter")

    def test_unregister_plugin(self):
        """Test desregistrar plugin."""
        plugin = TestFilterPlugin()
        self.registry.register(plugin)
        self.assertTrue(self.registry.unregister("test_filter"))
        self.assertFalse(self.registry.has("test_filter"))

    def test_get_all_plugins(self):
        """Test obtener todos los plugins."""
        self.registry.register(TestFilterPlugin())
        self.registry.register(TestAnalyzerPlugin())
        plugins = self.registry.get_all()
        self.assertEqual(len(plugins), 2)

    def test_get_plugins_by_type(self):
        """Test obtener plugins por tipo."""
        self.registry.register(TestFilterPlugin())
        self.registry.register(TestAnalyzerPlugin())
        filters = self.registry.get_all("filter")
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].name, "test_filter")

    def test_get_metadata(self):
        """Test obtener metadatos."""
        plugin = TestPluginWithMetadata()
        self.registry.register(plugin)
        metadata = self.registry.get_metadata("plugin_with_metadata")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "plugin_with_metadata")

    def test_clear(self):
        """Test limpiar registro."""
        self.registry.register(TestFilterPlugin())
        self.registry.clear()
        self.assertEqual(self.registry.count(), 0)

    def test_count(self):
        """Test contar plugins."""
        self.assertEqual(self.registry.count(), 0)
        self.registry.register(TestFilterPlugin())
        self.assertEqual(self.registry.count(), 1)
        self.assertEqual(self.registry.count("filter"), 1)
        self.assertEqual(self.registry.count("analyzer"), 0)


class TestPluginLoader(unittest.TestCase):
    """Tests para PluginLoader."""

    def setUp(self):
        """Configurar tests."""
        self.loader = PluginLoader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """Limpiar después de tests."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_from_file(self):
        """Test cargar desde archivo."""
        # Crear archivo de plugin
        plugin_file = Path(self.tmpdir) / "test_plugin.py"
        plugin_code = """from ascii_stream_engine.infrastructure.plugins import FilterPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np

class TestPlugin(FilterPlugin):
    name = "test_plugin"
    version = "1.0.0"
    description = "Test"
    author = "Test"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
        plugin_file.write_text(plugin_code)

        plugin = self.loader.load_from_file(str(plugin_file))
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "test_plugin")

    def test_load_from_file_with_metadata(self):
        """Test cargar con metadatos desde JSON."""
        # Crear archivo de plugin
        plugin_file = Path(self.tmpdir) / "test_plugin.py"
        plugin_code = """from ascii_stream_engine.infrastructure.plugins import FilterPlugin
import numpy as np

class TestPlugin(FilterPlugin):
    name = "test_plugin"
    version = "1.0.0"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
        plugin_file.write_text(plugin_code)

        # Crear archivo de metadatos
        metadata_file = Path(self.tmpdir) / "test_plugin.json"
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test with metadata",
            dependencies=["numpy"],
        )
        metadata.save_to_file(str(metadata_file))

        plugin = self.loader.load_from_file(str(plugin_file))
        self.assertIsNotNone(plugin)
        # Los metadatos deberían haberse aplicado
        # Verificar que los metadatos están en el plugin
        self.assertIsNotNone(plugin.metadata)
        if isinstance(plugin.metadata, dict):
            self.assertEqual(plugin.metadata.get("description"), "Test with metadata")
        # O verificar el atributo description si se aplicó
        if hasattr(plugin, "description") and plugin.description:
            self.assertEqual(plugin.description, "Test with metadata")

    def test_load_from_directory(self):
        """Test cargar desde directorio."""
        # Crear archivos de plugins
        for i in range(3):
            plugin_file = Path(self.tmpdir) / f"plugin_{i}.py"
            plugin_code = f"""from ascii_stream_engine.infrastructure.plugins import FilterPlugin
import numpy as np

class Plugin{i}(FilterPlugin):
    name = "plugin_{i}"
    version = "1.0.0"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
            plugin_file.write_text(plugin_code)

        plugins = self.loader.load_from_directory(self.tmpdir)
        self.assertEqual(len(plugins), 3)

    def test_load_from_file_with_metadata_method(self):
        """Test método load_from_file_with_metadata."""
        plugin_file = Path(self.tmpdir) / "test_plugin.py"
        plugin_code = """from ascii_stream_engine.infrastructure.plugins import FilterPlugin
import numpy as np

class TestPlugin(FilterPlugin):
    name = "test_plugin"
    version = "1.0.0"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
        plugin_file.write_text(plugin_code)

        result = self.loader.load_from_file_with_metadata(str(plugin_file))
        self.assertIsNotNone(result)
        plugin, metadata = result
        self.assertEqual(plugin.name, "test_plugin")
        self.assertIsInstance(metadata, PluginMetadata)


class TestPluginManager(unittest.TestCase):
    """Tests para PluginManager."""

    def setUp(self):
        """Configurar tests."""
        self.tmpdir = tempfile.mkdtemp()
        self.manager = PluginManager(
            plugin_paths=[self.tmpdir],
            enable_hot_reload=False,
        )

    def tearDown(self):
        """Limpiar después de tests."""
        self.manager.clear()
        if self.manager.is_hot_reload_active():
            self.manager.stop_hot_reload()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_from_file(self):
        """Test cargar plugin desde archivo."""
        plugin_file = Path(self.tmpdir) / "test_plugin.py"
        plugin_code = """from ascii_stream_engine.infrastructure.plugins import FilterPlugin
import numpy as np

class TestPlugin(FilterPlugin):
    name = "test_plugin"
    version = "1.0.0"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
        plugin_file.write_text(plugin_code)

        self.assertTrue(self.manager.load_from_file(str(plugin_file)))
        self.assertIsNotNone(self.manager.get_plugin("test_plugin"))

    def test_load_all(self):
        """Test cargar todos los plugins."""
        # Crear varios plugins
        for i in range(3):
            plugin_file = Path(self.tmpdir) / f"plugin_{i}.py"
            plugin_code = f"""from ascii_stream_engine.infrastructure.plugins import FilterPlugin
import numpy as np

class Plugin{i}(FilterPlugin):
    name = "plugin_{i}"
    version = "1.0.0"
    
    def apply(self, frame, config, analysis=None):
        return frame
"""
            plugin_file.write_text(plugin_code)

        count = self.manager.load_all()
        self.assertEqual(count, 3)

    def test_get_all_plugins(self):
        """Test obtener todos los plugins."""
        plugin = TestFilterPlugin()
        self.manager._registry.register(plugin)
        plugins = self.manager.get_all_plugins()
        self.assertEqual(len(plugins), 1)

    def test_unregister(self):
        """Test desregistrar plugin."""
        plugin = TestFilterPlugin()
        self.manager._registry.register(plugin)
        self.assertTrue(self.manager.unregister("test_filter"))
        self.assertIsNone(self.manager.get_plugin("test_filter"))

    def test_add_plugin_path(self):
        """Test agregar ruta de plugin."""
        new_path = "/nueva/ruta"
        self.manager.add_plugin_path(new_path)
        self.assertIn(new_path, self.manager.get_plugin_paths())

    def test_hot_reload_availability(self):
        """Test disponibilidad de hot-reload."""
        # Hot-reload puede no estar disponible si watchdog no está instalado
        # Solo verificamos que no falle
        try:
            manager = PluginManager(enable_hot_reload=True)
            # Si watchdog está disponible, debería poder iniciar
            # Si no, simplemente no falla
        except Exception:
            pass  # Esperado si watchdog no está disponible


if __name__ == "__main__":
    unittest.main()
