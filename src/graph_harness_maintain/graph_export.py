from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"

REQUIRED_NODE_TYPES = {
    "profile",
    "project",
    "project_summary",
    "pipeline_run",
    "artifact",
    "report",
    "proposal",
    "gate",
    "policy",
    "adapter",
    "tool",
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


def _load_profile_index(repo_root: Path) -> dict[str, Any]:
    from .profiles import build_profile_index

    return _load_json(repo_root / "artifacts" / "v2" / "profiles" / "profile-index.json") or build_profile_index()


def _load_project_manifest(repo_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    from .projects import build_project_manifest

    return _load_json(repo_root / "artifacts" / "v2" / "projects" / profile_id / project_id / "project-manifest.json") or build_project_manifest(profile_id, project_id)


def _load_project_summary(repo_root: Path, profile_id: str, project_id: str) -> dict[str, Any] | None:
    return _load_json(repo_root / "artifacts" / "v2" / "projects" / profile_id / project_id / "project-summary.json")


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
                    summary=(summary or {}).get("summary") or "Project summary is populated by agent-triggered archive artifacts.",
                    metadata={"profile_id": profile_id, "project_id": project_id, "archive_contract": "agent_triggered"},
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
                for link in summary.get("graph_links", []):
                    if link.get("source") and link.get("target") and link.get("type"):
                        edges.append(_edge(f"edge:project-summary-link:{_slug(link['source'])}:{_slug(link['type'])}:{_slug(link['target'])}", link["source"], link["target"], link["type"], confidence=0.8))
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

    skill_names = ["graph-harness-maintain", "test-driven-development", "writing-plans"]
    for name in skill_names:
        skill_id = f"tool:skill:{_slug(name)}"
        nodes.append(_node(skill_id, "tool", f"skill {name}", summary=f"Agent procedural skill relevant to v2 graph/log dashboard iteration: {name}", tags=["skill", "tool", "procedure"], metadata={"skill": name}))
        edges.append(_edge(f"edge:v2-uses-skill-{_slug(name)}", "pipeline:v2.0-rc", skill_id, "uses_tool", confidence=0.65))
        edges.append(_edge(f"edge:skill-{_slug(name)}-governed-by-policy", skill_id, "policy:safety-boundary", "governed_by", confidence=0.65))

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

    nodes = sorted(nodes, key=lambda item: item["id"])
    edges = sorted(edges, key=lambda item: item["id"])
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
