from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .archive_triggers import write_archive_trigger_report
from .lineage import write_global_lineage
from .profiles import build_profile_index, ensure_profile
from .projects import ensure_project, load_project_bundle
from .repo_adapter import read_repo_manifest
from .schemas import default_global_graph, deterministic_write_json, read_json, relpath


def _node(node_id: str, node_type: str, label: str, **extra: Any) -> dict[str, Any]:
    payload = {
        'id': node_id,
        'type': node_type,
        'kind': node_type,
        'label': label,
        'status': extra.pop('status', 'available'),
        'summary': extra.pop('summary', label),
        'description': extra.pop('description', label),
        'metadata': extra.pop('metadata', {}),
        'read_only': True,
        'sensitivity': extra.pop('sensitivity', 'none'),
    }
    payload.update(extra)
    return payload


def _edge(edge_id: str, source: str, target: str, edge_type: str, **extra: Any) -> dict[str, Any]:
    payload = {
        'id': edge_id,
        'source': source,
        'target': target,
        'type': edge_type,
        'relation': edge_type,
        'label': edge_type.replace('_', ' '),
        'status': extra.pop('status', 'active'),
        'confidence': extra.pop('confidence', 1.0),
        'metadata': extra.pop('metadata', {}),
    }
    payload.update(extra)
    return payload


