from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import SCHEMA_VERSION, validate_compiled_session

BANNED_SNIPPETS = (
    "/" + "home" + "/" + "vanila",
    "c:" + "\\\\",
    "d:" + "\\\\",
    "github" + "_token",
    "gh" + "_token",
    "openai" + "_api_key",
)


def compiled_session_example_dir(repo_root: Path | str) -> Path:
    repo_root = Path(repo_root).resolve()
    return repo_root / "docs" / "examples" / "agent-memory-graph" / "harness-self-governance"


def iter_compiled_session_examples(root: Path | str) -> list[Path]:
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(root.glob("compiled-session-*.json"))


def _quality_blockers(payload: dict[str, Any]) -> list[str]:
    blockers = validate_compiled_session(payload)
    if not str(payload.get("summary", "")).strip():
        blockers.append("summary must be non-empty")
    for section in ("decisions", "requirements", "constraints", "graph_links"):
        value = payload.get(section)
        if not value:
            blockers.append(f"{section} must be non-empty")
    text = json.dumps(payload, ensure_ascii=False).lower()
    if "raw transcript" in text:
        blockers.append("raw transcript dumps are not allowed")
    for banned in BANNED_SNIPPETS:
        if banned in text:
            blockers.append(f"contains banned snippet: {banned}")
    return sorted(set(blockers))


def validate_compiled_session_file(path: Path | str) -> dict[str, Any]:
    path = Path(path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    blockers = _quality_blockers(payload)
    return {
        "path": path.as_posix(),
        "session_id": payload.get("session_id"),
        "status": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "warnings": [],
    }


def validate_compiled_session_examples(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    examples = iter_compiled_session_examples(root)
    validations = [validate_compiled_session_file(path) for path in examples]
    blockers = [f"{Path(item['path']).name}: {msg}" for item in validations for msg in item.get("blockers", [])]
    status = "PASS" if not blockers else "FAIL"
    return {
        "status": status,
        "archive_quality_status": status,
        "schema_version": SCHEMA_VERSION,
        "root": root.as_posix(),
        "example_count": len(examples),
        "validated_examples": validations,
        "warnings": [],
        "blockers": blockers,
    }
