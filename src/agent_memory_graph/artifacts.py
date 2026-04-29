from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .context_gaps import list_context_gaps
from .context_index import build_context_index
from .repo_adapter import read_repo_manifest
from .router import route_query
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, relpath, resolve_memory_root

ROUTER_SAMPLE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "view-in-logs",
        "label": "Evidence route",
        "query": "view in logs lineage mapping",
        "expected_intent": "retrieve_existing",
        "expected_budget": "fast",
        "expected_raw_sessions_allowed": False,
    },
    {
        "id": "log定位",
        "label": "Log 定位",
        "query": "log定位",
        "expected_intent": "retrieve_existing",
        "expected_budget": "fast",
        "expected_raw_sessions_allowed": False,
    },
    {
        "id": "new-information",
        "label": "New info",
        "query": "我决定 v2.0 不做 Hub-side LLM API",
        "expected_intent": "new_information",
        "expected_budget": "fast",
        "expected_raw_sessions_allowed": False,
        "expected_pending_update": True,
    },
)


def _repo_artifact_paths(repo_root: Path, profile_id: str, project_id: str) -> dict[str, str]:
    project_root = repo_root / "artifacts" / "v2" / "projects" / profile_id / project_id
    return {
        "project_manifest": relpath(project_root / "project-manifest.json", repo_root),
        "project_summary": relpath(project_root / "project-summary.json", repo_root),
        "decision_ledger": relpath(project_root / "decision-ledger.json", repo_root),
        "requirements": relpath(project_root / "requirements.json", repo_root),
        "constraints": relpath(project_root / "constraints.json", repo_root),
        "session_index": relpath(project_root / "session-index.json", repo_root),
        "graph_fragment": relpath(project_root / "graph-fragment.json", repo_root),
        "lineage_index": relpath(project_root / "lineage-index.json", repo_root),
    }


