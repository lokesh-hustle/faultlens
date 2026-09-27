"""
FaultLens Engine - Service Dependency Graph
Establishes and traverses the structural topology of distributed microservices.
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ServiceNode:
    id: str
    name: str
    tier: str  # e.g., 'gateway', 'auth', 'app', 'database', 'third_party'
    sla_latency_ms: float = 200.0
    error_threshold_pct: float = 2.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceDependency:
    source: str
    target: str
    protocol: str = "HTTP/gRPC"
    circuit_breaker_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServiceDependencyGraph:
    def __init__(self):
        self.nodes: Dict[str, ServiceNode] = {}
        self.adjacency: Dict[str, List[str]] = {}  # source -> [targets]
        self.reverse_adjacency: Dict[str, List[str]] = {}  # target -> [sources]
        self.dependencies: Dict[str, ServiceDependency] = {}  # key "src->target"

    def add_node(self, node: ServiceNode):
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []
        if node.id not in self.reverse_adjacency:
            self.reverse_adjacency[node.id] = []

    def add_dependency(self, dep: ServiceDependency):
        if dep.source not in self.nodes or dep.target not in self.nodes:
            raise ValueError(f"Source {dep.source} or Target {dep.target} not present in graph nodes.")
        
        dep_key = f"{dep.source}->{dep.target}"
        self.dependencies[dep_key] = dep

        if dep.target not in self.adjacency[dep.source]:
            self.adjacency[dep.source].append(dep.target)
        if dep.source not in self.reverse_adjacency[dep.target]:
            self.reverse_adjacency[dep.target].append(dep.source)

    def get_upstream_services(self, service_id: str) -> List[str]:
        """Returns all direct callers of this service."""
        return self.reverse_adjacency.get(service_id, [])

    def get_downstream_services(self, service_id: str) -> List[str]:
        """Returns all direct dependencies called by this service."""
        return self.adjacency.get(service_id, [])

    def find_execution_paths(self, start_node: str, end_node: str, visited: Optional[Set[str]] = None) -> List[List[str]]:
        """Finds all paths from start_node to end_node in graph."""
        if visited is None:
            visited = set()
        
        if start_node == end_node:
            return [[start_node]]

        if start_node not in self.nodes or end_node not in self.nodes:
            return []

        visited.add(start_node)
        paths = []

        for neighbor in self.adjacency.get(start_node, []):
            if neighbor not in visited:
                sub_paths = self.find_execution_paths(neighbor, end_node, visited.copy())
                for sub_path in sub_paths:
                    paths.append([start_node] + sub_path)

        return paths

    def get_topological_depth(self, service_id: str) -> int:
        """Calculates distance from root entrypoints (gateways)."""
        visited = set()
        queue = [(service_id, 0)]
        min_depth = 0

        # Simple BFS reverse walk to entrypoints
        while queue:
            curr, depth = queue.pop(0)
            upstreams = self.get_upstream_services(curr)
            if not upstreams:
                min_depth = max(min_depth, depth)
            for up in upstreams:
                if up not in visited:
                    visited.add(up)
                    queue.append((up, depth + 1))

        return min_depth

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "tier": n.tier,
                    "sla_latency_ms": n.sla_latency_ms,
                    "error_threshold_pct": n.error_threshold_pct,
                    "metadata": n.metadata
                }
                for n in self.nodes.values()
            ],
            "dependencies": [
                {
                    "source": d.source,
                    "target": d.target,
                    "protocol": d.protocol,
                    "circuit_breaker_enabled": d.circuit_breaker_enabled,
                    "metadata": d.metadata
                }
                for d in self.dependencies.values()
            ]
        }
