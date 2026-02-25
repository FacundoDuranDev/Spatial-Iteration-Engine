"""Tests for ConfigPersistence service."""

import json
import os
import tempfile
import threading
import time

import pytest

from ascii_stream_engine.domain.config import EngineConfig, NeuralConfig
from ascii_stream_engine.infrastructure.config_persistence import (
    ConfigPersistence,
    ConfigPersistenceError,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def persistence(tmp_dir):
    """Create a ConfigPersistence with a temp default path."""
    return ConfigPersistence(default_path=os.path.join(tmp_dir, "test_config.json"))


@pytest.fixture
def default_config():
    """Create a default EngineConfig."""
    return EngineConfig()


@pytest.fixture
def custom_config():
    """Create a custom EngineConfig with non-default values."""
    return EngineConfig(
        fps=60,
        grid_w=200,
        grid_h=100,
        charset=" .+#@",
        render_mode="ascii",
        contrast=2.0,
        brightness=50,
        host="192.168.1.1",
        port=5678,
        enable_events=True,
        plugin_paths=["/path/to/plugins"],
    )


class TestConfigPersistenceRoundTrip:
    """Tests for save/load round-trip."""

    def test_save_load_default_config(self, persistence, default_config):
        """Default config round-trips through save/load."""
        persistence.save(default_config)
        loaded = persistence.load()
        assert loaded.fps == default_config.fps
        assert loaded.grid_w == default_config.grid_w
        assert loaded.grid_h == default_config.grid_h
        assert loaded.charset == default_config.charset
        assert loaded.render_mode == default_config.render_mode
        assert loaded.contrast == default_config.contrast
        assert loaded.brightness == default_config.brightness

    def test_save_load_custom_config(self, persistence, custom_config):
        """Custom config round-trips through save/load."""
        persistence.save(custom_config)
        loaded = persistence.load()
        assert loaded.fps == 60
        assert loaded.grid_w == 200
        assert loaded.grid_h == 100
        assert loaded.charset == " .+#@"
        assert loaded.contrast == 2.0
        assert loaded.brightness == 50
        assert loaded.host == "192.168.1.1"
        assert loaded.port == 5678
        assert loaded.enable_events is True
        assert loaded.plugin_paths == ["/path/to/plugins"]

    def test_save_load_with_neural_config(self, persistence):
        """Config with NeuralConfig sub-object round-trips."""
        config = EngineConfig(
            neural=NeuralConfig(
                enabled=True,
                style_encoder_path="model.onnx",
                inference_resolution=(320, 240),
            )
        )
        persistence.save(config)
        loaded = persistence.load()
        assert loaded.neural is not None
        assert loaded.neural.enabled is True
        assert loaded.neural.style_encoder_path == "model.onnx"
        assert loaded.neural.inference_resolution == (320, 240)

    def test_save_load_with_explicit_path(self, persistence, tmp_dir, default_config):
        """Save/load with an explicit path different from default."""
        explicit_path = os.path.join(tmp_dir, "explicit_config.json")
        persistence.save(default_config, path=explicit_path)
        loaded = persistence.load(path=explicit_path)
        assert loaded.fps == default_config.fps


class TestAtomicSave:
    """Tests for atomic write operations."""

    def test_save_atomic_round_trip(self, persistence, default_config):
        """Atomic save produces a loadable file."""
        persistence.save_atomic(default_config)
        loaded = persistence.load()
        assert loaded.fps == default_config.fps

    def test_save_atomic_no_tmp_artifacts(self, persistence, tmp_dir, default_config):
        """Atomic save leaves no .tmp files on success."""
        persistence.save_atomic(default_config)
        files = os.listdir(tmp_dir)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    def test_save_atomic_preserves_existing_on_success(
        self, persistence, tmp_dir, default_config, custom_config
    ):
        """Atomic save correctly replaces existing file."""
        persistence.save_atomic(default_config)
        persistence.save_atomic(custom_config)
        loaded = persistence.load()
        assert loaded.fps == 60  # custom_config value


class TestLoadErrors:
    """Tests for error handling during load."""

    def test_load_missing_file(self, persistence):
        """Load raises on missing file."""
        with pytest.raises(ConfigPersistenceError, match="not found"):
            persistence.load()

    def test_load_corrupt_json(self, persistence, tmp_dir):
        """Load raises on corrupt JSON."""
        path = os.path.join(tmp_dir, "test_config.json")
        with open(path, "w") as f:
            f.write("{invalid json")
        with pytest.raises(ConfigPersistenceError, match="corrupt"):
            persistence.load()

    def test_load_schema_mismatch(self, persistence, tmp_dir):
        """Load raises on schema version mismatch."""
        path = os.path.join(tmp_dir, "test_config.json")
        data = {
            "schema_version": "999.0.0",
            "saved_at": "2024-01-01T00:00:00",
            "config": {},
        }
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(ConfigPersistenceError, match="Schema version mismatch"):
            persistence.load()

    def test_load_missing_schema_version(self, persistence, tmp_dir):
        """Load raises when schema_version is missing."""
        path = os.path.join(tmp_dir, "test_config.json")
        data = {"config": {}}
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(ConfigPersistenceError, match="missing schema_version"):
            persistence.load()

    def test_load_missing_config_key(self, persistence, tmp_dir):
        """Load raises when 'config' key is missing."""
        path = os.path.join(tmp_dir, "test_config.json")
        data = {"schema_version": "1.0.0", "saved_at": "2024-01-01T00:00:00"}
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(ConfigPersistenceError, match="missing 'config' key"):
            persistence.load()


class TestJsonEnvelope:
    """Tests for JSON envelope metadata."""

    def test_envelope_contains_schema_version(self, persistence, tmp_dir, default_config):
        """Saved JSON contains schema_version."""
        path = os.path.join(tmp_dir, "test_config.json")
        persistence.save(default_config, path=path)
        with open(path, "r") as f:
            data = json.load(f)
        assert data["schema_version"] == "1.0.0"

    def test_envelope_contains_saved_at(self, persistence, tmp_dir, default_config):
        """Saved JSON contains saved_at timestamp."""
        path = os.path.join(tmp_dir, "test_config.json")
        persistence.save(default_config, path=path)
        with open(path, "r") as f:
            data = json.load(f)
        assert "saved_at" in data
        assert isinstance(data["saved_at"], str)

    def test_envelope_contains_config(self, persistence, tmp_dir, default_config):
        """Saved JSON contains config object."""
        path = os.path.join(tmp_dir, "test_config.json")
        persistence.save(default_config, path=path)
        with open(path, "r") as f:
            data = json.load(f)
        assert "config" in data
        assert isinstance(data["config"], dict)


class TestGetDiff:
    """Tests for config diff detection."""

    def test_diff_no_changes(self, persistence, default_config):
        """Diff of identical configs shows no changes."""
        diff = persistence.get_diff(default_config, default_config)
        assert diff["changed"] == {}
        assert diff["added"] == {}
        assert diff["removed"] == {}

    def test_diff_changed_values(self, persistence, default_config, custom_config):
        """Diff detects changed values."""
        diff = persistence.get_diff(default_config, custom_config)
        assert "fps" in diff["changed"]
        old_fps, new_fps = diff["changed"]["fps"]
        assert old_fps == 20
        assert new_fps == 60

    def test_diff_multiple_changes(self, persistence):
        """Diff detects multiple changed fields."""
        config_a = EngineConfig(fps=20, grid_w=120, contrast=1.2)
        config_b = EngineConfig(fps=60, grid_w=200, contrast=2.5)
        diff = persistence.get_diff(config_a, config_b)
        assert "fps" in diff["changed"]
        assert "grid_w" in diff["changed"]
        assert "contrast" in diff["changed"]


class TestExists:
    """Tests for file existence check."""

    def test_exists_false_initially(self, persistence):
        """exists() returns False when no file saved."""
        assert persistence.exists() is False

    def test_exists_true_after_save(self, persistence, default_config):
        """exists() returns True after save."""
        persistence.save(default_config)
        assert persistence.exists() is True


class TestSchemaVersion:
    """Tests for schema version."""

    def test_get_schema_version(self, persistence):
        """get_schema_version() returns the current version."""
        assert persistence.get_schema_version() == "1.0.0"


class TestThreadSafety:
    """Tests for concurrent access."""

    def test_concurrent_save_load(self, persistence, tmp_dir):
        """Concurrent saves and loads do not corrupt data."""
        errors = []
        iterations = 20

        def writer(idx):
            try:
                config = EngineConfig(fps=20 + idx)
                persistence.save(config)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                if persistence.exists():
                    config = persistence.load()
                    # fps should be a valid value
                    assert 20 <= config.fps <= 120
            except ConfigPersistenceError:
                # File may not exist yet or be mid-write
                pass
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(iterations):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
