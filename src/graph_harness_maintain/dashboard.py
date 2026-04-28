from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .graph_export import write_governance_graph
from .sessions import ensure_session_index


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _artifact_inventory(repo_root: Path) -> list[str]:
    root = repo_root / "artifacts" / "v2"
    if not root.exists():
        return []
    return sorted(path.relative_to(repo_root).as_posix() for path in root.rglob("*") if path.is_file())


def _html(graph: dict[str, Any], sessions: dict[str, Any], artifacts: list[str]) -> str:
    warnings = graph.get("warnings", [])
    blockers = graph.get("blockers", [])
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_rows = "\n".join(f"<li><strong>{escape(n['type'])}</strong>: {escape(n['label'])}</li>" for n in nodes[:80])
    edge_rows = "\n".join(f"<li>{escape(e['source'])} <span>{escape(e['type'])}</span> {escape(e['target'])}</li>" for e in edges[:120])
    artifact_rows = "\n".join(f"<li>{escape(item)}</li>" for item in artifacts) or "<li>No v2 artifacts yet.</li>"
    session_rows = "\n".join(
        f"<li><strong>{escape(item.get('title', item.get('session_id', 'session')))}</strong><br><code>{escape(item.get('summary_path', ''))}</code></li>"
        for item in sessions.get("sessions", [])
    ) or "<li>No compressed sessions available. Raw sessions are optional and local-only.</li>"
    warnings_rows = "".join(f"<li>{escape(item)}</li>" for item in warnings) or "<li>No warnings.</li>"
    blockers_rows = "".join(f"<li>{escape(item)}</li>" for item in blockers) or "<li>No blockers.</li>"
    graph_json = json.dumps(graph, sort_keys=True)
    session_json = json.dumps(sessions, sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>v2.0 Read-only Governance Dashboard</title>
<style>
:root {{ color-scheme: light; --bg:#f6f8fb; --card:#ffffff; --ink:#172033; --muted:#5d6b82; --ok:#18794e; --warn:#a15c00; --line:#d8dee9; --accent:#315efb; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background:var(--bg); color:var(--ink); }}
header {{ padding:32px; background:linear-gradient(135deg,#18223a,#315efb); color:white; }}
header p {{ max-width:900px; color:#dfe7ff; }}
main {{ padding:24px; display:grid; gap:20px; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; }}
.card, section {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px; box-shadow:0 8px 20px rgba(23,32,51,.06); }}
.status-card strong {{ display:block; font-size:28px; margin-top:6px; }}
h2 {{ margin:0 0 12px; }}
h3 {{ margin-bottom:8px; }}
ul {{ padding-left:20px; }}
code {{ background:#eef2ff; border-radius:6px; padding:2px 5px; }}
.badge {{ display:inline-block; border-radius:999px; padding:4px 9px; margin:2px; background:#eef2ff; color:#274ac7; font-weight:600; font-size:12px; }}
.ok {{ color:var(--ok); }} .warn {{ color:var(--warn); }}
.flow {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
.flow div {{ padding:10px 12px; border:1px solid var(--line); border-radius:12px; background:#fbfcff; }}
.matrix {{ width:100%; border-collapse:collapse; }}
.matrix td,.matrix th {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; }}
.small {{ color:var(--muted); font-size:13px; }}
</style>
</head>
<body>
<header>
  <h1>v2.0 Read-only Governance Dashboard</h1>
  <p>No external CDN, no npm, no server, no remote publication. This local filesystem dashboard visualizes governance state only; it does not execute destructive apply behavior or graph mutation.</p>
</header>
<main>
  <div class="grid">
    <div class="card status-card"><span>System Health</span><strong class="ok">{escape('PASS' if not blockers else 'BLOCKED')}</strong><p class="small">pipeline status from local graph export</p></div>
    <div class="card status-card"><span>Nodes</span><strong>{len(nodes)}</strong><p class="small">governance graph nodes</p></div>
    <div class="card status-card"><span>Edges</span><strong>{len(edges)}</strong><p class="small">logic/provenance links</p></div>
    <div class="card status-card"><span>Safety</span><strong class="ok">READ ONLY</strong><p class="small">destructive operations and graph mutation disabled</p></div>
  </div>

  <section><h2>Governance Graph</h2><p>Local data: <code>artifacts/v2/graph/governance-graph.json</code></p><div class="grid"><div><h3>Nodes</h3><ul>{node_rows}</ul></div><div><h3>Edges</h3><ul>{edge_rows}</ul></div></div></section>

  <section><h2>Logic Flow</h2><div class="flow"><div>v1 local checks</div><span>→</span><div>v1.1 proposal checks</div><span>→</span><div>session compression</div><span>→</span><div>graph export</div><span>→</span><div>dashboard build</div></div></section>

  <section><h2>Tools and Knowledge</h2><table class="matrix"><tr><th>Tools</th><th>Knowledge</th><th>Boundary</th></tr><tr><td>python module CLI</td><td>docs/plans, policies, artifacts, compressed sessions</td><td>read-only visualization; no external API</td></tr><tr><td>pytest validation</td><td>provenance current-state and release audit</td><td>local artifacts only</td></tr></table><p><span class="badge">Tools</span><span class="badge">Knowledge</span><span class="badge">Provenance</span></p></section>

  <section><h2>Sessions</h2><p>Local data: <code>artifacts/v2/sessions/session-index.json</code>. Raw transcripts stay under ignored local directories.</p><ul>{session_rows}</ul></section>

  <section><h2>Artifacts</h2><ul>{artifact_rows}</ul></section>

  <section><h2>Safety Boundary</h2><ul><li>Dashboard/UI is read-only.</li><li>destructive operations allowed: <strong>false</strong></li><li>graph mutation allowed: <strong>false</strong></li><li>sensitive export allowed: <strong>false</strong></li><li>raw sessions are local-only and ignored by git.</li><li>No raw archive apply execution.</li></ul></section>

  <section><h2>Warnings and Blockers</h2><div class="grid"><div><h3>Warnings</h3><ul>{warnings_rows}</ul></div><div><h3>Blockers</h3><ul>{blockers_rows}</ul></div></div></section>
</main>
<script type="application/json" id="governance-graph-data">{escape(graph_json)}</script>
<script type="application/json" id="session-index-data">{escape(session_json)}</script>
<script>
  const graphData = JSON.parse(document.getElementById('governance-graph-data').textContent);
  const sessionData = JSON.parse(document.getElementById('session-index-data').textContent);
  console.log('read-only governance dashboard loaded', {{nodes: graphData.nodes.length, sessions: sessionData.sessions.length}});
</script>
</body>
</html>
"""


def build_dashboard(repo_root: Path | str, out_path: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    graph_path = repo_root / "artifacts" / "v2" / "graph" / "governance-graph.json"
    if not graph_path.exists():
        write_governance_graph(repo_root, graph_path)
    session_path = ensure_session_index(repo_root)
    graph = _load_json(graph_path)
    sessions = _load_json(session_path)
    out = Path(out_path) if out_path else repo_root / "artifacts" / "v2" / "dashboard" / "index.html"
    if not out.is_absolute():
        out = repo_root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(graph, sessions, _artifact_inventory(repo_root)), encoding="utf-8")
    return {
        "status": "PASS",
        "path": _rel(repo_root, out),
        "graph_path": _rel(repo_root, graph_path),
        "session_index_path": _rel(repo_root, session_path),
        "read_only_ui": True,
        "external_dependencies": False,
    }
