from __future__ import annotations

from pathlib import Path

from agent_memory_graph.evidence_anchor import write_raw_evidence_index
from agent_memory_graph.retrieve import retrieve_project_context
from tests.test_agent_memory_graph_context_index import seed_memory


def _write_anchor_fixture(repo: Path) -> None:
    write_raw_evidence_index(
        repo / "docs" / "examples" / "agent-memory-graph" / "harness-self-governance" / "raw-evidence-index.json",
        [
            {
                "anchor_id": "raw_anchor:general:v2-dashboard-planning:graph-logs-decision",
                "profile": "general",
                "project": "harness-self-governance",
                "source_session_id": "session:v2-dashboard-planning",
                "claim_ids": ["decision:v2-core-graph-logs", "requirement:graph-main-focus"],
                "span_type": "decision",
                "message_range": [10, 14],
                "safe_excerpt": "User accepted v2 Graph and Logs as the core pages; raw sessions remain last-resort evidence.",
                "raw_path": "sessions/raw/session-v2-dashboard-planning.jsonl",
                "read_policy": "evidence_deepening_only",
                "sensitivity": "internal",
                "tags": ["graph", "logs", "dashboard", "v2"],
            }
        ],
    )


def test_evidence_depth_anchor_returns_metadata_without_excerpt_or_raw_read(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    _write_anchor_fixture(repo)

    packet = retrieve_project_context(
        repo,
        "continue graph logs dashboard work",
        memory_root=memory_root,
        budget="fast",
        evidence_depth="anchor",
    )

    assert packet["status"] in {"PASS", "LOW_CONFIDENCE"}
    assert packet["evidence_depth"] == "anchor"
    assert packet["selected_raw_evidence_anchors"]
    anchor = packet["selected_raw_evidence_anchors"][0]
    assert anchor["anchor_id"] == "raw_anchor:general:v2-dashboard-planning:graph-logs-decision"
    assert "safe_excerpt" not in anchor
    assert packet["raw_span_requests"] == []
    assert packet["raw_sessions_default_read"] is False
    assert packet["raw_sessions_allowed"] is False


def test_evidence_depth_excerpt_uses_precompiled_safe_excerpt_only(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    _write_anchor_fixture(repo)

    packet = retrieve_project_context(
        repo,
        "continue graph logs dashboard work",
        memory_root=memory_root,
        budget="normal",
        evidence_depth="excerpt",
    )

    anchor = packet["selected_raw_evidence_anchors"][0]
    assert "safe_excerpt" in anchor
    assert "Graph and Logs" in anchor["safe_excerpt"]
    assert packet["raw_span_requests"] == []
    assert packet["compiled_memory_raw_session_reads"] is False


def test_raw_span_request_is_blocked_without_forensic_budget_and_explicit_marker(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    _write_anchor_fixture(repo)

    packet = retrieve_project_context(
        repo,
        "continue graph logs dashboard work",
        memory_root=memory_root,
        budget="deep",
        evidence_depth="raw-span",
    )

    assert packet["raw_span_requests"] == []
    assert packet["raw_sessions_allowed"] is False
    assert any("raw-span evidence requires forensic budget" in blocker for blocker in packet["blockers"])
    assert packet["selected_raw_evidence_anchors"][0]["raw_span_blocked"] is True


def test_raw_span_request_requires_forensic_budget_and_explicit_discovery_marker(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    _write_anchor_fixture(repo)

    packet = retrieve_project_context(
        repo,
        "forensic raw sessions explicit discovery for graph logs dashboard work",
        memory_root=memory_root,
        budget="forensic",
        evidence_depth="raw-span",
    )

    assert packet["raw_sessions_allowed"] is True
    assert packet["raw_span_requests"]
    assert packet["raw_span_requests"][0]["raw_path"] == "sessions/raw/session-v2-dashboard-planning.jsonl"


def test_retrieve_uses_cached_index_and_reports_latency(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    first = retrieve_project_context(repo, "continue graph logs dashboard work", memory_root=memory_root, budget="fast")
    second = retrieve_project_context(repo, "continue graph logs dashboard work", memory_root=memory_root, budget="fast")

    assert first["latency_ms"] >= 0
    assert second["latency_ms"] >= 0
    assert "context_index_cache_or_lazy_build" in second["cache_events"]
    assert "global_graph_cache" in second["cache_events"]
