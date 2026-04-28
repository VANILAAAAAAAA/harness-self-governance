from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json

CONTEXT_PATH = Path('.agent/context.json')


def context_path(repo_root: Path | str) -> Path:
    return Path(repo_root).resolve() / CONTEXT_PATH


def build_repo_manifest(profile_id: str, project_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": profile_id,
        "project": project_id,
        "role": "governance_project" if profile_id == "general" else "knowledge_project",
        "memory_graph": {
            "source": "global",
            "export_to": {
                "graph": "artifacts/v2/graph/governance-graph.json",
                "project": f"artifacts/v2/projects/{profile_id}/{project_id}/",
                "lineage": "artifacts/v2/lineage/log-index.json",
            },
        },
        "adapters": {
            "repo_artifacts": True,
            "git_history": True,
            "sessions": True,
            "docs": True,
            "tests": True,
        },
    }


def init_repo_manifest(repo_root: Path | str, profile_id: str, project_id: str, force: bool = False) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    manifest_path = context_path(repo_root)
    if manifest_path.exists() and not force:
        return {
            "status": "PASS",
            "created": False,
            "path": manifest_path.relative_to(repo_root).as_posix(),
            "profile": read_repo_manifest(repo_root).get("profile"),
            "project": read_repo_manifest(repo_root).get("project"),
            "warnings": [],
            "blockers": [],
        }
    manifest = build_repo_manifest(profile_id, project_id)
    deterministic_write_json(manifest_path, manifest)
    return {
        "status": "PASS",
        "created": True,
        "path": manifest_path.relative_to(repo_root).as_posix(),
        "profile": profile_id,
        "project": project_id,
        "warnings": [],
        "blockers": [],
    }


def read_repo_manifest(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    return read_json(context_path(repo_root), default={})
