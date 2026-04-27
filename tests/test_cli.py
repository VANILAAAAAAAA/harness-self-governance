from pathlib import Path
import json, subprocess, sys, os

F = Path(__file__).parent / 'fixtures'
ROOT = Path(__file__).parents[1]
ENV = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
PY = sys.executable


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, '-m', 'graph_harness_maintain', *args], cwd=ROOT, text=True, capture_output=True, env=ENV)


def test_cli_validate_runs():
    cmd = [PY, '-m', 'graph_harness_maintain.cli', 'validate', '--schema', str(F / 'synthetic_schema.yaml'), '--graph', str(F / 'synthetic_graph.jsonl'), '--events', str(F / 'synthetic_events.jsonl'), '--evidence-candidates', str(F / 'synthetic_evidence_candidate_index.jsonl'), '--weak-associations', str(F / 'synthetic_weak_association_sidecar_index.jsonl')]
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=ENV)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data['policy_status'] == 'read_only'


def test_cli_retrieve_and_export_outputs_under_artifacts():
    sub = ROOT / 'artifacts' / 'cli_subgraph.json'
    exp = ROOT / 'artifacts' / 'cli_export.json'
    cmd = [PY, '-m', 'graph_harness_maintain.cli', 'retrieve', '--task', 'structured text transform', '--profile', 'lab', '--schema', str(F / 'synthetic_schema.yaml'), '--graph', str(F / 'synthetic_graph.jsonl'), '--events', str(F / 'synthetic_events.jsonl'), '--out', str(sub)]
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=ENV)
    assert r.returncode == 0, r.stderr
    assert sub.exists() and 'tool:python' in sub.read_text()
    cmd = [PY, '-m', 'graph_harness_maintain.cli', 'export-sanitized-dry-run', '--profile', 'lab', '--schema', str(F / 'synthetic_schema.yaml'), '--graph', str(F / 'synthetic_graph.jsonl'), '--events', str(F / 'synthetic_events.jsonl'), '--out', str(exp)]
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=ENV)
    assert r.returncode == 0, r.stderr
    assert exp.exists() and 'candidate_ref' not in exp.read_text()


def test_ghm_help_command():
    r = _run('--help')
    assert r.returncode == 0
    assert 'identity-check' in r.stdout
    assert 'pipeline' in r.stdout


def test_ghm_identity_check():
    r = _run('identity-check')
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data['status'] in {'PASS', 'PASS_WITH_WARNINGS'}


def test_ghm_check_gates():
    r = _run('check-gates')
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert 'git_push' in data['human_approval_required']


def test_ghm_locate_evidence():
    _run('pipeline', 'local-rc')
    r = _run('locate-evidence')
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data['claims']


def test_ghm_provenance_current_state():
    r = _run('provenance', 'current-state')
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data['pipeline'] == 'local-rc'


def test_ghm_pipeline_local_rc():
    r = _run('pipeline', 'local-rc')
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data['status'] in {'PASS', 'PASS_WITH_WARNINGS'}
