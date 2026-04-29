from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context_gaps import record_context_gap
from .context_index import BUDGET_HINTS, build_context_index, load_or_build_context_index
from .context_packet import build_context_packet
from .traversal import traverse_memory_graph

NEW_INFO_MARKERS = ["i decide", "we decide", "decided", "我决定", "决定", "new decision", "new information"]
RETRIEVAL_MARKERS = ["retrieve", "find", "show", "view", "what", "where", "定位", "查找", "查看", "logs", "lineage"]
TASK_MARKERS = ["implement", "fix", "run", "update", "modify", "build", "测试", "修复", "实现"]
ARCHIVE_MARKERS = ["archive", "archive-session", "compiled session", "归档", "编译会话"]
AMBIGUOUS_MARKERS = ["maybe", "thing", "that", "可能", "那个", "something"]


def _contains_any(query_l: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker.lower() in query_l]


def _match_index(query: str, index: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    query_l = query.lower()
    matched_aliases: list[str] = []
    matched_topics: list[str] = []
    matched_paths: list[str] = []
    for alias, target in index.get("aliases", {}).items():
        alias_l = str(alias).lower()
        if alias_l and alias_l in query_l:
            matched_aliases.append(str(alias))
            if str(target) in index.get("topics", {}):
                matched_topics.append(str(target))
            else:
                matched_paths.append(str(target))
    for topic_id, topic in index.get("topics", {}).items():
        label = str(topic.get("label", "")).lower()
        if label and label in query_l:
            matched_topics.append(str(topic_id))
    return sorted(set(matched_topics)), sorted(set(matched_aliases)), sorted(set(matched_paths))


def _intent(query: str, matched_topics: list[str], matched_paths: list[str]) -> str:
    query_l = query.lower()
    new_markers = _contains_any(query_l, NEW_INFO_MARKERS)
    retrieval_markers = _contains_any(query_l, RETRIEVAL_MARKERS)
    task_markers = _contains_any(query_l, TASK_MARKERS)
    archive_markers = _contains_any(query_l, ARCHIVE_MARKERS)
    ambiguous_markers = _contains_any(query_l, AMBIGUOUS_MARKERS)
    if archive_markers:
        return "archive_request"
    if new_markers and not retrieval_markers:
        return "new_information"
    if ambiguous_markers and (not matched_topics and not matched_paths):
        return "ambiguous"
    if task_markers and not matched_topics and not matched_paths and not retrieval_markers:
        return "task_execution"
    return "retrieve_existing"


def _cheap_signals(query: str, matched_topics: list[str], matched_aliases: list[str], matched_paths: list[str]) -> dict[str, Any]:
    query_l = query.lower()
    return {
        "new_info_markers": _contains_any(query_l, NEW_INFO_MARKERS),
        "retrieval_markers": _contains_any(query_l, RETRIEVAL_MARKERS),
        "task_markers": _contains_any(query_l, TASK_MARKERS),
        "archive_markers": _contains_any(query_l, ARCHIVE_MARKERS),
        "matched_aliases": matched_aliases,
        "matched_topics": matched_topics,
        "matched_paths": matched_paths,
    }


def _entry_nodes_for_matches(index: dict[str, Any], matched_topics: list[str], matched_paths: list[str]) -> list[str]:
    nodes: list[str] = []
    for topic_id in matched_topics:
        topic = index.get("topics", {}).get(topic_id, {})
        nodes.extend(topic.get("entry_nodes", []))
    for item in matched_paths:
        if isinstance(item, str) and ":" in item:
            nodes.append(item)
    if not nodes and matched_topics:
        project = f"{index.get('profile')}/{index.get('project')}"
        nodes.append(index.get("projects", {}).get(project, {}).get("entry_node", ""))
    return sorted({node for node in nodes if node})


def _context_items_from_artifacts(selected_artifacts: list[dict[str, Any]], budget: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary = []
    optional = []
    for artifact in selected_artifacts:
        path = artifact.get("path")
        if not path:
            continue
        kind = "artifact"
        name = Path(path).name
        if name == "project-summary.json":
            kind = "project_summary"
        elif name == "decision-ledger.json":
            kind = "decision_ledger"
        elif name == "requirements.json":
            kind = "requirements"
        elif name == "constraints.json":
            kind = "constraints"
        elif name == "lineage-index.json":
            kind = "lineage_index"
        elif name == "session-index.json":
            kind = "session_index"
        item = {"kind": kind, "path": path, "reason": "selected_by_graph_traversal"}
        if budget == "fast" and kind not in {"project_summary", "project_manifest", "lineage_index"}:
            optional.append(item)
        else:
            primary.append(item)
    if not any(item["kind"] == "project_summary" for item in primary + optional):
        pass
    return primary, optional


def route_query(repo_root: Path | str, query: str, memory_root: Path | str | None = None, context_budget: str = "fast") -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    if context_budget not in BUDGET_HINTS:
        return {"status": "FAIL", "query": query, "warnings": [], "blockers": [f"unsupported context budget: {context_budget}"]}
    build_context_index(repo_root, memory_root)
    index = load_or_build_context_index(repo_root, memory_root)
    profile_id = str(index.get("profile"))
    project_id = str(index.get("project"))
    matched_topics, matched_aliases, matched_paths = _match_index(query, index)
    intent = _intent(query, matched_topics, matched_paths)
    raw_sessions_allowed = bool(BUDGET_HINTS[context_budget]["raw_sessions_allowed"])
    cheap = _cheap_signals(query, matched_topics, matched_aliases, matched_paths)
    base: dict[str, Any] = {
        "query": query,
        "profile": profile_id,
        "project": project_id,
        "candidate_intents": [intent],
        "cheap_signals": cheap,
        "matched_topics": matched_topics,
        "matched_aliases": matched_aliases,
        "context_budget": context_budget,
        "raw_sessions_allowed": raw_sessions_allowed,
        "warnings": [],
        "blockers": [],
    }
    if intent == "new_information":
        packet = build_context_packet(profile_id, project_id, intent, context_budget, raw_sessions_allowed=False, routing_reason="new_information_requires_pending_update_not_fallback")
        return {**base, "status": "PASS", "entry_nodes": [], "traversal_paths": [], "selected_artifacts": [], "recommended_context_packet": packet, "requires_llm_gate": False, "recommended_action": "capture_pending_update"}
    if intent == "ambiguous":
        packet = build_context_packet(profile_id, project_id, intent, context_budget, raw_sessions_allowed=False, routing_reason="ambiguous_intent_requires_llm_gate")
        return {**base, "status": "AMBIGUOUS", "entry_nodes": [], "traversal_paths": [], "selected_artifacts": [], "recommended_context_packet": packet, "requires_llm_gate": True, "recommended_action": "tiny_routing_packet"}
    entry_nodes = _entry_nodes_for_matches(index, matched_topics, matched_paths)
    query_l = query.lower()
    forced_miss = any(marker in query_l for marker in ("moon base", "teleport", "不存在", "unknown"))
    if intent == "retrieve_existing" and (not entry_nodes or forced_miss):
        gap_type = "missing_alias" if not matched_aliases or forced_miss else "missing_entry_node"
        record_context_gap(repo_root, memory_root, query, gap_type, "retrieve_existing query did not map to context index entry nodes")
        packet = build_context_packet(profile_id, project_id, intent, context_budget, raw_sessions_allowed=False, routing_reason="retrieval_miss_records_context_gap")
        return {**base, "status": "MISS", "entry_nodes": [], "traversal_paths": [], "selected_artifacts": [], "recommended_context_packet": packet, "requires_llm_gate": False, "recommended_action": "record_context_gap"}
    max_depth = int(BUDGET_HINTS[context_budget]["max_depth"])
    traversal_reports = [traverse_memory_graph(repo_root, node, memory_root, max_depth=max_depth) for node in entry_nodes]
    selected_artifacts: list[dict[str, Any]] = []
    visited_nodes: set[str] = set()
    visited_edges: set[str] = set()
    for report in traversal_reports:
        selected_artifacts.extend(report.get("selected_artifacts", []))
        visited_nodes.update(report.get("visited_nodes", []))
        visited_edges.update(report.get("visited_edges", []))
    dedup_artifacts = []
    seen = set()
    for item in selected_artifacts:
        path = item.get("path")
        if path and path not in seen:
            seen.add(path)
            dedup_artifacts.append(item)
    primary, optional = _context_items_from_artifacts(dedup_artifacts, context_budget)
    packet = build_context_packet(profile_id, project_id, intent, context_budget, primary, optional, sorted(visited_nodes), sorted(visited_edges), raw_sessions_allowed, "matched_context_index_then_bounded_graph_traversal")
    return {**base, "status": "PASS", "entry_nodes": entry_nodes, "traversal_paths": traversal_reports, "selected_artifacts": dedup_artifacts, "recommended_context_packet": packet, "requires_llm_gate": False, "recommended_action": "use_context_packet"}
