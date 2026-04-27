from pathlib import Path
import json
from graph_harness_maintain.store import GraphStore
from graph_harness_maintain.sidecar import SidecarIndex
from graph_harness_maintain.export import export_sanitized_summary, write_export, redact_paths
from graph_harness_maintain.policy import Policy
F=Path(__file__).parent/'fixtures'

def test_export_sanitized_dry_run_no_raw_sensitive_path_token(tmp_path):
    root=Path(__file__).parents[1]
    s=GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))
    idx=SidecarIndex.from_paths(str(F/'synthetic_evidence_candidate_index.jsonl'), str(F/'synthetic_weak_association_sidecar_index.jsonl'))
    p=Policy('lab', repo_root=str(root), export_scope='public')
    summary=export_sanitized_summary('lab', s, idx, p)
    assert summary.policy_blocks
    out=root/'artifacts'/'test_export.json'
    wr=write_export(summary, str(out), p)
    assert wr['ok']
    text=out.read_text()
    low=text.lower()
    assert '/synthetic/private' not in text
    assert 'candidate_ref' not in text
    for bad in ['token','credential','subject_id','hadm_id','icustay','mimic']:
        assert bad not in low
