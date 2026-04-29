from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root, utc_now


def _gap_id(query: str, gap_type: str) -> str:
    digest = hashlib.sha256(f"{gap_type}:{query}".encode("utf-8")).hexdigest()[:12]
    return f"gap:{gap_type}:{digest}"


def record_context_gap(repo_root: Path | str, memory_root: Path | str | None, query: str, gap_type: str, reason: str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    target = memory_root / "routing" / "context-gaps" / f"{_gap_id(query, gap_type)}.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": _gap_id(query, gap_type),
        "gap_type": gap_type,
        "query": query,
        "profile": manifest.get("profile"),
        "project": manifest.get("project"),
        "reason": reason,
        "raw_sessions_allowed": False,
        "created_at": utc_now(),
        "status": "open",
    }
    if not target.exists():
        deterministic_write_json(target, payload)
    else:
        payload = read_json(target)
    return {"status": "PASS", "gap_path": target.as_posix(), "gap": payload, "warnings": [], "blockers": []}


def list_context_gaps(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    root = memory_root / "routing" / "context-gaps"
    gaps = []
    if root.exists():
        for path in sorted(root.glob("*.json")):
            gaps.append(read_json(path))
    return {
        "status": "PASS",
        "repo_path": repo_root.as_posix(),
        "profile": manifest.get("profile"),
        "project": manifest.get("project"),
        "context_gaps_root": root.as_posix(),
        "gaps": gaps,
        "warnings": [],
        "blockers": [],
    }
