from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.profile_local_graph import load_profile_graph_projection, profile_graph_text


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_profile_local_graph_projection_filters_sensitive_and_projects_edges(tmp_path: Path) -> None:
    graph_path = tmp_path / "ehrlab" / "graph-harness" / "graph.jsonl"
    _write_jsonl(
        graph_path,
        [
            {
                "id": "knowledge_claim:ehrlab:feature-groups",
                "type": "knowledge_claim",
                "label": "Feature groups",
                "profile_scope": "ehrlab",
                "summary": "G1 vitals, G2 static, G3 cumulative, G4 labs.",
                "state": "pinned",
                "sensitivity": "internal",
                "evidence_refs": ["/private/raw.png", "knowledge_raw:ehrlab:screenshot"],
                "weight": {"user_pin": 1.0, "utility": 1.0},
            },
            {
                "id": "knowledge_raw:ehrlab:secret",
                "type": "knowledge_raw",
                "label": "secret raw",
                "profile_scope": "ehrlab",
                "summary": "must not project",
                "sensitivity": "credential",
            },
            {
                "id": "edge:ehrlab:feature-support",
                "source": "knowledge_claim:ehrlab:feature-groups",
                "target": "knowledge_raw:ehrlab:secret",
                "type": "cites",
                "profile_scope": "ehrlab",
            },
        ],
    )

    projection = load_profile_graph_projection("ehrlab", "dirtycsv", profiles_root=tmp_path)

    assert projection["available"] is True
    assert [node["id"] for node in projection["nodes"]] == ["knowledge_claim:ehrlab:feature-groups"]
    assert projection["nodes"][0]["metadata"]["evidence_refs"] == ["knowledge_raw:ehrlab:screenshot"]
    assert any(edge["type"] == "imports_profile_graph_node" for edge in projection["edges"])
    assert not any(edge["type"] == "cites" for edge in projection["edges"])


def test_profile_local_graph_text_includes_safe_summary(tmp_path: Path, monkeypatch) -> None:
    graph_path = tmp_path / "ehrlab" / "graph-harness" / "graph.jsonl"
    _write_jsonl(
        graph_path,
        [
            {
                "id": "knowledge_claim:ehrlab:rules",
                "type": "knowledge_claim",
                "label": "dirtycsv cleaning rules",
                "profile_scope": "ehrlab",
                "summary": "Preserve user-defined table cleaning rules.",
                "sensitivity": "none",
            }
        ],
    )
    monkeypatch.setenv("HERMES_PROFILES_ROOT", tmp_path.as_posix())

    text = profile_graph_text("ehrlab", "dirtycsv")

    assert "dirtycsv cleaning rules" in text
    assert "Preserve user-defined table cleaning rules" in text
