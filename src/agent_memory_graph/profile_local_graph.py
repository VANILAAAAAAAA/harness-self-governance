from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SENSITIVE_BLOCKLIST = {"credential", "phi_or_patient_level", "patient_level", "secret"}
DEFAULT_MAX_NODES = 120


def _profiles_root() -> Path:
    return Path(os.environ.get("HERMES_PROFILES_ROOT", "/home/vanila/.hermes/profiles")).expanduser()


def profile_graph_path(profile_id: str, profiles_root: Path | None = None) -> Path:
    root = profiles_root or _profiles_root()
    return root / profile_id / "graph-harness" / "graph.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _record_kind(record: dict[str, Any]) -> str:
    return str(record.get("record_type") or ("edge" if record.get("source") and record.get("target") else "node"))


def _safe_node(record: dict[str, Any], profile_id: str) -> bool:
    if _record_kind(record) != "node":
        return False
    if record.get("id") in {None, ""}:
        return False
    if str(record.get("profile_scope", profile_id)) not in {profile_id, "local", "shared"}:
        return False
    sensitivity = str(record.get("sensitivity", "none")).lower()
    if sensitivity in SENSITIVE_BLOCKLIST:
        return False
    return True


def _safe_summary(value: Any, limit: int = 900) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _node_priority(record: dict[str, Any]) -> tuple[int, str]:
    weight = record.get("weight") if isinstance(record.get("weight"), dict) else {}
    user_pin = float(weight.get("user_pin") or 0.0)
    utility = float(weight.get("utility") or 0.0)
    observed = str(record.get("observed_at") or record.get("transaction_time") or "")
    state = str(record.get("state") or "")
    pinned_bonus = 10 if state == "pinned" else 0
    return (int(user_pin * 100 + utility * 20 + pinned_bonus), observed)


def load_profile_graph_projection(
    profile_id: str,
    project_id: str,
    *,
    profiles_root: Path | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> dict[str, Any]:
    """Load safe profile-local graph-harness records as a project graph projection.

    This is a boundary adapter: it exposes only compact node/edge metadata already
    recorded in the profile-local graph harness. It does not read raw sessions or
    raw evidence files referenced by those records.
    """
    path = profile_graph_path(profile_id, profiles_root)
    records = _read_jsonl(path)
    safe_nodes = [record for record in records if _safe_node(record, profile_id)]
    safe_nodes = sorted(safe_nodes, key=_node_priority, reverse=True)[:max_nodes]
    selected_ids = {str(node.get("id")) for node in safe_nodes}

    nodes: list[dict[str, Any]] = []
    for record in safe_nodes:
        node_id = str(record.get("id"))
        node_type = str(record.get("type") or record.get("kind") or "knowledge_claim")
        metadata = {
            "source": "profile_local_graph_harness",
            "profile_id": profile_id,
            "project_id": project_id,
            "observed_at": record.get("observed_at"),
            "transaction_time": record.get("transaction_time"),
            "state": record.get("state"),
            "owner": record.get("owner"),
            "sensitivity": record.get("sensitivity", "none"),
            "deletion_policy": record.get("deletion_policy"),
            "evidence_refs": [ref for ref in record.get("evidence_refs", []) if isinstance(ref, str) and not ref.startswith("/")][:8],
        }
        nodes.append({
            "id": node_id,
            "type": node_type,
            "kind": node_type,
            "label": str(record.get("label") or node_id)[:120],
            "summary": _safe_summary(record.get("summary") or record.get("label") or node_id),
            "description": _safe_summary(record.get("summary") or record.get("label") or node_id),
            "status": "available",
            "read_only": True,
            "sensitivity": record.get("sensitivity", "none"),
            "metadata": metadata,
            "tags": ["profile-local-graph", profile_id, project_id],
        })

    edges: list[dict[str, Any]] = []
    edge_records = [record for record in records if _record_kind(record) == "edge"]
    for record in edge_records:
        source = str(record.get("source") or "")
        target = str(record.get("target") or "")
        if source not in selected_ids or target not in selected_ids:
            continue
        edge_type = str(record.get("type") or record.get("relation") or "related_to")
        edge_id = str(record.get("id") or f"edge:{source}:{edge_type}:{target}")
        edges.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "type": edge_type,
            "relation": edge_type,
            "label": edge_type.replace("_", " "),
            "status": "active",
            "confidence": record.get("confidence", 0.7),
            "metadata": {"source": "profile_local_graph_harness", "profile_id": profile_id, "project_id": project_id},
        })

    project_node = f"project:{profile_id}:{project_id}"
    summary_node = f"project_summary:{profile_id}:{project_id}"
    for node in nodes[:24]:
        node_id = str(node.get("id"))
        edge_type = "imports_profile_graph_node"
        edges.append({
            "id": f"edge:{project_node}:imports-profile-node:{node_id}",
            "source": project_node,
            "target": node_id,
            "type": edge_type,
            "relation": edge_type,
            "label": "imports profile graph node",
            "status": "active",
            "confidence": 0.75,
            "metadata": {"source": "profile_local_graph_harness", "read_only_projection": True},
        })
        edges.append({
            "id": f"edge:{summary_node}:summarizes-profile-node:{node_id}",
            "source": summary_node,
            "target": node_id,
            "type": "summarizes",
            "relation": "summarizes",
            "label": "summarizes",
            "status": "active",
            "confidence": 0.65,
            "metadata": {"source": "profile_local_graph_harness", "read_only_projection": True},
        })

    return {
        "source_path": path.as_posix(),
        "available": path.exists(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "warnings": [] if path.exists() else [f"profile-local graph not found: {path}"],
    }


def profile_graph_text(profile_id: str, project_id: str, *, max_nodes: int = 80) -> str:
    projection = load_profile_graph_projection(profile_id, project_id, max_nodes=max_nodes)
    parts: list[str] = []
    for node in projection.get("nodes", []):
        parts.append(str(node.get("label", "")))
        parts.append(str(node.get("summary", "")))
    return "\n".join(parts)
