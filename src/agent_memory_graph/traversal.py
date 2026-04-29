from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from .context_index import BUDGET_HINTS, load_or_build_context_index
from .export import write_global_graph
from .projects import load_project_bundle
from .repo_adapter import read_repo_manifest
from .schemas import read_json, resolve_memory_root


def _artifact_for_node(node_id: str, index: dict[str, Any]) -> str | None:
    paths = index.get("artifact_paths", {})
    if node_id.startswith("project_summary:"):
        return paths.get("project_summary")
    if node_id.startswith("decision:"):
        return paths.get("decision_ledger")
    if node_id.startswith("requirement:"):
        return paths.get("requirements")
    if node_id.startswith("constraint:"):
        return paths.get("constraints")
    if node_id.startswith("session:"):
        return paths.get("session_index")
    if node_id.startswith("profile:"):
        profile = index.get("profile")
        return index.get("profiles", {}).get(profile, {}).get("artifact_path")
    if node_id.startswith("project:"):
        project_key = f"{index.get('profile')}/{index.get('project')}"
        return index.get("projects", {}).get(project_key, {}).get("artifact_paths", {}).get("project_manifest")
    if node_id.startswith("protocol:") or node_id.startswith("tool:"):
        return paths.get("project_manifest")
    return paths.get("graph_fragment")


def traverse_memory_graph(repo_root: Path | str, node: str, memory_root: Path | str | None = None, max_depth: int = 2) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    profile_id = str(manifest.get("profile", "general"))
    project_id = str(manifest.get("project", "harness-self-governance"))
    write_global_graph(memory_root, profile_id, project_id)
    graph = read_json(memory_root / "graph" / "global-graph.json", default={"nodes": [], "edges": []})
    index = load_or_build_context_index(repo_root, memory_root)
    node_ids = {str(item.get("id")) for item in graph.get("nodes", []) if item.get("id")}
    if node not in node_ids:
        return {
            "status": "MISS",
            "start_node": node,
            "max_depth": max_depth,
            "visited_nodes": [],
            "visited_edges": [],
            "selected_artifacts": [],
            "traversal_reason": "entry_node_not_found",
            "budget_used": {"max_depth": max_depth, "raw_sessions_allowed": False},
            "warnings": [],
            "blockers": ["start node not found in Agent Memory Graph"],
        }
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", []):
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if not source or not target:
            continue
        adjacency.setdefault(source, []).append(edge)
        adjacency.setdefault(target, []).append(edge)
    visited_nodes: set[str] = {node}
    visited_edges: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(node, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in sorted(adjacency.get(current, []), key=lambda item: str(item.get("id"))):
            edge_id = str(edge.get("id"))
            visited_edges[edge_id] = edge
            for neighbor in (str(edge.get("source")), str(edge.get("target"))):
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))
    artifacts = []
    seen_paths: set[str] = set()
    for node_id in sorted(visited_nodes):
        path = _artifact_for_node(node_id, index)
        if path and path not in seen_paths:
            seen_paths.add(path)
            artifacts.append({"node": node_id, "path": path, "raw_session": False})
    return {
        "status": "PASS",
        "start_node": node,
        "max_depth": max_depth,
        "visited_nodes": sorted(visited_nodes),
        "visited_edges": sorted(visited_edges),
        "selected_artifacts": artifacts,
        "traversal_reason": "bounded_agent_memory_graph_traversal",
        "budget_used": {"max_depth": max_depth, "raw_sessions_allowed": False, "budget_hint": next((k for k,v in BUDGET_HINTS.items() if v["max_depth"] == max_depth), "custom")},
        "warnings": [],
        "blockers": [],
    }
