from __future__ import annotations

from pathlib import Path

from agent_memory_graph.retrieve import retrieve_project_context
from tests.test_agent_memory_graph_context_index import seed_memory


def test_zero_hit_returns_miss_without_deep_fallback_or_raw_sessions(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    packet = retrieve_project_context(repo, "zzzz_unrelated_moonbase_teleport", memory_root=memory_root, budget="fast")

    assert packet["status"] == "MISS"
    assert packet["hit_count"] == 0
    assert packet["confidence"] == 0.0
    assert packet["raw_sessions_allowed"] is False
    assert packet["automatic_fallback_depth"] == 0
    assert packet["recommended_action"] == "create_pending_project_or_ask_for_scope_or_explicit_discovery"
    assert (memory_root / "routing" / "context-gaps").exists()
