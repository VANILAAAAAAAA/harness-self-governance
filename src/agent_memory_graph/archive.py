from __future__ import annotations

from pathlib import Path
from typing import Any


def _slug(value: str) -> str:
    import re
    return re.sub(r'[^a-z0-9一-龥]+', '-', str(value).lower()).strip('-') or 'unnamed'

from .export import write_global_graph
from .lineage import write_global_lineage
from .profiles import ensure_profile, load_profile
from .projects import load_project_bundle, write_project_bundle
from .schemas import (
    default_project_summary,
    deterministic_write_json,
    read_json,
    stable_items_by_id,
    stable_links,
    validate_compiled_session,
)


def _session_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        'session_id': payload['session_id'],
        'privacy': payload['privacy'],
        'summary': payload['summary'],
    }


def _merge_summary(existing: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(existing or default_project_summary(payload['profile_id'], payload['project_id']))
    session_summaries = list(summary.get('session_summaries', []))
    session_summaries.append(_session_entry(payload))
    summary['session_summaries'] = stable_items_by_id(session_summaries, id_key='session_id')
    summary['summary'] = ' | '.join(item['summary'] for item in summary['session_summaries'] if item.get('summary'))
    summary['privacy'] = 'local_only' if 'local_only' in {summary.get('privacy'), payload.get('privacy')} else payload['privacy']
    summary['decisions'] = stable_items_by_id(list(summary.get('decisions', [])) + list(payload.get('decisions', [])))
    summary['requirements'] = stable_items_by_id(list(summary.get('requirements', [])) + list(payload.get('requirements', [])))
    summary['constraints'] = stable_items_by_id(list(summary.get('constraints', [])) + list(payload.get('constraints', [])))
    summary['graph_links'] = stable_links(list(summary.get('graph_links', [])) + list(payload.get('graph_links', [])))
    summary['key_skills'] = stable_items_by_id(list(summary.get('key_skills', [])) + list(payload.get('key_skills', [])), id_key='id')
    summary['warnings'] = []
    summary['blockers'] = []
    return summary


def _build_graph_fragment(profile_id: str, project_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {'id': f'profile:{profile_id}', 'type': 'profile', 'label': profile_id},
        {'id': f'project:{profile_id}:{project_id}', 'type': 'project', 'label': project_id},
        {'id': f'project_summary:{profile_id}:{project_id}', 'type': 'project_summary', 'label': f'{project_id} summary'},
        {'id': f'plan:{profile_id}:{project_id}', 'type': 'plan', 'label': f'{project_id} plan', 'metadata': summary.get('project_plan', {'completed': [], 'todo': [], 'update_mode': 'agent_plan_command_compatible'})},
    ]
    edges = [
        {'id': f'edge:profile:{profile_id}:owns-project:{project_id}', 'source': f'profile:{profile_id}', 'target': f'project:{profile_id}:{project_id}', 'type': 'owns_project'},
        {'id': f'edge:project:{project_id}:summarizes', 'source': f'project:{profile_id}:{project_id}', 'target': f'project_summary:{profile_id}:{project_id}', 'type': 'summarizes'},
        {'id': f'edge:project:{project_id}:planned-by', 'source': f'project:{profile_id}:{project_id}', 'target': f'plan:{profile_id}:{project_id}', 'type': 'planned_by'},
        {'id': f'edge:summary:{project_id}:requires-plan', 'source': f'project_summary:{profile_id}:{project_id}', 'target': f'plan:{profile_id}:{project_id}', 'type': 'requires'},
    ]
    for section, node_type, relation in (
        ('decisions', 'decision', 'summarizes'),
        ('requirements', 'requirement', 'summarizes'),
        ('constraints', 'constraint', 'constrains'),
    ):
        for item in summary.get(section, []):
            ident = item.get('id')
            if not ident:
                continue
            nodes.append({'id': ident, 'type': node_type, 'label': item.get('text', ident)[:80], 'summary': item.get('text', ident)})
            edges.append({'id': f'edge:summary:{ident}', 'source': f'project_summary:{profile_id}:{project_id}', 'target': ident, 'type': relation})
    for skill in summary.get('key_skills', []):
        name = skill.get('name') or skill.get('id') or 'unnamed-skill'
        ident = skill.get('id') or f"skill:{_slug(name)}"
        role = skill.get('role') or skill.get('summary') or f"Procedural skill for {project_id}"
        nodes.append({
            'id': ident,
            'type': 'skill',
            'label': name,
            'summary': role,
            'metadata': {
                'skill': name,
                'profile_id': profile_id,
                'project_id': project_id,
                'role': role,
                'load_policy': skill.get('load_policy', 'when_selected_by_project_subgraph'),
                'mount_role': skill.get('mount_role', 'procedural_adapter'),
            },
        })
        edges.append({'id': f"edge:project:{project_id}:uses-skill:{_slug(ident)}", 'source': f'project:{profile_id}:{project_id}', 'target': ident, 'type': 'uses_skill'})
        edges.append({'id': f"edge:summary:{project_id}:summarizes-skill:{_slug(ident)}", 'source': f'project_summary:{profile_id}:{project_id}', 'target': ident, 'type': 'summarizes'})
    for session in summary.get('session_summaries', []):
        ident = session.get('session_id')
        if not ident:
            continue
        nodes.append({'id': ident, 'type': 'session', 'label': ident, 'summary': session.get('summary', ident), 'privacy': session.get('privacy', 'local_only')})
        edges.append({'id': f'edge:project:{project_id}:archives:{ident}', 'source': f'project:{profile_id}:{project_id}', 'target': ident, 'type': 'archives_session'})
    for link in summary.get('graph_links', []):
        source = link.get('source')
        target = link.get('target')
        link_type = link.get('type')
        if source and target and link_type:
            edges.append({'id': f'edge:{source}:{link_type}:{target}', 'source': source, 'target': target, 'type': link_type})
    return {
        'schema_version': '2.0',
        'profile_id': profile_id,
        'project_id': project_id,
        'privacy': summary.get('privacy', 'local_only'),
        'nodes': sorted(nodes, key=lambda item: item['id']),
        'edges': sorted(edges, key=lambda item: item['id']),
        'warnings': [],
        'blockers': [],
    }


def archive_session(memory_root: Path | str, profile_id: str, project_id: str, input_path: Path | str) -> dict[str, Any]:
    memory_root = Path(memory_root).resolve()
    input_path = Path(input_path).resolve()
    payload = read_json(input_path)
    blockers = validate_compiled_session(payload)
    if payload.get('profile_id') != profile_id:
        blockers.append('input profile_id does not match --profile')
    if payload.get('project_id') != project_id:
        blockers.append('input project_id does not match --project')
    if blockers:
        return {'status': 'FAIL', 'warnings': [], 'blockers': blockers}
    ensure_profile(memory_root, profile_id)
    profile = load_profile(memory_root, profile_id)
    if project_id not in profile.get('projects', []):
        profile['projects'] = sorted(set(profile.get('projects', []) + [project_id]))
        deterministic_write_json(memory_root / 'profiles' / profile_id / 'profile.json', profile)
    bundle = load_project_bundle(memory_root, profile_id, project_id)
    summary = _merge_summary(bundle['summary'], payload)
    bundle['summary'] = summary
    bundle['decision_ledger'].update({'privacy': summary['privacy'], 'decisions': stable_items_by_id(list(bundle['decision_ledger'].get('decisions', [])) + list(payload.get('decisions', []))), 'warnings': [], 'blockers': []})
    bundle['requirements'].update({'privacy': summary['privacy'], 'requirements': stable_items_by_id(list(bundle['requirements'].get('requirements', [])) + list(payload.get('requirements', []))), 'warnings': [], 'blockers': []})
    bundle['constraints'].update({'privacy': summary['privacy'], 'constraints': stable_items_by_id(list(bundle['constraints'].get('constraints', [])) + list(payload.get('constraints', []))), 'warnings': [], 'blockers': []})
    sessions = list(bundle['session_index'].get('sessions', [])) + [_session_entry(payload)]
    bundle['session_index'].update({'privacy': summary['privacy'], 'sessions': stable_items_by_id(sessions, id_key='session_id'), 'warnings': [], 'blockers': []})
    bundle['graph_fragment'] = _build_graph_fragment(profile_id, project_id, summary)
    write_project_bundle(memory_root, profile_id, project_id, bundle)
    write_global_graph(memory_root, profile_id, project_id)
    write_global_lineage(memory_root, profile_id, project_id)
    return {
        'status': 'PASS',
        'profile': profile_id,
        'project': project_id,
        'session_id': payload['session_id'],
        'privacy': summary['privacy'],
        'project_summary_path': (bundle['root'] / 'project-summary.json').as_posix(),
        'decision_ledger_path': (bundle['root'] / 'decision-ledger.json').as_posix(),
        'requirements_path': (bundle['root'] / 'requirements.json').as_posix(),
        'constraints_path': (bundle['root'] / 'constraints.json').as_posix(),
        'session_index_path': (bundle['root'] / 'session-index.json').as_posix(),
        'graph_fragment_path': (bundle['root'] / 'graph-fragment.json').as_posix(),
        'warnings': [],
        'blockers': [],
    }
