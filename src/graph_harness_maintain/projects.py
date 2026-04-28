from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"
DEFAULT_PROFILE_ID = "general"
DEFAULT_PROJECT_ID = "harness-self-governance"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def project_root(repo_root: Path | str, profile_id: str, project_id: str) -> Path:
    return Path(repo_root).resolve() / "artifacts" / "v2" / "projects" / profile_id / project_id


def build_project_manifest(profile_id: str = DEFAULT_PROFILE_ID, project_id: str = DEFAULT_PROJECT_ID) -> dict[str, Any]:
    base = f"artifacts/v2/projects/{profile_id}/{project_id}"
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "title": "Harness Self Governance" if project_id == DEFAULT_PROJECT_ID else project_id.replace("-", " ").title(),
        "status": "active",
        "role": "governance_project" if profile_id == "general" else "knowledge_project",
        "sessions": [],
        "decisions": [],
        "requirements": [],
        "constraints": [],
        "artifacts": [],
        "summaries": [],
        "graph_nodes": [f"project:{profile_id}:{project_id}", f"project_summary:{profile_id}:{project_id}"],
        "graph_edges": [f"edge:profile:{profile_id}:owns-project:{project_id}"],
        "summary_path": f"{base}/project-summary.json",
        "warnings": [],
        "blockers": [],
    }


def build_default_project_summary(profile_id: str = DEFAULT_PROFILE_ID, project_id: str = DEFAULT_PROJECT_ID) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "privacy": "local_only",
        "summary": "Agent-triggered local archive summary for the v2.0 read-only Graph and Logs governance hub foundation.",
        "decisions": [
            {
                "id": "decision:v2-core-graph-logs",
                "text": "v2.0 uses Graph and Logs as the two core pages.",
                "status": "accepted",
                "source": "agent_archive",
            }
        ],
        "requirements": [
            {
                "id": "requirement:graph-main-focus",
                "text": "The Graph page should make the graph the primary user focus.",
                "source": "agent_archive",
            }
        ],
        "constraints": [
            {
                "id": "constraint:read-only-ui",
                "text": "The Hub remains read-only and local-first.",
                "source": "agent_archive",
            }
        ],
        "graph_links": [
            {
                "source": "decision:v2-core-graph-logs",
                "target": "requirement:graph-main-focus",
                "type": "supports",
            }
        ],
        "warnings": [],
        "blockers": [],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_project(repo_root: Path | str, profile_id: str = DEFAULT_PROFILE_ID, project_id: str = DEFAULT_PROJECT_ID) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    root = project_root(repo_root, profile_id, project_id)
    manifest = build_project_manifest(profile_id, project_id)
    summary = build_default_project_summary(profile_id, project_id)
    manifest_path = root / "project-manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(root / "project-summary.json", summary)
    _write_json(root / "decision-ledger.json", {"schema_version": SCHEMA_VERSION, "privacy": "local_only", "decisions": summary["decisions"], "warnings": [], "blockers": []})
    _write_json(root / "requirements.json", {"schema_version": SCHEMA_VERSION, "privacy": "local_only", "requirements": summary["requirements"], "warnings": [], "blockers": []})
    _write_json(root / "constraints.json", {"schema_version": SCHEMA_VERSION, "privacy": "local_only", "constraints": summary["constraints"], "warnings": [], "blockers": []})
    _write_json(root / "session-index.json", {"schema_version": SCHEMA_VERSION, "privacy": "local_only", "sessions": [], "warnings": [], "blockers": []})
    return {
        "generated_at": _utc_now(),
        "status": "PASS",
        "profile_id": profile_id,
        "project_id": project_id,
        "manifest_path": _rel(repo_root, manifest_path),
        "summary_path": _rel(repo_root, root / "project-summary.json"),
        "llm_api_required": False,
        "warnings": [],
        "blockers": [],
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def validate_agent_archive_contract(summary: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if summary.get("schema_version") != SCHEMA_VERSION:
        blockers.append("project summary schema_version must be 2.0")
    if summary.get("privacy") != "local_only":
        blockers.append("project summary privacy must be local_only")
    for key in ("decisions", "requirements", "constraints", "graph_links"):
        if not isinstance(summary.get(key), list):
            blockers.append(f"{key} must be a list")
    return {
        "status": "PASS" if not blockers else "FAIL",
        "llm_hub_api_enabled": False,
        "agent_triggered_archive": True,
        "blockers": blockers,
        "warnings": summary.get("warnings", []),
    }


def validate_project(repo_root: Path | str, profile_id: str = DEFAULT_PROFILE_ID, project_id: str = DEFAULT_PROJECT_ID) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    root = project_root(repo_root, profile_id, project_id)
    manifest = _load_json(root / "project-manifest.json")
    summary = _load_json(root / "project-summary.json")
    blockers: list[str] = []
    if not manifest:
        blockers.append("project-manifest.json is missing or invalid")
    else:
        if manifest.get("schema_version") != SCHEMA_VERSION:
            blockers.append("project manifest schema_version must be 2.0")
        if manifest.get("profile_id") != profile_id or manifest.get("project_id") != project_id:
            blockers.append("project manifest profile/project mismatch")
        if manifest.get("summary_path") != f"artifacts/v2/projects/{profile_id}/{project_id}/project-summary.json":
            blockers.append("project manifest summary_path mismatch")
    if not summary:
        blockers.append("project-summary.json is missing or invalid")
        contract = {"blockers": []}
    else:
        contract = validate_agent_archive_contract(summary)
        blockers.extend(contract.get("blockers", []))
    return {
        "generated_at": _utc_now(),
        "status": "PASS" if not blockers else "FAIL",
        "profile_id": profile_id,
        "project_id": project_id,
        "manifest_path": f"artifacts/v2/projects/{profile_id}/{project_id}/project-manifest.json",
        "summary_path": f"artifacts/v2/projects/{profile_id}/{project_id}/project-summary.json",
        "llm_api_required": False,
        "llm_hub_api_enabled": False,
        "agent_triggered_archive": True,
        "warnings": [],
        "blockers": blockers,
    }
