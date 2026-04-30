from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.archive import archive_session
from agent_memory_graph.retrieve import retrieve_project_context
from tests.test_agent_memory_graph_context_index import seed_memory


def test_retrieve_project_context_returns_summary_first_packet(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    packet = retrieve_project_context(repo, "continue graph logs dashboard work", memory_root=memory_root, budget="fast")

    assert packet["status"] in {"PASS", "LOW_CONFIDENCE"}
    assert packet["context_role"] == "compiled_project_memory"
    assert packet["summary_first"]["project_identity"]["project"] == "harness-self-governance"
    assert packet["plan"]["update_mode"] == "agent_plan_command_compatible"
    assert packet["raw_sessions_default_read"] is False
    assert packet["raw_sessions_allowed"] is False
    assert packet["current_session_raw_context"] == "preserved_by_hermes_live_context_not_graph_memory"
    assert packet["compiled_memory_raw_session_reads"] is False
    assert "project_summary:general:harness-self-governance" in packet["selected_nodes"]
    assert packet["summary_first"]["key_skills"][0]["name"] == "graph-harness-maintain"
    assert packet["skill_load_order"] == ["graph-harness-maintain"]
    assert packet["skill_mounts"][0]["id"] == "skill:graph-harness-maintain"
    assert packet["skill_mounts"][0]["mount_role"] == "governance_protocol"


def test_retrieve_skill_mounts_are_selected_from_project_subgraph(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    packet = retrieve_project_context(repo, "continue graph harness skill governance protocol work", memory_root=memory_root, budget="fast")

    assert packet["status"] in {"PASS", "LOW_CONFIDENCE"}
    assert any(mount["skill"] == "graph-harness-maintain" for mount in packet["skill_mounts"])
    assert "skill:graph-harness-maintain" in packet["selected_nodes"]


def test_retrieve_new_information_creates_pending_update(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    packet = retrieve_project_context(repo, "我决定 retrieval 不自动读 raw sessions", memory_root=memory_root)

    assert packet["status"] == "NEW_INFORMATION"
    assert packet["recommended_action"] == "capture_pending_update"
    assert packet["pending_context"]
    assert packet["archive_gate_required"] is True
    assert (memory_root / "routing" / "pending-updates.json").exists()


def test_retrieve_auto_routes_between_known_projects_without_hints(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    dirty = {
        "schema_version": "2.0",
        "profile_id": "ehrlab",
        "project_id": "dirtycsv",
        "session_id": "session:dirtycsv-routing",
        "privacy": "local_only",
        "summary": "dirtycsv cleans malformed CSV tables, delimiter issues, and data cleaning schemas.",
        "routing_hints": {"aliases": ["dirtycsv", "dirty csv", "csv cleaning", "malformed csv"], "negative_aliases": []},
        "decisions": [{"id": "decision:dirtycsv-project", "text": "dirtycsv is a standalone ehrlab data-cleaning project."}],
        "requirements": [{"id": "requirement:clean-csv", "text": "Clean malformed CSV inputs."}],
        "constraints": [{"id": "constraint:no-patient-data", "text": "No patient-level data in governance exports."}],
        "graph_links": [{"source": "decision:dirtycsv-project", "target": "requirement:clean-csv", "type": "supports"}],
    }
    compiled = tmp_path / "dirtycsv.json"
    compiled.write_text(json.dumps(dirty), encoding="utf-8")
    archive_session(memory_root, "ehrlab", "dirtycsv", compiled)

    packet = retrieve_project_context(repo, "continue dirty csv delimiter cleaning work", memory_root=memory_root)

    assert packet["selected_profile"] == "ehrlab"
    assert packet["selected_project"] == "dirtycsv"
    assert packet["routing"]["mode"] == "auto"
    assert packet["routing"]["candidate_count"] >= 2
