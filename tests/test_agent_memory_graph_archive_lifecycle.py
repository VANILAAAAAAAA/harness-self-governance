from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.archive import archive_session
from agent_memory_graph.archive_gate import classify_archive_input, write_archive_gate_report
from agent_memory_graph.archive_quality import validate_compiled_session_examples
from agent_memory_graph.bootstrap import bootstrap_repo
from agent_memory_graph.export import export_repo_projection
from agent_memory_graph.maintenance import (
    generate_archive_maintenance_proposal,
    validate_archive_maintenance,
    write_archive_maintenance_report,
)
from agent_memory_graph.pending_updates import capture_pending_update
from agent_memory_graph.repo_adapter import init_repo_manifest

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "docs" / "examples" / "agent-memory-graph" / "harness-self-governance"


def _archive_examples(memory_root: Path, repo_root: Path) -> None:
    for path in sorted(EXAMPLES.glob("compiled-session-*.json")):
        report = archive_session(memory_root, "general", "harness-self-governance", path)
        assert report["status"] == "PASS", (path.name, report)


def test_archive_gate_classifies_transient_pending_candidate_and_forensic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)

    transient_path = tmp_path / "transient-note.json"
    transient_path.write_text(json.dumps({"summary": "wip scratch note", "notes": ["still exploring"]}, indent=2) + "\n", encoding="utf-8")
    transient = classify_archive_input(transient_path, repo, memory_root)
    assert transient["status"] == "PASS"
    assert transient["archive_gate"]["classification"] == "transient"
    assert transient["archive_gate"]["archive_allowed"] is False

    update = capture_pending_update(repo, "We may rename the graph inspector later.", "general", "harness-self-governance", memory_root)
    pending = classify_archive_input(Path(update["pending_updates_path"]), repo, memory_root)
    assert pending["archive_gate"]["classification"] == "pending_update"
    assert pending["archive_gate"]["archive_allowed"] is False
    assert pending["archive_gate"]["auto_archive_allowed"] is False

    candidate = classify_archive_input(EXAMPLES / "compiled-session-context-router.json", repo, memory_root)
    assert candidate["archive_gate"]["classification"] == "compiled_candidate"
    assert candidate["archive_gate"]["archive_allowed"] is True
    assert candidate["archive_gate"]["review_required"] is True
    assert candidate["archive_gate"]["auto_archive_allowed"] is False

    raw_path = tmp_path / "session-raw.txt"
    raw_path.write_text("user: here's a raw transcript line\nassistant: still live\n", encoding="utf-8")
    forensic = classify_archive_input(raw_path, repo, memory_root)
    assert forensic["archive_gate"]["classification"] == "forensic_only"
    assert forensic["archive_gate"]["raw_sessions_default_read"] is False
    assert forensic["archive_gate"]["archive_allowed"] is False


def test_archive_gate_and_maintenance_reports_are_generated_without_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)
    _archive_examples(memory_root, repo)
    capture_pending_update(repo, "Need stale summary review for context router docs.", "general", "harness-self-governance", memory_root)

    gate_report = write_archive_gate_report(repo, memory_root)
    assert gate_report["status"] == "PASS"
    assert gate_report["report_path"].endswith("reports/archive-gate-report.json")
    gate_payload = json.loads((memory_root / "reports" / "archive-gate-report.json").read_text(encoding="utf-8"))
    assert gate_payload["counts"]["compiled_candidate"] >= 7
    assert gate_payload["counts"]["pending_update"] >= 1
    assert gate_payload["raw_sessions_required"] is False

    before_export = json.loads((memory_root / "projects" / "general" / "harness-self-governance" / "session-index.json").read_text(encoding="utf-8"))

    maintenance = write_archive_maintenance_report(repo, memory_root)
    assert maintenance["status"] == "PASS"
    assert maintenance["report_path"].endswith("reports/archive-maintenance-report.json")
    maintenance_payload = json.loads((memory_root / "reports" / "archive-maintenance-report.json").read_text(encoding="utf-8"))
    assert maintenance_payload["archive_quality_status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert maintenance_payload["pending_updates_count"] >= 1
    assert "compiled_candidates_count" in maintenance_payload
    assert "forensic_only_count" in maintenance_payload

    validation = validate_archive_maintenance(repo, memory_root)
    assert validation["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert validation["proposal_only"] is True

    proposal = generate_archive_maintenance_proposal(repo, memory_root)
    assert proposal["status"] == "PASS"
    assert proposal["proposal_only"] is True
    proposal_payload = json.loads((memory_root / "reports" / "archive-maintenance-proposal.json").read_text(encoding="utf-8"))
    assert proposal_payload["proposal_only"] is True
    assert proposal_payload["recommended_actions"]

    after_propose = json.loads((memory_root / "projects" / "general" / "harness-self-governance" / "session-index.json").read_text(encoding="utf-8"))
    assert after_propose == before_export


def test_export_projects_archive_lifecycle_reports_into_repo_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)
    _archive_examples(memory_root, repo)
    capture_pending_update(repo, "Need context-gap repair workflow.", "general", "harness-self-governance", memory_root)
    write_archive_gate_report(repo, memory_root)
    write_archive_maintenance_report(repo, memory_root)
    generate_archive_maintenance_proposal(repo, memory_root)

    report = export_repo_projection(repo, memory_root)
    assert report["status"] == "PASS"
    for rel in [
        "artifacts/v2/maintenance/archive-gate-report.json",
        "artifacts/v2/maintenance/archive-maintenance-report.json",
        "artifacts/v2/maintenance/archive-maintenance-proposal.json",
    ]:
        assert (repo / rel).exists(), rel


def test_curated_compiled_session_examples_pass_archive_quality_validation() -> None:
    report = validate_compiled_session_examples(EXAMPLES)
    assert report["status"] == "PASS"
    assert report["archive_quality_status"] == "PASS"
    assert report["example_count"] == 9
    assert report["blockers"] == []
