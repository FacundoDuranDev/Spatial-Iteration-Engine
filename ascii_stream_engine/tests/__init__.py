import importlib.util


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None
