from __future__ import annotations

import json
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import GraphSchema, GraphNode, GraphEdge, GraphEvent, ValidationError

DEPENDENCY_EDGE_TYPES = {"depends_on", "invokes", "reads", "writes"}
STRICT_PROVENANCE_EDGE_TYPES = {"derived_from", "cites", "supports"}

@dataclass
class StoreValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def iter_jsonl(path: str | Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValidationError(f"{path}:{i}: malformed JSONL: {e}") from e
            if not isinstance(obj, dict):
                raise ValidationError(f"{path}:{i}: row is not object")
            yield obj

@dataclass
class GraphStore:
    schema: GraphSchema
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[str, GraphEdge] = field(default_factory=dict)
    events: list[GraphEvent] = field(default_factory=list)
    edges_by_source: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list))
    edges_by_target: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list))
    nodes_by_type: dict[str, list[GraphNode]] = field(default_factory=lambda: defaultdict(list))
    nodes_by_profile: dict[str, list[GraphNode]] = field(default_factory=lambda: defaultdict(list))
    nodes_by_sensitivity: dict[str, list[GraphNode]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_paths(cls, graph_path: str, events_path: str | None = None, schema_path: str | None = None, profile: str | None = None) -> "GraphStore":
        schema = GraphSchema.from_file(schema_path)
        store = cls(schema)
        for rec in iter_jsonl(graph_path):
            rt = rec.get("record_type") or ("edge" if "source" in rec and "target" in rec else "node")
            if rt == "node":
                n = GraphNode.from_record(rec, schema)
                if profile and n.profile_scope not in {profile, "shared"}:
                    continue
                if n.id in store.nodes:
                    raise ValidationError(f"duplicate node id {n.id}")
                store.nodes[n.id] = n
            elif rt == "edge":
                e = GraphEdge.from_record(rec, schema)
                if profile and e.profile_scope not in {profile, "shared", "cross_profile"}:
                    continue
                if e.id in store.edges:
                    raise ValidationError(f"duplicate edge id {e.id}")
                store.edges[e.id] = e
            else:
                raise ValidationError(f"invalid record_type {rt}")
        store._reindex()
        if events_path:
            for rec in iter_jsonl(events_path):
                store.events.append(GraphEvent.from_record(rec, schema))
        return store

    def _reindex(self) -> None:
        self.edges_by_source.clear(); self.edges_by_target.clear(); self.nodes_by_type.clear(); self.nodes_by_profile.clear(); self.nodes_by_sensitivity.clear()
        for n in self.nodes.values():
            self.nodes_by_type[n.type].append(n); self.nodes_by_profile[n.profile_scope].append(n); self.nodes_by_sensitivity[n.sensitivity].append(n)
        for e in self.edges.values():
            self.edges_by_source[e.source].append(e); self.edges_by_target[e.target].append(e)
        for d in [self.edges_by_source, self.edges_by_target, self.nodes_by_type, self.nodes_by_profile, self.nodes_by_sensitivity]:
            for k in d: d[k].sort(key=lambda x: x.id)

    def iter_nodes(self): return iter(sorted(self.nodes.values(), key=lambda n: n.id))
    def iter_edges(self): return iter(sorted(self.edges.values(), key=lambda e: e.id))
    def get_node(self, node_id: str): return self.nodes.get(node_id)
    def get_edge(self, edge_id: str): return self.edges.get(edge_id)

    def neighbors(self, node_id: str, edge_types: set[str] | None = None, direction: str = "both") -> list[GraphEdge]:
        out: list[GraphEdge] = []
        if direction in {"out", "both"}: out.extend(self.edges_by_source.get(node_id, []))
        if direction in {"in", "both"}: out.extend(self.edges_by_target.get(node_id, []))
        if edge_types is not None: out = [e for e in out if e.type in edge_types]
        return sorted(out, key=lambda e: e.id)

    def dependency_edges(self, node_id: str) -> list[GraphEdge]:
        return self.neighbors(node_id, DEPENDENCY_EDGE_TYPES, "out")

    def provenance_edges(self, node_id: str, strict: bool = True) -> list[GraphEdge]:
        types = STRICT_PROVENANCE_EDGE_TYPES if strict else None
        return self.neighbors(node_id, types, "out")

    def events_for_node(self, node_id: str) -> list[GraphEvent]:
        return [e for e in self.events if node_id in e.used_nodes or node_id in e.changed_nodes]

    def validate_integrity(self) -> StoreValidationReport:
        errors: list[str] = []
        for e in self.edges.values():
            if e.source not in self.nodes: errors.append(f"{e.id}: missing source {e.source}")
            if e.target not in self.nodes: errors.append(f"{e.id}: missing target {e.target}")
        counts = {"nodes": len(self.nodes), "edges": len(self.edges), "events": len(self.events)}
        counts.update({f"node_type:{k}": v for k,v in Counter(n.type for n in self.nodes.values()).items()})
        counts.update({f"edge_type:{k}": v for k,v in Counter(e.type for e in self.edges.values()).items()})
        return StoreValidationReport(not errors, errors, counts)
