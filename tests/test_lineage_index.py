from __future__ import annotations

import json
from pathlib import Path

from graph_harness_maintain.graph_export import write_governance_graph
from graph_harness_maintain.lineage_index import build_lineage_index, mapping_for_ref, validate_lineage_index, write_lineage_index


def test_lineage_index_builds_with_mapped_and_unmapped_nodes(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "v2" / "graph").mkdir(parents=True)
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "plans" / "example.md").write_text("# Example\n", encoding="utf-8")
    graph = {
        "schema_version": "2.0",
        "generated_at": "now",
        "summary": {},
        "nodes": [
            {"id": "node:mapped", "type": "artifact", "path": "docs/plans/example.md", "metadata": {}},
            {"id": "node:unmapped", "type": "tool", "metadata": {}},
        ],
        "edges": [{"id": "edge:mapped", "source": "node:mapped", "target": "node:unmapped", "type": "references", "metadata": {"path": "docs/plans/example.md"}}],
        "warnings": [],
        "blockers": [],
    }
    index = build_lineage_index(tmp_path, graph)

    assert index["schema_version"] == "2.0"
    assert index["nodes"]["node:mapped"]["mapping_status"] == "mapped"
    assert index["nodes"]["node:mapped"]["preferred_path"] == "docs/plans/example.md"
    assert index["nodes"]["node:unmapped"]["mapping_status"] == "unmapped"
    assert index["nodes"]["node:unmapped"]["preferred_path"] is None
    assert index["edges"]["edge:mapped"]["mapping_status"] == "mapped"


def test_lineage_view_in_logs_contract_distinguishes_mapped_vs_unmapped(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("readme\n", encoding="utf-8")
    index = build_lineage_index(
        tmp_path,
        {"nodes": [{"id": "node:mapped", "path": "README.md"}, {"id": "node:missing"}], "edges": []},
    )

    mapped = mapping_for_ref(index, "nodes", "node:mapped")
    unmapped = mapping_for_ref(index, "nodes", "node:missing")

    assert mapped["enabled"] is True
    assert mapped["preferred_path"] == "README.md"
    assert unmapped["enabled"] is False
    assert unmapped["label"] == "No direct log mapping"


def test_lineage_cli_artifact_validates_for_repo_root() -> None:
    root = Path(__file__).parents[1]
    write_governance_graph(root)
    report = write_lineage_index(root)
    validate = validate_lineage_index(root)

    assert report["status"] == "PASS"
    assert (root / report["path"]).exists()
    assert validate["status"] == "PASS"
    data = json.loads((root / report["path"]).read_text(encoding="utf-8"))
    assert data["nodes"]
    assert any(item["mapping_status"] == "mapped" for item in data["nodes"].values())
    assert any(item["mapping_status"] == "unmapped" for item in data["nodes"].values())
