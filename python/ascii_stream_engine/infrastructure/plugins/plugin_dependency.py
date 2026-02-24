"""Plugin dependency resolution using topological sort.

Resolves plugin load order to ensure dependencies are loaded before
the plugins that depend on them.
"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class CyclicDependencyError(Exception):
    """Raised when a cyclic dependency is detected between plugins."""

    pass


class PluginDependencyResolver:
    """Resolves plugin load order using topological sort."""

    def __init__(self) -> None:
        """Initialize the dependency resolver."""
        # plugin_name -> list of dependency names
        self._dependencies: Dict[str, List[str]] = {}
        # plugin_name -> set of plugins that depend on it (reverse edges)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)

    def add_plugin(self, name: str, dependencies: List[str]) -> None:
        """Register a plugin with its dependencies.

        Args:
            name: Plugin name.
            dependencies: List of plugin names this plugin depends on.
        """
        self._dependencies[name] = list(dependencies)
        # Build reverse graph
        for dep in dependencies:
            self._dependents[dep].add(name)
            # Ensure dependency is in the graph even if not explicitly added
            if dep not in self._dependencies:
                self._dependencies[dep] = []
        logger.debug(f"Plugin '{name}' registered with dependencies: {dependencies}")

    def remove_plugin(self, name: str) -> None:
        """Remove a plugin from the resolver.

        Args:
            name: Plugin name to remove.
        """
        # Remove from dependencies
        deps = self._dependencies.pop(name, [])
        # Remove from reverse graph
        for dep in deps:
            self._dependents[dep].discard(name)
        # Remove its own dependents entry
        self._dependents.pop(name, None)

    def resolve_order(self) -> List[str]:
        """Compute topological sort of plugins (dependencies first).

        Returns:
            List of plugin names in load order.

        Raises:
            CyclicDependencyError: If a cycle is detected.
        """
        # Kahn's algorithm for topological sort
        in_degree: Dict[str, int] = {name: 0 for name in self._dependencies}
        for name, deps in self._dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] = in_degree.get(name, 0)  # ensure exists
                # Only count edges where both nodes are in the graph
                pass

        # Recompute properly
        in_degree = {name: 0 for name in self._dependencies}
        for name, deps in self._dependencies.items():
            for dep in deps:
                if dep in self._dependencies:
                    in_degree[name] += 1

        # Start with nodes that have no dependencies
        queue: deque = deque()
        for name, degree in in_degree.items():
            if degree == 0:
                queue.append(name)

        result: List[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            # For each plugin that depends on this node
            for dependent in self._dependents.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(self._dependencies):
            # Find the cycle for a helpful error message
            remaining = set(self._dependencies.keys()) - set(result)
            raise CyclicDependencyError(f"Cyclic dependency detected among plugins: {remaining}")

        return result

    def get_dependents(self, name: str) -> Set[str]:
        """Get all plugins that directly or transitively depend on the given plugin.

        Args:
            name: Plugin name.

        Returns:
            Set of plugin names that depend on this plugin (transitive).
        """
        result: Set[str] = set()
        queue: deque = deque()
        direct = self._dependents.get(name, set())
        queue.extend(direct)
        while queue:
            dep = queue.popleft()
            if dep not in result:
                result.add(dep)
                # Add transitive dependents
                for transitive in self._dependents.get(dep, set()):
                    if transitive not in result:
                        queue.append(transitive)
        return result

    def get_dependencies(self, name: str) -> List[str]:
        """Get direct dependencies of a plugin.

        Args:
            name: Plugin name.

        Returns:
            List of dependency names.
        """
        return list(self._dependencies.get(name, []))

    def has_plugin(self, name: str) -> bool:
        """Check if a plugin is registered.

        Args:
            name: Plugin name.

        Returns:
            True if registered.
        """
        return name in self._dependencies

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._dependencies.clear()
        self._dependents.clear()
