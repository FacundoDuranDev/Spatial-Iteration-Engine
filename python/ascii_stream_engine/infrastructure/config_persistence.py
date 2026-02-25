"""Config persistence service with atomic writes and schema versioning.

Provides thread-safe save/load of EngineConfig to/from JSON files,
with versioning, atomic writes, and diff tracking.
"""

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..domain.config import EngineConfig, NeuralConfig

logger = logging.getLogger(__name__)


class ConfigPersistenceError(Exception):
    """Raised when config persistence operations fail."""

    pass


class ConfigPersistence:
    """Thread-safe config save/load with versioning and atomic writes."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(self, default_path: str = "engine_config.json") -> None:
        """Initialize config persistence.

        Args:
            default_path: Default file path for save/load operations.
        """
        self._default_path = default_path
        self._lock = threading.Lock()

    def save(self, config: EngineConfig, path: Optional[str] = None) -> None:
        """Save config to a JSON file.

        Args:
            config: EngineConfig instance to save.
            path: File path (uses default_path if None).

        Raises:
            ConfigPersistenceError: If save fails.
        """
        target_path = path or self._default_path
        try:
            envelope = self._build_envelope(config)
            json_str = json.dumps(envelope, indent=2, ensure_ascii=False)
            with self._lock:
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(json_str)
            logger.info(f"Config saved to {target_path}")
        except Exception as e:
            raise ConfigPersistenceError(f"Failed to save config to {target_path}: {e}") from e

    def save_atomic(self, config: EngineConfig, path: Optional[str] = None) -> None:
        """Save config atomically using a temp file and os.replace.

        Writes to a .tmp file first, then renames for crash safety.

        Args:
            config: EngineConfig instance to save.
            path: File path (uses default_path if None).

        Raises:
            ConfigPersistenceError: If save fails.
        """
        target_path = path or self._default_path
        tmp_path = None
        try:
            envelope = self._build_envelope(config)
            json_str = json.dumps(envelope, indent=2, ensure_ascii=False)
            with self._lock:
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                # Write to temp file in the same directory for atomic replace
                dir_name = str(Path(target_path).parent)
                fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix=".config_", dir=dir_name)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(json_str)
                    os.replace(tmp_path, target_path)
                    tmp_path = None  # Successfully replaced, no cleanup needed
                except Exception:
                    # Close fd if still open, cleanup handled in finally
                    raise
            logger.info(f"Config saved atomically to {target_path}")
        except ConfigPersistenceError:
            raise
        except Exception as e:
            raise ConfigPersistenceError(
                f"Failed to save config atomically to {target_path}: {e}"
            ) from e
        finally:
            # Clean up tmp file if it still exists
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def load(self, path: Optional[str] = None) -> EngineConfig:
        """Load config from a JSON file.

        Args:
            path: File path (uses default_path if None).

        Returns:
            EngineConfig instance.

        Raises:
            ConfigPersistenceError: If file is missing, corrupt, or schema version mismatches.
        """
        target_path = path or self._default_path
        with self._lock:
            if not Path(target_path).exists():
                raise ConfigPersistenceError(f"Config file not found: {target_path}")
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigPersistenceError(
                    f"Config file is corrupt (invalid JSON): {target_path}: {e}"
                ) from e
            except Exception as e:
                raise ConfigPersistenceError(
                    f"Failed to read config file {target_path}: {e}"
                ) from e

        # Validate envelope
        if not isinstance(data, dict):
            raise ConfigPersistenceError(
                f"Config file has invalid format (expected object): {target_path}"
            )

        schema_version = data.get("schema_version")
        if schema_version is None:
            raise ConfigPersistenceError(f"Config file missing schema_version: {target_path}")
        if schema_version != self.SCHEMA_VERSION:
            raise ConfigPersistenceError(
                f"Schema version mismatch: file has {schema_version}, "
                f"expected {self.SCHEMA_VERSION}"
            )

        config_data = data.get("config")
        if config_data is None:
            raise ConfigPersistenceError(f"Config file missing 'config' key: {target_path}")

        try:
            return self._dict_to_config(config_data)
        except Exception as e:
            raise ConfigPersistenceError(f"Failed to deserialize config: {e}") from e

    def exists(self, path: Optional[str] = None) -> bool:
        """Check if a config file exists.

        Args:
            path: File path (uses default_path if None).

        Returns:
            True if file exists.
        """
        target_path = path or self._default_path
        return Path(target_path).exists()

    def get_diff(self, config_a: EngineConfig, config_b: EngineConfig) -> Dict[str, Any]:
        """Compute the difference between two configs.

        Args:
            config_a: First config (old).
            config_b: Second config (new).

        Returns:
            Dict with keys: 'changed' (key -> (old, new)), 'added' (key -> val),
            'removed' (key -> val).
        """
        dict_a = self._config_to_dict(config_a)
        dict_b = self._config_to_dict(config_b)

        changed: Dict[str, Tuple[Any, Any]] = {}
        added: Dict[str, Any] = {}
        removed: Dict[str, Any] = {}

        all_keys = set(dict_a.keys()) | set(dict_b.keys())
        for key in all_keys:
            in_a = key in dict_a
            in_b = key in dict_b
            if in_a and in_b:
                if dict_a[key] != dict_b[key]:
                    changed[key] = (dict_a[key], dict_b[key])
            elif in_b and not in_a:
                added[key] = dict_b[key]
            elif in_a and not in_b:
                removed[key] = dict_a[key]

        return {"changed": changed, "added": added, "removed": removed}

    def get_schema_version(self) -> str:
        """Return the current schema version.

        Returns:
            Schema version string.
        """
        return self.SCHEMA_VERSION

    # --- Private helpers ---

    def _build_envelope(self, config: EngineConfig) -> Dict[str, Any]:
        """Build the JSON envelope with metadata."""
        return {
            "schema_version": self.SCHEMA_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "config": self._config_to_dict(config),
        }

    @staticmethod
    def _config_to_dict(config: EngineConfig) -> Dict[str, Any]:
        """Convert EngineConfig to a JSON-serializable dict."""
        data = {}
        for f in fields(config):
            value = getattr(config, f.name)
            if isinstance(value, NeuralConfig):
                value = asdict(value)
            data[f.name] = value
        return data

    @staticmethod
    def _dict_to_config(data: Dict[str, Any]) -> EngineConfig:
        """Convert a dict back to EngineConfig.

        Handles NeuralConfig sub-object deserialization.
        """
        config_data = dict(data)

        # Handle NeuralConfig sub-object
        neural_data = config_data.get("neural")
        if neural_data is not None and isinstance(neural_data, dict):
            # Convert tuple fields stored as lists
            if "inference_resolution" in neural_data and isinstance(
                neural_data["inference_resolution"], list
            ):
                neural_data["inference_resolution"] = tuple(neural_data["inference_resolution"])
            config_data["neural"] = NeuralConfig(**neural_data)

        # Filter to only valid EngineConfig fields
        valid_fields = {f.name for f in fields(EngineConfig)}
        filtered_data = {k: v for k, v in config_data.items() if k in valid_fields}

        return EngineConfig(**filtered_data)