def build_global_graph(memory_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    ensure_profile(memory_root, profile_id)
    ensure_project(memory_root, profile_id, project_id)
    bundle = load_project_bundle(memory_root, profile_id, project_id)
    graph = default_global_graph()
    manifest = bundle['manifest']
    summary = bundle['summary']
    nodes = [
        _node(f'profile:{profile_id}', 'profile', profile_id, summary=f'{profile_id} profile context'),
        _node(f'project:{profile_id}:{project_id}', 'project', project_id, summary=f'Active project {project_id}'),
        _node(f'project_summary:{profile_id}:{project_id}', 'project_summary', f'{project_id} summary', summary=summary.get('summary') or 'Project summary'),
        _node('protocol:graph-governed-context', 'policy', 'graph-governed context protocol', summary='Graph-first context loading; raw sessions last.'),
        _node('tool:agent-graph-cli', 'tool', 'agent-graph CLI', summary='Portable CLI for repo manifest, bootstrap, validate, archive-session, and export commands.'),
    ]
    edges = [
        _edge(f'edge:profile:{profile_id}:owns-project:{project_id}', f'profile:{profile_id}', f'project:{profile_id}:{project_id}', 'owns_project'),
        _edge(f'edge:project:{profile_id}:{project_id}:summarizes', f'project:{profile_id}:{project_id}', f'project_summary:{profile_id}:{project_id}', 'summarizes'),
        _edge(f'edge:project:{profile_id}:{project_id}:governed-by-protocol', f'project:{profile_id}:{project_id}', 'protocol:graph-governed-context', 'governed_by'),
        _edge(f'edge:project:{profile_id}:{project_id}:uses-agent-graph', f'project:{profile_id}:{project_id}', 'tool:agent-graph-cli', 'uses_tool'),
    ]
    for decision in bundle['decision_ledger'].get('decisions', []):
        decision_id = decision.get('id')
        if not decision_id:
            continue
        nodes.append(_node(decision_id, 'decision', decision.get('text', decision_id)[:80], summary=decision.get('text', decision_id), metadata={'source': decision.get('source'), 'status': decision.get('status', 'accepted')}))
        edges.append(_edge(f'edge:summary:{decision_id}', f'project_summary:{profile_id}:{project_id}', decision_id, 'summarizes'))
    for requirement in bundle['requirements'].get('requirements', []):
        requirement_id = requirement.get('id')
        if not requirement_id:
            continue
        nodes.append(_node(requirement_id, 'requirement', requirement.get('text', requirement_id)[:80], summary=requirement.get('text', requirement_id), metadata={'source': requirement.get('source')}))
        edges.append(_edge(f'edge:summary:{requirement_id}', f'project_summary:{profile_id}:{project_id}', requirement_id, 'summarizes'))
    for constraint in bundle['constraints'].get('constraints', []):
        constraint_id = constraint.get('id')
        if not constraint_id:
            continue
        nodes.append(_node(constraint_id, 'constraint', constraint.get('text', constraint_id)[:80], summary=constraint.get('text', constraint_id), metadata={'source': constraint.get('source')}))
        edges.append(_edge(f'edge:summary:{constraint_id}', f'project_summary:{profile_id}:{project_id}', constraint_id, 'constrains'))
    for session in bundle['session_index'].get('sessions', []):
        session_id = session.get('session_id')
        if not session_id:
            continue
        nodes.append(_node(session_id, 'session', session_id, summary=session.get('summary', session_id), metadata={'privacy': session.get('privacy', 'local_only')}))
        edges.append(_edge(f'edge:project:{project_id}:session:{session_id}', f'project:{profile_id}:{project_id}', session_id, 'archives_session'))
    for link in summary.get('graph_links', []):
        source = link.get('source')
        target = link.get('target')
        link_type = link.get('type')
        if source and target and link_type:
            edges.append(_edge(f'edge:{source}:{link_type}:{target}', source, target, link_type, confidence=0.8))
    graph['nodes'] = sorted(nodes, key=lambda item: item['id'])
    graph['edges'] = sorted(edges, key=lambda item: item['id'])
    maintenance = read_json(memory_root / 'reports' / 'archive-maintenance-report.json')
    trigger_report = read_json(memory_root / 'reports' / 'archive-trigger-report.json')
    graph['summary'] = {
        'profile_support': True,
        'project_support': True,
        'global_agent_memory_graph_supported': True,
        'graph_governed_context_protocol': True,
        'raw_sessions_default_read': False,
        'live_session_boundary_supported': True,
        'archive_gate_available': (memory_root / 'reports' / 'archive-gate-report.json').exists(),
        'archive_maintenance_available': bool(maintenance),
        'archive_trigger_policy_available': True,
        'archive_trigger_report_available': bool(trigger_report),
        'repo_context_manifest_available': True,
        'agent_graph_cli_available': True,
        'project_role': manifest.get('role'),
        'archive_quality_status': maintenance.get('archive_quality_status', 'unknown'),
        'latest_archive_recommendation_count': trigger_report.get('latest_recommendation_count', 0),
    }
    return graph


def write_global_graph(memory_root: Path, profile_id: str, project_id: str) -> dict[str, Any]:
    graph = build_global_graph(memory_root, profile_id, project_id)
    deterministic_write_json(memory_root / 'graph' / 'global-graph.json', graph)
    return graph


def _rewrite_lineage_for_repo(lineage: dict[str, Any], profile_id: str, project_id: str, project_export_root: Path, repo_root: Path) -> dict[str, Any]:
    from copy import deepcopy

    repo_lineage = deepcopy(lineage)
    source_prefix = f'projects/{profile_id}/{project_id}/'
    target_prefix = relpath(project_export_root, repo_root).rstrip('/') + '/'
    for section in ('nodes', 'edges'):
        for mapping in repo_lineage.get(section, {}).values():
            paths = []
            for path in mapping.get('paths', []):
                if isinstance(path, str) and path.startswith(source_prefix):
                    paths.append(target_prefix + path.removeprefix(source_prefix))
                else:
                    paths.append(path)
            mapping['paths'] = paths
            preferred = mapping.get('preferred_path')
            if isinstance(preferred, str) and preferred.startswith(source_prefix):
                mapping['preferred_path'] = target_prefix + preferred.removeprefix(source_prefix)
    return repo_lineage


def export_repo_projection(repo_root: Path | str, memory_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = Path(memory_root).resolve()
    manifest = read_repo_manifest(repo_root)
    profile_id = manifest['profile']
    project_id = manifest['project']
    bundle = load_project_bundle(memory_root, profile_id, project_id)
    write_archive_trigger_report(repo_root, memory_root)
    graph = write_global_graph(memory_root, profile_id, project_id)
    lineage = write_global_lineage(memory_root, profile_id, project_id)
    profile_index = build_profile_index(memory_root)
    project_export_root = repo_root / manifest['memory_graph']['export_to']['project']
    project_export_root.mkdir(parents=True, exist_ok=True)
    for name in (
        'project-manifest.json',
        'project-summary.json',
        'decision-ledger.json',
        'requirements.json',
        'constraints.json',
        'session-index.json',
        'graph-fragment.json',
    ):
        shutil.copyfile(bundle['root'] / name, project_export_root / name)
    repo_lineage = _rewrite_lineage_for_repo(lineage, profile_id, project_id, project_export_root, repo_root)
    deterministic_write_json(project_export_root / 'lineage-index.json', repo_lineage)
    graph_path = repo_root / manifest['memory_graph']['export_to']['graph']
    lineage_path = repo_root / manifest['memory_graph']['export_to']['lineage']
    deterministic_write_json(graph_path, graph)
    deterministic_write_json(lineage_path, repo_lineage)
    profile_index_path = repo_root / 'artifacts' / 'v2' / 'profiles' / 'profile-index.json'
    deterministic_write_json(profile_index_path, profile_index)
    maintenance_root = repo_root / 'artifacts' / 'v2' / 'maintenance'
    maintenance_root.mkdir(parents=True, exist_ok=True)
    for name in (
        'archive-gate-report.json',
        'archive-maintenance-report.json',
        'archive-maintenance-proposal.json',
        'archive-trigger-report.json',
    ):
        source = memory_root / 'reports' / name
        if source.exists():
            shutil.copyfile(source, maintenance_root / name)
    return {
        'status': 'PASS',
        'repo_path': repo_root.as_posix(),
        'memory_root': memory_root.as_posix(),
        'profile': profile_id,
        'project': project_id,
        'project_export_root': relpath(project_export_root, repo_root),
        'memory_graph_path': relpath(graph_path, repo_root),
        'graph_path': relpath(graph_path, repo_root),
        'lineage_path': relpath(lineage_path, repo_root),
        'profile_index_path': relpath(profile_index_path, repo_root),
        'warnings': [],
        'blockers': [],
    }
