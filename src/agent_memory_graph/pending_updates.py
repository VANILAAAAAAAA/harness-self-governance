from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root, utc_now


def _update_id(profile_id: str, project_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{profile_id}:{project_id}:{text}".encode("utf-8")).hexdigest()[:12]
    return f"pending-update:{digest}"


def capture_pending_update(repo_root: Path | str, text: str, profile_id: str, project_id: str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    target = memory_root / "routing" / "pending-updates.json"
    payload = read_json(target, default={
        "schema_version": SCHEMA_VERSION,
        "routing_policy": "new_information_becomes_pending_update",
        "updates": [],
        "warnings": [],
        "blockers": [],
    })
    update = {
        "id": _update_id(profile_id, project_id, text),
        "profile": profile_id,
        "project": project_id,
        "text": text,
        "status": "pending_archive_compilation",
        "raw_sessions_allowed": False,
        "created_at": utc_now(),
        "source": "agent_graph_capture_update",
    }
    updates = {item.get("id"): item for item in payload.get("updates", []) if isinstance(item, dict)}
    updates[update["id"]] = update
    payload["updates"] = [updates[key] for key in sorted(updates)]
    deterministic_write_json(target, payload)
    return {
        "status": "PASS",
        "repo_path": repo_root.as_posix(),
        "pending_updates_path": target.as_posix(),
        "update": update,
        "warnings": [],
        "blockers": [],
    }
