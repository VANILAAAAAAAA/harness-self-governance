from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_memory_graph.profile_local_graph import load_profile_graph_projection

SCHEMA_VERSION = "2.0"

REQUIRED_NODE_TYPES = {
    "profile",
    "project",
    "project_summary",
    "plan",
    "pipeline_run",
    "artifact",
    "report",
    "proposal",
    "gate",
    "policy",
    "adapter",
    "tool",
    "skill",
    "knowledge_source",
    "session",
    "decision",
    "requirement",
    "provenance_state",
    "test_result",
    "release_audit",
}

REQUIRED_EDGE_TYPES = {
    "owns_project",
    "archives_session",
    "summarizes",
    "supports",
    "constrains",
    "maps_to_log",
    "generated",
    "validates",
    "blocks",
    "references",
    "derived_from",
    "governed_by",
    "reports_on",
    "decided",
    "requires",
    "uses_tool",
    "summarized_into",
    "planned_by",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _node(node_id: str, node_type: str, label: str, **extra: Any) -> dict[str, Any]:
    summary = extra.pop("summary", label)
    status = extra.pop("status", "available" if extra.get("exists", True) is not False else "missing")
    tags = sorted(set(extra.pop("tags", []) + [node_type]))
    metadata = dict(extra.pop("metadata", {}))
    for key in ("path", "privacy", "source_hash", "exists"):
        if key in extra:
            metadata[key] = extra[key]
    payload = {
        "id": node_id,
        "type": node_type,
        "kind": node_type,
        "label": label,
        "status": status,
        "tags": tags,
        "metadata": metadata,
        "description": summary,
        "summary": summary,
        "read_only": extra.pop("read_only", True),
        "sensitivity": extra.pop("sensitivity", "none"),
    }
    payload.update(extra)
    return payload


def _edge(edge_id: str, source: str, target: str, edge_type: str, **extra: Any) -> dict[str, Any]:
    metadata = dict(extra.pop("metadata", {}))
    payload = {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": edge_type,
        "relation": edge_type,
        "label": edge_type.replace("_", " "),
        "status": extra.pop("status", "active"),
        "metadata": metadata,
        "confidence": extra.pop("confidence", 1.0),
    }
    payload.update(extra)
    return payload


def _artifact_node(repo_root: Path, rel_path: str, label: str, node_type: str = "artifact") -> dict[str, Any]:
    path = repo_root / rel_path
    return _node(
        f"artifact:{rel_path}",
        node_type,
        label,
        path=rel_path,
        exists=path.exists(),
        summary=f"Local generated artifact: {rel_path}",
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _memory_root_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get("AGENT_MEMORY_GRAPH_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend(
        [
            Path("~/.agent-memory-graph").expanduser(),
            Path.home() / ".hermes" / "profiles" / "general" / "home" / ".agent-memory-graph",
        ]
    )
    seen: set[str] = set()
    out: list[Path] = []
    for candidate in candidates:
        key = candidate.resolve().as_posix() if candidate.exists() else candidate.expanduser().as_posix()
        if key not in seen and candidate.exists():
            seen.add(key)
            out.append(candidate)
    return out


def _memory_project_dir(profile_id: str, project_id: str) -> Path | None:
    for memory_root in _memory_root_candidates():
        root = memory_root / "projects" / profile_id / project_id
        if root.exists():
            return root
    return None


def _merge_profile_indexes(base: dict[str, Any], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {}
    for item in base.get("profiles", []):
        profile_id = item.get("profile_id")
        if profile_id:
            profiles[profile_id] = dict(item)
    for overlay in overlays:
        for item in overlay.get("profiles", []):
            profile_id = item.get("profile_id")
            if not profile_id:
                continue
            merged = dict(profiles.get(profile_id, {}))
            merged.update({key: value for key, value in item.items() if key != "projects"})
            merged["projects"] = sorted(set(merged.get("projects", [])) | set(item.get("projects", [])))
            profiles[profile_id] = merged
    return {
        **base,
        "profiles": [profiles[key] for key in sorted(profiles)],
        "warnings": sorted(set(base.get("warnings", []))),
    }


def _profile_index_from_memory_root(memory_root: Path) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_file in sorted((memory_root / "profiles").glob("*/profile.json")):
        profile = _load_json(profile_file)
        if profile:
            profile_id = profile.get("profile_id") or profile_file.parent.name
            projects = set(profile.get("projects", []))
            project_parent = memory_root / "projects" / profile_id
            if project_parent.exists():
                projects.update(path.name for path in project_parent.iterdir() if path.is_dir())
            profiles.append({**profile, "profile_id": profile_id, "projects": sorted(projects)})
    return {"schema_version": SCHEMA_VERSION, "active_profile": "general", "profiles": profiles, "warnings": [], "blockers": []}


def _load_profile_index(repo_root: Path) -> dict[str, Any]:
    from .profiles import build_profile_index

    base = _load_json(repo_root / "artifacts" / "v2" / "profiles" / "profile-index.json") or build_profile_index()
    overlays = [_profile_index_from_memory_root(root) for root in _memory_root_candidates()]
    return _merge_profile_indexes(base, overlays)


def _load_project_manifest(repo_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    from .projects import build_project_manifest

    memory_project = _memory_project_dir(profile_id, project_id)
    candidates = [
        repo_root / "artifacts" / "v2" / "projects" / profile_id / project_id / "project-manifest.json",
    ]
    if memory_project:
        candidates.append(memory_project / "project-manifest.json")
    for path in candidates:
        loaded = _load_json(path)
        if loaded:
            return loaded
    return build_project_manifest(profile_id, project_id)


def _load_project_summary(repo_root: Path, profile_id: str, project_id: str) -> dict[str, Any] | None:
    memory_project = _memory_project_dir(profile_id, project_id)
    candidates = [
        repo_root / "docs" / "examples" / "agent-memory-graph" / f"{profile_id}-{project_id}" / "compiled-session-project-scope.json",
        repo_root / "docs" / "examples" / "agent-memory-graph" / project_id / "compiled-session-project-scope.json",
        repo_root / "docs" / "examples" / "agent-memory-graph" / project_id / "compiled-session-project-scope-and-phase-boundary.json",
        repo_root / "artifacts" / "v2" / "projects" / profile_id / project_id / "project-summary.json",
    ]
    if memory_project:
        candidates.append(memory_project / "project-summary.json")
    for summary_path in candidates:
        loaded = _load_json(summary_path)
        if loaded:
            return loaded
    return None


def _load_project_graph_fragment(profile_id: str, project_id: str) -> dict[str, list[dict[str, Any]]]:
    memory_project = _memory_project_dir(profile_id, project_id)
    if not memory_project:
        return {"nodes": [], "edges": []}
    fragment = _load_json(memory_project / "graph-fragment.json")
    if not fragment:
        return {"nodes": [], "edges": []}
    nodes: list[dict[str, Any]] = []
    for raw in fragment.get("nodes", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        metadata = dict(raw.get("metadata") or {})
        metadata.setdefault("profile_id", profile_id)
        metadata.setdefault("project_id", project_id)
        metadata.setdefault("source", "memory_root_graph_fragment")
        node = _node(
            str(raw["id"]),
            str(raw.get("type") or raw.get("kind") or "knowledge_claim"),
            str(raw.get("label") or raw["id"]),
            path=raw.get("path"),
            summary=str(raw.get("description") or raw.get("summary") or raw.get("label") or raw["id"]),
            tags=list(raw.get("tags") or []),
            metadata=metadata,
        )
        for key, value in raw.items():
            if key not in node and key not in {"metadata"}:
                node[key] = value
        nodes.append(node)
    edges: list[dict[str, Any]] = []
    for raw in fragment.get("edges", []):
        if not isinstance(raw, dict) or not raw.get("source") or not raw.get("target"):
            continue
        relation = raw.get("type") or raw.get("relation") or "references"
        edge_id = raw.get("id") or f"edge:{_slug(str(raw['source']))}:{_slug(str(relation))}:{_slug(str(raw['target']))}"
        metadata = dict(raw.get("metadata") or {})
        metadata.setdefault("profile_id", profile_id)
        metadata.setdefault("project_id", project_id)
        metadata.setdefault("source", "memory_root_graph_fragment")
        edge = _edge(
            edge_id,
            str(raw["source"]),
            str(raw["target"]),
            str(relation),
            confidence=float(raw.get("confidence", 0.8)),
            metadata=metadata,
        )
        for key, value in raw.items():
            if key not in edge and key not in {"metadata"}:
                edge[key] = value
        edges.append(edge)
    return {"nodes": nodes, "edges": edges}


def _stringify_summary_item(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or item.get("meaning") or item.get("phase") or item.get("name") or item.get("id") or item)
    return str(item)


def _summary_description(summary: dict[str, Any], fallback: str) -> str:
    if not summary:
        return fallback
    sections: list[str] = []
    for key, label in (
        ("summary", "Summary"),
        ("project_goal", "Goal"),
        ("project_status", "Status"),
        ("purpose", "Purpose"),
    ):
        if summary.get(key):
            prefix = "" if key == "summary" else f"{label}: "
            sections.append(prefix + str(summary[key]))
    for key, label in (
        ("current_problems", "Problems"),
        ("phase_boundaries", "Phase boundaries"),
        ("key_decisions", "Key decisions"),
        ("requirements", "Requirements"),
        ("constraints", "Constraints"),
        ("read_order", "Read order"),
        ("cautions", "Cautions"),
    ):
        values = [_stringify_summary_item(item) for item in summary.get(key, []) if item]
        if values:
            sections.append(f"{label}: " + " ".join(f"- {item}" for item in values[:5]))
    return "\n".join(sections) or fallback


def _profile_project_nodes_and_edges(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    index = _load_profile_index(repo_root)
    for profile in index.get("profiles", []):
        profile_id = profile.get("profile_id", "unknown")
        profile_node = f"profile:{profile_id}"
        nodes.append(
            _node(
                profile_node,
                "profile",
                profile.get("label") or profile_id,
                summary=profile.get("description") or profile_id,
                metadata={"profile_id": profile_id, "role": profile.get("role"), "projects": profile.get("projects", [])},
            )
        )
        projects = profile.get("projects", [])
        if not projects and profile_id == "ehrlab":
            warnings.append("ehrlab has no archived projects yet; dashboard should show an empty state")
        for project_id in projects:
            manifest = _load_project_manifest(repo_root, profile_id, project_id)
            project_node = f"project:{profile_id}:{project_id}"
            summary_node = f"project_summary:{profile_id}:{project_id}"
            nodes.append(
                _node(
                    project_node,
                    "project",
                    manifest.get("title") or project_id,
                    path=f"artifacts/v2/projects/{profile_id}/{project_id}/project-manifest.json",
                    summary=f"Project archive manifest for {profile_id}/{project_id}",
                    metadata={"profile_id": profile_id, "project_id": project_id, "role": manifest.get("role")},
                )
            )
            summary = _load_project_summary(repo_root, profile_id, project_id)
            nodes.append(
                _node(
                    summary_node,
                    "project_summary",
                    f"{manifest.get('title') or project_id} summary",
                    path=manifest.get("summary_path"),
                    privacy="local_only",
                    summary=_summary_description(summary or {}, "Project summary is populated by agent-triggered archive artifacts."),
                    metadata={"profile_id": profile_id, "project_id": project_id, "archive_contract": "agent_triggered", "summary_sections": {"project_goal": (summary or {}).get("project_goal"), "project_status": (summary or {}).get("project_status"), "current_problems": (summary or {}).get("current_problems", []), "phase_boundaries": (summary or {}).get("phase_boundaries", []), "key_decisions": (summary or {}).get("key_decisions", []), "purpose": (summary or {}).get("purpose"), "actions": (summary or {}).get("actions", []), "results": (summary or {}).get("results", []), "requirements": (summary or {}).get("requirements", []), "constraints": (summary or {}).get("constraints", []), "cautions": (summary or {}).get("cautions", []), "evidence_paths": (summary or {}).get("evidence_paths", []), "read_order": (summary or {}).get("read_order", []), "memory_lifecycle": (summary or {}).get("memory_lifecycle", {}), "project_plan": (summary or {}).get("project_plan", {}), "key_skills": (summary or {}).get("key_skills", []), "key_tools": (summary or {}).get("key_tools", [])}},
                )
            )
            edges.append(_edge(f"edge:profile:{profile_id}:owns-project:{project_id}", profile_node, project_node, "owns_project"))
            edges.append(_edge(f"edge:project:{profile_id}:{project_id}:summarizes", project_node, summary_node, "summarizes"))
            edges.append(_edge(f"edge:project:{profile_id}:{project_id}:governed-by-policy", project_node, "policy:safety-boundary", "governed_by"))
            if summary:
                for decision in summary.get("decisions", []):
                    node_id = decision.get("id") or f"decision:{_slug(decision.get('text', project_id))}"
                    nodes.append(_node(node_id, "decision", decision.get("text", node_id)[:80], summary=decision.get("text", node_id), metadata={"profile_id": profile_id, "project_id": project_id, "source": decision.get("source")}))
                    edges.append(_edge(f"edge:{summary_node}:summarizes:{node_id}", summary_node, node_id, "summarizes"))
                for requirement in summary.get("requirements", []):
                    node_id = requirement.get("id") or f"requirement:{_slug(requirement.get('text', project_id))}"
                    nodes.append(_node(node_id, "requirement", requirement.get("text", node_id)[:80], summary=requirement.get("text", node_id), metadata={"profile_id": profile_id, "project_id": project_id, "source": requirement.get("source")}))
                    edges.append(_edge(f"edge:{summary_node}:summarizes:{node_id}", summary_node, node_id, "summarizes"))
                for constraint in summary.get("constraints", []):
                    node_id = constraint.get("id") or f"constraint:{_slug(constraint.get('text', project_id))}"
                    nodes.append(_node(node_id, "constraint", constraint.get("text", node_id)[:80], summary=constraint.get("text", node_id), metadata={"profile_id": profile_id, "project_id": project_id, "source": constraint.get("source")}))
                    edges.append(_edge(f"edge:{summary_node}:constrains:{node_id}", summary_node, node_id, "constrains"))
                plan = summary.get("project_plan") or {}
                if plan:
                    plan_id = plan.get("id") or f"plan:{profile_id}:{project_id}"
                    completed = plan.get("completed", []) or []
                    todo = plan.get("todo", []) or []
                    plan_summary = f"Agent-readable project plan: {len(completed)} completed, {len(todo)} todo. Status: {plan.get('status', 'active')}"
                    nodes.append(_node(plan_id, "plan", f"{manifest.get('title') or project_id} plan", summary=plan_summary, tags=["plan", "agent-readable"], metadata={"profile_id": profile_id, "project_id": project_id, "completed": completed, "todo": todo, "status": plan.get("status"), "source": plan.get("source")}))
                    edges.append(_edge(f"edge:project:{profile_id}:{project_id}:planned-by", project_node, plan_id, "planned_by", confidence=0.95))
                    edges.append(_edge(f"edge:{summary_node}:summarizes-plan", summary_node, plan_id, "summarizes", confidence=0.9))
                for skill in summary.get("key_skills", []):
                    skill_id = skill.get("id") or f"skill:{_slug(skill.get('name', project_id))}"
                    nodes.append(_node(skill_id, "skill", skill.get("name", skill_id), summary=skill.get("role", skill.get("name", skill_id)), tags=["skill", "capability"], metadata={"profile_id": profile_id, "project_id": project_id, "role": skill.get("role")}))
                    edges.append(_edge(f"edge:project:{profile_id}:{project_id}:uses-skill:{_slug(skill_id)}", project_node, skill_id, "uses_tool", confidence=0.85))
                    edges.append(_edge(f"edge:{summary_node}:summarizes-skill:{_slug(skill_id)}", summary_node, skill_id, "summarizes", confidence=0.7))
                for tool in summary.get("key_tools", []):
                    tool_id = tool.get("id") or f"tool:{_slug(tool.get('name', project_id))}"
                    nodes.append(_node(tool_id, "tool", tool.get("name", tool_id), summary=tool.get("role", tool.get("name", tool_id)), tags=["tool", "capability"], metadata={"profile_id": profile_id, "project_id": project_id, "role": tool.get("role")}))
                    edges.append(_edge(f"edge:project:{profile_id}:{project_id}:uses-tool:{_slug(tool_id)}", project_node, tool_id, "uses_tool", confidence=0.85))
                    edges.append(_edge(f"edge:{summary_node}:summarizes-tool:{_slug(tool_id)}", summary_node, tool_id, "summarizes", confidence=0.7))
                for link in summary.get("graph_links", []):
                    if link.get("source") and link.get("target") and link.get("type"):
                        edges.append(_edge(f"edge:project-summary-link:{_slug(link['source'])}:{_slug(link['type'])}:{_slug(link['target'])}", link["source"], link["target"], link["type"], confidence=0.8))
            fragment = _load_project_graph_fragment(profile_id, project_id)
            nodes.extend(fragment.get("nodes", []))
            edges.extend(fragment.get("edges", []))
    return nodes, edges, warnings


def _lineage_map_edges(repo_root: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    existing_paths = {node.get("path") for node in nodes if node.get("path") and (repo_root / str(node.get("path"))).exists()}
    for node in nodes:
        path = node.get("path") or node.get("metadata", {}).get("path")
        if path in existing_paths:
            artifact_id = f"artifact:{path}"
            if any(candidate.get("id") == artifact_id for candidate in nodes):
                out.append(_edge(f"edge:{_slug(node['id'])}:maps-to-log", node["id"], artifact_id, "maps_to_log", metadata={"path": path}))
    if not out:
        out.append(_edge("edge:lineage-index:maps-to-log-placeholder", "artifact:artifacts/v2/lineage/log-index.json", "artifact:v2-generated-artifacts", "maps_to_log", confidence=0.5, metadata={"reason": "lineage index maps graph refs to local logs when generated"}))
    return out



def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "item"


def _capability_nodes_and_edges(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    cli_tools = [
        ("graph-export", "graph export", "python -m graph_harness_maintain graph export"),
        ("dashboard-build", "dashboard build", "python -m graph_harness_maintain dashboard build"),
        ("sessions-compress", "sessions compress", "python -m graph_harness_maintain sessions compress --input sessions/raw"),
        ("pipeline-v2.0-rc", "pipeline v2.0-rc", "python -m graph_harness_maintain pipeline v2.0-rc"),
        ("pipeline-local-rc", "pipeline local-rc", "python -m graph_harness_maintain pipeline local-rc"),
        ("pipeline-v1.1-rc", "pipeline v1.1-rc", "python -m graph_harness_maintain pipeline v1.1-rc"),
    ]
    for slug, label, command in cli_tools:
        tool_id = f"tool:cli:{slug}"
        nodes.append(_node(tool_id, "tool", label, summary=f"Local CLI tool: {command}", tags=["tool", "cli"], metadata={"command": command}))
        edges.append(_edge(f"edge:pipeline-v2-uses-tool-{slug}", "pipeline:v2.0-rc", tool_id, "uses_tool", metadata={"command": command}))

    module_root = repo_root / "src" / "graph_harness_maintain"
    for path in sorted(module_root.rglob("*.py"))[:36] if module_root.exists() else []:
        rel = _rel(repo_root, path)
        name = path.relative_to(module_root).with_suffix("").as_posix().replace("/", ".")
        node_id = f"knowledge:src-module:{_slug(name)}"
        nodes.append(_node(node_id, "knowledge_source", f"module {name}", path=rel, summary=f"Source module inventory node for {rel}", tags=["source", "module"]))
        if path.name in {"dashboard.py", "graph_export.py", "sessions.py", "pipeline.py", "cli.py"}:
            edges.append(_edge(f"edge:{node_id}:derived-from-docs", node_id, "knowledge:docs", "derived_from", confidence=0.7))
            edges.append(_edge(f"edge:pipeline-v2-references-{_slug(name)}", "pipeline:v2.0-rc", node_id, "references", confidence=0.75))

    tests_root = repo_root / "tests"
    for path in sorted(tests_root.glob("test_*.py"))[:28] if tests_root.exists() else []:
        rel = _rel(repo_root, path)
        test_id = f"knowledge:test:{_slug(path.stem)}"
        nodes.append(_node(test_id, "knowledge_source", path.stem, path=rel, summary=f"Test coverage source: {rel}", tags=["test", "validation"]))
        edges.append(_edge(f"edge:test-pytest-references-{_slug(path.stem)}", "test:pytest", test_id, "references", confidence=0.8))

    for root in [repo_root / "docs" / "plans", repo_root / "docs"]:
        if root.exists():
            for path in sorted(root.glob("*.md"))[:20]:
                rel = _rel(repo_root, path)
                doc_id = f"knowledge:doc:{_slug(path.stem)}"
                nodes.append(_node(doc_id, "knowledge_source", path.stem, path=rel, summary=f"Documentation knowledge source: {rel}", tags=["doc", "knowledge"]))
                edges.append(_edge(f"edge:docs-reference-{_slug(path.stem)}", "knowledge:docs", doc_id, "references", confidence=0.75))

    policies_root = repo_root / "policies"
    for path in sorted(policies_root.glob("*")) if policies_root.exists() else []:
        if path.is_file():
            rel = _rel(repo_root, path)
            policy_id = f"knowledge:policy:{_slug(path.stem)}"
            nodes.append(_node(policy_id, "knowledge_source", path.stem, path=rel, summary=f"Policy source file: {rel}", tags=["policy", "safety"]))
            edges.append(_edge(f"edge:policy-boundary-references-{_slug(path.stem)}", "policy:safety-boundary", policy_id, "references", confidence=0.8))

    skill_names = ["graph-harness-maintain", "frontend-visual-qa", "systematic-debugging", "test-driven-development", "writing-plans", "subagent-driven-development"]
    for name in skill_names:
        skill_id = f"skill:{_slug(name)}"
        nodes.append(_node(skill_id, "skill", f"skill {name}", summary=f"Agent procedural skill governed as part of the project capability graph: {name}", tags=["skill", "procedure", "governance-capability"], metadata={"skill": name, "profile_id": "general", "project_id": "harness-self-governance"}))
        edges.append(_edge(f"edge:v2-uses-skill-{_slug(name)}", "pipeline:v2.0-rc", skill_id, "uses_tool", confidence=0.75))
        edges.append(_edge(f"edge:skill-{_slug(name)}-governed-by-policy", skill_id, "policy:safety-boundary", "governed_by", confidence=0.75))

    return nodes, edges

def _session_nodes_and_edges(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    index_path = repo_root / "artifacts" / "v2" / "sessions" / "session-index.json"
    index = _load_json(index_path)
    if not index:
        warnings.append("session knowledge index not available; run sessions compress to add local-only session summaries")
        nodes.append(
            _node(
                "session:placeholder-local-only",
                "session",
                "session knowledge when available",
                privacy="local_only",
                summary="Placeholder for optional local-only compressed session summaries; raw transcripts are never required for graph export",
            )
        )
        return nodes, edges, warnings
    index_node_id = "knowledge:session-index"
    nodes.append(
        _node(
            index_node_id,
            "knowledge_source",
            "session knowledge index",
            path="artifacts/v2/sessions/session-index.json",
            privacy="local_only",
            summary="Compressed local-only session knowledge index",
        )
    )
    for item in index.get("sessions", []):
        session_id = item.get("session_id", "unknown")
        node_id = f"session:{session_id}"
        nodes.append(
            _node(
                node_id,
                "session",
                item.get("title") or session_id,
                path=item.get("summary_path"),
                privacy="local_only",
                source_hash=item.get("source_hash"),
                summary="Local-only compressed session summary",
            )
        )
        edges.append(_edge(f"edge:{node_id}:summarized_into:{index_node_id}", node_id, index_node_id, "summarized_into"))
        edges.append(_edge(f"edge:{node_id}:references:decision-read-only", node_id, "decision:read-only-v2", "references", confidence=0.6))
    if not index.get("sessions", []):
        nodes.append(
            _node(
                "session:placeholder-local-only",
                "session",
                "session knowledge when available",
                privacy="local_only",
                summary="Placeholder for optional local-only compressed session summaries; raw transcripts are never required for graph export",
            )
        )
        edges.append(_edge("edge:session-placeholder:summarized_into:session-index", "session:placeholder-local-only", index_node_id, "summarized_into", confidence=0.5))
    return nodes, edges, warnings


def _dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id not in deduped:
            deduped[item_id] = item
            continue
        merged = dict(deduped[item_id])
        existing_metadata = dict(merged.get("metadata") or {})
        incoming_metadata = dict(item.get("metadata") or {})
        merged.update({key: value for key, value in item.items() if value not in (None, "", [], {})})
        merged["metadata"] = {**incoming_metadata, **existing_metadata}
        deduped[item_id] = merged
    return list(deduped.values())


def build_governance_graph(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    warnings: list[str] = []

    nodes = [
        _node("pipeline:v1-local-rc", "pipeline_run", "v1 local pipeline", path="artifacts/v1/pipeline-run.json", summary="v1 local read-only governance pipeline"),
        _node("pipeline:v1.1-rc", "pipeline_run", "v1.1 proposal pipeline", path="artifacts/v1.1/pipeline-run.json", summary="v1.1 reviewed proposal-only validation pipeline"),
        _node("pipeline:v2.0-rc", "pipeline_run", "v2.0 read-only visualization pipeline", path="artifacts/v2/pipeline-run.json", summary="v2.0 graph/dashboard/session knowledge foundation pipeline"),
        _node("gate:approval", "gate", "approval gates", path="policies/approval-gates.yaml", summary="Policy gates block destructive, mutation, publication, sensitive export, and apply actions"),
        _node("policy:safety-boundary", "policy", "read-only safety boundary", path="policies/approval-gates.yaml", summary="No destructive apply, graph mutation execution, raw archive apply, or sensitive export"),
        _node("proposal:v1.1-reviewed-apply-plan", "proposal", "v1.1 reviewed apply proposal", path="artifacts/v1.1/proposals/reviewed-apply-plan.json", summary="Proposal manifest is validated but apply execution remains blocked"),
        _node("adapter:v1.1-report", "adapter", "adapter report", path="artifacts/v1.1/adapter-report.json", summary="Adapter capability report with approval-required mutation behavior"),
        _node("provenance:v1-current-state", "provenance_state", "provenance current-state", path="artifacts/v1/provenance/current-state.json", summary="Current local provenance state from v1 pipeline"),
        _node("provenance:v1.1-current-state", "provenance_state", "v1.1 provenance current-state", path="artifacts/v1.1/provenance/current-state.json", summary="Current local provenance state from v1.1 pipeline"),
        _node("release-audit:v1", "release_audit", "release audit", path="artifacts/v1/open-source-surface.json", summary="Open-source release surface audit"),
        _node("release-audit:v1.1", "release_audit", "v1.1 release audit", path="artifacts/v1.1/open-source-surface.json", summary="v1.1 release surface audit"),
        _node("test:pytest", "test_result", "pytest validation", path="artifacts/v1/test-results.json", summary="Local pytest validation results"),
        _node("tool:python-module-cli", "tool", "python module CLI", summary="python -m graph_harness_maintain CLI commands"),
        _node("knowledge:docs", "knowledge_source", "documentation knowledge", path="docs/plans", summary="v2.0 planning documents describe schema, roadmap, session knowledge, and UI safety"),
        _node("decision:read-only-v2", "decision", "v2.0 dashboard is read-only", summary="Dashboard and graph export are visualization-only and local artifact generation only"),
        _node("requirement:no-destructive-apply", "requirement", "no destructive apply", summary="No delete/move/quarantine/rehydrate/raw archive apply execution"),
        _node("requirement:no-graph-mutation", "requirement", "no graph mutation execution", summary="Graph export is read-only projection; it does not mutate graph/events stores"),
        _node("requirement:no-sensitive-export", "requirement", "no sensitive export", summary="Session summaries are redacted and marked local_only; raw sessions are ignored"),
        _node("artifact:v2-generated-artifacts", "artifact", "generated artifacts", path="artifacts/v2/", summary="v2 graph, dashboard, session index, and pipeline run outputs remain local"),
        _artifact_node(repo_root, "artifacts/v2/graph/governance-graph.json", "governance graph JSON"),
        _artifact_node(repo_root, "artifacts/v2/dashboard/index.html", "dashboard HTML", "report"),
        _artifact_node(repo_root, "artifacts/v2/sessions/session-index.json", "session index", "knowledge_source"),
        _artifact_node(repo_root, "artifacts/v2/pipeline-run.json", "v2 pipeline run", "report"),
        _artifact_node(repo_root, "artifacts/v2/profiles/profile-index.json", "profile index", "knowledge_source"),
        _artifact_node(repo_root, "artifacts/v2/projects/general/harness-self-governance/project-manifest.json", "project manifest", "knowledge_source"),
        _artifact_node(repo_root, "artifacts/v2/projects/general/harness-self-governance/project-summary.json", "project summary", "project_summary"),
        _artifact_node(repo_root, "artifacts/v2/lineage/log-index.json", "lineage log index", "knowledge_source"),
    ]

    edges = [
        _edge("edge:pipeline-v1-generated-provenance", "pipeline:v1-local-rc", "provenance:v1-current-state", "generated"),
        _edge("edge:pipeline-v1-generated-release-audit", "pipeline:v1-local-rc", "release-audit:v1", "generated"),
        _edge("edge:pipeline-v1-generated-tests", "pipeline:v1-local-rc", "test:pytest", "generated"),
        _edge("edge:pipeline-v1.1-generated-proposal", "pipeline:v1.1-rc", "proposal:v1.1-reviewed-apply-plan", "generated"),
        _edge("edge:pipeline-v1.1-generated-adapter", "pipeline:v1.1-rc", "adapter:v1.1-report", "generated"),
        _edge("edge:pipeline-v1.1-generated-provenance", "pipeline:v1.1-rc", "provenance:v1.1-current-state", "generated"),
        _edge("edge:pipeline-v2-generated-graph", "pipeline:v2.0-rc", "artifact:artifacts/v2/graph/governance-graph.json", "generated"),
        _edge("edge:pipeline-v2-generated-dashboard", "pipeline:v2.0-rc", "artifact:artifacts/v2/dashboard/index.html", "generated"),
        _edge("edge:pipeline-v2-generated-session-index", "pipeline:v2.0-rc", "artifact:artifacts/v2/sessions/session-index.json", "generated"),
        _edge("edge:pipeline-v2-generated-run", "pipeline:v2.0-rc", "artifact:artifacts/v2/pipeline-run.json", "generated"),
        _edge("edge:pipeline-v2-generated-profile-index", "pipeline:v2.0-rc", "artifact:artifacts/v2/profiles/profile-index.json", "generated"),
        _edge("edge:pipeline-v2-generated-project-manifest", "pipeline:v2.0-rc", "artifact:artifacts/v2/projects/general/harness-self-governance/project-manifest.json", "generated"),
        _edge("edge:pipeline-v2-generated-lineage-index", "pipeline:v2.0-rc", "artifact:artifacts/v2/lineage/log-index.json", "generated"),
        _edge("edge:proposal-validated-by-gates", "proposal:v1.1-reviewed-apply-plan", "gate:approval", "validates"),
        _edge("edge:gates-block-destructive", "gate:approval", "requirement:no-destructive-apply", "blocks"),
        _edge("edge:gates-block-graph-mutation", "gate:approval", "requirement:no-graph-mutation", "blocks"),
        _edge("edge:gates-block-sensitive-export", "gate:approval", "requirement:no-sensitive-export", "blocks"),
        _edge("edge:dashboard-references-graph", "artifact:artifacts/v2/dashboard/index.html", "artifact:artifacts/v2/graph/governance-graph.json", "references"),
        _edge("edge:v2-derived-from-v1", "pipeline:v2.0-rc", "pipeline:v1-local-rc", "derived_from"),
        _edge("edge:v2-derived-from-v1.1", "pipeline:v2.0-rc", "pipeline:v1.1-rc", "derived_from"),
        _edge("edge:v2-governed-by-policy", "pipeline:v2.0-rc", "policy:safety-boundary", "governed_by"),
        _edge("edge:adapter-reports-on-tools", "adapter:v1.1-report", "tool:python-module-cli", "reports_on"),
        _edge("edge:decision-decided-requirements", "decision:read-only-v2", "requirement:no-destructive-apply", "decided"),
        _edge("edge:v2-requires-read-only", "pipeline:v2.0-rc", "decision:read-only-v2", "requires"),
        _edge("edge:v2-uses-python-cli", "pipeline:v2.0-rc", "tool:python-module-cli", "uses_tool"),
        _edge("edge:docs-reference-decision", "knowledge:docs", "decision:read-only-v2", "references"),
        _edge("edge:v2-artifacts-summarized-into-graph", "artifact:v2-generated-artifacts", "artifact:artifacts/v2/graph/governance-graph.json", "summarized_into"),
    ]

    capability_nodes, capability_edges = _capability_nodes_and_edges(repo_root)
    nodes.extend(capability_nodes)
    edges.extend(capability_edges)

    profile_nodes, profile_edges, profile_warnings = _profile_project_nodes_and_edges(repo_root)
    nodes.extend(profile_nodes)
    edges.extend(profile_edges)
    warnings.extend(profile_warnings)

    session_nodes, session_edges, session_warnings = _session_nodes_and_edges(repo_root)
    nodes.extend(session_nodes)
    edges.extend(session_edges)
    warnings.extend(session_warnings)
    edges.extend(_lineage_map_edges(repo_root, nodes, edges))

    for profile in _load_profile_index(repo_root).get("profiles", []):
        profile_id = profile.get("profile_id")
        for project_id in profile.get("projects", []):
            if not profile_id or not project_id:
                continue
            projection = load_profile_graph_projection(profile_id, project_id)
            nodes.extend(projection.get("nodes", []))
            edges.extend(projection.get("edges", []))
            warnings.extend(projection.get("warnings", []))

    nodes = sorted(_dedupe_by_id(nodes), key=lambda item: item["id"])
    edges = sorted(_dedupe_by_id(edges), key=lambda item: item["id"])
    node_types = {node["type"] for node in nodes}
    edge_types = {edge["type"] for edge in edges}

    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": sorted(node_types),
        "edge_types": sorted(edge_types),
        "read_only": True,
        "proposal_only": True,
        "destructive_operations_allowed": False,
        "graph_mutation_allowed": False,
        "sensitive_export_allowed": False,
        "artifact_root": "artifacts/v2/",
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "warnings": sorted(set(warnings)),
        "blockers": [],
    }


def write_governance_graph(repo_root: Path | str, out_path: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    out = Path(out_path) if out_path else repo_root / "artifacts" / "v2" / "graph" / "governance-graph.json"
    if not out.is_absolute():
        out = repo_root / out
    graph = build_governance_graph(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "generated_at": graph["generated_at"],
        "status": "PASS" if not graph["blockers"] else "FAIL",
        "path": _rel(repo_root, out),
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "warnings": graph["warnings"],
        "blockers": graph["blockers"],
    }
