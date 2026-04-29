from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".json"}
TOKEN_NAME_PATTERN = "(" + "|".join(["OPENAI" + "_API_KEY", "GITHUB" + "_TOKEN", "GH" + "_TOKEN", "API_KEY", "TOKEN"]) + ")"
TOKEN_PATTERNS = [
    re.compile(r"(?i)" + TOKEN_NAME_PATTERN + r"\s*=\s*[^\s`]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"[A-Za-z0-9_-]{32,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def redact_sensitive_values(text: str) -> str:
    redacted = text
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub("[REDACTED_TOKEN]", redacted)
    return redacted


def _source_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read_source(path: Path) -> tuple[str, str | None]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            title = data.get("title") if isinstance(data, dict) else None
            text = json.dumps(data, sort_keys=True, ensure_ascii=False) if not isinstance(data, str) else data
            if isinstance(data, dict):
                joined = []
                for key in ("title", "summary", "body", "content", "text"):
                    if data.get(key):
                        joined.append(str(data[key]))
                text = "\n".join(joined) or text
            return text, title
        except json.JSONDecodeError:
            return text, None
    return text, None


def _slug(path: Path) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", path.stem).strip("-").lower()
    return value or hashlib.sha256(path.as_posix().encode()).hexdigest()[:12]


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_prefixed(lines: list[str], prefixes: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    lowered = tuple(prefix.lower() for prefix in prefixes)
    for line in lines:
        compact = line.lstrip("#-* >").strip()
        lower = compact.lower()
        for prefix in lowered:
            if lower.startswith(prefix):
                value = compact.split(":", 1)[1].strip() if ":" in compact else compact
                if value and value not in out:
                    out.append(value[:300])
                break
    return out


def _extract_commands(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        compact = line.strip().strip("`")
        lower = compact.lower()
        if lower.startswith(("command:", "$ ")) or "python -m " in compact or compact.startswith(("git ", "pytest ")):
            value = compact.split(":", 1)[1].strip() if lower.startswith("command:") else compact.removeprefix("$ ").strip()
            if value and value not in out:
                out.append(value[:300])
    return out


def _extract_artifacts(lines: list[str]) -> list[str]:
    seen: list[str] = []
    pattern = re.compile(r"(?:artifacts|docs|src|tests|policies)/[A-Za-z0-9_./-]+")
    for line in lines:
        for match in pattern.findall(line):
            item = match.rstrip(".,);]")
            if item not in seen:
                seen.append(item)
    return seen


def _extract_graph_links(text: str, session_id: str) -> list[dict[str, str]]:
    links = [{"type": "summarized_into", "source": f"session:{session_id}", "target": "knowledge:session-index"}]
    for branch in sorted(set(re.findall(r"\b(?:branch[: ]+)?(v\d+\.\d+(?:-dev|-rc)?)\b", text, flags=re.I))):
        links.append({"type": "references", "source": f"session:{session_id}", "target": f"branch:{branch}"})
    for tag in sorted(set(re.findall(r"\b(?:tag[: ]+)?(v\d+\.\d+\.\d+)\b", text, flags=re.I))):
        links.append({"type": "references", "source": f"session:{session_id}", "target": f"tag:{tag}"})
    for pr in sorted(set(re.findall(r"\bPR\s*#?(\d+)\b", text, flags=re.I))):
        links.append({"type": "references", "source": f"session:{session_id}", "target": f"pr:{pr}"})
    return links


def summarize_session(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text, json_title = _read_source(path)
    text = redact_sensitive_values(text)
    lines = _lines(text)
    session_id = _slug(path)
    title = json_title or path.stem.replace("-", " ").replace("_", " ").strip().title()
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("# ").strip() or title
    summary_source = " ".join(lines[:5])
    summary = summary_source[:500] if summary_source else "No session content available after redaction."
    decisions = _extract_prefixed(lines, ("decision:", "decided:"))
    requirements = _extract_prefixed(lines, ("requirement:", "required:"))
    constraints = _extract_prefixed(lines, ("constraint:", "boundary:", "safety:"))
    open_questions = _extract_prefixed(lines, ("open question:", "question:", "todo:"))
    commands = _extract_commands(lines)
    artifacts = _extract_artifacts(lines)
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "title": title,
        "source_hash": _source_hash(raw),
        "privacy": "local_only",
        "summary": summary,
        "decisions": decisions,
        "requirements": requirements,
        "constraints": constraints,
        "commands": commands,
        "artifacts_referenced": artifacts,
        "open_questions": open_questions,
        "graph_links": _extract_graph_links(text, session_id),
    }


def ensure_session_index(repo_root: Path | str) -> Path:
    repo_root = Path(repo_root).resolve()
    out_dir = repo_root / "artifacts" / "v2" / "sessions"
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "session-index.json"
    if not index.exists():
        index.write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": _utc_now(),
                    "privacy": "local_only",
                    "source": "sessions/raw",
                    "sessions": [],
                    "warnings": ["session raw input directory has not been compressed yet"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return index


def compress_sessions(repo_root: Path | str, input_dir: Path | str, out_dir: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    raw_dir = Path(input_dir)
    if not raw_dir.is_absolute():
        raw_dir = repo_root / raw_dir
    out = Path(out_dir) if out_dir else repo_root / "artifacts" / "v2" / "sessions"
    if not out.is_absolute():
        out = repo_root / out
    out.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    sessions: list[dict[str, Any]] = []
    if not raw_dir.exists():
        warnings.append(f"input directory does not exist: {_rel(repo_root, raw_dir)}")
    else:
        for source in sorted(path for path in raw_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS):
            summary = summarize_session(source)
            summary_path = out / f"{summary['session_id']}.summary.json"
            summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            sessions.append(
                {
                    "session_id": summary["session_id"],
                    "title": summary["title"],
                    "source_hash": summary["source_hash"],
                    "privacy": "local_only",
                    "summary_path": _rel(repo_root, summary_path),
                    "source_path": _rel(repo_root, source),
                }
            )
    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "privacy": "local_only",
        "source": _rel(repo_root, raw_dir),
        "sessions": sorted(sessions, key=lambda item: item["session_id"]),
        "warnings": warnings,
    }
    index_path = out / "session-index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "generated_at": index["generated_at"],
        "status": "PASS_WITH_WARNINGS" if warnings else "PASS",
        "path": _rel(repo_root, index_path),
        "session_count": len(sessions),
        "privacy": "local_only",
        "warnings": warnings,
        "blockers": [],
    }
