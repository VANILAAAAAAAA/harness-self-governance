from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.context_gaps import list_context_gaps
from agent_memory_graph.pending_updates import capture_pending_update
from agent_memory_graph.router import route_query

from tests.test_agent_memory_graph_context_index import seed_memory


def test_route_view_in_logs_matches_topic_and_builds_fast_packet(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = route_query(repo, "view in logs lineage mapping", memory_root, context_budget="fast")

    assert report["status"] == "PASS"
    assert report["candidate_intents"] == ["retrieve_existing"]
    assert "view-in-logs" in report["matched_topics"]
    assert report["entry_nodes"]
    assert report["raw_sessions_allowed"] is False
    packet = report["recommended_context_packet"]
    assert packet["schema_version"] == "2.0"
    assert packet["profile"] == "general"
    assert packet["project"] == "harness-self-governance"
    assert packet["budget"] == "fast"
    assert packet["raw_sessions_allowed"] is False
    assert packet["do_not_read_by_default"] == ["sessions/raw/"]
    assert any(item["kind"] == "project_summary" for item in packet["primary_context"])


def test_route_chinese_log_alias_matches_view_in_logs_topic(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = route_query(repo, "log定位", memory_root, context_budget="fast")

    assert report["status"] == "PASS"
    assert "log定位" in report["matched_aliases"]
    assert "view-in-logs" in report["matched_topics"]
    assert report["raw_sessions_allowed"] is False


def test_new_information_recommends_pending_update_without_deep_fallback(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = route_query(repo, "我决定 v2.0 不做 Hub-side LLM API", memory_root, context_budget="fast")

    assert report["status"] == "PASS"
    assert report["candidate_intents"] == ["new_information"]
    assert report["recommended_action"] == "capture_pending_update"
    assert report["raw_sessions_allowed"] is False
    assert report["requires_llm_gate"] is False
    assert report["recommended_context_packet"]["archive_policy"]["new_information"] == "capture_pending_update"


def test_capture_pending_update_writes_deterministic_routing_file(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = capture_pending_update(
        repo,
        "v2.0 keeps Hub-side LLM API deferred.",
        "general",
        "harness-self-governance",
        memory_root,
    )

    target = memory_root / "routing" / "pending-updates.json"
    assert report["status"] == "PASS"
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["updates"][0]["text"] == "v2.0 keeps Hub-side LLM API deferred."
    assert data["updates"][0]["raw_sessions_allowed"] is False


def test_retrieve_existing_miss_creates_context_gap_and_does_not_read_raw_sessions(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = route_query(repo, "retrieve existing moon base teleport lineage", memory_root, context_budget="normal")

    assert report["status"] == "MISS"
    assert report["candidate_intents"] == ["retrieve_existing"]
    assert report["raw_sessions_allowed"] is False
    assert report["recommended_action"] == "record_context_gap"
    gaps = list_context_gaps(repo, memory_root)
    assert gaps["status"] == "PASS"
    assert gaps["gaps"]
    assert gaps["gaps"][0]["gap_type"] in {"missing_alias", "missing_entry_node"}


def test_ambiguous_input_sets_llm_gate_without_context_deepening(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = route_query(repo, "maybe update or find that thing", memory_root, context_budget="fast")

    assert report["status"] == "AMBIGUOUS"
    assert report["candidate_intents"] == ["ambiguous"]
    assert report["requires_llm_gate"] is True
    assert report["raw_sessions_allowed"] is False
    assert report["selected_artifacts"] == []


def test_budget_rules_keep_fast_clean_and_forensic_allows_raw_sessions(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    fast = route_query(repo, "view in logs", memory_root, context_budget="fast")
    forensic = route_query(repo, "view in logs", memory_root, context_budget="forensic")

    assert fast["context_budget"] == "fast"
    assert fast["raw_sessions_allowed"] is False
    assert forensic["context_budget"] == "forensic"
    assert forensic["raw_sessions_allowed"] is True
    assert forensic["recommended_context_packet"]["raw_sessions_allowed"] is True
