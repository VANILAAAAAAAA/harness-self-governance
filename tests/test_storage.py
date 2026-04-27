from pathlib import Path
import json, os, subprocess, sys

from graph_harness_maintain.storage import storage_audit, raw_archive_proposal, blocked_raw_archive_apply

ROOT = Path(__file__).parents[1]
ENV = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}


def test_storage_audit_capacity_only(tmp_path):
    active = tmp_path / 'active'
    active.mkdir()
    (active / 'a.txt').write_text('abc', encoding='utf-8')
    archive = tmp_path / 'archive'
    report = storage_audit([str(active)], archive_root=str(archive), warning_bytes=10, hard_limit_bytes=20)
    assert report.read_only is True
    assert report.total_active_bytes == 3
    assert report.capacity_status == 'below_warning'
    assert 'no_move' in report.actions


def test_raw_archive_proposal_is_proposal_only(tmp_path):
    active = tmp_path / 'active'
    active.mkdir()
    (active / 'large.bin').write_bytes(b'x' * 32)
    archive = tmp_path / 'archive'
    proposal = raw_archive_proposal([str(active)], archive_root=str(archive), hard_limit_bytes=20)
    assert proposal['proposal_only'] is True
    assert proposal['applied'] is False
    assert proposal['human_approval_required_for_apply'] is True
    assert proposal['recommended_next_gate'] == 'HUMAN_APPROVAL_REQUIRED'


def test_raw_archive_apply_is_blocked():
    block = blocked_raw_archive_apply()
    assert block['allowed'] is False
    assert block['code'] == 'HUMAN_APPROVAL_REQUIRED'
    assert block['applied'] is False


def test_cli_storage_guard_outputs_under_artifacts(tmp_path):
    out = ROOT / 'artifacts' / 'storage_guard_test_audit.json'
    cmd = [sys.executable, '-m', 'graph_harness_maintain.cli', 'storage-audit', '--active-root', str(tmp_path), '--archive-root', str(tmp_path / 'archive'), '--out', str(out)]
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=ENV)
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['read_only'] is True
    assert data['hard_limit_bytes'] == 4294967296


def test_cli_public_surface_excludes_raw_archive_apply():
    cmd = [sys.executable, '-m', 'graph_harness_maintain.cli', '--help']
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=ENV)
    assert r.returncode == 0
    assert 'raw-archive-apply' not in r.stdout
