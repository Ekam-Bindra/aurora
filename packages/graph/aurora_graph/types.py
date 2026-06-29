"""Graph node and edge types for API + UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GraphNode:
    id: str
    label: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "name": self.name,
            **{k: v for k, v in self.properties.items() if k not in ("id", "label", "name")},
        }


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.type,
            **self.properties,
        }


@dataclass
class GraphSnapshot:
    tenant_id: str
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    def node_map(self) -> Dict[str, GraphNode]:
        return {n.id: n for n in self.nodes}
