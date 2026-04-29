from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.bootstrap import bootstrap_repo
from agent_memory_graph.export import export_repo_projection
from agent_memory_graph.repo_adapter import init_repo_manifest
from agent_memory_graph.archive_triggers import evaluate_archive_trigger, write_archive_trigger_report


ROOT = Path(__file__).parents[1]


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)
    return repo, memory_root


def _event(tmp_path: Path, event_type: str, summary: str = "test event") -> Path:
    path = tmp_path / f"{event_type}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "event_type": event_type,
                "profile_id": "general",
                "project_id": "harness-self-governance",
                "summary": summary,
                "source": "pytest",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_milestone_completed_recommends_manual_archive(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    report = evaluate_archive_trigger(_event(tmp_path, "milestone_completed", "v2 milestone closed"), repo, memory_root)
    assert report["status"] == "PASS"
    assert report["trigger_type"] == "milestone_completed"
    assert report["recommended_action"] == "recommend_manual_archive"
    assert report["archive_auto_apply_enabled"] is False


def test_architecture_decision_recommends_compiled_candidate(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    report = evaluate_archive_trigger(_event(tmp_path, "architecture_decision", "Dual graph semantics locked"), repo, memory_root)
    assert report["recommended_action"] == "create_compiled_candidate"
    assert report["archive_auto_apply_enabled"] is False


def test_context_gap_detected_recommends_maintenance_proposal(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    report = evaluate_archive_trigger(_event(tmp_path, "context_gap_detected", "Lineage mapping missing for logs"), repo, memory_root)
    assert report["recommended_action"] == "create_maintenance_proposal"
    assert report["archive_auto_apply_enabled"] is False


def test_user_requested_archive_recommends_manual_archive(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    report = evaluate_archive_trigger(_event(tmp_path, "user_requested_archive", "Please archive this milestone"), repo, memory_root)
    assert report["recommended_action"] == "recommend_manual_archive"
    assert report["archive_auto_apply_enabled"] is False


def test_transient_event_returns_no_action(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    report = evaluate_archive_trigger(_event(tmp_path, "transient_event", "scratch note only"), repo, memory_root)
    assert report["recommended_action"] == "no_action"
    assert report["archive_auto_apply_enabled"] is False


def test_trigger_report_collects_recommendations_without_auto_apply(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    evaluate_archive_trigger(_event(tmp_path, "architecture_decision", "Keep archive automation proposal-only"), repo, memory_root)
    evaluate_archive_trigger(_event(tmp_path, "context_gap_detected", "Missing decision summary link"), repo, memory_root)
    evaluate_archive_trigger(_event(tmp_path, "milestone_completed", "Manual archive pass complete"), repo, memory_root)

    report = write_archive_trigger_report(repo, memory_root)
    assert report["status"] == "PASS"
    assert report["report_path"].endswith("reports/archive-trigger-report.json")

    payload = json.loads((memory_root / "reports" / "archive-trigger-report.json").read_text(encoding="utf-8"))
    assert payload["archive_auto_apply_enabled"] is False
    assert payload["manual_archive_required"] is True
    assert payload["recommendation_count"] >= 3
    assert payload["counts_by_action"]["recommend_manual_archive"] >= 1
    assert payload["counts_by_action"]["create_compiled_candidate"] >= 1
    assert payload["counts_by_action"]["create_maintenance_proposal"] >= 1


def test_export_projects_trigger_report_into_repo_artifacts(tmp_path: Path) -> None:
    repo, memory_root = _repo(tmp_path)
    evaluate_archive_trigger(_event(tmp_path, "user_requested_archive", "Archive request from operator"), repo, memory_root)
    write_archive_trigger_report(repo, memory_root)

    exported = export_repo_projection(repo, memory_root)
    assert exported["status"] == "PASS"
    assert (repo / "artifacts" / "v2" / "maintenance" / "archive-trigger-report.json").exists()
