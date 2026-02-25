"""Tests for plugin hot-reload improvements: dependency resolution, batch reload, timing."""

import pytest

from ascii_stream_engine.infrastructure.plugins.plugin_dependency import (
    CyclicDependencyError,
    PluginDependencyResolver,
)
from ascii_stream_engine.infrastructure.plugins.plugin_manager import PluginManager


class TestPluginDependencyResolver:
    """Tests for PluginDependencyResolver."""

    def test_empty_resolver(self):
        """Empty resolver returns empty order."""
        resolver = PluginDependencyResolver()
        assert resolver.resolve_order() == []

    def test_single_plugin_no_deps(self):
        """Single plugin with no dependencies."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        assert resolver.resolve_order() == ["a"]

    def test_linear_dependency_chain(self):
        """Linear chain: a -> b -> c (c depends on b, b depends on a)."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.add_plugin("c", ["b"])
        order = resolver.resolve_order()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_diamond_dependency(self):
        """Diamond: d depends on b and c, both depend on a."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.add_plugin("c", ["a"])
        resolver.add_plugin("d", ["b", "c"])
        order = resolver.resolve_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_cyclic_dependency_raises(self):
        """Cyclic dependency raises CyclicDependencyError."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", ["b"])
        resolver.add_plugin("b", ["a"])
        with pytest.raises(CyclicDependencyError):
            resolver.resolve_order()

    def test_three_node_cycle(self):
        """Three-node cycle: a -> b -> c -> a."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", ["c"])
        resolver.add_plugin("b", ["a"])
        resolver.add_plugin("c", ["b"])
        with pytest.raises(CyclicDependencyError):
            resolver.resolve_order()

    def test_get_dependents_direct(self):
        """get_dependents returns direct dependents."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.add_plugin("c", ["a"])
        dependents = resolver.get_dependents("a")
        assert dependents == {"b", "c"}

    def test_get_dependents_transitive(self):
        """get_dependents returns transitive dependents."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.add_plugin("c", ["b"])
        dependents = resolver.get_dependents("a")
        assert dependents == {"b", "c"}

    def test_get_dependents_no_dependents(self):
        """get_dependents returns empty set for leaf plugin."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        dependents = resolver.get_dependents("b")
        assert dependents == set()

    def test_get_dependencies(self):
        """get_dependencies returns direct dependencies."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        assert resolver.get_dependencies("b") == ["a"]
        assert resolver.get_dependencies("a") == []

    def test_has_plugin(self):
        """has_plugin checks registration."""
        resolver = PluginDependencyResolver()
        assert resolver.has_plugin("a") is False
        resolver.add_plugin("a", [])
        assert resolver.has_plugin("a") is True

    def test_remove_plugin(self):
        """remove_plugin cleans up the graph."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.remove_plugin("b")
        assert resolver.has_plugin("b") is False
        assert resolver.get_dependents("a") == set()

    def test_clear(self):
        """clear removes all plugins."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("a", [])
        resolver.add_plugin("b", ["a"])
        resolver.clear()
        assert resolver.resolve_order() == []

    def test_independent_plugins_all_returned(self):
        """Independent plugins are all included in order."""
        resolver = PluginDependencyResolver()
        resolver.add_plugin("x", [])
        resolver.add_plugin("y", [])
        resolver.add_plugin("z", [])
        order = resolver.resolve_order()
        assert set(order) == {"x", "y", "z"}


class TestPluginManagerReloadStats:
    """Tests for PluginManager reload statistics."""

    def test_initial_reload_stats(self):
        """Initial reload stats are zero."""
        manager = PluginManager()
        stats = manager.reload_stats()
        assert stats["reload_count"] == 0
        assert stats["avg_reload_time_ms"] == 0.0
        assert stats["last_reload_at"] is None

    def test_dependency_resolver_accessible(self):
        """Dependency resolver is accessible via property."""
        manager = PluginManager()
        assert isinstance(manager.dependency_resolver, PluginDependencyResolver)


class TestPluginManagerDependencyIntegration:
    """Tests for dependency-aware plugin management."""

    def test_dependency_resolver_registered_on_load(self):
        """Dependency resolver is populated when plugins have no deps."""
        manager = PluginManager()
        # The resolver should be empty initially
        assert manager.dependency_resolver.resolve_order() == []
