from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PLUGIN_PATH = Path(__file__).resolve().parents[2] / "plugins" / "graph_memory" / "__init__.py"


def _load_plugin(name: str = "graph_memory_under_test"):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / "skills" / "architecture" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Governance skill used by graph memory.\n"
        "---\n\n"
        "# Skill\n\n"
        "## When to use\n"
        "Use when the graph selects this procedural attachment.\n\n"
        "## Procedure\n"
        "Follow project summary, plan, constraints, and evidence policy.\n",
        encoding="utf-8",
    )


def test_pre_llm_call_injects_graph_packet_and_skill_mounts(tmp_path, monkeypatch):
    plugin = _load_plugin("graph_memory_under_test_inject")
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_skill(hermes_home, "graph-harness-maintain")
    repo = tmp_path / "repo"
    (repo / ".agent").mkdir(parents=True)
    (repo / ".agent" / "context.json").write_text("{}", encoding="utf-8")
    (repo / "src" / "agent_memory_graph").mkdir(parents=True)
    (repo / "src" / "agent_memory_graph" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "agent_memory_graph" / "retrieve.py").write_text(
        "def retrieve_project_context(repo, query, **kwargs):\n"
        "    return {\n"
        "      'status': 'PASS', 'selected_profile': 'general', 'selected_project': 'harness-self-governance',\n"
        "      'confidence': 1.0, 'budget': kwargs.get('budget'), 'evidence_depth': kwargs.get('evidence_depth'),\n"
        "      'raw_sessions_allowed': False, 'latency_ms': 1.2, 'cache_events': ['test-cache'],\n"
        "      'summary_first': {'project_identity': {'project': 'harness-self-governance'}},\n"
        "      'plan': {'todo': ['adapter']}, 'selected_nodes': ['project_summary:general:harness-self-governance'],\n"
        "      'selected_edges': [], 'selected_raw_evidence_anchors': [],\n"
        "      'skill_mounts': [{'skill': 'graph-harness-maintain', 'mount_role': 'governance_protocol'}],\n"
        "      'skill_load_order': ['graph-harness-maintain'], 'miss_policy': {}, 'hit_count': 2\n"
        "    }\n",
        encoding="utf-8",
    )
    config = {
        "plugins": {"enabled": ["graph-memory"]},
        "skills": {"external_dirs": str(hermes_home / "skills")},
        "graph_memory": {
            "enabled": True,
            "mode": "inject",
            "repo_roots": [str(repo)],
            "repo_project_hints": {
                str(repo): {"profile": "general", "project": "harness-self-governance"}
            },
            "max_context_chars": 5000,
            "auto_skill_mounts": True,
            "skill_mount_mode": "summary",
            "trace_dir": str(tmp_path / "traces"),
        },
    }
    (hermes_home / "config.yaml").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HOME", str(hermes_home / "home"))

    result = plugin.pre_llm_call(
        session_id="s1",
        user_message=f"[Workspace: {tmp_path}] continue graph harness work",
        conversation_history=[],
        is_first_turn=True,
    )

    assert result and "context" in result
    context = result["context"]
    assert "<graph_memory_context>" in context
    assert "harness-self-governance" in context
    assert "graph-harness-maintain" in context
    assert "mounted_skill_contracts" in context
    assert "Use when the graph selects" in context
    traces = list((tmp_path / "traces").glob("*.jsonl"))
    assert traces
    assert "\"injected\": true" in traces[0].read_text(encoding="utf-8")


def test_observe_mode_traces_without_injection(tmp_path, monkeypatch):
    plugin = _load_plugin("graph_memory_under_test_observe")
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    repo = tmp_path / "repo"
    (repo / ".agent").mkdir(parents=True)
    (repo / ".agent" / "context.json").write_text("{}", encoding="utf-8")
    (repo / "src" / "agent_memory_graph").mkdir(parents=True)
    (repo / "src" / "agent_memory_graph" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "agent_memory_graph" / "retrieve.py").write_text(
        "def retrieve_project_context(repo, query, **kwargs):\n"
        "    return {'status': 'PASS', 'selected_profile': 'general', 'selected_project': 'p', 'hit_count': 1}\n",
        encoding="utf-8",
    )
    (hermes_home / "config.yaml").write_text(json.dumps({
        "graph_memory": {"enabled": True, "mode": "observe", "repo_roots": [str(repo)], "trace_dir": str(tmp_path / "traces")}
    }), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert plugin.pre_llm_call(session_id="s2", user_message=f"[Workspace: {tmp_path}] task", conversation_history=[]) is None
    trace = next((tmp_path / "traces").glob("*.jsonl")).read_text(encoding="utf-8")
    assert "\"injected\": false" in trace


def test_post_llm_call_can_capture_pending_update(tmp_path, monkeypatch):
    plugin = _load_plugin("graph_memory_under_test_pending")
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    repo = tmp_path / "repo"
    (repo / ".agent").mkdir(parents=True)
    (repo / ".agent" / "context.json").write_text("{}", encoding="utf-8")
    (repo / "src" / "agent_memory_graph").mkdir(parents=True)
    (repo / "src" / "agent_memory_graph" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "agent_memory_graph" / "retrieve.py").write_text(
        "def retrieve_project_context(repo, query, **kwargs):\n"
        "    return {'status': 'PASS', 'selected_profile': 'general', 'selected_project': 'p', 'hit_count': 1, 'skill_load_order': []}\n",
        encoding="utf-8",
    )
    (repo / "src" / "agent_memory_graph" / "pending_updates.py").write_text(
        "def capture_pending_update(repo, text, profile_id, project_id, memory_root=None, source='x', update_type='x'):\n"
        "    import json, pathlib\n"
        "    root = pathlib.Path(memory_root or pathlib.Path(repo)/'mem')\n"
        "    path = root/'routing'/'pending-updates.json'\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    path.write_text(json.dumps({'profile': profile_id, 'project': project_id, 'text': text, 'update_type': update_type}))\n"
        "    return {'status': 'PASS', 'pending_updates_path': str(path)}\n",
        encoding="utf-8",
    )
    mem = tmp_path / "mem"
    (hermes_home / "config.yaml").write_text(json.dumps({
        "graph_memory": {
            "enabled": True, "mode": "inject", "repo_roots": [str(repo)],
            "capture_pending_updates": True, "memory_root": str(mem), "trace_dir": str(tmp_path / "traces")
        }
    }), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    plugin.pre_llm_call(session_id="s3", user_message=f"[Workspace: {tmp_path}] task", conversation_history=[])
    plugin.post_llm_call(session_id="s3", user_message="我决定 graph memory 必须捕获 pending update", assistant_response="ok")
    payload = json.loads((mem / "routing" / "pending-updates.json").read_text(encoding="utf-8"))
    assert payload["profile"] == "general"
    assert payload["project"] == "p"
    assert payload["update_type"] == "decision"
