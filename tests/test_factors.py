from pathlib import Path
from graph_harness_maintain.store import GraphStore
from graph_harness_maintain.sidecar import SidecarIndex
from graph_harness_maintain.retrieve import retrieve_minimal_subgraph
from graph_harness_maintain.factors import evaluate_provenance_integrity, evaluate_dependency_closure
from graph_harness_maintain.schema import Subgraph
from graph_harness_maintain.policy import Policy
F=Path(__file__).parent/'fixtures'

def load():
    return (GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml')), SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl')))

def test_dependency_closure_factor():
    s,_=load(); sg=Subgraph(nodes={'skill:structured-text-transform':s.nodes['skill:structured-text-transform']}, edges={})
    assert evaluate_dependency_closure(sg,s).hard_fail
    sg.nodes['tool:python']=s.nodes['tool:python']
    assert not evaluate_dependency_closure(sg,s).hard_fail

def test_weak_sidecar_does_not_satisfy_provenance():
    s,idx=load()
    n=s.nodes['claim:field-derived-statement']
    n.id='claim:sidecar-only'
    sg=Subgraph(nodes={'claim:sidecar-only': n}, edges={})
    f=evaluate_provenance_integrity(sg,s,idx)
    assert f.hard_fail
