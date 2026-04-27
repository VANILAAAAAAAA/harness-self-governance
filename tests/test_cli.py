from pathlib import Path
import json, subprocess, sys, os
F=Path(__file__).parent/'fixtures'
ROOT=Path(__file__).parents[1]
ENV={**os.environ, 'PYTHONPATH': str(ROOT/'src')}

def test_cli_validate_runs():
    cmd=[sys.executable,'-m','graph_harness_maintain.cli','validate','--schema',str(F/'synthetic_schema.yaml'),'--graph',str(F/'synthetic_graph.jsonl'),'--events',str(F/'synthetic_events.jsonl'),'--evidence-candidates',str(F/'synthetic_evidence_candidate_index.jsonl'),'--weak-associations',str(F/'synthetic_weak_association_sidecar_index.jsonl')]
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,env=ENV)
    assert r.returncode==0, r.stderr
    data=json.loads(r.stdout)
    assert data['policy_status']=='read_only'

def test_cli_retrieve_and_export_outputs_under_artifacts():
    sub=ROOT/'artifacts'/'cli_subgraph.json'; exp=ROOT/'artifacts'/'cli_export.json'
    cmd=[sys.executable,'-m','graph_harness_maintain.cli','retrieve','--task','structured text transform','--profile','lab','--schema',str(F/'synthetic_schema.yaml'),'--graph',str(F/'synthetic_graph.jsonl'),'--events',str(F/'synthetic_events.jsonl'),'--out',str(sub)]
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,env=ENV)
    assert r.returncode==0, r.stderr
    assert sub.exists() and 'tool:python' in sub.read_text()
    cmd=[sys.executable,'-m','graph_harness_maintain.cli','export-sanitized-dry-run','--profile','lab','--schema',str(F/'synthetic_schema.yaml'),'--graph',str(F/'synthetic_graph.jsonl'),'--events',str(F/'synthetic_events.jsonl'),'--out',str(exp)]
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,env=ENV)
    assert r.returncode==0, r.stderr
    assert exp.exists() and 'candidate_ref' not in exp.read_text()
