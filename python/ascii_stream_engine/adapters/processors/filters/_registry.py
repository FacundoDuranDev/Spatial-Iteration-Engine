"""Filter registry -- discovery, serialization, and deserialization of filters.

Provides ALL_FILTERS dict (name -> class), plus helpers to introspect, serialize,
and deserialize filter instances with their parameters. Used by the preset system
and Gradio dashboard for dynamic filter management.
"""

import inspect

from .base import BaseFilter

# Populated by _build_registry() at module load time.
ALL_FILTERS: dict = {}

# Parameters to exclude from serialization (inherited from BaseFilter).
_SKIP_PARAMS = {"self", "enabled"}


def _build_registry() -> dict:
    """Build name -> class mapping from sibling modules.

    Imports the parent package and iterates its exported names to find
    all BaseFilter subclasses.
    """
    import importlib

    pkg = importlib.import_module("ascii_stream_engine.adapters.processors.filters")
    registry = {}
    for attr_name in getattr(pkg, "__all__", dir(pkg)):
        cls = getattr(pkg, attr_name, None)
        if cls is None:
            continue
        if isinstance(cls, type) and issubclass(cls, BaseFilter) and cls is not BaseFilter:
            filter_name = getattr(cls, "name", None)
            if filter_name:
                registry[filter_name] = cls
    return registry


def get_filter_params(instance: BaseFilter) -> dict:
    """Extract current parameter values from a filter instance.

    Introspects the ``__init__`` signature and reads matching ``_param``
    attributes from the instance.
    """
    sig = inspect.signature(type(instance).__init__)
    params = {}
    for pname, param in sig.parameters.items():
        if pname in _SKIP_PARAMS:
            continue
        attr_name = f"_{pname}"
        if hasattr(instance, attr_name):
            val = getattr(instance, attr_name)
            # Convert numpy types to native Python for JSON serialization.
            if hasattr(val, "item"):
                val = val.item()
            elif isinstance(val, tuple):
                val = list(val)
            params[pname] = val
    return params


def set_filter_params(instance: BaseFilter, params: dict) -> None:
    """Set parameter values on a filter instance."""
    for key, value in params.items():
        attr_name = f"_{key}"
        if hasattr(instance, attr_name):
            setattr(instance, attr_name, value)


def serialize_filter(instance: BaseFilter) -> dict:
    """Serialize a filter instance to a JSON-compatible dict."""
    return {
        "name": instance.name,
        "class": type(instance).__name__,
        "params": get_filter_params(instance),
        "enabled": instance.enabled,
    }


def deserialize_filter(data: dict) -> BaseFilter:
    """Reconstruct a filter instance from a serialized dict.

    Raises ``KeyError`` if the filter name is not in the registry.
    """
    _ensure_registry()
    name = data["name"]
    if name not in ALL_FILTERS:
        raise KeyError(f"Unknown filter: {name!r}. Available: {sorted(ALL_FILTERS)}")
    cls = ALL_FILTERS[name]
    params = data.get("params", {})
    # Convert lists back to tuples for color params etc.
    sig = inspect.signature(cls.__init__)
    for pname, param in sig.parameters.items():
        if pname in params and param.default is not inspect.Parameter.empty:
            if isinstance(param.default, tuple) and isinstance(params[pname], list):
                params[pname] = tuple(params[pname])
    instance = cls(**params)
    instance.enabled = data.get("enabled", True)
    return instance


_registry_built = False


def _ensure_registry():
    """Lazily populate ALL_FILTERS on first access."""
    global _registry_built
    if _registry_built:
        return
    _registry_built = True
    try:
        ALL_FILTERS.update(_build_registry())
    except ImportError:
        pass  # Partial installs -- registry will be empty.
