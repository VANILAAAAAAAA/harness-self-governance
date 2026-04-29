from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph_export import build_governance_graph

SCHEMA_VERSION = "2.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _candidate_paths(item: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for value in [item.get("path"), item.get("preferred_path")]:
        if isinstance(value, str) and value:
            paths.append(value)
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for key in ("path", "preferred_path", "summary_path", "manifest_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return sorted(set(paths))


def _mapping(repo_root: Path, item: dict[str, Any]) -> dict[str, Any]:
    existing = [path for path in _candidate_paths(item) if (repo_root / path).exists()]
    if existing:
        return {"paths": existing, "preferred_path": existing[0], "mapping_status": "mapped", "reason": "preferred_path exists in local repository artifacts/docs/source"}
    return {"paths": [], "preferred_path": None, "mapping_status": "unmapped", "reason": "No direct log mapping"}


def build_lineage_index(repo_root: Path | str, graph: dict[str, Any] | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    graph = graph or build_governance_graph(repo_root)
    nodes = {item.get("id", ""): _mapping(repo_root, item) for item in graph.get("nodes", []) if item.get("id")}
    edges = {item.get("id", ""): _mapping(repo_root, item) for item in graph.get("edges", []) if item.get("id")}
    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": dict(sorted(nodes.items())),
        "edges": dict(sorted(edges.items())),
        "warnings": [],
        "blockers": [],
    }


def write_lineage_index(repo_root: Path | str, out_path: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    out = Path(out_path) if out_path else repo_root / "artifacts" / "v2" / "lineage" / "log-index.json"
    if not out.is_absolute():
        out = repo_root / out
    data = build_lineage_index(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mapped_nodes = sum(1 for item in data["nodes"].values() if item["mapping_status"] == "mapped")
    mapped_edges = sum(1 for item in data["edges"].values() if item["mapping_status"] == "mapped")
    return {
        "generated_at": _utc_now(),
        "status": "PASS" if not data["blockers"] else "FAIL",
        "path": _rel(repo_root, out),
        "node_count": len(data["nodes"]),
        "edge_count": len(data["edges"]),
        "mapped_nodes": mapped_nodes,
        "mapped_edges": mapped_edges,
        "view_in_logs_requires_mapping": True,
        "warnings": data["warnings"],
        "blockers": data["blockers"],
    }


def _load_index(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / "artifacts" / "v2" / "lineage" / "log-index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def validate_lineage_index(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    data = _load_index(repo_root) or build_lineage_index(repo_root)
    blockers: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        blockers.append("lineage index schema_version must be 2.0")
    for section in ("nodes", "edges"):
        if not isinstance(data.get(section), dict):
            blockers.append(f"{section} must be a mapping")
            continue
        for ref_id, mapping in data[section].items():
            if mapping.get("mapping_status") not in {"mapped", "unmapped"}:
                blockers.append(f"{section}.{ref_id} has invalid mapping_status")
            if mapping.get("mapping_status") == "mapped" and not mapping.get("preferred_path"):
                blockers.append(f"{section}.{ref_id} is mapped without preferred_path")
    return {
        "generated_at": _utc_now(),
        "status": "PASS" if not blockers else "FAIL",
        "path": "artifacts/v2/lineage/log-index.json",
        "node_count": len(data.get("nodes", {})),
        "edge_count": len(data.get("edges", {})),
        "view_in_logs_requires_mapping": True,
        "warnings": data.get("warnings", []),
        "blockers": blockers,
    }


def mapping_for_ref(index: dict[str, Any], section: str, ref_id: str) -> dict[str, Any]:
    mapping = index.get(section, {}).get(ref_id) or {"mapping_status": "unmapped", "preferred_path": None, "reason": "No direct log mapping"}
    enabled = mapping.get("mapping_status") == "mapped" and bool(mapping.get("preferred_path"))
    return {
        "enabled": enabled,
        "preferred_path": mapping.get("preferred_path") if enabled else None,
        "label": "View in Logs" if enabled else "No direct log mapping",
        "reason": mapping.get("reason") or ("mapped" if enabled else "No direct log mapping"),
    }
