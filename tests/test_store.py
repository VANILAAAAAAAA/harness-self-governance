from pathlib import Path
import pytest
from graph_harness_maintain.store import GraphStore
from graph_harness_maintain.schema import ValidationError
F=Path(__file__).parent/'fixtures'

def load(): return GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))

def test_store_loads_indexes_neighbors_and_integrity():
    s=load(); r=s.validate_integrity()
    assert r.ok and r.counts['nodes']==11 and r.counts['edges']==8 and r.counts['events']==2
    assert s.nodes_by_type['skill'][0].id=='skill:structured-text-transform'
    assert s.nodes_by_sensitivity['phi_or_patient_level'][0].id=='raw:private_table'
    assert [e.id for e in s.neighbors('skill:structured-text-transform', {'depends_on'}, 'out')]==['edge:skill-depends-python']
    assert [e.type for e in s.dependency_edges('skill:structured-text-transform')]==['depends_on']
    assert [e.id for e in s.provenance_edges('claim:field-derived-statement', strict=True)]==['edge:claim-derived-raw']

def test_duplicate_and_missing_endpoint_validation(tmp_path):
    p=tmp_path/'g.jsonl'; p.write_text('{"record_type":"node","id":"x","type":"skill","profile_scope":"lab"}\n{"record_type":"node","id":"x","type":"skill","profile_scope":"lab"}\n')
    with pytest.raises(ValidationError): GraphStore.from_paths(str(p), None, str(F/'synthetic_schema.yaml'))
    p.write_text('{"record_type":"edge","id":"e","source":"x","target":"y","type":"depends_on","profile_scope":"lab"}\n')
    s=GraphStore.from_paths(str(p), None, str(F/'synthetic_schema.yaml'))
    assert not s.validate_integrity().ok
