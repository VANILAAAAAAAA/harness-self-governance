from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"

REQUIRED_NODE_TYPES = {
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
    payload = {
        "id": node_id,
        "type": node_type,
        "label": label,
        "summary": extra.pop("summary", label),
        "read_only": extra.pop("read_only", True),
        "sensitivity": extra.pop("sensitivity", "none"),
    }
    payload.update(extra)
    return payload


def _edge(edge_id: str, source: str, target: str, edge_type: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": edge_type,
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

    session_nodes, session_edges, session_warnings = _session_nodes_and_edges(repo_root)
    nodes.extend(session_nodes)
    edges.extend(session_edges)
    warnings.extend(session_warnings)

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
