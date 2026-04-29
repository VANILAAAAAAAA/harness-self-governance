from __future__ import annotations

from pathlib import Path
from typing import Any

from .profiles import build_profile_index
from .projects import load_project_bundle
from .schemas import default_global_lineage, deterministic_write_json


def _project_lineage(profile_id: str, project_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    root = Path('projects') / profile_id / project_id
    nodes: dict[str, Any] = {
        f'profile:{profile_id}': {'mapping_status': 'mapped', 'preferred_path': (root / 'project-manifest.json').as_posix(), 'paths': [(root / 'project-manifest.json').as_posix()], 'reason': 'profile maps to project manifest'},
        f'project:{profile_id}:{project_id}': {'mapping_status': 'mapped', 'preferred_path': (root / 'project-manifest.json').as_posix(), 'paths': [(root / 'project-manifest.json').as_posix()], 'reason': 'project maps to project manifest'},
        f'project_summary:{profile_id}:{project_id}': {'mapping_status': 'mapped', 'preferred_path': (root / 'project-summary.json').as_posix(), 'paths': [(root / 'project-summary.json').as_posix()], 'reason': 'summary maps to project summary'},
    }
    edges: dict[str, Any] = {}
    for decision in bundle['decision_ledger'].get('decisions', []):
        decision_id = decision.get('id')
        if decision_id:
            nodes[decision_id] = {'mapping_status': 'mapped', 'preferred_path': (root / 'decision-ledger.json').as_posix(), 'paths': [(root / 'decision-ledger.json').as_posix()], 'reason': 'decision maps to decision ledger'}
            edges[f'edge:project:{profile_id}:{project_id}:decision:{decision_id}'] = {'mapping_status': 'mapped', 'preferred_path': (root / 'decision-ledger.json').as_posix(), 'paths': [(root / 'decision-ledger.json').as_posix()], 'reason': 'decision edge maps to decision ledger'}
    for requirement in bundle['requirements'].get('requirements', []):
        requirement_id = requirement.get('id')
        if requirement_id:
            nodes[requirement_id] = {'mapping_status': 'mapped', 'preferred_path': (root / 'requirements.json').as_posix(), 'paths': [(root / 'requirements.json').as_posix()], 'reason': 'requirement maps to requirements artifact'}
    for constraint in bundle['constraints'].get('constraints', []):
        constraint_id = constraint.get('id')
        if constraint_id:
            nodes[constraint_id] = {'mapping_status': 'mapped', 'preferred_path': (root / 'constraints.json').as_posix(), 'paths': [(root / 'constraints.json').as_posix()], 'reason': 'constraint maps to constraints artifact'}
    for session in bundle['session_index'].get('sessions', []):
        session_id = session.get('session_id')
        if session_id:
            nodes[session_id] = {'mapping_status': 'mapped', 'preferred_path': (root / 'session-index.json').as_posix(), 'paths': [(root / 'session-index.json').as_posix()], 'reason': 'session maps to session index'}
    for link in bundle['summary'].get('graph_links', []):
        source = link.get('source')
        target = link.get('target')
        link_type = link.get('type')
        if source and target and link_type:
            edge_id = f'edge:{source}:{link_type}:{target}'
            edges[edge_id] = {'mapping_status': 'mapped', 'preferred_path': (root / 'graph-fragment.json').as_posix(), 'paths': [(root / 'graph-fragment.json').as_posix()], 'reason': 'graph link maps to graph fragment'}
    return {'nodes': nodes, 'edges': edges}


def write_global_lineage(memory_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    bundle = load_project_bundle(memory_root, profile_id, project_id)
    lineage = default_global_lineage()
    lineage['profile_index'] = build_profile_index(memory_root)
    lineage.update(_project_lineage(profile_id, project_id, bundle))
    target = memory_root / 'graph' / 'global-lineage-index.json'
    deterministic_write_json(target, lineage)
    deterministic_write_json(bundle['root'] / 'lineage-index.json', lineage)
    return lineage
