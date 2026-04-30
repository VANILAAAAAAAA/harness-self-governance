from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .context_gaps import record_context_gap
from .context_index import BUDGET_HINTS, build_context_index, load_or_build_context_index
from .context_packet import build_context_packet
from .evidence_anchor import EVIDENCE_DEPTHS, load_raw_evidence_index, select_raw_evidence_anchors
from .export import write_global_graph
from .pending_updates import capture_pending_update
from .profile_local_graph import profile_graph_text
from .projects import load_project_bundle
from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root
from .traversal import traverse_weighted_subgraph

NEW_INFO_MARKERS = ("i decide", "we decide", "decided", "new decision", "new information", "我决定", "决定", "更正", "纠正", "新知识")
EXPLICIT_DISCOVERY_MARKERS = ("explicit discovery", "forensic", "raw sessions", "深度查找", "取证", "原始会话")


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9一-龥]+", text.lower()) if len(tok) >= 2}


def _compiled_summary_candidates(repo_root: Path, profile_id: str, project_id: str) -> list[Path]:
    return [
        repo_root / "docs" / "examples" / "agent-memory-graph" / f"{profile_id}-{project_id}" / "compiled-session-project-scope.json",
        repo_root / "docs" / "examples" / "agent-memory-graph" / project_id / "compiled-session-project-scope.json",
        repo_root / "docs" / "examples" / "agent-memory-graph" / project_id / "compiled-session-project-scope-and-phase-boundary.json",
        repo_root / "docs" / "examples" / "agent-memory-graph" / f"{profile_id}-{project_id}" / "compiled-session-project-scope-and-phase-boundary.json",
    ]


