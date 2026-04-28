from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph_export import write_governance_graph
from .sessions import ensure_session_index

PREVIEW_MAX_CHARS = 5000
INVENTORY_ROOTS = {
    "artifacts": ["artifacts/v1", "artifacts/v1.1", "artifacts/v2"],
    "sessions": ["artifacts/v2/sessions"],
    "proposals": ["artifacts/v1.1/proposals"],
    "policies": ["policies"],
    "provenance": ["artifacts/v1/provenance", "artifacts/v1.1/provenance"],
    "system": ["README.md", "pyproject.toml", ".gitignore"],
}


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


def _safe_json_for_script(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")


def classify_artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "JSON"
    if suffix in {".jsonl", ".log", ".trace"}:
        return "LOG"
    if suffix in {".md", ".markdown", ".yaml", ".yml", ".toml"}:
        return "Markdown"
    if suffix in {".html", ".htm"}:
        return "HTML"
    if suffix == ".txt":
        return "Text"
    return suffix.lstrip(".").upper() or "File"


def render_preview(text: str, max_chars: int = PREVIEW_MAX_CHARS) -> tuple[str, bool]:
    normalized = text.replace("\r\n", "\n")
    if len(normalized) <= max_chars:
        return normalized, False
    return normalized[:max_chars].rstrip() + "… [truncated]", True


def _read_preview(path: Path) -> tuple[str, str, bool]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    file_type = classify_artifact_type(path)
    if file_type == "JSON":
        try:
            raw = json.dumps(json.loads(raw), indent=2, sort_keys=True, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    preview, truncated = render_preview(raw)
    return preview, file_type, truncated


def _level_for_path(path: Path) -> str:
    lower = path.as_posix().lower()
    if "block" in lower or "fail" in lower:
        return "WARN"
    if lower.endswith((".log", ".jsonl")):
        return "INFO"
    if "policy" in lower or "gate" in lower:
        return "READ_ONLY"
    return "INFO"


def build_lineage_for_artifact(rel_path: str, graph: dict[str, Any] | None = None) -> list[dict[str, str]]:
    lineage: list[dict[str, str]] = []
    graph = graph or {}
    candidate_ids = {f"artifact:{rel_path}", rel_path}
    for node in graph.get("nodes", []):
        if node.get("path") == rel_path:
            candidate_ids.add(node.get("id", ""))
    for edge in graph.get("edges", []):
        if edge.get("source") in candidate_ids or edge.get("target") in candidate_ids:
            lineage.append(
                {
                    "edge_id": edge.get("id", ""),
                    "source": edge.get("source", ""),
                    "relation": edge.get("relation") or edge.get("type", ""),
                    "target": edge.get("target", ""),
                }
            )
    if not lineage and rel_path.startswith("artifacts/"):
        lineage.append({"edge_id": "local-artifact", "source": "local filesystem", "relation": "contains", "target": rel_path})
    return lineage[:12]


def collect_file_inventory(repo_root: Path | str, graph: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    repo_root = Path(repo_root).resolve()
    warnings: list[str] = []
    files: dict[str, dict[str, Any]] = {}
    for group, roots in INVENTORY_ROOTS.items():
        for root in roots:
            path = repo_root / root
            if not path.exists():
                warnings.append(f"missing optional local directory or file: {root}")
                continue
            paths = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
            for item in paths:
                rel = _rel(repo_root, item)
                if rel in files:
                    files[rel]["groups"].append(group)
                    continue
                stat = item.stat()
                preview, file_type, truncated = _read_preview(item)
                files[rel] = {
                    "path": rel,
                    "name": item.name,
                    "group": group,
                    "groups": [group],
                    "type": file_type,
                    "size": stat.st_size,
                    "size_label": _size_label(stat.st_size),
                    "modified_epoch": int(stat.st_mtime),
                    "modified": _iso_from_epoch(stat.st_mtime),
                    "level": _level_for_path(item),
                    "source": "local_generated_artifact" if rel.startswith("artifacts/") else "repository_file",
                    "preview": preview,
                    "preview_truncated": truncated,
                    "lineage": build_lineage_for_artifact(rel, graph),
                }
    return sorted(files.values(), key=lambda item: (item["group"], item["path"])), sorted(set(warnings))


def _iso_from_epoch(value: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, timezone.utc).replace(microsecond=0).isoformat()


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def build_dashboard_data(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    graph_path = repo_root / "artifacts" / "v2" / "graph" / "governance-graph.json"
    write_governance_graph(repo_root, graph_path)
    session_path = ensure_session_index(repo_root)
    graph = _load_json(graph_path)
    sessions = _load_json(session_path)
    pipeline = _load_json(repo_root / "artifacts" / "v2" / "pipeline-run.json")
    inventory, inventory_warnings = collect_file_inventory(repo_root, graph)
    safety = {
        "read_only_ui": True,
        "destructive_operations_allowed": False,
        "graph_mutation_allowed": False,
        "remote_publication_allowed": False,
        "sensitive_export_allowed": False,
    }
    return {
        "schema_version": "2.0",
        "app": {"name": "Governance Hub", "version": "v2.0", "default_route": "#/graph"},
        "graph": graph,
        "sessions": sessions,
        "pipeline_status": pipeline or {"status": "PASS", **safety},
        "artifact_inventory": [item["path"] for item in inventory if item["path"].startswith("artifacts/")],
        "file_inventory": inventory,
        "inventory_warnings": inventory_warnings,
        "graph_filter_types": sorted({node.get("type", "unknown") for node in graph.get("nodes", [])}),
        "log_groups": list(INVENTORY_ROOTS.keys()),
        "safety_boundary": safety,
    }


def _html(data: dict[str, Any]) -> str:
    graph = data.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    status = "BLOCKED" if graph.get("blockers") else "PASS"
    payload = _safe_json_for_script(data)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Governance Hub v2.0</title>
<style>
:root {{ --bg:#f7f8fc; --panel:#fff; --ink:#172033; --muted:#667085; --line:#e7eaf1; --accent:#6657f6; --accent-soft:#f1efff; --ok:#15803d; --warn:#b45309; --blue:#2f6fed; --green:#16a34a; --purple:#7c3aed; --red:#dc2626; --amber:#d97706; --teal:#0891b2; --indigo:#4f46e5; --rose:#e11d48; --slate:#475569; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); overflow:hidden; }}
button,input {{ font:inherit; }}
.topbar {{ height:68px; display:flex; align-items:center; justify-content:space-between; padding:0 22px; background:var(--panel); border-bottom:1px solid var(--line); }}
body.dark {{ --bg:#0f172a; --panel:#111827; --ink:#e5e7eb; --muted:#9ca3af; --line:#263244; --accent-soft:#252044; }}
body.dark .btn, body.dark .status-card, body.dark .graph-workspace, body.dark .logs-layout, body.dark .sidebar, body.dark .topbar {{ background:var(--panel); color:var(--ink); }}
.brand {{ display:flex; align-items:center; gap:10px; font-weight:750; }} .logo {{ width:32px; height:32px; display:grid; place-items:center; border-radius:10px; color:white; background:linear-gradient(135deg,#6557f6,#22c7d8); }}
.badge {{ border-radius:999px; background:var(--accent-soft); color:var(--accent); padding:4px 9px; font-size:12px; font-weight:700; }}
.top-actions {{ display:flex; align-items:center; gap:10px; }} .btn {{ border:1px solid var(--line); background:#fff; border-radius:10px; padding:8px 12px; color:#344054; text-decoration:none; cursor:pointer; }} .btn.primary {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.avatar {{ width:30px; height:30px; border-radius:50%; background:#101828; color:#fff; display:grid; place-items:center; font-weight:700; }}
.shell {{ display:grid; grid-template-columns:86px 1fr; height:calc(100vh - 68px); }}
.sidebar {{ background:#fff; border-right:1px solid var(--line); padding:14px 10px; display:flex; flex-direction:column; gap:8px; }}
.nav-item {{ text-align:center; text-decoration:none; color:#667085; padding:10px 4px; border-radius:14px; font-size:12px; }} .nav-item span {{ display:block; font-size:20px; line-height:1.1; }} .nav-item.active {{ background:var(--accent-soft); color:var(--accent); font-weight:750; }}
.route {{ display:none; height:100%; overflow:hidden; }} .route.active {{ display:block; }}
.content {{ padding:20px; height:100%; overflow:hidden; }}
.page-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px; margin-bottom:14px; }} h1 {{ margin:0; font-size:28px; letter-spacing:-.03em; }} .subtitle {{ color:var(--muted); margin-top:5px; }}
.health-row {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }} .status-card {{ min-width:120px; border:1px solid var(--line); background:#fff; border-radius:14px; padding:10px 12px; box-shadow:0 4px 14px rgba(16,24,40,.04); }} .status-card small {{ color:var(--muted); display:block; }} .status-card strong {{ display:block; font-size:17px; margin-top:2px; }} .ok {{ color:var(--ok); }} .warn {{ color:var(--warn); }}
.graph-workspace {{ height:calc(100% - 86px); display:grid; grid-template-columns:1fr 340px; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; box-shadow:0 16px 40px rgba(16,24,40,.06); }}
.graph-main {{ display:grid; grid-template-rows:auto auto 1fr auto; min-width:0; }} .toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:14px; border-bottom:1px solid var(--line); }} .toolbar-left,.legend {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
.search {{ border:1px solid var(--line); border-radius:10px; padding:9px 12px; min-width:230px; }} .legend-item {{ color:#475467; font-size:12px; }} .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }}
.type-filter-panel {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:10px 14px; border-bottom:1px solid var(--line); background:#fbfcff; }} .filter-chip {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:5px 9px; font-size:12px; cursor:pointer; }} .filter-chip.active {{ background:var(--accent-soft); color:var(--accent); border-color:var(--accent); }} .count-pill {{ color:var(--muted); font-size:12px; margin-left:auto; }}
.graph-canvas-wrap {{ position:relative; overflow:hidden; background-image:radial-gradient(#e8ecf4 1px, transparent 1px); background-size:22px 22px; }}
#graph-canvas {{ width:100%; height:100%; display:block; cursor:grab; }} .edge-line {{ stroke:#a8b2c7; stroke-width:1.8; fill:none; cursor:pointer; }} .edge-line:hover {{ stroke:var(--accent); stroke-width:2.6; }} .edge-label {{ font-size:10px; fill:#667085; pointer-events:none; }} .node-card rect {{ stroke-width:1.4; rx:12; filter:drop-shadow(0 6px 10px rgba(16,24,40,.08)); }} .node-card text {{ font-size:12px; fill:#172033; pointer-events:none; }} .node-card {{ cursor:grab; }} .node-card.selected rect {{ stroke:#111827; stroke-width:2.3; }}
.float-controls {{ position:absolute; left:14px; top:72px; display:grid; gap:7px; }} .float-controls button {{ width:34px; height:34px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 8px 20px rgba(16,24,40,.08); cursor:pointer; }}
.minimap {{ position:absolute; left:14px; bottom:16px; width:150px; height:90px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.9); padding:8px; }} .mini-node {{ position:absolute; width:10px; height:7px; border-radius:4px; opacity:.75; }}
.graph-hint {{ padding:10px 14px; border-top:1px solid var(--line); color:#667085; font-size:13px; }}
.inspector {{ border-left:1px solid var(--line); background:#fbfcff; padding:16px; overflow:auto; }} .tabs {{ display:flex; gap:16px; border-bottom:1px solid var(--line); margin-bottom:14px; }} .tab {{ padding:0 0 9px; color:#667085; }} .tab.active {{ color:var(--accent); border-bottom:2px solid var(--accent); font-weight:750; }}
.kv {{ display:grid; gap:10px; }} .kv-row label {{ display:block; font-size:12px; color:#667085; margin-bottom:4px; }} .chip {{ display:inline-block; margin:2px 4px 2px 0; padding:4px 7px; border-radius:999px; background:#eef2ff; color:#344054; font-size:12px; }} .logs-link {{ display:block; margin-top:16px; text-align:center; }}
.logs-layout {{ display:grid; grid-template-columns:290px 1fr 370px; height:calc(100% - 72px); border:1px solid var(--line); border-radius:18px; background:#fff; overflow:hidden; box-shadow:0 16px 40px rgba(16,24,40,.06); }}
.explorer,.preview-panel {{ min-width:0; overflow:auto; }} .file-table {{ min-width:0; overflow:hidden; border-right:1px solid var(--line); display:grid; grid-template-rows:auto 1fr; }} .explorer {{ border-right:1px solid var(--line); padding:16px; }} .pane-head {{ display:flex; justify-content:space-between; align-items:center; gap:8px; padding:15px 16px; border-bottom:1px solid var(--line); }} .file-table-scroll {{ overflow:auto; min-height:0; }} .file-table-scroll thead th {{ position:sticky; top:0; z-index:2; }}
.tree {{ list-style:none; padding-left:0; margin:10px 0; }} .tree ul {{ list-style:none; padding-left:18px; margin:4px 0; }} .tree li {{ padding:5px 7px; border-radius:9px; color:#344054; }} .tree li.active {{ background:var(--accent-soft); color:var(--accent); font-weight:700; }} .tree .folder-row {{ cursor:pointer; user-select:none; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ padding:11px 12px; border-bottom:1px solid #eff2f6; text-align:left; vertical-align:top; }} th {{ color:#667085; font-size:12px; font-weight:700; background:#fbfcff; }} tr.selected {{ background:#f6f3ff; }} .level-dot {{ width:8px; height:8px; display:inline-block; border-radius:50%; margin-right:6px; background:#22c55e; }} .level-WARN .level-dot {{ background:#f59e0b; }} .level-READ_ONLY .level-dot {{ background:#6657f6; }}
.preview-panel {{ padding:16px; }} .file-title {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }} .preview-tabs {{ display:flex; gap:18px; margin:14px 0; border-bottom:1px solid var(--line); }} .preview-tabs button {{ background:transparent; border:0; padding:0 0 10px; color:#667085; cursor:pointer; }} .preview-tabs button.active {{ color:var(--accent); border-bottom:2px solid var(--accent); font-weight:750; }}
pre {{ margin:0; white-space:pre-wrap; overflow:auto; max-height:42vh; background:#fbfcff; border:1px solid var(--line); border-radius:14px; padding:13px; font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }} .lineage-flow {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px; }} .lineage-node {{ border:1px solid var(--line); border-radius:12px; background:#f8fafc; padding:8px; font-size:12px; max-width:150px; }}
</style>
</head>
<body>
<header class="topbar"><div class="brand"><div class="logo">◆</div><span>Governance Hub</span><span class="badge">v2.0</span></div><div class="top-actions"><a class="btn" href="#/logs" id="top-logs-link">Logs</a><button class="btn" id="theme-toggle" aria-label="Theme toggle visual only">☼</button><div class="avatar">A</div><span>Admin</span></div></header>
<div class="shell"><aside class="sidebar"><a class="nav-item active" data-nav="graph" href="#/graph"><span>◎</span>Graph</a><a class="nav-item" data-nav="logs" href="#/logs"><span>▤</span>Logs</a></aside>
<main>
<section class="route active content" data-route="graph" id="graph-route"><div class="page-head"><div><h1>Governance Graph</h1><div class="subtitle">Interactive view of tools, knowledge, policies, artifacts, proposals, sessions, and provenance.</div></div><div class="health-row"><div class="status-card"><small>System Health</small><strong class="ok">{status}</strong></div><div class="status-card"><small>Nodes</small><strong>{len(nodes)}</strong></div><div class="status-card"><small>Edges</small><strong>{len(edges)}</strong></div><div class="status-card"><small>Safety</small><strong class="warn">READ ONLY</strong></div></div></div>
<div class="graph-workspace"><div class="graph-main"><div class="toolbar"><div class="toolbar-left"><input id="graph-search" class="search" placeholder="Search nodes"><button class="btn" id="fit-view">Fit view</button><button class="btn" id="clear-graph-filters">Clear filters</button><button class="btn">Layout</button></div><div class="legend" id="graph-legend"></div></div><div class="type-filter-panel" id="type-filter-panel"><span class="subtitle">Filters</span><span id="type-filter-chips"></span><span class="count-pill" id="visible-node-count">0 visible nodes</span></div><div class="graph-canvas-wrap" id="graph-wrap"><svg id="graph-canvas" role="img" aria-label="Governance Graph"><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#a8b2c7"></path></marker></defs><g id="viewport"><g id="edge-layer"></g><g id="node-layer"></g></g></svg><div class="float-controls"><button id="zoom-in">+</button><button id="zoom-out">−</button><button id="zoom-reset">⌂</button><button title="Read-only lock">🔒</button></div><div class="minimap" id="minimap"></div></div><div class="graph-hint">ⓘ Drag nodes to reposition · Click nodes or edges to inspect · Scroll to zoom · Double-click empty space to reset view</div></div><aside class="inspector"><div class="tabs"><div class="tab active">Node</div><div class="tab" id="edge-inspector">Edge</div></div><h2 id="node-inspector">Select a node or edge</h2><div class="kv" id="inspector-body"></div><a class="btn logs-link" href="#/logs" id="view-in-logs">View in Logs →</a></aside></div>
</section>
<section class="route content" data-route="logs" id="logs-route"><div class="page-head"><div><h1>Logs</h1><div class="subtitle">Browse and inspect raw local artifacts, metadata, and lineage. No actions execute from this page.</div></div><div class="top-actions"><a class="btn primary" href="#/graph">Graph</a><span class="badge">READ ONLY</span></div></div><div class="logs-layout"><aside class="explorer"><div class="pane-head"><strong>File Explorer</strong><span class="badge" id="explorer-count">0 items</span></div><ul class="tree" id="file-tree"></ul></aside><section class="file-table"><div class="pane-head"><div><strong id="folder-title">artifacts/</strong> <span class="badge" id="table-count">0 items</span></div><div><input id="file-search" class="search" placeholder="Search files and folders"><button class="btn">All types</button><button class="btn">Level / All</button></div></div><div class="file-table-scroll"><table><thead><tr><th>Name</th><th>Type</th><th>Size</th><th>Modified</th><th>Level/Status</th></tr></thead><tbody id="file-rows"></tbody></table></div></section><aside class="preview-panel"><div class="file-title"><div><h2 id="preview-title">Select a file</h2><div class="subtitle" id="preview-subtitle">Preview, Raw, Metadata, and Lineage</div></div><button class="btn" id="copy-path">Copy path</button></div><div class="preview-tabs"><button class="active" data-preview-tab="preview">Preview</button><button data-preview-tab="raw">Raw</button><button data-preview-tab="metadata">Metadata</button><button data-preview-tab="lineage">Lineage</button></div><pre id="preview-code">No file selected.</pre><section><h3>Lineage</h3><div class="lineage-flow" id="lineage-flow"></div></section></aside></div></section>
</main></div>
<script id="governance-data" type="application/json">{payload}</script>
<script>
const DATA = JSON.parse(document.getElementById('governance-data').textContent);
const colorMap = {{tool:['#dbeafe','#2f6fed'], knowledge_source:['#dcfce7','#16a34a'], session:['#ede9fe','#7c3aed'], policy:['#fee2e2','#dc2626'], gate:['#fee2e2','#dc2626'], artifact:['#fef3c7','#d97706'], report:['#fef3c7','#d97706'], proposal:['#cffafe','#0891b2'], provenance_state:['#e0e7ff','#4f46e5'], decision:['#ffe4e6','#e11d48'], requirement:['#f1f5f9','#475569'], pipeline_run:['#f8fafc','#475569'], adapter:['#dbeafe','#2f6fed'], test_result:['#dcfce7','#16a34a'], release_audit:['#fef3c7','#d97706']}};
let panZoomState = {{x: 20, y: 20, scale: 1}};
let positions = {{}};
let selectedFile = null;
let activeGraphTypes = new Set(DATA.graph_filter_types || []);
let activeLogGroup = 'artifacts';
let currentFileRows = [];
function route() {{ const name = (location.hash || '#/graph').replace('#/',''); document.querySelectorAll('.route').forEach(r => r.classList.toggle('active', r.dataset.route === name)); document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.nav === name)); }}
window.addEventListener('hashchange', route); route(); if (!location.hash) location.hash = '#/graph';
function initPositions() {{ const cols = Math.max(6, Math.ceil(Math.sqrt(DATA.graph.nodes.length))); DATA.graph.nodes.forEach((n,i) => positions[n.id] = positions[n.id] || {{x:70+(i%cols)*185, y:70+Math.floor(i/cols)*100}}); }}
function applyZoom() {{ document.getElementById('viewport').setAttribute('transform', `translate(${{panZoomState.x}} ${{panZoomState.y}}) scale(${{panZoomState.scale}})`); }}
function visibleNodes() {{ const q=(document.getElementById('graph-search').value||'').toLowerCase(); return DATA.graph.nodes.filter(n => activeGraphTypes.has(n.type) && (!q || [n.id,n.label,n.type,n.description,n.summary,(n.tags||[]).join(' ')].join(' ').toLowerCase().includes(q))); }}
function visibleNodeIds() {{ return new Set(visibleNodes().map(n => n.id)); }}
function visibleEdges() {{ const ids=visibleNodeIds(); return DATA.graph.edges.filter(e => ids.has(e.source) && ids.has(e.target)); }}
function renderLegend() {{ const types = DATA.graph_filter_types || []; document.getElementById('graph-legend').innerHTML = types.slice(0,9).map(t => `<span class="legend-item"><i class="dot" style="background:${{(colorMap[t]||colorMap.requirement)[1]}}"></i>${{t.replace('_',' ')}}</span>`).join(''); }}
function renderTypeFilters() {{ const types = DATA.graph_filter_types || []; document.getElementById('type-filter-chips').innerHTML = types.map(t => `<button class="filter-chip ${{activeGraphTypes.has(t) ? 'active' : ''}}" data-type="${{t}}">${{t.replace('_',' ')}}</button>`).join(''); document.querySelectorAll('[data-type]').forEach(btn => btn.onclick = () => filterNodesByType(btn.dataset.type)); updateVisibleNodeCount(); }}
function filterNodesByType(type) {{ if (activeGraphTypes.has(type) && activeGraphTypes.size > 1) activeGraphTypes.delete(type); else activeGraphTypes.add(type); renderTypeFilters(); renderGraph(); }}
function clearGraphFilters() {{ activeGraphTypes = new Set(DATA.graph_filter_types || []); document.getElementById('graph-search').value=''; renderTypeFilters(); renderGraph(); }}
function updateVisibleNodeCount() {{ document.getElementById('visible-node-count').textContent = `${{visibleNodes().length}} visible nodes · ${{visibleEdges().length}} visible edges`; }}
function renderGraph() {{ initPositions(); const edgeLayer = document.getElementById('edge-layer'); const nodeLayer = document.getElementById('node-layer'); edgeLayer.innerHTML=''; nodeLayer.innerHTML=''; const nodeList=visibleNodes(); const edgeList=visibleEdges(); const ids=new Set(nodeList.map(n=>n.id)); edgeList.forEach(e => {{ const s=positions[e.source], t=positions[e.target]; if(!s||!t) return; const midx=(s.x+t.x)/2, midy=(s.y+t.y)/2-18; const path=document.createElementNS('http://www.w3.org/2000/svg','path'); path.setAttribute('class','edge-line'); path.setAttribute('d',`M ${{s.x+70}} ${{s.y+20}} Q ${{midx}} ${{midy}} ${{t.x+70}} ${{t.y+20}}`); path.setAttribute('marker-end','url(#arrow)'); path.addEventListener('click', ev => {{ ev.stopPropagation(); selectEdge(e); }}); edgeLayer.appendChild(path); const label=document.createElementNS('http://www.w3.org/2000/svg','text'); label.setAttribute('class','edge-label'); label.setAttribute('x',midx); label.setAttribute('y',midy); label.textContent=e.relation || e.type; edgeLayer.appendChild(label); }}); nodeList.forEach(n => {{ const p=positions[n.id]; const colors=colorMap[n.type] || colorMap.requirement; const g=document.createElementNS('http://www.w3.org/2000/svg','g'); g.setAttribute('class','node-card'); g.setAttribute('transform',`translate(${{p.x}} ${{p.y}})`); g.dataset.id=n.id; g.innerHTML=`<rect width="150" height="44" fill="${{colors[0]}}" stroke="${{colors[1]}}"></rect><text x="12" y="18">${{escapeSvg(n.label || n.id).slice(0,22)}}</text><text x="12" y="34" fill="#667085">${{escapeSvg(n.type)}}</text>`; g.addEventListener('mousedown', ev => startNodeDrag(ev,n.id)); g.addEventListener('click', ev => {{ ev.stopPropagation(); selectNode(n); }}); nodeLayer.appendChild(g); }}); updateVisibleNodeCount(); applyZoom(); renderMinimap(ids); }}
function escapeSvg(s) {{ return String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])); }}
function startNodeDrag(ev,id) {{ ev.preventDefault(); const start={{x:ev.clientX,y:ev.clientY,px:positions[id].x,py:positions[id].y}}; function move(e){{positions[id].x=start.px+(e.clientX-start.x)/panZoomState.scale; positions[id].y=start.py+(e.clientY-start.y)/panZoomState.scale; renderGraph();}} function up(){{window.removeEventListener('mousemove',move); window.removeEventListener('mouseup',up);}} window.addEventListener('mousemove',move); window.addEventListener('mouseup',up); }}
function selectNode(n) {{ document.querySelectorAll('.node-card').forEach(el => el.classList.toggle('selected', el.dataset.id===n.id)); document.getElementById('node-inspector').textContent=n.label || n.id; document.getElementById('inspector-body').innerHTML = kv({{ID:n.id, Type:n.type, Status:n.status, Description:n.description || n.summary || '', Tags:(n.tags||[]).join(', '), Path:(n.path || (n.metadata||{{}}).path || '')}}); }}
function selectEdge(e) {{ document.getElementById('node-inspector').textContent=e.label || e.type; document.getElementById('inspector-body').innerHTML = kv({{ID:e.id, Type:'edge', Relation:e.relation || e.type, Source:e.source, Target:e.target, Status:e.status || 'active', Metadata: JSON.stringify(e.metadata || {{}})}}); }}
function kv(obj) {{ return Object.entries(obj).map(([k,v]) => `<div class="kv-row"><label>${{k}}</label><span class="chip">${{String(v || '—')}}</span></div>`).join(''); }}
document.getElementById('graph-canvas').addEventListener('wheel', ev => {{ ev.preventDefault(); panZoomState.scale=Math.max(.35, Math.min(2.5, panZoomState.scale + (ev.deltaY < 0 ? .08 : -.08))); applyZoom(); }});
document.getElementById('zoom-in').onclick=()=>{{panZoomState.scale+=.15; applyZoom();}}; document.getElementById('zoom-out').onclick=()=>{{panZoomState.scale=Math.max(.35,panZoomState.scale-.15); applyZoom();}}; document.getElementById('zoom-reset').onclick=document.getElementById('fit-view').onclick=()=>{{panZoomState={{x:20,y:20,scale:1}}; applyZoom();}};
document.getElementById('graph-search').addEventListener('input', renderGraph); document.getElementById('clear-graph-filters').onclick=clearGraphFilters;
function renderMinimap(ids) {{ const mini=document.getElementById('minimap'); mini.innerHTML=''; Object.entries(positions).filter(([id]) => !ids || ids.has(id)).slice(0,80).forEach(([id,p]) => {{ const node=DATA.graph.nodes.find(n=>n.id===id)||{{type:'requirement'}}; const d=document.createElement('i'); d.className='mini-node'; d.style.left=(8+(p.x%120))+'px'; d.style.top=(10+(p.y%60))+'px'; d.style.background=(colorMap[node.type]||colorMap.requirement)[1]; mini.appendChild(d); }}); }}
function selectLogGroup(group) {{ activeLogGroup = group; selectedFile = null; document.querySelectorAll('[data-log-group]').forEach(el => el.classList.toggle('active', el.dataset.logGroup === group)); document.getElementById('folder-title').textContent = group + '/'; renderFiles(); }}
function renderTree() {{ const groups=DATA.log_groups || ['artifacts','sessions','proposals','policies','provenance','system']; const inv=DATA.file_inventory; document.getElementById('explorer-count').textContent=inv.length+' items'; document.getElementById('file-tree').innerHTML=groups.map(g=>{{ const items=inv.filter(i=>i.group===g || (i.groups||[]).includes(g)); return `<li data-log-group="${{g}}" class="${{g===activeLogGroup?'active':''}}"><div class="folder-row">▾ 📁 ${{g}}/ <span class="badge">${{items.length}}</span></div><ul>${{items.slice(0,10).map(i=>`<li data-file-path="${{i.path}}">◇ ${{i.name}}</li>`).join('')}}</ul></li>`; }}).join(''); document.querySelectorAll('[data-log-group] > .folder-row').forEach(row => row.onclick = () => selectLogGroup(row.parentElement.dataset.logGroup)); document.querySelectorAll('[data-file-path]').forEach(row => row.onclick = (ev) => {{ ev.stopPropagation(); selectFile(row.dataset.filePath); }}); }}
function renderFiles() {{ const q=(document.getElementById('file-search').value||'').toLowerCase(); currentFileRows=DATA.file_inventory.filter(i=>(i.group===activeLogGroup || (i.groups||[]).includes(activeLogGroup)) && (!q || i.path.toLowerCase().includes(q))); document.getElementById('table-count').textContent=currentFileRows.length+' items'; document.getElementById('file-rows').innerHTML=currentFileRows.map((f,i)=>`<tr class="${{i===0?'selected':''}} level-${{f.level}}" data-path="${{f.path}}"><td>▧ ${{f.name}}</td><td>${{f.type}}</td><td>${{f.size_label}}</td><td>${{f.modified}}</td><td><span class="level-dot"></span>${{f.level}}</td></tr>`).join(''); document.querySelectorAll('#file-rows tr').forEach(row => row.onclick=()=>selectFile(row.dataset.path)); if(currentFileRows[0] && !selectedFile) selectFile(currentFileRows[0].path); }}
function selectFile(path) {{ selectedFile=DATA.file_inventory.find(f=>f.path===path); if(!selectedFile) return; document.querySelectorAll('#file-rows tr').forEach(r=>r.classList.toggle('selected', r.dataset.path===path)); document.getElementById('preview-title').textContent=selectedFile.name; document.getElementById('preview-subtitle').textContent=`${{selectedFile.type}} • ${{selectedFile.size_label}}`; showPreviewTab('preview'); renderLineage(); }}
function showPreviewTab(tab) {{ if(!selectedFile) return; document.querySelectorAll('[data-preview-tab]').forEach(b=>b.classList.toggle('active', b.dataset.previewTab===tab)); let text=selectedFile.preview; if(tab==='raw') text=selectedFile.preview + (selectedFile.preview_truncated ? '\\n\\n[local preview truncated]' : ''); if(tab==='metadata') text=JSON.stringify({{path:selectedFile.path,type:selectedFile.type,size:selectedFile.size,modified:selectedFile.modified,source:selectedFile.source,level:selectedFile.level,groups:selectedFile.groups}}, null, 2); if(tab==='lineage') text=JSON.stringify(selectedFile.lineage, null, 2); document.getElementById('preview-code').textContent=text; }}
document.querySelectorAll('[data-preview-tab]').forEach(b=>b.onclick=()=>showPreviewTab(b.dataset.previewTab)); document.getElementById('file-search').addEventListener('input', renderFiles); document.getElementById('copy-path').onclick=()=>{{ if(selectedFile) navigator.clipboard && navigator.clipboard.writeText(selectedFile.path); }};
function toggleTheme() {{ document.body.classList.toggle('dark'); document.getElementById('theme-toggle').textContent = document.body.classList.contains('dark') ? '☾' : '☼'; }}
document.getElementById('theme-toggle').onclick=toggleTheme;
function renderLineage() {{ const flow=document.getElementById('lineage-flow'); const line=selectedFile.lineage || []; flow.innerHTML = line.length ? line.slice(0,4).map(l=>`<div class="lineage-node"><strong>${{l.source}}</strong><br><span>${{l.relation}} →</span><br>${{l.target}}</div>`).join('') : '<span class="subtitle">No lineage edges found.</span>'; }}
renderLegend(); renderTypeFilters(); renderGraph(); renderTree(); renderFiles(); selectNode(visibleNodes()[0] || DATA.graph.nodes[0] || {{id:'none',type:'unknown',label:'No graph nodes'}});
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
    data = build_dashboard_data(repo_root)
    out = Path(out_path) if out_path else repo_root / "artifacts" / "v2" / "dashboard" / "index.html"
    if not out.is_absolute():
        out = repo_root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(data), encoding="utf-8")
    return {
        "status": "PASS",
        "path": _rel(repo_root, out),
        "graph_path": _rel(repo_root, graph_path),
        "session_index_path": _rel(repo_root, session_path),
        "read_only_ui": True,
        "external_dependencies": False,
        "routes": ["#/graph", "#/logs"],
        "file_count": len(data["file_inventory"]),
        "warnings": data["inventory_warnings"],
    }
