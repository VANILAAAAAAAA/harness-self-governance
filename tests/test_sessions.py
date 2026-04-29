from __future__ import annotations

import json
from pathlib import Path

from graph_harness_maintain.sessions import compress_sessions, redact_sensitive_values

ROOT = Path(__file__).parents[1]


def test_session_compression_handles_missing_input_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    report = compress_sessions(ROOT, missing, ROOT / "artifacts" / "v2" / "sessions")

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert "does not exist" in report["warnings"][0]
    index = ROOT / "artifacts" / "v2" / "sessions" / "session-index.json"
    data = json.loads(index.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["privacy"] == "local_only"
    assert data["sessions"] == []


def test_session_compression_handles_md_txt_json_and_extracts_fields(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "session-one.md").write_text(
        "# Build v2\nDecision: keep dashboard read-only.\nRequirement: add graph export.\n"
        "Constraint: no graph mutation execution.\nCommand: python -m pytest\n"
        "Artifact: artifacts/v2/dashboard/index.html\nBranch: v2.0-dev\nTag: v1.1.0\nPR #42\n",
        encoding="utf-8",
    )
    (raw / "session-two.txt").write_text("Open question: should graph layout change?", encoding="utf-8")
    (raw / "session-three.json").write_text(json.dumps({"title": "JSON session", "body": "Decision: local only"}), encoding="utf-8")

    report = compress_sessions(ROOT, raw, ROOT / "artifacts" / "v2" / "sessions")
    index = json.loads((ROOT / report["path"]).read_text(encoding="utf-8"))

    assert report["status"] == "PASS"
    assert len(index["sessions"]) == 3
    first = json.loads((ROOT / index["sessions"][0]["summary_path"]).read_text(encoding="utf-8"))
    assert first["schema_version"] == "2.0"
    assert first["privacy"] == "local_only"
    assert first["source_hash"].startswith("sha256:")
    assert "keep dashboard read-only" in first["decisions"][0]
    assert "add graph export" in first["requirements"][0]
    assert "no graph mutation execution" in first["constraints"][0]
    assert "python -m pytest" in first["commands"][0]
    assert "artifacts/v2/dashboard/index.html" in first["artifacts_referenced"]
    assert any(link["type"] == "summarized_into" for link in first["graph_links"])


def test_token_like_values_are_redacted() -> None:
    key_name = "OPENAI" + "_API_KEY"
    text = f"{key_name}=sk-abcdefghijklmnopqrstuvwxyz1234567890 and ghp_abcdefghijklmnopqrstuvwxyz123456"
    redacted = redact_sensitive_values(text)

    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "ghp_" not in redacted
    assert "[REDACTED_TOKEN]" in redacted
