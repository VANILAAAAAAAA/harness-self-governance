from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_package_versions_are_aligned_for_v2_release() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_init = (ROOT / "src" / "graph_harness_maintain" / "__init__.py").read_text(encoding="utf-8")
    memory_init = (ROOT / "src" / "agent_memory_graph" / "__init__.py").read_text(encoding="utf-8")

    assert 'version = "2.0.0"' in pyproject
    assert '__version__ = "2.0.0"' in package_init
    assert '__version__ = "2.0.0"' in memory_init


def test_release_docs_describe_frozen_v2_surface() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    assert "Graph + Logs" in readme
    assert "Archive Trigger Policy" in readme
    assert "## 2.0.0" in changelog
    assert "Graph + Logs dashboard" in changelog
    assert "Graph + Logs dashboard" in architecture
    assert "automatic archival" in architecture
    assert "agent-graph triggers" in architecture
