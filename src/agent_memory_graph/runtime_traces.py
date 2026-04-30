from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import SCHEMA_VERSION, deterministic_write_json


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-max(1, limit):]:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-limit:]


def load_graph_memory_traces(trace_dir: Path | str, limit: int = 50) -> dict[str, Any]:
    trace_dir = Path(trace_dir).expanduser().resolve()
    events: list[dict[str, Any]] = []
    if trace_dir.exists():
        files = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        for path in files[-8:]:
            events.extend(_read_jsonl(path, limit))
    events = events[-limit:]
    pre_events = [e for e in events if e.get("event") == "pre_llm_call"]
    injected = [e for e in pre_events if e.get("injected") is True]
    errors = [e for e in events if e.get("status") == "ERROR"]
    latest = events[-1] if events else None
    skill_counts: dict[str, int] = {}
    for event in pre_events:
        for skill in event.get("skill_load_order") or []:
            skill_counts[str(skill)] = skill_counts.get(str(skill), 0) + 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "graph_memory_runtime_traces",
        "trace_dir": trace_dir.as_posix(),
        "available": bool(events),
        "event_count": len(events),
        "pre_llm_call_count": len(pre_events),
        "injected_count": len(injected),
        "error_count": len(errors),
        "raw_sessions_allowed_count": sum(1 for e in pre_events if e.get("raw_sessions_allowed") is True),
        "latest": latest,
        "skill_counts": dict(sorted(skill_counts.items())),
        "events": events,
        "warnings": [] if trace_dir.exists() else [f"trace directory not found: {trace_dir.as_posix()}"],
        "blockers": [],
    }
    return payload


def export_graph_memory_traces(trace_dir: Path | str, out_path: Path | str, limit: int = 50) -> dict[str, Any]:
    payload = load_graph_memory_traces(trace_dir, limit=limit)
    out_path = Path(out_path).expanduser().resolve()
    deterministic_write_json(out_path, payload)
    return {
        "status": "PASS",
        "trace_dir": payload["trace_dir"],
        "out_path": out_path.as_posix(),
        "event_count": payload["event_count"],
        "injected_count": payload["injected_count"],
        "error_count": payload["error_count"],
        "warnings": payload.get("warnings", []),
        "blockers": [],
    }
