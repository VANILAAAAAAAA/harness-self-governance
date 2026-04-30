"""Graph-governed project memory plugin for Hermes.

This plugin is intentionally a pre-LLM-call adapter, not a replacement context
compressor.  It preserves the active live session as short-term context and
injects a bounded, graph-retrieved project memory packet beside the user's turn.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PLUGIN_NAME = "graph-memory"
DEFAULT_MAX_CONTEXT_CHARS = 6000
DEFAULT_MAX_SKILL_CHARS = 1600
DEFAULT_BUDGET = "fast"
DEFAULT_EVIDENCE_DEPTH = "anchor"
VALID_MODES = {"off", "observe", "inject", "enforce"}

_LAST_PACKETS: dict[str, dict[str, Any]] = {}


def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_llm_call", post_llm_call)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_config() -> dict[str, Any]:
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        cfg = _load_config_file(Path(env_home).expanduser() / "config.yaml")
        if cfg:
            return cfg
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        if isinstance(cfg, dict) and isinstance(cfg.get("graph_memory"), dict) and cfg.get("graph_memory"):
            return cfg
    except Exception:
        pass
    return _load_config_file(_hermes_home() / "config.yaml")


def _load_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        raw = config_path.read_text(encoding="utf-8")
        try:
            import yaml
            cfg = yaml.safe_load(raw) or {}
        except Exception:
            try:
                cfg = json.loads(raw)
            except Exception:
                cfg = _parse_profile_config_fallback(raw)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _parse_simple_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _parse_profile_config_fallback(raw: str) -> dict[str, Any]:
    """Parse the graph_memory YAML block when PyYAML is unavailable."""
    graph_memory: dict[str, Any] = {}
    lines = raw.splitlines()
    in_block = False
    block_indent = 0
    current_list_key: str | None = None
    current_mapping_key: str | None = None
    current_mapping_item: str | None = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if not in_block:
            if stripped == "graph_memory:":
                in_block = True
                block_indent = indent
            continue
        if indent <= block_indent:
            break
        rel = indent - block_indent
        if rel == 2 and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_list_key = None
            current_mapping_key = None
            current_mapping_item = None
            if value:
                graph_memory[key] = _parse_simple_scalar(value)
            else:
                if key in {"repo_roots"}:
                    graph_memory[key] = []
                    current_list_key = key
                elif key in {"repo_project_hints"}:
                    graph_memory[key] = {}
                    current_mapping_key = key
                else:
                    graph_memory[key] = {}
                    current_mapping_key = key
            continue
        if rel == 2 and stripped.startswith("- ") and current_list_key:
            graph_memory.setdefault(current_list_key, []).append(_parse_simple_scalar(stripped[2:].strip()))
            continue
        if rel == 4 and stripped.startswith("- ") and current_list_key:
            graph_memory.setdefault(current_list_key, []).append(_parse_simple_scalar(stripped[2:].strip()))
            continue
        if rel == 4 and current_mapping_key and stripped.endswith(":"):
            current_mapping_item = stripped[:-1].strip()
            graph_memory.setdefault(current_mapping_key, {})[current_mapping_item] = {}
            continue
        if rel >= 6 and current_mapping_key and current_mapping_item and ":" in stripped:
            key, value = stripped.split(":", 1)
            graph_memory.setdefault(current_mapping_key, {}).setdefault(current_mapping_item, {})[key.strip()] = _parse_simple_scalar(value.strip())
            continue
    return {"graph_memory": graph_memory} if graph_memory else {}


def _plugin_config() -> dict[str, Any]:
    cfg = _load_config()
    section = cfg.get("graph_memory", {})
    if not isinstance(section, dict):
        section = {}
    mode = str(section.get("mode", "inject" if section.get("enabled") else "off")).strip().lower()
    if mode not in VALID_MODES:
        mode = "off"
    return {
        "enabled": bool(section.get("enabled", mode not in {"off"})),
        "mode": mode,
        "default_budget": str(section.get("default_budget", DEFAULT_BUDGET)),
        "default_evidence_depth": str(section.get("default_evidence_depth", DEFAULT_EVIDENCE_DEPTH)),
        "max_context_chars": int(section.get("max_context_chars", DEFAULT_MAX_CONTEXT_CHARS)),
        "auto_skill_mounts": bool(section.get("auto_skill_mounts", True)),
        "skill_mount_mode": str(section.get("skill_mount_mode", "summary")).strip().lower(),
        "max_skill_chars": int(section.get("max_skill_chars", DEFAULT_MAX_SKILL_CHARS)),
        "trace": bool(section.get("trace", True)),
        "trace_dir": str(section.get("trace_dir", "")),
        "memory_root": str(section.get("memory_root", "")),
        "repo_roots": list(section.get("repo_roots", []) or []),
        "repo_project_hints": section.get("repo_project_hints", {}) if isinstance(section.get("repo_project_hints", {}), dict) else {},
        "default_profile": str(section.get("default_profile", "") or ""),
        "default_project": str(section.get("default_project", "") or ""),
        "raw_span_enabled": bool(section.get("raw_span_enabled", False)),
        "capture_pending_updates": bool(section.get("capture_pending_updates", False)),
        "search_workspace_children": bool(section.get("search_workspace_children", True)),
        "workspace_child_depth": int(section.get("workspace_child_depth", 1)),
    }


def _hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home()).expanduser().resolve()
    except Exception:
        return Path("~/.hermes").expanduser().resolve()


def _memory_root(config: dict[str, Any]) -> Path | None:
    raw = (config.get("memory_root") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    home = Path(os.environ.get("HOME", "")).expanduser()
    if home:
        candidate = home / ".agent-memory-graph"
        if candidate.exists():
            return candidate.resolve()
    profile_home_candidate = _hermes_home() / "home" / ".agent-memory-graph"
    if profile_home_candidate.exists():
        return profile_home_candidate.resolve()
    return None


def _workspace_from_message(user_message: str | None, conversation_history: list[dict[str, Any]] | None = None) -> Path | None:
    texts: list[str] = []
    if isinstance(user_message, str):
        texts.append(user_message)
    for msg in reversed(conversation_history or []):
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, str):
            texts.append(content)
            if len(texts) >= 4:
                break
    pat = re.compile(r"\[Workspace:\s*([^\]\n]+)\]")
    for text in texts:
        m = pat.search(text)
        if m:
            p = Path(m.group(1).strip()).expanduser()
            if p.exists():
                return p.resolve()
    for env_name in ("TERMINAL_CWD", "PWD"):
        raw = os.environ.get(env_name)
        if raw:
            p = Path(raw).expanduser()
            if p.exists():
                return p.resolve()
    return None


def _ancestors(path: Path) -> Iterable[Path]:
    cur = path.resolve()
    if cur.is_file():
        cur = cur.parent
    yield cur
    yield from cur.parents


def _has_manifest(path: Path) -> bool:
    return (path / ".agent" / "context.json").is_file()


def _candidate_repos(workspace: Path | None, config: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(p: Path | str | None):
        if not p:
            return
        try:
            pp = Path(p).expanduser().resolve()
        except Exception:
            return
        key = pp.as_posix()
        if pp.exists() and key not in seen:
            seen.add(key)
            candidates.append(pp)

    for raw in config.get("repo_roots", []):
        add(raw)
    if workspace:
        for p in _ancestors(workspace):
            add(p)
        if config.get("search_workspace_children", True) and workspace.is_dir():
            max_depth = max(0, int(config.get("workspace_child_depth", 1)))
            frontier = [(workspace, 0)]
            while frontier:
                cur, depth = frontier.pop(0)
                if depth >= max_depth:
                    continue
                try:
                    children = sorted([c for c in cur.iterdir() if c.is_dir() and not c.name.startswith(".")])
                except Exception:
                    continue
                for child in children:
                    add(child)
                    if depth + 1 < max_depth:
                        frontier.append((child, depth + 1))

    return [p for p in candidates if _has_manifest(p)]


def _ensure_repo_import(repo: Path) -> None:
    src = repo / "src"
    if src.is_dir():
        s = src.as_posix()
        if s not in sys.path:
            sys.path.insert(0, s)


def _project_hints_for_repo(repo: Path, config: dict[str, Any], workspace: Path | None = None) -> tuple[str | None, str | None]:
    mapping = config.get("repo_project_hints") or {}
    keys: list[str] = []
    if workspace:
        try:
            ws = workspace.expanduser().resolve()
            keys.extend([p.as_posix() for p in _ancestors(ws)])
            keys.extend([p.name for p in _ancestors(ws)])
        except Exception:
            pass
    keys.extend([repo.as_posix(), repo.name])
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        raw = mapping.get(key) if isinstance(mapping, dict) else None
        if isinstance(raw, dict):
            return raw.get("profile") or config.get("default_profile") or None, raw.get("project") or config.get("default_project") or None
        if isinstance(raw, str) and "/" in raw:
            profile, project = raw.split("/", 1)
            return profile or None, project or None
    return config.get("default_profile") or None, config.get("default_project") or None


def _call_retriever(repo: Path, query: str, config: dict[str, Any], workspace: Path | None = None) -> dict[str, Any]:
    _ensure_repo_import(repo)
    from agent_memory_graph.retrieve import retrieve_project_context
    memory_root = _memory_root(config)
    evidence_depth = config["default_evidence_depth"]
    budget = config["default_budget"]
    if evidence_depth == "raw-span" and not config.get("raw_span_enabled", False):
        evidence_depth = "anchor"
        budget = "fast" if budget == "forensic" else budget
    profile_hint, project_hint = _project_hints_for_repo(repo, config, workspace=workspace)
    return retrieve_project_context(
        repo,
        query or "",
        profile_hint=profile_hint,
        project_hint=project_hint,
        memory_root=memory_root,
        budget=budget,
        evidence_depth=evidence_depth,
    )


def _score_packet(packet: dict[str, Any]) -> tuple[int, int]:
    status_score = {"PASS": 4, "LOW_CONFIDENCE": 2, "NEW_INFORMATION": 1, "MISS": 0}.get(str(packet.get("status")), 0)
    hit_count = int(packet.get("hit_count") or 0)
    skill_count = len(packet.get("skill_load_order") or [])
    return (status_score, hit_count + skill_count)


def _retrieve_best_packet(repos: list[Path], query: str, config: dict[str, Any], workspace: Path | None = None) -> tuple[dict[str, Any] | None, Path | None, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    best_packet: dict[str, Any] | None = None
    best_repo: Path | None = None
    best_score = (-1, -1)
    for repo in repos:
        started = time.perf_counter()
        try:
            packet = _call_retriever(repo, query, config, workspace=workspace)
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            attempts.append({"repo": repo.as_posix(), "status": packet.get("status"), "latency_ms": elapsed, "project": packet.get("selected_project")})
            score = _score_packet(packet)
            if score > best_score:
                best_score = score
                best_packet = packet
                best_repo = repo
        except Exception as exc:
            attempts.append({"repo": repo.as_posix(), "status": "ERROR", "error": str(exc)[:240]})
    return best_packet, best_repo, attempts


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    body = text[end + 4:].lstrip("\n")
    raw = text[3:end]
    data: dict[str, Any] = {}
    try:
        import yaml
        parsed = yaml.safe_load(raw) or {}
        if isinstance(parsed, dict):
            data = parsed
    except Exception:
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    return data, body


def _skill_dirs() -> list[Path]:
    try:
        from agent.skill_utils import get_all_skills_dirs
        return [Path(p) for p in get_all_skills_dirs()]
    except Exception:
        return [_hermes_home() / "skills", Path("~/.agents/skills").expanduser()]


def _find_skill_file(skill_name: str) -> Path | None:
    if not skill_name:
        return None
    bare = skill_name.split(":")[-1]
    for root in _skill_dirs():
        if not root.is_dir():
            continue
        direct = root / bare / "SKILL.md"
        if direct.is_file():
            return direct
        try:
            for path in root.rglob("SKILL.md"):
                if path.parent.name == bare:
                    return path
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")[:2000]
                    fm, _ = _parse_frontmatter(text)
                    if str(fm.get("name", "")) == bare:
                        return path
                except Exception:
                    continue
        except Exception:
            continue
    return None


def _summarize_skill(skill_name: str, max_chars: int, mode: str) -> dict[str, Any]:
    path = _find_skill_file(skill_name)
    if not path:
        return {"skill": skill_name, "found": False, "content": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(text)
    desc = str(fm.get("description") or "").strip()
    if mode == "full":
        content = text[:max_chars]
    elif mode == "summary":
        # Keep enough procedural signal to be useful without dumping huge skills.
        lines = []
        capture = False
        for line in body.splitlines():
            lower = line.lower().strip()
            if lower.startswith("## when") or lower.startswith("## core") or lower.startswith("## procedure") or lower.startswith("## rules") or lower.startswith("## non-negotiable"):
                capture = True
            if capture:
                lines.append(line)
            if len("\n".join(lines)) >= max_chars:
                break
        content = ("description: " + desc + "\n" + "\n".join(lines)).strip()[:max_chars]
    else:
        content = desc[:max_chars]
    return {"skill": skill_name, "found": True, "path": path.as_posix(), "content": content}


def _compact_json(value: Any, max_chars: int = 1200) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n...[truncated]"


def _render_context(packet: dict[str, Any], repo: Path, config: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    max_chars = int(config.get("max_context_chars") or DEFAULT_MAX_CONTEXT_CHARS)
    skill_names = [str(s) for s in packet.get("skill_load_order") or [] if s]
    skills: list[dict[str, Any]] = []
    if config.get("auto_skill_mounts", True) and skill_names:
        per_skill = max(300, int(config.get("max_skill_chars", DEFAULT_MAX_SKILL_CHARS)))
        mode = str(config.get("skill_mount_mode", "summary"))
        skills = [_summarize_skill(name, per_skill, mode) for name in skill_names[:6]]

    raw_allowed = bool(packet.get("raw_sessions_allowed"))
    summary = packet.get("summary_first") or {}
    block = {
        "adapter": "graph-memory",
        "contract": "Graph-governed project memory packet. Preserve live session raw context; do not read historical raw sessions unless packet explicitly allows forensic raw-span requests.",
        "repo": repo.as_posix(),
        "status": packet.get("status"),
        "selected_profile": packet.get("selected_profile"),
        "selected_project": packet.get("selected_project"),
        "confidence": packet.get("confidence"),
        "budget": packet.get("budget"),
        "evidence_depth": packet.get("evidence_depth"),
        "raw_sessions_allowed": raw_allowed,
        "latency_ms": packet.get("latency_ms"),
        "cache_events": packet.get("cache_events"),
        "summary_first": summary,
        "plan": packet.get("plan"),
        "selected_nodes": packet.get("selected_nodes"),
        "selected_edges": packet.get("selected_edges"),
        "selected_raw_evidence_anchors": packet.get("selected_raw_evidence_anchors"),
        "skill_mounts": packet.get("skill_mounts"),
        "skill_load_order": skill_names,
        "mounted_skill_contracts": skills,
        "miss_policy": packet.get("miss_policy"),
        "attempts": attempts,
    }
    text = "<graph_memory_context>\n" + _compact_json(block, max_chars=max_chars - 64) + "\n</graph_memory_context>"
    if len(text) > max_chars:
        text = text[: max_chars - 32].rstrip() + "\n...[graph_memory_truncated]\n</graph_memory_context>"
    return text


def _trace_path(config: dict[str, Any]) -> Path:
    raw = str(config.get("trace_dir") or "").strip()
    base = Path(raw).expanduser() if raw else (_hermes_home() / "graph-memory-traces")
    base.mkdir(parents=True, exist_ok=True)
    return base / (datetime.now(timezone.utc).strftime("%Y%m%d") + ".jsonl")


def _write_trace(config: dict[str, Any], record: dict[str, Any]) -> None:
    if not config.get("trace", True):
        return
    record = {"ts": _utc_now(), **record}
    path = _trace_path(config)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def pre_llm_call(**kwargs) -> dict[str, str] | None:
    config = _plugin_config()
    if not config.get("enabled") or config.get("mode") == "off":
        return None
    user_message = kwargs.get("user_message") or ""
    session_id = str(kwargs.get("session_id") or "")
    workspace = _workspace_from_message(user_message, kwargs.get("conversation_history") or [])
    repos = _candidate_repos(workspace, config)
    if not repos:
        _write_trace(config, {"event": "pre_llm_call", "status": "NO_REPO", "workspace": workspace.as_posix() if workspace else None, "session_id": session_id})
        return None
    started = time.perf_counter()
    packet, repo, attempts = _retrieve_best_packet(repos, user_message, config)
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    if not packet or not repo:
        _write_trace(config, {"event": "pre_llm_call", "status": "ERROR", "workspace": workspace.as_posix() if workspace else None, "session_id": session_id, "attempts": attempts, "latency_ms": elapsed})
        return None
    _LAST_PACKETS[session_id] = {"packet": packet, "repo": repo.as_posix(), "config": config}
    trace = {
        "event": "pre_llm_call",
        "status": packet.get("status"),
        "mode": config.get("mode"),
        "workspace": workspace.as_posix() if workspace else None,
        "repo": repo.as_posix(),
        "session_id": session_id,
        "selected_profile": packet.get("selected_profile"),
        "selected_project": packet.get("selected_project"),
        "skill_load_order": packet.get("skill_load_order"),
        "raw_sessions_allowed": packet.get("raw_sessions_allowed"),
        "adapter_latency_ms": elapsed,
        "packet_latency_ms": packet.get("latency_ms"),
        "attempts": attempts,
        "injected": config.get("mode") in {"inject", "enforce"},
    }
    _write_trace(config, trace)
    if config.get("mode") == "observe":
        return None
    return {"context": _render_context(packet, repo, config, attempts)}


def _looks_like_pending_update(text: str) -> tuple[bool, str]:
    lower = text.lower()
    markers = [
        ("decision", "decision"), ("决定", "decision"),
        ("requirement", "requirement"), ("必须", "requirement"), ("需要", "requirement"),
        ("constraint", "constraint"), ("约束", "constraint"), ("不要", "constraint"),
        ("correction", "correction"), ("不是", "correction"),
        ("remember", "observation"), ("记住", "observation"),
    ]
    for marker, typ in markers:
        if marker in lower or marker in text:
            return True, typ
    return False, "observation"


def post_llm_call(**kwargs) -> None:
    config = _plugin_config()
    if not config.get("enabled") or not config.get("capture_pending_updates"):
        return None
    user_message = str(kwargs.get("user_message") or "")
    should_capture, update_type = _looks_like_pending_update(user_message)
    session_id = str(kwargs.get("session_id") or "")
    last = _LAST_PACKETS.get(session_id)
    if not should_capture or not last:
        return None
    packet = last.get("packet") or {}
    repo = Path(str(last.get("repo") or ".")).resolve()
    try:
        _ensure_repo_import(repo)
        from agent_memory_graph.pending_updates import capture_pending_update
        memory_root = _memory_root(config)
        result = capture_pending_update(
            repo,
            user_message,
            str(packet.get("selected_profile") or "unknown"),
            str(packet.get("selected_project") or "unknown"),
            memory_root=memory_root,
            source="hermes_graph_memory_post_llm_call",
            update_type=update_type,
        )
        _write_trace(config, {"event": "post_llm_call", "status": "PENDING_UPDATE_CAPTURED", "session_id": session_id, "update_type": update_type, "path": result.get("pending_updates_path")})
    except Exception as exc:
        _write_trace(config, {"event": "post_llm_call", "status": "ERROR", "session_id": session_id, "error": str(exc), "traceback": traceback.format_exc(limit=4)})
    return None
