from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def build_profile_index() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "active_profile": "general",
        "profiles": [
            {
                "profile_id": "general",
                "label": "General Governance",
                "role": "governance_hub",
                "description": "General remains the governance center for cross-project policy, release, provenance, and system health.",
                "projects": ["harness-self-governance"],
            },
            {
                "profile_id": "ehrlab",
                "label": "EHR Lab",
                "role": "knowledge_profile",
                "description": "Domain/project profile for EHR and healthcare modeling work.",
                "projects": ["dirtycsv"],
            },
        ],
        "warnings": [],
        "blockers": [],
    }


def write_profile_index(repo_root: Path | str, out_path: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    out = Path(out_path) if out_path else repo_root / "artifacts" / "v2" / "profiles" / "profile-index.json"
    if not out.is_absolute():
        out = repo_root / out
    data = build_profile_index()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "generated_at": _utc_now(),
        "status": "PASS" if not data["blockers"] else "FAIL",
        "path": _rel(repo_root, out),
        "active_profile": data["active_profile"],
        "profile_count": len(data["profiles"]),
        "warnings": data["warnings"],
        "blockers": data["blockers"],
    }


def _load_profile_index(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / "artifacts" / "v2" / "profiles" / "profile-index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def validate_profile_index(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    data = _load_profile_index(repo_root) or build_profile_index()
    blockers: list[str] = []
    profile_ids = [item.get("profile_id") for item in data.get("profiles", [])]
    if data.get("schema_version") != SCHEMA_VERSION:
        blockers.append("profile index schema_version must be 2.0")
    if data.get("active_profile") not in profile_ids:
        blockers.append("active_profile must be present in profiles")
    roles = {item.get("profile_id"): item.get("role") for item in data.get("profiles", [])}
    if roles.get("general") != "governance_hub":
        blockers.append("general profile must remain governance_hub")
    if "ehrlab" not in profile_ids:
        blockers.append("ehrlab profile must be present as a knowledge profile")
    return {
        "generated_at": _utc_now(),
        "status": "PASS" if not blockers else "FAIL",
        "path": "artifacts/v2/profiles/profile-index.json",
        "active_profile": data.get("active_profile"),
        "profile_count": len(data.get("profiles", [])),
        "warnings": data.get("warnings", []),
        "blockers": blockers,
    }
