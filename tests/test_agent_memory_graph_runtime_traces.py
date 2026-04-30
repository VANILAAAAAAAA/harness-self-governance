from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.runtime_traces import export_graph_memory_traces, load_graph_memory_traces


def test_runtime_traces_loads_bounded_jsonl_events(tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    (trace_dir / "graph-memory.jsonl").write_text(
        "\n".join([
            json.dumps({"event": "pre_llm_call", "status": "PASS", "injected": True, "skill_load_order": ["graph-harness-maintain"], "raw_sessions_allowed": False}),
            json.dumps({"event": "post_llm_call", "status": "PASS"}),
            json.dumps({"event": "pre_llm_call", "status": "ERROR", "injected": False, "raw_sessions_allowed": False}),
        ]) + "\n",
        encoding="utf-8",
    )

    payload = load_graph_memory_traces(trace_dir, limit=10)
    assert payload["available"] is True
    assert payload["event_count"] == 3
    assert payload["pre_llm_call_count"] == 2
    assert payload["injected_count"] == 1
    assert payload["error_count"] == 1
    assert payload["raw_sessions_allowed_count"] == 0
    assert payload["skill_counts"] == {"graph-harness-maintain": 1}


def test_runtime_traces_export_writes_report(tmp_path: Path) -> None:
    trace_dir = tmp_path / "missing"
    out = tmp_path / "artifacts" / "v2" / "runtime" / "graph-memory-traces.json"
    report = export_graph_memory_traces(trace_dir, out, limit=5)
    assert report["status"] == "PASS"
    assert report["event_count"] == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["available"] is False
    assert payload["warnings"]
