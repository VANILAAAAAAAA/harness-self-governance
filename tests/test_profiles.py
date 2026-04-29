from __future__ import annotations

import json
from pathlib import Path

from graph_harness_maintain.profiles import build_profile_index, validate_profile_index, write_profile_index


def test_profile_index_includes_general_and_ehrlab(tmp_path: Path) -> None:
    report = write_profile_index(tmp_path)
    data = json.loads((tmp_path / report["path"]).read_text(encoding="utf-8"))

    assert report["status"] == "PASS"
    assert data["schema_version"] == "2.0"
    assert data["active_profile"] == "general"
    profiles = {item["profile_id"]: item for item in data["profiles"]}
    assert {"general", "ehrlab"}.issubset(profiles)
    assert profiles["general"]["role"] == "governance_hub"
    assert profiles["general"]["projects"] == ["harness-self-governance"]
    assert profiles["ehrlab"]["projects"] == []


def test_profile_validation_passes_for_default_index(tmp_path: Path) -> None:
    write_profile_index(tmp_path)
    report = validate_profile_index(tmp_path)

    assert report["status"] == "PASS"
    assert report["active_profile"] == "general"
    assert report["profile_count"] >= 2
    assert report["blockers"] == []


def test_build_profile_index_is_deterministic() -> None:
    assert build_profile_index() == build_profile_index()
