from pathlib import Path
from graph_harness_maintain.store import GraphStore
from graph_harness_maintain.sidecar import SidecarIndex
from graph_harness_maintain.retrieve import retrieve_minimal_subgraph
F=Path(__file__).parent/'fixtures'

def test_retrieve_dependency_closed_subgraph_and_no_prompt():
    s=GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    sg, report=retrieve_minimal_subgraph('structured text transform', 'lab', 40, s, idx)
    assert 'skill:structured-text-transform' in sg.nodes
    assert 'tool:python' in sg.nodes
    assert 'edge:skill-depends-python' in sg.edges
    assert 'prompt' not in str(sg.to_dict()).lower()
    assert all(e.type != 'caused_by' for e in sg.edges.values())

def test_retrieve_attaches_weak_annotation_only():
    s=GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    sg, _=retrieve_minimal_subgraph('field derived statement', 'lab', 40, s, idx)
    assert 'edge:claim-derived-raw' in sg.edges
    assert sg.annotations['edge:claim-derived-raw'][0]['kind']=='weak_association_annotation'
