from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import (
    collection_document,
    default_graph_fragment,
    default_project_manifest,
    default_project_summary,
    deterministic_write_json,
    read_json,
)


def project_dir(memory_root: Path, profile_id: str, project_id: str) -> Path:
    return memory_root / 'projects' / profile_id / project_id


def project_manifest_path(memory_root: Path, profile_id: str, project_id: str) -> Path:
    return project_dir(memory_root, profile_id, project_id) / 'project-manifest.json'


def ensure_project(memory_root: Path, profile_id: str, project_id: str) -> Path:
    root = project_dir(memory_root, profile_id, project_id)
    payloads = {
        'project-manifest.json': default_project_manifest(profile_id, project_id),
        'project-summary.json': default_project_summary(profile_id, project_id),
        'decision-ledger.json': collection_document(profile_id, project_id, 'decision-ledger'),
        'requirements.json': collection_document(profile_id, project_id, 'requirements'),
        'constraints.json': collection_document(profile_id, project_id, 'constraints'),
        'session-index.json': collection_document(profile_id, project_id, 'session-index'),
        'graph-fragment.json': default_graph_fragment(profile_id, project_id),
        'lineage-index.json': {'schema_version': '2.0', 'view_in_logs_requires_mapping': True, 'nodes': {}, 'edges': {}, 'warnings': [], 'blockers': []},
    }
    for name, payload in payloads.items():
        target = root / name
        if not target.exists():
            deterministic_write_json(target, payload)
    return root


def load_project_bundle(memory_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    root = ensure_project(memory_root, profile_id, project_id)
    return {
        'root': root,
        'manifest': read_json(root / 'project-manifest.json'),
        'summary': read_json(root / 'project-summary.json'),
        'decision_ledger': read_json(root / 'decision-ledger.json'),
        'requirements': read_json(root / 'requirements.json'),
        'constraints': read_json(root / 'constraints.json'),
        'session_index': read_json(root / 'session-index.json'),
        'graph_fragment': read_json(root / 'graph-fragment.json'),
        'lineage_index': read_json(root / 'lineage-index.json'),
    }


def write_project_bundle(memory_root: Path, profile_id: str, project_id: str, bundle: dict[str, Any]) -> None:
    root = ensure_project(memory_root, profile_id, project_id)
    deterministic_write_json(root / 'project-manifest.json', bundle['manifest'])
    deterministic_write_json(root / 'project-summary.json', bundle['summary'])
    deterministic_write_json(root / 'decision-ledger.json', bundle['decision_ledger'])
    deterministic_write_json(root / 'requirements.json', bundle['requirements'])
    deterministic_write_json(root / 'constraints.json', bundle['constraints'])
    deterministic_write_json(root / 'session-index.json', bundle['session_index'])
    deterministic_write_json(root / 'graph-fragment.json', bundle['graph_fragment'])
    deterministic_write_json(root / 'lineage-index.json', bundle['lineage_index'])
