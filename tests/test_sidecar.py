from pathlib import Path
from dataclasses import asdict
import json
from graph_harness_maintain.sidecar import SidecarIndex
from graph_harness_maintain.store import GraphStore
from graph_harness_maintain.policy import Policy
F=Path(__file__).parent/'fixtures'

def test_sidecar_gates_annotation_only_and_not_strict_provenance():
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    assert idx.validate_gates()['ok']
    assert idx.candidates_for_object('claim:field-derived-statement')
    assert idx.weak_annotation_for_edge('edge:claim-derived-raw')[0].evidence_strength=='insufficient'
    store=GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))
    assert all(e.id != 'edge:weak' for e in store.provenance_edges('claim:field-derived-statement', strict=True))

def test_hard_gates_block_upgrade():
    p=Policy('lab')
    assert not p.check_sidecar_upgrade(True, False).allowed
    assert p.check_sidecar_upgrade(True, False).code=='human_confirmation_required'
    assert not p.check_sidecar_upgrade(False, False).allowed
    assert p.check_sidecar_upgrade(False, False).code=='upgrade_not_allowed'

def test_redacted_copy_strips_raw_pointer_fields():
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    original_candidate=idx.evidence_candidates[0]
    original_weak=idx.weak_associations[0]
    original_candidate.raw.update({
        'source_path':'/home/private/source',
        'target_path':'/mnt/private/target',
        'raw_path':'C:\\\\Users\\\\Private\\\\raw.txt',
        'path':'file:///home/private/raw.txt',
        'file':'/home/private/file.txt',
        'uri':'file:///C:/Users/Private/raw.txt',
        'extra_ref':'/home/private/ref',
    })
    redacted=idx.redacted_copy()
    payload={
        'evidence_candidates':[asdict(r) for r in redacted.evidence_candidates],
        'weak_associations':[asdict(r) for r in redacted.weak_associations],
    }
    assert redacted.evidence_candidates[0] is not original_candidate
    assert redacted.weak_associations[0] is not original_weak
    assert redacted.by_object[redacted.evidence_candidates[0].object_id][0] is redacted.evidence_candidates[0]
    assert redacted.weak_by_edge[redacted.weak_associations[0].edge_id][0] is redacted.weak_associations[0]
    rendered=str(payload)
    for bad in [
        'candidate_ref', 'source_path', 'target_path', 'raw_path',
        "'path'", ' path:', '"path"', "'file'", '"file"', "'uri'", '"uri"',
        '/home/', '/mnt/', 'C:\\\\Users\\\\', 'file://'
    ]:
        assert bad not in rendered


def test_redacted_copy_recursively_strips_nested_raw_pointer_fields_and_path_values():
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    idx.evidence_candidates[0].raw.update({
        'safe_status':'review_only',
        'debug_note':'observed at /home/private/debug.txt',
        'windows_note':'observed at C:\\\\Users\\\\Private\\\\debug.txt',
        'wsl_note':'observed at \\\\\\\\wsl.localhost\\\\Ubuntu\\\\home\\\\private\\\\debug.txt',
        'nested':{
            'source_path':'/home/private/source.txt',
            'path':'/mnt/c/Users/Private/source.txt',
            'uri':'file:///home/private/source.txt',
            'candidate_ref':'claim:/home/private/ref',
            'safe_note':'keep me',
            'deeper':[
                {'target_path':'C:\\\\Users\\\\Private\\\\target.txt'},
                {'raw_ref':'\\\\\\\\wsl.localhost\\\\Ubuntu\\\\home\\\\private\\\\raw.txt'},
                {'safe_relative':'relative/id'},
            ],
        },
        'items':[
            {'file':'file:///mnt/c/Users/Private/raw.txt'},
            {'safe_value':'safe-id'},
        ],
    })
    idx.weak_associations[0].raw.update({
        'nested':{
            'source_path':'/home/private/weak-source.txt',
            'path':'/mnt/d/private/weak-path.txt',
            'uri':'file:///C:/Users/Private/weak-uri.txt',
            'candidate_ref':'/home/private/weak-ref',
        }
    })
    redacted=idx.redacted_copy()
    payload={
        'evidence_candidates':[asdict(r) for r in redacted.evidence_candidates],
        'weak_associations':[asdict(r) for r in redacted.weak_associations],
    }
    rendered=json.dumps(payload, sort_keys=True)
    assert 'safe_status' in rendered
    assert 'debug_note' in rendered
    assert 'windows_note' in rendered
    assert 'wsl_note' in rendered
    assert 'safe_note' in rendered
    assert 'safe_relative' in rendered
    for bad in [
        'source_path', 'path', 'uri', 'candidate_ref', 'target_path', 'raw_ref',
        '/home/', '/mnt/', 'file://', 'C:\\\\Users', 'wsl.localhost',
    ]:
        assert bad not in rendered