def _sanitize_path(value: Any, repo_root: Path, memory_root: Path, repo_paths: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    root_s = repo_root.as_posix()
    memory_s = memory_root.as_posix()
    if value.startswith(root_s + "/"):
        return relpath(Path(value), repo_root)
    for kind, repo_path in repo_paths.items():
        suffix = f"/{Path(repo_path).name}"
        if value.startswith(memory_s + "/projects/") and value.endswith(suffix):
            return repo_path
    if value.startswith(memory_s + "/graph/global-graph.json"):
        return "artifacts/v2/graph/agent-memory-graph.json"
    if value.startswith(memory_s + "/graph/global-lineage-index.json"):
        return "artifacts/v2/lineage/log-index.json"
    if value.startswith(memory_s + "/"):
        return "<memory-root>/" + value.removeprefix(memory_s + "/")
    return value


def _sanitize_payload(payload: Any, repo_root: Path, memory_root: Path, repo_paths: dict[str, str]) -> Any:
    if isinstance(payload, dict):
        return {key: _sanitize_payload(value, repo_root, memory_root, repo_paths) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_sanitize_payload(item, repo_root, memory_root, repo_paths) for item in payload]
    return _sanitize_path(payload, repo_root, memory_root, repo_paths)


def _sample_from_route(definition: dict[str, Any], route: dict[str, Any], repo_root: Path, memory_root: Path, repo_paths: dict[str, str]) -> dict[str, Any]:
    cleaned = _sanitize_payload(deepcopy(route), repo_root, memory_root, repo_paths)
    packet = cleaned.get("recommended_context_packet") or {}
    intent = (cleaned.get("candidate_intents") or [None])[0]
    sample = {
        "id": definition["id"],
        "label": definition["label"],
        "query": definition["query"],
        "expected_intent": definition["expected_intent"],
        "expected_budget": definition["expected_budget"],
        "expected_raw_sessions_allowed": definition["expected_raw_sessions_allowed"],
        "status": cleaned.get("status"),
        "candidate_intents": cleaned.get("candidate_intents", []),
        "matched_topics": cleaned.get("matched_topics", []),
        "matched_aliases": cleaned.get("matched_aliases", []),
        "entry_nodes": cleaned.get("entry_nodes", []),
        "traversal_paths": cleaned.get("traversal_paths", []),
        "selected_artifacts": cleaned.get("selected_artifacts", []),
        "recommended_context_packet": packet,
        "context_budget": cleaned.get("context_budget", definition["expected_budget"]),
        "raw_sessions_allowed": cleaned.get("raw_sessions_allowed", False),
        "requires_llm_gate": cleaned.get("requires_llm_gate", False),
        "routing_reason": packet.get("routing_reason") or cleaned.get("recommended_action") or "not_reported",
        "recommended_action": cleaned.get("recommended_action"),
        "context_packet_ref": "artifacts/v2/context/context-packets.json",
        "pending_update": intent == "new_information" and cleaned.get("recommended_action") == "capture_pending_update",
    }
    return sample


def build_context_router_artifacts(repo_root: Path | str, memory_root: Path | str, out_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    out_root = Path(out_root) if out_root else repo_root / "artifacts" / "v2" / "context"
    if not out_root.is_absolute():
        out_root = repo_root / out_root
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = read_repo_manifest(repo_root)
    profile_id = manifest["profile"]
    project_id = manifest["project"]
    repo_paths = _repo_artifact_paths(repo_root, profile_id, project_id)

    index_report = build_context_index(repo_root, memory_root)
    if index_report.get("status") != "PASS":
        return {"status": "FAIL", "warnings": index_report.get("warnings", []), "blockers": index_report.get("blockers", ["context index build failed"])}
    raw_index = read_json(memory_root / "index" / "context-index.json")
    context_index = _sanitize_payload(raw_index, repo_root, memory_root, repo_paths)
    deterministic_write_json(out_root / "context-index.json", context_index)

    samples = []
    for definition in ROUTER_SAMPLE_DEFINITIONS:
        route = route_query(repo_root, definition["query"], memory_root, context_budget=definition["expected_budget"])
        samples.append(_sample_from_route(definition, route, repo_root, memory_root, repo_paths))

    router_samples = {
        "schema_version": SCHEMA_VERSION,
        "router_artifact_type": "context_router_samples",
        "samples": [
            {
                "id": sample["id"],
                "label": sample["label"],
                "query": sample["query"],
                "expected_intent": sample["expected_intent"],
                "expected_budget": sample["expected_budget"],
                "expected_raw_sessions_allowed": sample["expected_raw_sessions_allowed"],
                "expected_pending_update": bool(sample.get("pending_update")),
            }
            for sample in samples
        ],
        "count": len(samples),
    }
    context_packets = {
        "schema_version": SCHEMA_VERSION,
        "router_artifact_type": "context_packets",
        "raw_sessions_default_read": False,
        "raw_sessions_policy": "explicit_forensic_only",
        "samples": samples,
        "count": len(samples),
    }

    gaps_report = list_context_gaps(repo_root, memory_root)
    context_gaps = {
        "schema_version": SCHEMA_VERSION,
        "gaps": _sanitize_payload(gaps_report.get("gaps", []), repo_root, memory_root, repo_paths),
        "count": len(gaps_report.get("gaps", [])),
    }
    pending_updates = {
        "schema_version": SCHEMA_VERSION,
        "items": [
            {
                "id": "sample:new-information",
                "sample_id": "new-information",
                "query": "我决定 v2.0 不做 Hub-side LLM API",
                "status": "sample_not_applied",
                "pending_update": True,
                "raw_sessions_allowed": False,
                "note": "Rendered observability sample only; archive-session is not executed by the dashboard or pipeline sample.",
            }
        ],
        "count": 1,
    }

    deterministic_write_json(out_root / "router-samples.json", router_samples)
    deterministic_write_json(out_root / "context-packets.json", context_packets)
    deterministic_write_json(out_root / "context-gaps.json", context_gaps)
    deterministic_write_json(out_root / "pending-updates.json", pending_updates)
    return {
        "status": "PASS",
        "context_index_path": relpath(out_root / "context-index.json", repo_root),
        "router_samples_path": relpath(out_root / "router-samples.json", repo_root),
        "context_packets_path": relpath(out_root / "context-packets.json", repo_root),
        "context_gaps_path": relpath(out_root / "context-gaps.json", repo_root),
        "pending_updates_path": relpath(out_root / "pending-updates.json", repo_root),
        "sample_count": len(samples),
        "raw_sessions_default_read": False,
        "raw_sessions_policy": "explicit_forensic_only",
        "warnings": [],
        "blockers": [],
    }
