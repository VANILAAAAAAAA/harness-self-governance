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


NODE_TYPE_PRIORITY = {
    "project_summary": 100,
    "plan": 95,
    "constraint": 86,
    "requirement": 82,
    "decision": 78,
    "project": 70,
    "profile": 55,
    "policy": 50,
    "tool": 35,
    "skill": 35,
    "session": -20,
}
EDGE_TYPE_PRIORITY = {
    "constrains": 90,
    "requires": 86,
    "planned_by": 84,
    "summarizes": 80,
    "supports": 70,
    "cites": 66,
    "derived_from": 64,
    "owns_project": 50,
    "uses_tool": 30,
    "uses_skill": 62,
    "archives_session": -25,
}


def _query_tokens(text: str) -> set[str]:
    import re
    return {token for token in re.split(r"[^a-z0-9一-龥]+", text.lower()) if len(token) >= 2}


def _node_text(node: dict[str, Any]) -> str:
    return " ".join(str(node.get(key, "")) for key in ("id", "label", "summary", "description", "type"))


def traverse_weighted_subgraph(
    graph: dict[str, Any],
    seed_nodes: list[str],
    query: str,
    budget_nodes: int = 24,
    budget_edges: int = 40,
    max_depth: int = 2,
    allow_raw_sessions: bool = False,
) -> dict[str, Any]:
    """Select a small agent-readable subgraph using deterministic type/query weights.

    This is the baseline before PageRank/Steiner expansion. It is intentionally
    dependency-free and conservative: summary/plan/constraints are preferred,
    raw/session nodes are excluded unless explicitly allowed.
    """
    nodes_by_id = {str(node.get("id")): node for node in graph.get("nodes", []) if node.get("id")}
    edges = [edge for edge in graph.get("edges", []) if edge.get("source") and edge.get("target")]
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        adjacency.setdefault(str(edge.get("source")), []).append(edge)
        adjacency.setdefault(str(edge.get("target")), []).append(edge)
    query_tokens = _query_tokens(query)
    selected: set[str] = {node_id for node_id in seed_nodes if node_id in nodes_by_id}
    frontier: list[tuple[str, int]] = [(node_id, 0) for node_id in selected]
    candidates: dict[str, float] = {}
    seen_depth: dict[str, int] = {node_id: 0 for node_id in selected}
    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for edge in adjacency.get(current, []):
            neighbor = str(edge.get("target")) if str(edge.get("source")) == current else str(edge.get("source"))
            if neighbor not in nodes_by_id:
                continue
            if neighbor not in seen_depth or depth + 1 < seen_depth[neighbor]:
                seen_depth[neighbor] = depth + 1
                frontier.append((neighbor, depth + 1))
            node = nodes_by_id[neighbor]
            node_type = str(node.get("type", node.get("kind", "")))
            if node_type == "session" and not allow_raw_sessions:
                continue
            text_tokens = _query_tokens(_node_text(node))
            query_score = min(30, len(query_tokens & text_tokens) * 10)
            type_score = NODE_TYPE_PRIORITY.get(node_type, 10)
            edge_score = EDGE_TYPE_PRIORITY.get(str(edge.get("type", edge.get("relation", ""))), 0)
            depth_penalty = (depth + 1) * 7
            candidates[neighbor] = max(candidates.get(neighbor, -999), type_score + query_score + edge_score - depth_penalty)
    for node_id in selected:
        candidates[node_id] = max(candidates.get(node_id, 0), 999)
    ordered_nodes = [node_id for node_id, _ in sorted(candidates.items(), key=lambda item: (-item[1], item[0]))]
    selected = set(ordered_nodes[:budget_nodes])
    # Close over direct constraint/requirement neighbors for selected summaries/projects when budget allows.
    for edge in sorted(edges, key=lambda item: str(item.get("id"))):
        if len(selected) >= budget_nodes:
            break
        if str(edge.get("type")) not in {"constrains", "requires", "summarizes"}:
            continue
        endpoints = [str(edge.get("source")), str(edge.get("target"))]
        if any(ep in selected for ep in endpoints):
            for ep in endpoints:
                node_type = str(nodes_by_id.get(ep, {}).get("type", ""))
                if ep in nodes_by_id and node_type in {"constraint", "requirement", "decision"}:
                    selected.add(ep)
    selected_edges = []
    for edge in sorted(edges, key=lambda item: str(item.get("id"))):
        if len(selected_edges) >= budget_edges:
            break
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in selected and target in selected:
            selected_edges.append(str(edge.get("id", f"edge:{source}:{target}")))
    return {
        "status": "PASS",
        "traversal_reason": "weighted_agent_memory_subgraph_selection",
        "selected_nodes": sorted(selected),
        "selected_edges": selected_edges,
        "seed_nodes": sorted([node_id for node_id in seed_nodes if node_id in nodes_by_id]),
        "budget_used": {"budget_nodes": budget_nodes, "budget_edges": budget_edges, "max_depth": max_depth},
        "raw_sessions_allowed": allow_raw_sessions,
        "warnings": [],
        "blockers": [],
    }
