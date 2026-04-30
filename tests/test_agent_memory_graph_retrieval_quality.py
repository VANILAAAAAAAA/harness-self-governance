from __future__ import annotations

from pathlib import Path

from agent_memory_graph.retrieve import retrieve_project_context
from tests.test_agent_memory_graph_context_index import seed_memory


def test_retrieval_quality_budget_and_sections(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    packet = retrieve_project_context(repo, "view graph logs constraints", memory_root=memory_root, budget="fast")

    assert len(packet["selected_nodes"]) <= 12
    assert packet["raw_sessions_allowed"] is False
    assert packet["summary_first"]
    assert packet["plan"]
    assert packet["miss_policy"]
    assert packet["do_not_read_by_default"] == ["sessions/raw/"]
