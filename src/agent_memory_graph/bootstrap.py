from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .export import write_global_graph
from .lineage import write_global_lineage
from .profiles import ensure_profile
from .projects import ensure_project
from .repo_adapter import context_path, read_repo_manifest
from .schemas import (
    RECOMMENDED_READ_ORDER,
    default_config,
    deterministic_write_json,
    ensure_memory_layout,
    read_json,
    relpath,
    resolve_memory_root,
    validate_id,
)


def _write_config(memory_root: Path) -> Path:
    target = memory_root / "config.json"
    if not target.exists():
        deterministic_write_json(target, default_config())
    return target


def bootstrap_repo(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    blockers: list[str] = []
    manifest = read_repo_manifest(repo_root)
    ensure_memory_layout(memory_root)
    if not manifest:
        blockers.append(".agent/context.json is missing; run agent-graph init-repo first")
        report = {"status": "FAIL", "repo_path": repo_root.as_posix(), "warnings": [], "blockers": blockers}
        deterministic_write_json(memory_root / "reports" / "context-bootstrap-report.json", report)
        return report
    profile_id = str(manifest.get("profile", ""))
    project_id = str(manifest.get("project", ""))
    blockers.extend(validate_id(profile_id, "profile"))
    blockers.extend(validate_id(project_id, "project"))
    config_path = _write_config(memory_root)
    profile_path = ensure_profile(memory_root, profile_id)
    project_root = ensure_project(memory_root, profile_id, project_id)
    graph_path = memory_root / "graph" / "global-graph.json"
    lineage_path = memory_root / "graph" / "global-lineage-index.json"
    write_global_graph(memory_root, profile_id, project_id)
    write_global_lineage(memory_root, profile_id, project_id)
    report = {
        "status": "PASS" if not blockers else "FAIL",
        "repo_path": repo_root.as_posix(),
        "memory_root": memory_root.as_posix(),
        "profile": profile_id,
        "project": project_id,
        "config_path": config_path.as_posix(),
        "graph_path": graph_path.as_posix(),
        "profile_path": profile_path.as_posix(),
        "project_manifest_path": (project_root / "project-manifest.json").as_posix(),
        "project_summary_path": (project_root / "project-summary.json").as_posix(),
        "decision_ledger_path": (project_root / "decision-ledger.json").as_posix(),
        "requirements_path": (project_root / "requirements.json").as_posix(),
        "constraints_path": (project_root / "constraints.json").as_posix(),
        "lineage_index_path": lineage_path.as_posix(),
        "recommended_read_order": RECOMMENDED_READ_ORDER,
        "raw_sessions_policy": "last_resort",
        "warnings": [],
        "blockers": blockers,
    }
    deterministic_write_json(memory_root / "reports" / "context-bootstrap-report.json", report)
    return report


def validate_repo(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    blockers: list[str] = []
    warnings: list[str] = []
    manifest_path = context_path(repo_root)
    if not manifest_path.exists():
        blockers.append(".agent/context.json does not exist")
        return {"status": "FAIL", "warnings": warnings, "blockers": blockers}
    manifest = read_repo_manifest(repo_root)
    profile_id = str(manifest.get("profile", ""))
    project_id = str(manifest.get("project", ""))
    blockers.extend(validate_id(profile_id, "profile"))
    blockers.extend(validate_id(project_id, "project"))
    config = read_json(memory_root / "config.json", default=default_config())
    if config.get("default_context_order") != RECOMMENDED_READ_ORDER:
        blockers.append("default_context_order must be graph-first with raw_sessions last")
    if config.get("raw_sessions_policy") != "last_resort":
        blockers.append("raw_sessions_policy must be last_resort")
    if config.get("graph_mutation_enabled") is not False:
        blockers.append("graph_mutation_enabled must be false")
    if config.get("destructive_operations_enabled") is not False:
        blockers.append("destructive_operations_enabled must be false")
    profile_path = memory_root / "profiles" / profile_id / "profile.json"
    project_root = memory_root / "projects" / profile_id / project_id
    if not profile_path.exists():
        blockers.append("profile can not be resolved under memory root")
    if not project_root.exists():
        blockers.append("project can not be resolved under memory root")
    export_to = ((manifest.get("memory_graph") or {}).get("export_to") or {})
    graph_path = repo_root / str(export_to.get("graph", ""))
    project_export_root = repo_root / str(export_to.get("project", ""))
    lineage_path = repo_root / str(export_to.get("lineage", ""))
    if graph_path.name != "governance-graph.json":
        blockers.append("graph export path must end with governance-graph.json")
    if lineage_path.name != "log-index.json":
        blockers.append("lineage export path must end with log-index.json")
    if not str(project_export_root).endswith(f"artifacts/v2/projects/{profile_id}/{project_id}"):
        blockers.append("project export path is not coherent with profile/project ids")
    if "raw_sessions" != RECOMMENDED_READ_ORDER[-1]:
        blockers.append("raw sessions are not the default context tail")
    if ((manifest.get("memory_graph") or {}).get("source")) != "global":
        blockers.append("memory_graph.source must be global")
    if os.path.isabs(str(export_to.get("graph", ""))):
        blockers.append("repo export paths must be relative")
    return {
        "status": "PASS" if not blockers else "FAIL",
        "repo_path": repo_root.as_posix(),
        "memory_root": memory_root.as_posix(),
        "profile": profile_id,
        "project": project_id,
        "graph_path": relpath(graph_path, repo_root),
        "project_export_root": relpath(project_export_root, repo_root),
        "lineage_path": relpath(lineage_path, repo_root),
        "raw_sessions_default_read": False,
        "warnings": warnings,
        "blockers": blockers,
    }
