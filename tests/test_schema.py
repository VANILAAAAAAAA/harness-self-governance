from pathlib import Path
import pytest
from graph_harness_maintain.schema import *

F=Path(__file__).parent/'fixtures'
S=GraphSchema.from_file(str(F/'synthetic_schema.yaml'))

def test_valid_node_edge_event_and_invalid_type():
    n=GraphNode.from_record({'id':'n1','type':'skill','profile_scope':'lab','sensitivity':'internal','deletion_policy':'confirm'}, S)
    assert n.id=='n1'
    e=GraphEdge.from_record({'id':'e1','source':'n1','target':'n2','type':'depends_on','profile_scope':'lab'}, S)
    assert e.type=='depends_on'
    ev=GraphEvent.from_record({'id':'event:1','type':'audit','profile':'lab'}, S)
    assert ev.type=='audit'
    with pytest.raises(ValidationError): GraphNode.from_record({'id':'bad','type':'bad','profile_scope':'lab'}, S)
    with pytest.raises(ValidationError): GraphEdge.from_record({'id':'bad','source':'a','target':'b','type':'bad','profile_scope':'lab'}, S)

def test_missing_scope_sensitivity_tombstone_and_sidecar_gates():
    with pytest.raises(ValidationError): GraphNode.from_record({'id':'n','type':'skill'}, S)
    with pytest.raises(ValidationError): GraphNode.from_record({'id':'n','type':'skill','profile_scope':'lab','sensitivity':'unknown'}, S)
    t=Tombstone.from_record({'id':'t','profile':'lab','original_path':'/x','content_hash':'h','reason':'r','restore_command':'cp a b'})
    assert t.human_confirmation_required
    EvidenceCandidateSidecarRow.from_record({'object_id':'o','candidate_ref':'opaque','human_confirmation_required':True,'upgrade_allowed':False})
    with pytest.raises(ValidationError): EvidenceCandidateSidecarRow.from_record({'object_id':'o','human_confirmation_required':False,'upgrade_allowed':False})
    with pytest.raises(ValidationError): EvidenceCandidateSidecarRow.from_record({'object_id':'o','human_confirmation_required':True,'upgrade_allowed':True})
    WeakAssociationSidecarRow.from_record({'edge_id':'e','human_confirmation_required':True,'upgrade_allowed':False,'evidence_strength':'insufficient','apply_status':'not_applied'})
    with pytest.raises(ValidationError): WeakAssociationSidecarRow.from_record({'edge_id':'e','human_confirmation_required':True,'upgrade_allowed':False,'evidence_strength':'weak','apply_status':'not_applied'})
    with pytest.raises(ValidationError): GraphEdge.from_record({'id':'c','source':'a','target':'b','type':'caused_by','profile_scope':'lab'}, S)
