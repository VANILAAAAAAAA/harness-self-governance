from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .bootstrap import bootstrap_repo
from .lineage import write_global_lineage
from .projects import load_project_bundle
from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, ensure_memory_layout, resolve_memory_root

BUDGET_HINTS: dict[str, dict[str, Any]] = {
    "fast": {"layers": ["context-index", "project-summary", "direct-entry-artifacts"], "max_depth": 1, "raw_sessions_allowed": False},
    "normal": {"layers": ["fast", "selected-decisions", "selected-requirements", "selected-constraints", "selected-lineage-paths"], "max_depth": 2, "raw_sessions_allowed": False},
    "deep": {"layers": ["normal", "mapped-logs", "session-summaries"], "max_depth": 3, "raw_sessions_allowed": False},
    "forensic": {"layers": ["deep", "raw-sessions-explicit"], "max_depth": 4, "raw_sessions_allowed": True},
}

BUILTIN_TOPICS: dict[str, dict[str, Any]] = {
    "view-in-logs": {
        "label": "View in Logs",
        "aliases": ["view in logs", "logs", "log", "log定位", "日志定位", "lineage mapping", "lineage"],
        "entry_nodes": ["project_summary:{profile}:{project}", "tool:agent-graph-cli", "protocol:graph-governed-context"],
        "artifact_kinds": ["project_summary", "lineage_index", "graph_fragment"],
        "budget_hint": "fast",
    },
    "raw-sessions-policy": {
        "label": "Raw sessions policy",
        "aliases": ["raw sessions", "raw session", "sessions/raw", "原始会话"],
        "entry_nodes": ["protocol:graph-governed-context", "constraint:raw-sessions-last"],
        "artifact_kinds": ["constraints", "project_summary"],
        "budget_hint": "normal",
    },
    "hub-llm-api-policy": {
        "label": "Hub-side LLM API policy",
        "aliases": ["hub-side llm api", "hub llm api", "Hub-side LLM API", "模型设置", "provider settings"],
        "entry_nodes": ["constraint:no-hub-llm-api", "protocol:graph-governed-context"],
        "artifact_kinds": ["constraints", "decision_ledger"],
        "budget_hint": "normal",
    },
}


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9一-龥]+", text.lower()) if token]


def _artifact_paths(project_root: Path) -> dict[str, str]:
    return {
        "project_manifest": (project_root / "project-manifest.json").as_posix(),
        "project_summary": (project_root / "project-summary.json").as_posix(),
        "decision_ledger": (project_root / "decision-ledger.json").as_posix(),
        "requirements": (project_root / "requirements.json").as_posix(),
        "constraints": (project_root / "constraints.json").as_posix(),
        "session_index": (project_root / "session-index.json").as_posix(),
        "graph_fragment": (project_root / "graph-fragment.json").as_posix(),
        "lineage_index": (project_root / "lineage-index.json").as_posix(),
    }


def _project_key(profile_id: str, project_id: str) -> str:
    return f"{profile_id}/{project_id}"


def build_context_index(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    ensure_memory_layout(memory_root)
    manifest = read_repo_manifest(repo_root)
    if not manifest:
        return {"status": "FAIL", "warnings": [], "blockers": [".agent/context.json is missing"]}
    profile_id = str(manifest.get("profile", ""))
    project_id = str(manifest.get("project", ""))
    bootstrap_repo(repo_root, memory_root)
    bundle = load_project_bundle(memory_root, profile_id, project_id)
    write_global_lineage(memory_root, profile_id, project_id)
    project_root = bundle["root"]
    artifact_paths = _artifact_paths(project_root)
    nodes = bundle["graph_fragment"].get("nodes") or []
    graph_node_ids = sorted({str(node.get("id")) for node in nodes if node.get("id")})
    topics: dict[str, Any] = {}
    aliases: dict[str, str] = {}
    for topic_id, topic in BUILTIN_TOPICS.items():
        entry_nodes = [item.format(profile=profile_id, project=project_id) for item in topic["entry_nodes"]]
        topics[topic_id] = {
            "label": topic["label"],
            "entry_nodes": sorted(set(entry_nodes)),
            "artifact_kinds": topic["artifact_kinds"],
            "budget_hint": topic["budget_hint"],
        }
        for alias in topic["aliases"]:
            aliases[alias.lower()] = topic_id
            aliases[alias] = topic_id
    searchable_sections = [
        ("decision_ledger", bundle["decision_ledger"].get("decisions", [])),
        ("requirements", bundle["requirements"].get("requirements", [])),
        ("constraints", bundle["constraints"].get("constraints", [])),
    ]
    for section, items in searchable_sections:
        for item in items:
            node_id = item.get("id")
            text = str(item.get("text", ""))
            if not node_id:
                continue
            for token in _tokens(text):
                if len(token) >= 4:
                    aliases.setdefault(token, str(node_id))
    index = {
        "schema_version": SCHEMA_VERSION,
        "routing_table_type": "graph_traversal_context_index",
        "not_search_database": True,
        "repo_path": repo_root.as_posix(),
        "profile": profile_id,
        "project": project_id,
        "profiles": {
            profile_id: {
                "entry_node": f"profile:{profile_id}",
                "artifact_path": (memory_root / "profiles" / profile_id / "profile.json").as_posix(),
            }
        },
        "projects": {
            _project_key(profile_id, project_id): {
                "entry_node": f"project:{profile_id}:{project_id}",
                "summary_node": f"project_summary:{profile_id}:{project_id}",
                "artifact_paths": artifact_paths,
            }
        },
        "topics": dict(sorted(topics.items())),
        "aliases": dict(sorted(aliases.items())),
        "entry_nodes": sorted(set([f"profile:{profile_id}", f"project:{profile_id}:{project_id}", f"project_summary:{profile_id}:{project_id}"] + graph_node_ids)),
        "artifact_paths": artifact_paths,
        "budget_hints": BUDGET_HINTS,
        "graph_layers": {
            "agent_memory_graph": (memory_root / "graph" / "global-graph.json").as_posix(),
            "lineage_index": (memory_root / "graph" / "global-lineage-index.json").as_posix(),
            "governance_graph": str((repo_root / "artifacts" / "v2" / "graph" / "governance-graph.json").as_posix()),
            "layer_boundary": "governance_graph_is_observability_agent_memory_graph_is_context_protocol",
        },
        "warnings": [],
        "blockers": [],
    }
    target = memory_root / "index" / "context-index.json"
    deterministic_write_json(target, index)
    return {"status": "PASS", "context_index_path": target.as_posix(), "profile": profile_id, "project": project_id, "warnings": [], "blockers": []}


def load_or_build_context_index(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    memory_root = resolve_memory_root(memory_root)
    target = memory_root / "index" / "context-index.json"
    if not target.exists():
        build_context_index(repo_root, memory_root)
    import json
    return json.loads(target.read_text(encoding="utf-8"))