def load_compiled_project_summary(repo_root: Path | str, profile_id: str, project_id: str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    for path in _compiled_summary_candidates(repo_root, profile_id, project_id):
        if path.exists():
            payload = read_json(path)
            payload.setdefault("source_path", path.as_posix())
            return payload
    try:
        bundle = load_project_bundle(resolve_memory_root(memory_root), profile_id, project_id)
        payload = dict(bundle.get("summary") or {})
        payload.setdefault("source_path", (bundle["root"] / "project-summary.json").as_posix())
        return payload
    except Exception:
        return {}


def normalize_agent_summary(summary: dict[str, Any], profile_id: str, project_id: str) -> dict[str, Any]:
    identity = summary.get("project_identity") if isinstance(summary.get("project_identity"), dict) else {}
    plan = summary.get("project_plan") if isinstance(summary.get("project_plan"), dict) else {}
    return {
        "summary_contract": summary.get("summary_contract", "agent_readable_project_context_v1"),
        "project_identity": {
            "profile": identity.get("profile", summary.get("profile_id", profile_id)),
            "project": identity.get("project", summary.get("project_id", project_id)),
            "one_line": identity.get("one_line", summary.get("summary", f"{profile_id}/{project_id} compiled project memory")),
        },
        "routing_hints": summary.get("routing_hints", {
            "aliases": [profile_id, project_id, project_id.replace("-", " ")],
            "negative_aliases": [],
            "default_entry_nodes": [f"project_summary:{profile_id}:{project_id}", f"plan:{profile_id}:{project_id}"],
        }),
        "agent_priority_order": summary.get("agent_priority_order", [
            "hard_constraints", "current_state", "active_phase", "plan.todo", "key_decisions", "evidence_paths"
        ]),
        "project_goal": summary.get("project_goal") or summary.get("purpose") or summary.get("summary", ""),
        "current_state": summary.get("current_state", summary.get("status", [])),
        "active_phase": summary.get("active_phase", summary.get("phase", "compiled_memory")),
        "open_problems": summary.get("open_problems", summary.get("problems", [])),
        "hard_constraints": summary.get("hard_constraints", summary.get("constraints", [])),
        "phase_boundaries": summary.get("phase_boundaries", []),
        "key_decisions": summary.get("key_decisions", summary.get("decisions", [])),
        "requirements": summary.get("requirements", []),
        "evidence_paths": summary.get("evidence_paths", []),
        "read_order": summary.get("read_order", ["project_summary", "project_plan", "constraints", "requirements", "decisions", "evidence_paths"]),
        "memory_lifecycle": summary.get("memory_lifecycle", {
            "live_session_ram": "current turn only",
            "pending_update": "new facts wait here",
            "compiled_candidate": "candidate after session compilation",
            "archive_gate": "quality/scope gate before stable memory",
            "compiled_memory": "summary/plan/graph artifacts used by retriever",
        }),
        "miss_policy": summary.get("miss_policy", {
            "if_no_project_match": "return_zero_hit_packet_then_offer_create_pending_project_or_run_explicit_discovery",
            "if_project_match_but_no_claim_match": "return_low_confidence_packet_with_summary_and_plan_only_then_require_user_or_single_deepening_decision",
            "if_claim_not_in_summary": "traverse_evidence_once_before_answering; if still absent record_context_gap",
            "if_new_user_decision": "capture_pending_update_not_compiled_memory",
            "if_user_supplies_new_knowledge": "create_pending_update_with_source=this_turn_then_wait_for_archive_gate",
            "fallback_budget_rule": "at_most_one_automatic_deepening_step; never_scan_all_docs_or_raw_sessions_by_default",
        }),
        "project_plan": {
            "completed": plan.get("completed", []),
            "todo": plan.get("todo", []),
            "update_mode": plan.get("update_mode", "agent_plan_command_compatible"),
        },
        "key_skills": summary.get("key_skills", []),
        "source_path": summary.get("source_path"),
    }


def _summary_text(summary: dict[str, Any]) -> str:
    parts: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for key, v in value.items():
                if key in {"source_path", "raw_path"}:
                    continue
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(summary)
    return "\n".join(parts).lower()


def _classify_new_information(query: str) -> bool:
    q = query.lower()
    return any(marker in q for marker in NEW_INFO_MARKERS)


def _candidate_confidence(query: str, summary: dict[str, Any], profile_id: str, project_id: str) -> tuple[float, list[str]]:
    q_tokens = _tokens(query)
    hints = summary.get("routing_hints", {}) if isinstance(summary.get("routing_hints"), dict) else {}
    aliases = [str(x).lower() for x in hints.get("aliases", [])] + [profile_id.lower(), project_id.lower(), project_id.replace("-", " ").lower()]
    negative = [str(x).lower() for x in hints.get("negative_aliases", [])]
    matched = [a for a in aliases if a and a in query.lower()]
    neg = [a for a in negative if a and a in query.lower()]
    text_tokens = _tokens(_summary_text(summary))
    overlap = sorted(q_tokens & text_tokens)
    score = min(1.0, len(matched) * 0.35 + min(len(overlap), 8) * 0.04)
    score = max(0.0, score - len(neg) * 0.25)
    return round(score, 3), matched + overlap[:10]


def _project_candidates(repo_root: Path, memory_root: Path) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def add(profile_id: str | None, project_id: str | None) -> None:
        if not profile_id or not project_id:
            return
        item = (str(profile_id), str(project_id))
        if item not in candidates:
            candidates.append(item)

    try:
        manifest = read_repo_manifest(repo_root)
        add(manifest.get("profile"), manifest.get("project"))
    except Exception:
        add("general", "harness-self-governance")

    projects_root = memory_root / "projects"
    if projects_root.exists():
        for profile_dir in sorted(p for p in projects_root.iterdir() if p.is_dir()):
            for project_dir in sorted(p for p in profile_dir.iterdir() if p.is_dir()):
                add(profile_dir.name, project_dir.name)

    examples_root = repo_root / "docs" / "examples" / "agent-memory-graph"
    if examples_root.exists():
        for path in sorted(examples_root.glob("*/compiled-session-project-scope*.json")):
            stem = path.parent.name
            if stem == "ehrlab-dirty-csv-data-cleaning":
                continue
            if stem == "harness-self-governance":
                add("general", stem)
                continue
            parts = stem.split("-", 1)
            if len(parts) == 2:
                add(parts[0], parts[1])
    return candidates or [("general", "harness-self-governance")]


def _routing_cache_path(memory_root: Path) -> Path:
    return memory_root / "index" / "project-routing-cache.json"


def _build_project_routing_cache(repo_root: Path, memory_root: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for profile_id, project_id in _project_candidates(repo_root, memory_root):
        summary = normalize_agent_summary(load_compiled_project_summary(repo_root, profile_id, project_id, memory_root), profile_id, project_id)
        hints = summary.get("routing_hints", {}) if isinstance(summary.get("routing_hints"), dict) else {}
        aliases = [str(x).lower() for x in hints.get("aliases", [])] + [profile_id.lower(), project_id.lower(), project_id.replace("-", " ").lower()]
        negative_aliases = [str(x).lower() for x in hints.get("negative_aliases", [])]
        anchor_text_parts: list[str] = []
        for anchor in load_raw_evidence_index(repo_root, profile_id, project_id):
            for key in ("anchor_id", "span_type", "safe_excerpt"):
                if anchor.get(key):
                    anchor_text_parts.append(str(anchor.get(key)))
            for key in ("claim_ids", "tags"):
                if isinstance(anchor.get(key), list):
                    anchor_text_parts.extend(str(item) for item in anchor.get(key, []))
        local_profile_text = profile_graph_text(profile_id, project_id)
        candidates.append({
            "profile": profile_id,
            "project": project_id,
            "aliases": sorted(set(alias for alias in aliases if alias)),
            "negative_aliases": sorted(set(alias for alias in negative_aliases if alias)),
            "summary_tokens": sorted(_tokens(_summary_text(summary) + "\n" + "\n".join(anchor_text_parts) + "\n" + local_profile_text)),
            "summary_source_path": summary.get("source_path"),
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cache_type": "project_routing_lite_index",
        "not_search_database": True,
        "candidate_count": len(candidates),
        "candidates": sorted(candidates, key=lambda item: (item["profile"], item["project"])),
    }
    deterministic_write_json(_routing_cache_path(memory_root), payload)
    return payload


def _load_or_build_project_routing_cache(repo_root: Path, memory_root: Path, *, refresh: bool = False) -> tuple[dict[str, Any], str]:
    path = _routing_cache_path(memory_root)
    if path.exists() and not refresh:
        return read_json(path, default={"candidates": []}), "cache"
    return _build_project_routing_cache(repo_root, memory_root), "rebuilt"


def _candidate_confidence_from_cache(query: str, candidate: dict[str, Any]) -> tuple[float, list[str]]:
    query_l = query.lower()
    q_tokens = _tokens(query)
    aliases = [str(x).lower() for x in candidate.get("aliases", [])]
    negative = [str(x).lower() for x in candidate.get("negative_aliases", [])]
    matched = [alias for alias in aliases if alias and alias in query_l]
    neg = [alias for alias in negative if alias and alias in query_l]
    text_tokens = set(str(x) for x in candidate.get("summary_tokens", []))
    overlap = sorted(q_tokens & text_tokens)
    score = min(1.0, len(matched) * 0.35 + min(len(overlap), 8) * 0.04)
    score = max(0.0, score - len(neg) * 0.25)
    return round(score, 3), matched + overlap[:10]


def _project_from_hints(
    repo_root: Path,
    memory_root: Path,
    profile_hint: str | None,
    project_hint: str | None,
    query: str = "",
    *,
    refresh_cache: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    if profile_hint and project_hint:
        return profile_hint, project_hint, {"mode": "explicit", "cache_source": "not_needed", "candidates": [{"profile": profile_hint, "project": project_hint, "confidence": 1.0}]}

    cache, cache_source = _load_or_build_project_routing_cache(repo_root, memory_root, refresh=refresh_cache)
    raw_candidates = [item for item in cache.get("candidates", []) if isinstance(item, dict)]
    candidates = [
        item for item in raw_candidates
        if (not profile_hint or item.get("profile") == profile_hint) and (not project_hint or item.get("project") == project_hint)
    ]
    scored: list[dict[str, Any]] = []
    best: tuple[str, str] | None = None
    best_score = -1.0
    best_matched: list[str] = []
    for candidate in candidates:
        cand_profile = str(candidate.get("profile"))
        cand_project = str(candidate.get("project"))
        score, matched = _candidate_confidence_from_cache(query, candidate)
        scored.append({"profile": cand_profile, "project": cand_project, "confidence": score, "matched_signals": matched})
        if score > best_score:
            best = (cand_profile, cand_project)
            best_score = score
            best_matched = matched

    if best is None:
        manifest = read_repo_manifest(repo_root)
        best = (profile_hint or str(manifest.get("profile", "general")), project_hint or str(manifest.get("project", "harness-self-governance")))

    return best[0], best[1], {
        "mode": "auto" if not (profile_hint and project_hint) else "explicit",
        "cache_source": cache_source,
        "candidate_count": len(scored),
        "selected_confidence": round(max(best_score, 0.0), 3),
        "selected_matched_signals": best_matched,
        "candidates": sorted(scored, key=lambda item: (-item["confidence"], item["profile"], item["project"]))[:8],
    }


def _selected_skill_mounts(graph: dict[str, Any], selected_node_ids: list[str]) -> list[dict[str, Any]]:
    nodes_by_id = {str(node.get("id")): node for node in graph.get("nodes", []) if node.get("id")}
    mounts: list[dict[str, Any]] = []
    for node_id in selected_node_ids:
        node = nodes_by_id.get(str(node_id))
        if not node or str(node.get("type", node.get("kind", ""))) != "skill":
            continue
        metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        skill_name = metadata.get("skill") or node.get("label") or str(node_id).removeprefix("skill:")
        mounts.append({
            "id": str(node_id),
            "skill": skill_name,
            "role": metadata.get("role") or node.get("summary") or node.get("description") or "procedural adapter selected by graph traversal",
            "load_policy": metadata.get("load_policy", "when_selected_by_project_subgraph"),
            "mount_role": metadata.get("mount_role", "procedural_adapter"),
            "source": "selected_project_subgraph",
        })
    return sorted(mounts, key=lambda item: (str(item.get("mount_role")), str(item.get("skill"))))


def _summary_skill_mounts(summary: dict[str, Any], existing_mounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_ids = {str(item.get("id")) for item in existing_mounts}
    mounts: list[dict[str, Any]] = []
    for skill in summary.get("key_skills", []):
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id") or f"skill:{skill.get('name', 'unnamed-skill')}")
        if skill_id in existing_ids:
            continue
        mounts.append({
            "id": skill_id,
            "skill": skill.get("name") or skill_id.removeprefix("skill:"),
            "role": skill.get("role") or "procedural adapter declared by compiled project summary",
            "load_policy": skill.get("load_policy", "when_selected_by_project_subgraph"),
            "mount_role": skill.get("mount_role", "procedural_adapter"),
            "source": "compiled_project_summary_key_skills",
        })
    return sorted(existing_mounts + mounts, key=lambda item: (str(item.get("mount_role")), str(item.get("skill"))))


def _packet_base(query: str, profile_id: str, project_id: str, budget: str, status: str, confidence: float, summary: dict[str, Any], **extra: Any) -> dict[str, Any]:
    packet = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "query": query,
        "selected_profile": profile_id,
        "selected_project": project_id,
        "confidence": confidence,
        "budget": budget,
        "context_role": "compiled_project_memory",
        "summary_first": {k: summary.get(k) for k in ("summary_contract", "project_identity", "routing_hints", "agent_priority_order", "project_goal", "current_state", "active_phase", "open_problems", "hard_constraints", "read_order", "memory_lifecycle", "key_skills")},
        "plan": summary.get("project_plan", {"completed": [], "todo": [], "update_mode": "agent_plan_command_compatible"}),
        "skill_mounts": [],
        "skill_load_order": [],
        "selected_nodes": [],
        "selected_edges": [],
        "selected_evidence_paths": [],
        "selected_raw_evidence_anchors": [],
        "raw_span_requests": [],
        "evidence_depth": extra.pop("evidence_depth", "anchor"),
        "pending_context": [],
        "do_not_read_by_default": ["sessions/raw/"],
        "raw_sessions_default_read": False,
        "current_session_raw_context": "preserved_by_hermes_live_context_not_graph_memory",
        "compiled_memory_raw_session_reads": False,
        "raw_sessions_allowed": False,
        "miss_policy": summary.get("miss_policy", {}),
        "routing": extra.pop("routing", None),
        "warnings": [],
        "blockers": [],
    }
    packet.update(extra)
    return packet


def _load_or_build_global_graph(memory_root: Path, profile_id: str, project_id: str, *, refresh_graph: bool = False) -> tuple[dict[str, Any], str]:
    graph_path = memory_root / "graph" / "global-graph.json"
    if graph_path.exists() and not refresh_graph:
        return read_json(graph_path, default={"nodes": [], "edges": []}), "cache"
    return write_global_graph(memory_root, profile_id, project_id), "rebuilt"


def retrieve_project_context(
    repo_root: Path | str,
    query: str,
    profile_hint: str | None = None,
    project_hint: str | None = None,
    memory_root: Path | str | None = None,
    budget: str = "fast",
    evidence_depth: str = "anchor",
    refresh_index: bool = False,
    refresh_graph: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    repo_root = Path(repo_root).resolve()
    memory_root_path = resolve_memory_root(memory_root)
    if budget not in BUDGET_HINTS:
        return {"status": "FAIL", "query": query, "warnings": [], "blockers": [f"unsupported budget: {budget}"]}
    if evidence_depth not in EVIDENCE_DEPTHS:
        return {"status": "FAIL", "query": query, "warnings": [], "blockers": [f"unsupported evidence_depth: {evidence_depth}"]}
    cache_events: list[str] = []
    if refresh_index:
        build_context_index(repo_root, memory_root_path)
        cache_events.append("context_index_rebuilt")
    else:
        load_or_build_context_index(repo_root, memory_root_path)
        cache_events.append("context_index_cache_or_lazy_build")
    profile_id, project_id, routing = _project_from_hints(repo_root, memory_root_path, profile_hint, project_hint, query, refresh_cache=refresh_index)
    cache_events.append(f"project_routing_{routing.get('cache_source', 'unknown')}")
    raw_summary = load_compiled_project_summary(repo_root, profile_id, project_id, memory_root_path)
    summary = normalize_agent_summary(raw_summary, profile_id, project_id)
    confidence, matched = _candidate_confidence(query, summary, profile_id, project_id)

    if _classify_new_information(query):
        update = capture_pending_update(repo_root, query, profile_id, project_id, memory_root_path)
        return _packet_base(query, profile_id, project_id, budget, "NEW_INFORMATION", max(confidence, 0.2), summary,
                            hit_count=len(matched), matched_signals=matched, routing=routing, pending_context=[update.get("update")],
                            evidence_depth=evidence_depth,
                            recommended_action="capture_pending_update", archive_gate_required=True,
                            latency_ms=round((time.perf_counter() - started) * 1000, 3), cache_events=cache_events)

    if confidence <= 0.0:
        gap = record_context_gap(repo_root, memory_root_path, query, "zero_hit", "retrieve_project_context found no project or summary hits")
        return _packet_base(query, profile_id, project_id, budget, "MISS", 0.0, summary,
                            hit_count=0, matched_signals=[], routing=routing, context_gap=gap.get("gap"),
                            recommended_action="create_pending_project_or_ask_for_scope_or_explicit_discovery",
                            evidence_depth=evidence_depth,
                            automatic_fallback_depth=0,
                            latency_ms=round((time.perf_counter() - started) * 1000, 3), cache_events=cache_events)

    graph, graph_source = _load_or_build_global_graph(memory_root_path, profile_id, project_id, refresh_graph=refresh_graph)
    cache_events.append(f"global_graph_{graph_source}")
    seed_nodes = [f"project_summary:{profile_id}:{project_id}", f"plan:{profile_id}:{project_id}", f"project:{profile_id}:{project_id}"]
    traversal = traverse_weighted_subgraph(
        graph,
        seed_nodes=seed_nodes,
        query=query,
        budget_nodes={"fast": 12, "normal": 24, "deep": 36, "forensic": 48}[budget],
        budget_edges={"fast": 18, "normal": 40, "deep": 72, "forensic": 100}[budget],
        max_depth=int(BUDGET_HINTS[budget]["max_depth"]),
        allow_raw_sessions=bool(BUDGET_HINTS[budget]["raw_sessions_allowed"] and any(m in query.lower() for m in EXPLICIT_DISCOVERY_MARKERS)),
    )
    status = "PASS" if confidence >= 0.18 or traversal.get("selected_nodes") else "LOW_CONFIDENCE"
    evidence = summary.get("evidence_paths", [])
    allow_raw_span = bool(
        evidence_depth == "raw-span"
        and BUDGET_HINTS[budget]["raw_sessions_allowed"]
        and any(m in query.lower() for m in EXPLICIT_DISCOVERY_MARKERS)
    )
    anchor_selection = select_raw_evidence_anchors(
        load_raw_evidence_index(repo_root, profile_id, project_id),
        query,
        evidence_depth=evidence_depth,
        max_anchors={"fast": 2, "normal": 4, "deep": 6, "forensic": 8}[budget],
        allow_raw_span=allow_raw_span,
    )
    skill_mounts = _summary_skill_mounts(summary, _selected_skill_mounts(graph, traversal.get("selected_nodes", [])))
    packet = _packet_base(query, profile_id, project_id, budget, status, confidence, summary,
                          hit_count=len(matched), matched_signals=matched, routing=routing,
                          skill_mounts=skill_mounts,
                          skill_load_order=[mount["skill"] for mount in skill_mounts],
                          selected_nodes=traversal.get("selected_nodes", []),
                          selected_edges=traversal.get("selected_edges", []),
                          selected_evidence_paths=evidence[:8] if isinstance(evidence, list) else [],
                          selected_raw_evidence_anchors=anchor_selection.get("anchors", []),
                          raw_span_requests=anchor_selection.get("raw_span_requests", []),
                          evidence_depth=evidence_depth,
                          traversal=traversal,
                          recommended_action="use_context_packet" if status == "PASS" else "single_deepening_or_record_context_gap",
                          automatic_fallback_depth=0,
                          latency_ms=round((time.perf_counter() - started) * 1000, 3), cache_events=cache_events)
    packet["raw_sessions_allowed"] = bool(traversal.get("raw_sessions_allowed", False) and allow_raw_span)
    packet["warnings"].extend(anchor_selection.get("warnings", []))
    packet["blockers"].extend(anchor_selection.get("blockers", []))
    return packet
