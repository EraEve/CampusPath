"""CampusPath Data Models.

Data structures for representing campus building floor plans as graphs:
- Node: A vertex in the indoor navigation graph
- AdjacencyListGraph: Sparse graph representation for pathfinding
- Building: Multi-floor building model with vertical connectors
"""

# Lazy imports — modules are imported only when accessed.
# This avoids circular dependencies and lets tests import directly
# from submodules (e.g. 'from backend.models.node import Node').

__all__ = ["Node", "NodeType", "AdjacencyListGraph", "Building"]
