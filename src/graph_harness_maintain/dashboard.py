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


def build_graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = {node.get("id", "") for node in nodes}
    node_type_counts: dict[str, int] = {}
    edge_type_counts: dict[str, int] = {}
    degree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    in_degree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    out_degree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    broken_edges: list[dict[str, Any]] = []

    for node in nodes:
        node_type = node.get("type", "unknown")
        node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
    for edge in edges:
        edge_type = edge.get("relation") or edge.get("type", "unknown")
        edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source not in node_ids or target not in node_ids:
            broken_edges.append(edge)
            continue
        degree[source] += 1
        degree[target] += 1
        out_degree[source] += 1
        in_degree[target] += 1
        adjacency[source].add(target)
        adjacency[target].add(source)

    visited: set[str] = set()
    component_sizes: list[int] = []
    for node_id in node_ids:
        if node_id in visited:
            continue
        stack = [node_id]
        visited.add(node_id)
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component_sizes.append(size)

    node_by_id = {node.get("id", ""): node for node in nodes}
    hubs = []
    for node_id, value in sorted(degree.items(), key=lambda item: (-item[1], item[0]))[:8]:
        node = node_by_id.get(node_id, {})
        hubs.append(
            {
                "id": node_id,
                "label": node.get("label") or node_id,
                "type": node.get("type", "unknown"),
                "degree": value,
                "in_degree": in_degree.get(node_id, 0),
                "out_degree": out_degree.get(node_id, 0),
            }
        )

    possible_directed = max(1, len(nodes) * max(1, len(nodes) - 1))
    density = round(len(edges) / possible_directed, 4)
    isolated = sorted(node_id for node_id, value in degree.items() if value == 0)
    diagnostics = []
    diagnostics.append(f"Graph has {len(nodes)} nodes and {len(edges)} edges; directed density={density}.")
    if hubs:
        diagnostics.append(f"Highest traversal hub: {hubs[0]['label']} ({hubs[0]['degree']} incident edges).")
    if broken_edges:
        diagnostics.append(f"{len(broken_edges)} broken edge endpoint(s) need schema/export review.")
    else:
        diagnostics.append("No broken edge endpoints detected in the exported projection.")
    if isolated:
        diagnostics.append(f"{len(isolated)} isolated node(s) may need provenance or dependency edges.")
    if component_sizes:
        diagnostics.append(f"Connected components={len(component_sizes)}; largest component covers {max(component_sizes)} nodes.")

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "density": density,
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "hubs": hubs,
        "isolated_node_ids": isolated[:20],
        "isolated_count": len(isolated),
        "broken_edge_count": len(broken_edges),
        "component_count": len(component_sizes),
        "largest_component_size": max(component_sizes) if component_sizes else 0,
        "diagnostics": diagnostics,
    }


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
    graph_summary = build_graph_summary(graph)
    return {
        "schema_version": "2.0",
        "app": {"name": "Governance Hub", "version": "v2.0", "default_route": "#/graph"},
        "graph": graph,
        "graph_summary": graph_summary,
        "sessions": sessions,
        "pipeline_status": pipeline or {"status": "PASS", **safety},
        "artifact_inventory": [item["path"] for item in inventory if item["path"].startswith("artifacts/")],
        "file_inventory": inventory,
        "inventory_warnings": inventory_warnings,
        "graph_filter_types": sorted({node.get("type", "unknown") for node in graph.get("nodes", [])}),
        "edge_filter_types": sorted({edge.get("relation") or edge.get("type", "unknown") for edge in graph.get("edges", [])}),
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
html, body {{ height:100%; overflow:hidden; }}
body {{ margin:0; min-height:100vh; font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); overflow:hidden; }}
button,input {{ font:inherit; }}
.topbar {{ height:64px; display:flex; align-items:center; justify-content:space-between; padding:0 22px; background:var(--panel); border-bottom:1px solid var(--line); }}
.sr-only {{ position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }}
body.dark {{ --bg:#0f172a; --panel:#111827; --ink:#e5e7eb; --muted:#9ca3af; --line:#263244; --accent-soft:#252044; }}
body.dark .btn, body.dark .status-card, body.dark .graph-workspace, body.dark .logs-layout, body.dark .sidebar, body.dark .topbar {{ background:var(--panel); color:var(--ink); }}
.brand {{ display:flex; align-items:center; gap:10px; font-weight:750; }} .logo {{ width:32px; height:32px; display:grid; place-items:center; border-radius:10px; color:white; background:linear-gradient(135deg,#6557f6,#22c7d8); }}
.badge {{ border-radius:999px; background:var(--accent-soft); color:var(--accent); padding:4px 9px; font-size:12px; font-weight:700; }}
.top-actions {{ display:flex; align-items:center; gap:10px; }} .btn {{ border:1px solid var(--line); background:#fff; border-radius:10px; padding:8px 12px; color:#344054; text-decoration:none; cursor:pointer; }} .btn.primary {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.avatar {{ width:30px; height:30px; border-radius:50%; background:#101828; color:#fff; display:grid; place-items:center; font-weight:700; }}
.shell {{ display:grid; grid-template-columns:86px 1fr; height:calc(100vh - 64px); min-height:0; }} main {{ min-height:0; overflow:hidden; }}
.sidebar {{ background:#fff; border-right:1px solid var(--line); padding:14px 10px; display:flex; flex-direction:column; gap:8px; }}
.nav-item {{ text-align:center; text-decoration:none; color:#667085; padding:10px 4px; border-radius:14px; font-size:12px; }} .nav-item span {{ display:block; font-size:20px; line-height:1.1; }} .nav-item.active {{ background:var(--accent-soft); color:var(--accent); font-weight:750; }}
.route {{ display:none; height:100%; overflow:hidden; }} .route.active {{ display:block; }}
.content {{ padding:16px 18px; height:100%; overflow:hidden; min-height:0; }}
#logs-route.active {{ display:flex; flex-direction:column; height:100%; min-height:0; overflow:hidden; padding-bottom:0; }}
.page-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:10px; }} h1 {{ margin:0; font-size:26px; letter-spacing:-.03em; }} .subtitle {{ color:var(--muted); margin-top:4px; }}
.health-row {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }} .status-card {{ min-width:108px; border:1px solid var(--line); background:#fff; border-radius:13px; padding:8px 10px; box-shadow:0 4px 14px rgba(16,24,40,.04); }} .status-card small {{ color:var(--muted); display:block; }} .status-card strong {{ display:block; font-size:17px; margin-top:2px; }} .ok {{ color:var(--ok); }} .warn {{ color:var(--warn); }}
.graph-workspace {{ height:calc(100% - 72px); min-height:0; display:grid; grid-template-columns:minmax(0,1fr) 300px; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; box-shadow:0 16px 40px rgba(16,24,40,.06); }}
.graph-main {{ display:grid; grid-template-rows:auto auto minmax(300px,1fr) auto; min-width:0; min-height:0; }} .toolbar {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; padding:8px 12px; border-bottom:1px solid var(--line); max-height:128px; overflow:auto; }} .toolbar-left,.legend,.mode-switch {{ display:flex; align-items:center; gap:7px; flex-wrap:wrap; }} .mode-switch {{ padding:6px 12px; border-bottom:1px solid var(--line); background:#fff; }} .mode-btn[aria-pressed="true"] {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.search {{ border:1px solid var(--line); border-radius:10px; padding:8px 11px; min-width:220px; }} .legend-item {{ color:#475467; font-size:12px; }} .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }}
.type-filter-panel {{ display:flex; align-items:center; gap:5px; flex-wrap:wrap; padding:6px 0 0; border-bottom:0; background:transparent; max-width:52vw; }} .filter-panel {{ max-width:58vw; }} .filter-panel summary {{ cursor:pointer; color:var(--accent); font-weight:750; }} .filter-chip {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:4px 8px; font-size:11px; cursor:pointer; }} .filter-chip.active {{ background:var(--accent-soft); color:var(--accent); border-color:var(--accent); }} .filter-chip.edge.active {{ background:#fff7ed; color:#c2410c; border-color:#fb923c; }} .count-pill {{ color:var(--muted); font-size:12px; margin-left:6px; white-space:nowrap; }}
.edge-filter-strip {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:7px 12px; border-bottom:1px solid var(--line); background:#fbfcff; max-height:78px; overflow:auto; }} .edge-filter-strip strong {{ font-size:12px; color:var(--muted); margin-right:2px; }}
.summary-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0 12px; }} .summary-card {{ border:1px solid var(--line); border-radius:12px; background:#fff; padding:9px; }} .summary-card small {{ color:var(--muted); display:block; }} .summary-card strong {{ font-size:18px; }} .diagnostic-list {{ margin:8px 0; padding-left:18px; color:#475467; font-size:13px; line-height:1.45; }} .hub-list {{ display:grid; gap:6px; margin-top:8px; }} .hub-row {{ border:1px solid var(--line); border-radius:10px; padding:7px; cursor:pointer; background:#fff; }} .hub-row:hover {{ background:#f8f7ff; }}
.graph-canvas-wrap {{ position:relative; overflow:hidden; min-height:0; background-image:radial-gradient(#e8ecf4 1px, transparent 1px); background-size:22px 22px; }}
#graph-canvas {{ width:100%; height:100%; display:block; cursor:grab; touch-action:none; }} #graph-canvas.panning {{ cursor:grabbing; }} .edge-control {{ cursor:pointer; pointer-events:all; }} .edge-control:focus .edge-line, .edge-control.selected .edge-line {{ stroke:var(--accent); stroke-width:3.2; opacity:1; }} .edge-hit {{ stroke:transparent; stroke-width:18; fill:none; cursor:pointer; pointer-events:stroke; }} .edge-line {{ stroke:#a8b2c7; stroke-width:2.2; fill:none; cursor:pointer; pointer-events:stroke; opacity:.72; }} .edge-line.edge-blocks {{ stroke:#dc2626; stroke-dasharray:5 4; }} .edge-line.edge-generated {{ stroke:#d97706; }} .edge-line.edge-references {{ stroke:#64748b; stroke-dasharray:2 5; }} .edge-line.edge-requires,.edge-line.edge-governed_by {{ stroke:#7c3aed; }} .edge-line.edge-summarized_into {{ stroke:#0891b2; }} .edge-line:hover, .edge-line.selected {{ stroke:var(--accent); stroke-width:3.2; opacity:1; }} .edge-label-bg {{ fill:#fff; stroke:#c7d2fe; stroke-width:1; filter:drop-shadow(0 2px 4px rgba(16,24,40,.12)); pointer-events:none; }} .edge-label {{ font-size:10px; fill:#40506c; font-weight:750; cursor:pointer; pointer-events:auto; }} .node-card rect {{ stroke-width:1.4; rx:12; filter:drop-shadow(0 6px 10px rgba(16,24,40,.08)); }} .node-card text {{ font-size:12px; fill:#172033; pointer-events:none; }} .node-card {{ cursor:pointer; }} .node-card.dimmed {{ opacity:.32; }} .node-card.selected rect {{ stroke:#111827; stroke-width:2.3; }}
.float-controls {{ position:absolute; left:14px; top:72px; display:grid; gap:7px; }} .float-controls button {{ width:34px; height:34px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 8px 20px rgba(16,24,40,.08); cursor:pointer; }}
.minimap {{ position:absolute; left:14px; bottom:16px; width:150px; height:90px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.9); padding:8px; }} .mini-node {{ position:absolute; width:10px; height:7px; border-radius:4px; opacity:.75; }}
.graph-hint {{ padding:10px 14px; border-top:1px solid var(--line); color:#667085; font-size:13px; }}
.inspector {{ border-left:1px solid var(--line); background:#fbfcff; padding:16px; overflow:auto; }} .tabs {{ display:flex; gap:16px; border-bottom:1px solid var(--line); margin-bottom:14px; }} .tab {{ padding:0 0 9px; color:#667085; }} .tab.active {{ color:var(--accent); border-bottom:2px solid var(--accent); font-weight:750; }}
.kv {{ display:grid; gap:10px; }} .logs-link.disabled {{ pointer-events:none; opacity:.55; cursor:not-allowed; background:#f8fafc; }} .kv-row label {{ display:block; font-size:12px; color:#667085; margin-bottom:4px; }} .chip {{ display:inline-block; margin:2px 4px 2px 0; padding:4px 7px; border-radius:999px; background:#eef2ff; color:#344054; font-size:12px; }} .logs-link {{ display:block; margin-top:16px; text-align:center; }}
.logs-scroll-hint {{ flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:10px; margin:0 0 8px; padding:7px 10px; border:1px solid #fed7aa; border-radius:12px; background:#fff7ed; color:#9a3412; font-size:12px; font-weight:700; }} .logs-layout {{ display:grid; grid-template-columns:280px minmax(380px,1fr) 440px; height:auto; flex:1 1 auto; min-height:0; border:1px solid var(--line); border-radius:18px; background:#fff; overflow:hidden; box-shadow:0 16px 40px rgba(16,24,40,.06); }}
.explorer,.preview-panel {{ min-width:0; min-height:0; overflow:auto; overscroll-behavior:contain; scrollbar-gutter:stable; }} .file-table {{ min-width:0; min-height:0; overflow:hidden; border-right:1px solid var(--line); display:grid; grid-template-rows:auto minmax(0,1fr); }} .explorer {{ border-right:1px solid var(--line); padding:16px; }} .pane-head {{ display:flex; justify-content:space-between; align-items:center; gap:8px; padding:15px 16px; border-bottom:1px solid var(--line); }} .scroll-actions {{ display:flex; gap:5px; flex-wrap:wrap; }} .scroll-btn {{ border:1px solid var(--line); background:#fff; border-radius:8px; padding:5px 8px; cursor:pointer; color:#475467; }} .file-table-scroll {{ overflow-y:scroll; overflow-x:auto; min-height:0; height:100%; overscroll-behavior:contain; scrollbar-gutter:stable; border-top:1px solid var(--line); }} .file-table-scroll thead th {{ position:sticky; top:0; z-index:2; box-shadow:0 1px 0 var(--line); }} .file-table-scroll table {{ min-width:760px; }} .file-table-scroll::-webkit-scrollbar, .explorer::-webkit-scrollbar, .preview-panel::-webkit-scrollbar, pre::-webkit-scrollbar {{ width:10px; height:10px; }} .file-table-scroll::-webkit-scrollbar-thumb, .explorer::-webkit-scrollbar-thumb, .preview-panel::-webkit-scrollbar-thumb, pre::-webkit-scrollbar-thumb {{ background:#cbd5e1; border-radius:999px; }}
.tree {{ list-style:none; padding-left:0; margin:10px 0; }} .tree ul {{ list-style:none; padding-left:18px; margin:4px 0; }} .tree li {{ padding:5px 7px; border-radius:9px; color:#344054; }} .tree li.active {{ background:var(--accent-soft); color:var(--accent); font-weight:700; }} .tree .folder-row {{ cursor:pointer; user-select:none; border-radius:10px; padding:6px 8px; transition:background .15s ease, color .15s ease; }} .tree .folder-row:hover, .tree [data-file-path]:hover {{ background:#eef2ff; color:var(--accent); cursor:pointer; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ padding:11px 12px; border-bottom:1px solid #eff2f6; text-align:left; vertical-align:top; }} th {{ color:#667085; font-size:12px; font-weight:700; background:#fbfcff; }} tr {{ cursor:pointer; }} tr:hover {{ background:#f8f7ff; }} tr.selected {{ background:#f6f3ff; }} .level-dot {{ width:8px; height:8px; display:inline-block; border-radius:50%; margin-right:6px; background:#22c55e; }} .level-WARN .level-dot {{ background:#f59e0b; }} .level-READ_ONLY .level-dot {{ background:#6657f6; }}
.preview-panel {{ padding:16px; }} .file-title {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }} .preview-tabs {{ display:flex; gap:18px; margin:14px 0; border-bottom:1px solid var(--line); }} .preview-tabs button {{ background:transparent; border:0; padding:0 0 10px; color:#667085; cursor:pointer; }} .preview-tabs button.active {{ color:var(--accent); border-bottom:2px solid var(--accent); font-weight:750; }}
pre {{ margin:0; white-space:pre-wrap; overflow:auto; max-height:52vh; background:#fbfcff; border:1px solid var(--line); border-radius:14px; padding:13px; font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace; }} .preview-toolbar {{ display:flex; gap:6px; justify-content:flex-end; margin:-4px 0 8px; }} .line-number {{ color:#94a3b8; user-select:none; margin-right:10px; }} .lineage-flow {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px; }} .lineage-node {{ border:1px solid var(--line); border-radius:12px; background:#f8fafc; padding:8px; font-size:12px; max-width:150px; }}
</style>
</head>
<body>
<span class="sr-only">Artifacts Safety Boundary</span>
<header class="topbar"><div class="brand"><div class="logo">◆</div><span>Governance Hub</span><span class="badge">v2.0</span></div><div class="top-actions"><a class="btn" href="#/logs" id="top-logs-link">Logs</a><button class="btn" id="theme-toggle" aria-label="Theme toggle visual only">☼</button><div class="avatar">A</div><span>Admin</span></div></header>
<div class="shell"><aside class="sidebar"><a class="nav-item active" data-nav="graph" href="#/graph"><span>◎</span>Graph</a><a class="nav-item" data-nav="logs" href="#/logs"><span>▤</span>Logs</a></aside>
<main>
<section class="route active content" data-route="graph" id="graph-route"><div class="page-head"><div><h1>Governance Graph</h1><div class="subtitle">Interactive view of tools, knowledge, policies, artifacts, proposals, sessions, and provenance.</div></div><div class="health-row"><div class="status-card"><small>System Health</small><strong class="ok">{status}</strong></div><div class="status-card"><small>Nodes</small><strong>{len(nodes)}</strong></div><div class="status-card"><small>Edges</small><strong>{len(edges)}</strong></div><div class="status-card"><small>Safety</small><strong class="warn">READ ONLY</strong></div></div></div>
<div class="graph-workspace"><div class="graph-main"><div class="toolbar"><div class="toolbar-left"><input id="graph-search" class="search" placeholder="Search visible graph"><button class="btn" id="fit-view">Fit view</button><button class="btn" id="focus-hubs">Focus hubs</button><details class="filter-panel" id="filter-panel"><summary>Filters</summary><div class="type-filter-panel" id="type-filter-panel"><span class="subtitle">Node filters</span><span id="type-filter-chips"></span></div><div class="type-filter-panel"><span class="subtitle">Edge filters</span><span id="edge-filter-chips"></span><button class="btn" id="clear-edge-filters">All edges</button><button class="btn" id="clear-graph-filters">Clear filters</button></div></details></div><div class="legend" id="graph-legend"></div><span class="count-pill" id="visible-node-count">0 visible nodes</span></div><div class="mode-switch" aria-label="Graph view mode"><button class="btn mode-btn" data-graph-mode="overview" aria-pressed="true">Overview</button><button class="btn mode-btn" data-graph-mode="focus" aria-pressed="false">Focus</button><button class="btn mode-btn" data-graph-mode="full" aria-pressed="false">Full graph</button><span class="subtitle" id="mode-help">Overview shows a curated graph; Full graph is debug mode.</span></div><div class="graph-canvas-wrap" id="graph-wrap"><svg id="graph-canvas" role="img" aria-label="Governance Graph"><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#a8b2c7"></path></marker></defs><g id="viewport"><g id="edge-layer"></g><g id="node-layer"></g></g></svg><div class="float-controls"><button id="zoom-in">+</button><button id="zoom-out">−</button><button id="zoom-reset">⌂</button><button title="Read-only lock">🔒</button></div><div class="minimap" id="minimap"></div></div><div class="graph-hint">ⓘ Drag nodes to reposition · Click nodes or edges to inspect · Edge filters reduce dense views · Scroll to zoom · Double-click empty space to reset view</div></div><aside class="inspector"><div class="tabs"><div class="tab active">Inspect</div><div class="tab" id="edge-inspector">Edge</div><div class="tab">Summary</div></div><h2 id="node-inspector">Graph diagnostic summary</h2><div class="kv" id="inspector-body"></div><a class="btn logs-link" href="#/logs" id="view-in-logs">View in Logs →</a></aside></div>
</section>
<section class="route content" data-route="logs" id="logs-route"><div class="page-head"><div><h1>Logs</h1><div class="subtitle">Browse and inspect raw local artifacts, metadata, and lineage. No actions execute from this page.</div></div><div class="top-actions"><a class="btn primary" href="#/graph">Graph</a><span class="badge">READ ONLY</span></div></div><div class="logs-scroll-hint"><span>Use the File Explorer, Table, and Preview scrollbars for lower content</span><span>No browser page scroll</span></div><div class="logs-layout"><aside class="explorer"><div class="pane-head"><strong>File Explorer</strong><span class="badge" id="explorer-count">0 items</span></div><ul class="tree" id="file-tree"></ul></aside><section class="file-table"><div class="pane-head"><div><strong id="folder-title">artifacts/</strong> <span class="badge" id="table-count">0 items</span></div><div><input id="file-search" class="search" placeholder="Search files and folders"><div class="scroll-actions"><button class="scroll-btn" id="table-scroll-up">↑ table</button><button class="scroll-btn" id="table-scroll-down">↓ table</button></div></div></div><div class="file-table-scroll" id="file-table-scroll"><table><thead><tr><th>Name / Path</th><th>Type</th><th>Size</th><th>Modified</th><th>Level/Status</th></tr></thead><tbody id="file-rows"></tbody></table></div></section><aside class="preview-panel" id="preview-panel"><div class="file-title"><div><h2 id="preview-title">Select a file</h2><div class="subtitle" id="preview-subtitle">Preview, Raw, Metadata, and Lineage</div></div><button class="btn" id="copy-path">Copy path</button></div><div class="preview-tabs"><button class="active" data-preview-tab="preview">Preview</button><button data-preview-tab="raw">Raw</button><button data-preview-tab="metadata">Metadata</button><button data-preview-tab="lineage">Lineage</button></div><div class="preview-toolbar"><button class="scroll-btn" id="preview-scroll-up">↑ preview</button><button class="scroll-btn" id="preview-scroll-down">↓ preview</button></div><pre id="preview-code">No file selected.</pre><section><h3>Lineage</h3><div class="lineage-flow" id="lineage-flow"></div></section></aside></div></section>
</main></div>
<script id="governance-data" type="application/json">{payload}</script>
<script>
const DATA = JSON.parse(document.getElementById('governance-data').textContent);
const colorMap = {{tool:['#dbeafe','#2f6fed'], knowledge_source:['#dcfce7','#16a34a'], session:['#ede9fe','#7c3aed'], policy:['#fee2e2','#dc2626'], gate:['#fee2e2','#dc2626'], artifact:['#fef3c7','#d97706'], report:['#fef3c7','#d97706'], proposal:['#cffafe','#0891b2'], provenance_state:['#e0e7ff','#4f46e5'], decision:['#ffe4e6','#e11d48'], requirement:['#f1f5f9','#475569'], pipeline_run:['#f8fafc','#475569'], adapter:['#dbeafe','#2f6fed'], test_result:['#dcfce7','#16a34a'], release_audit:['#fef3c7','#d97706']}};
let panZoomState = {{x: 20, y: 20, scale: 1}};
let positions = {{}};
let selectedFile = null;
let activeGraphTypes = new Set(DATA.graph_filter_types || []);
let activeEdgeTypes = new Set(DATA.edge_filter_types || []);
let activeLogGroup = 'artifacts';
let currentFileRows = [];
let isCanvasPanning = false;
let canvasPanStart = null;
let selectedGraphRef = null;
let activeGraphMode = 'overview';
let focusNodeId = null;
function route() {{ const name = (location.hash || '#/graph').replace('#/',''); document.querySelectorAll('.route').forEach(r => r.classList.toggle('active', r.dataset.route === name)); document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.nav === name)); }}
window.addEventListener('hashchange', route); route(); if (!location.hash) location.hash = '#/graph';
function initPositions() {{ const cols = Math.max(6, Math.ceil(Math.sqrt(DATA.graph.nodes.length))); DATA.graph.nodes.forEach((n,i) => positions[n.id] = positions[n.id] || {{x:70+(i%cols)*185, y:70+Math.floor(i/cols)*100}}); }}
function applyZoom() {{ document.getElementById('viewport').setAttribute('transform', `translate(${{panZoomState.x}} ${{panZoomState.y}}) scale(${{panZoomState.scale}})`); }}
function nodeSearchText(n) {{ return [n.id,n.label,n.type,n.description,n.summary,(n.tags||[]).join(' ')].join(' ').toLowerCase(); }}
function overviewNodeIds() {{ const priorityTypes=new Set(['session','knowledge_source','tool','proposal','policy','gate','artifact','report','provenance_state','pipeline_run','decision']); const priorityWords=/session|dashboard|pipeline|policy|gate|proposal|provenance|artifact|report|tool|storage-guard|safety|approval/i; const chosen=[]; const add=n=>{{ if(n && !chosen.includes(n.id)) chosen.push(n.id); }}; (DATA.graph_summary.hubs||[]).slice(0,6).forEach(h=>add(DATA.graph.nodes.find(n=>n.id===h.id))); DATA.graph.nodes.filter(n=>priorityTypes.has(n.type) && priorityWords.test(`${{n.id}} ${{n.label}} ${{n.path||''}}`)).forEach(add); DATA.graph.nodes.filter(n=>['tool','policy','gate','proposal','pipeline_run','provenance_state'].includes(n.type)).forEach(add); return new Set(chosen.slice(0,24)); }}
function focusNodeIds() {{ const base=focusNodeId || ((DATA.graph_summary.hubs||[])[0]||{{}}).id || (DATA.graph.nodes[0]||{{}}).id; const ids=new Set([base]); DATA.graph.edges.forEach(e=>{{ if(e.source===base) ids.add(e.target); if(e.target===base) ids.add(e.source); }}); return ids; }}
function modeNodeAllowed(n) {{ if(activeGraphMode==='full') return true; if(activeGraphMode==='focus') return focusNodeIds().has(n.id); return overviewNodeIds().has(n.id); }}
function visibleNodes() {{ const q=(document.getElementById('graph-search').value||'').toLowerCase(); return DATA.graph.nodes.filter(n => modeNodeAllowed(n) && activeGraphTypes.has(n.type) && (!q || nodeSearchText(n).includes(q))); }}
function visibleNodeIds() {{ return new Set(visibleNodes().map(n => n.id)); }}
function edgeType(e) {{ return e.relation || e.type || 'unknown'; }}
function visibleEdges() {{ const ids=visibleNodeIds(); return DATA.graph.edges.filter(e => ids.has(e.source) && ids.has(e.target) && activeEdgeTypes.has(edgeType(e))); }}
function renderLegend() {{ const types = DATA.graph_filter_types || []; document.getElementById('graph-legend').innerHTML = types.slice(0,9).map(t => `<span class="legend-item"><i class="dot" style="background:${{(colorMap[t]||colorMap.requirement)[1]}}"></i>${{t.replace('_',' ')}}</span>`).join(''); }}
function renderTypeFilters() {{ const types = DATA.graph_filter_types || []; document.getElementById('type-filter-chips').innerHTML = types.map(t => `<button class="filter-chip ${{activeGraphTypes.has(t) ? 'active' : ''}}" data-type="${{t}}">${{t.replaceAll('_',' ')}}</button>`).join(''); document.querySelectorAll('[data-type]').forEach(btn => btn.onclick = () => filterNodesByType(btn.dataset.type)); updateVisibleNodeCount(); }}
function renderEdgeFilters() {{ const types = DATA.edge_filter_types || []; document.getElementById('edge-filter-chips').innerHTML = types.map(t => `<button class="filter-chip edge ${{activeEdgeTypes.has(t) ? 'active' : ''}}" data-edge-type="${{t}}">${{t.replaceAll('_',' ')}}</button>`).join(''); document.querySelectorAll('[data-edge-type]').forEach(btn => btn.onclick = () => filterEdgesByType(btn.dataset.edgeType)); updateVisibleNodeCount(); }}
function filterNodesByType(type) {{ if (activeGraphTypes.has(type) && activeGraphTypes.size > 1) activeGraphTypes.delete(type); else activeGraphTypes.add(type); renderTypeFilters(); renderGraph(); }}
function filterEdgesByType(type) {{ if (activeEdgeTypes.has(type) && activeEdgeTypes.size > 1) activeEdgeTypes.delete(type); else activeEdgeTypes.add(type); renderEdgeFilters(); renderGraph(); }}
function clearGraphFilters() {{ activeGraphTypes = new Set(DATA.graph_filter_types || []); activeEdgeTypes = new Set(DATA.edge_filter_types || []); document.getElementById('graph-search').value=''; renderTypeFilters(); renderEdgeFilters(); renderGraph(); }}
function updateVisibleNodeCount() {{ document.getElementById('visible-node-count').textContent = `${{activeGraphMode}} · ${{visibleNodes().length}} visible nodes · ${{visibleEdges().length}} visible edges · density ${{DATA.graph_summary.density}}`; }}
function renderGraph() {{ initPositions(); const edgeLayer = document.getElementById('edge-layer'); const nodeLayer = document.getElementById('node-layer'); edgeLayer.innerHTML=''; nodeLayer.innerHTML=''; const nodeList=visibleNodes(); const edgeList=visibleEdges(); const ids=new Set(nodeList.map(n=>n.id)); const edgeNodeIds=new Set(); edgeList.forEach(e => {{ edgeNodeIds.add(e.source); edgeNodeIds.add(e.target); const s=positions[e.source], t=positions[e.target]; if(!s||!t) return; const midx=(s.x+t.x)/2, midy=(s.y+t.y)/2-18; const et=edgeType(e); const edgeId = e.id || `${{e.source}}--${{et}}--${{e.target}}`; const d=`M ${{s.x+70}} ${{s.y+20}} Q ${{midx}} ${{midy}} ${{t.x+70}} ${{t.y+20}}`; const group=document.createElementNS('http://www.w3.org/2000/svg','g'); group.setAttribute('class','edge-control'); group.setAttribute('role','button'); group.setAttribute('tabindex','0'); group.setAttribute('data-edge-id', edgeId); group.addEventListener('click', ev => {{ ev.stopPropagation(); selectEdge(edgeId); }}); group.addEventListener('keydown', ev => {{ if(ev.key==='Enter' || ev.key===' ') {{ ev.preventDefault(); selectEdge(edgeId); }} }}); const path=document.createElementNS('http://www.w3.org/2000/svg','path'); path.setAttribute('class',`edge-line edge-${{et}}`); path.setAttribute('d',d); path.setAttribute('marker-end','url(#arrow)'); const hit=document.createElementNS('http://www.w3.org/2000/svg','path'); hit.setAttribute('class','edge-hit'); hit.setAttribute('d',d); const labelBg=document.createElementNS('http://www.w3.org/2000/svg','rect'); const labelWidth=Math.max(58, et.length*7+16); labelBg.setAttribute('class','edge-label-bg'); labelBg.setAttribute('x',midx-labelWidth/2); labelBg.setAttribute('y',midy-14); labelBg.setAttribute('width',labelWidth); labelBg.setAttribute('height',20); labelBg.setAttribute('rx',10); const label=document.createElementNS('http://www.w3.org/2000/svg','text'); label.setAttribute('class','edge-label'); label.setAttribute('x',midx); label.setAttribute('y',midy); label.setAttribute('text-anchor','middle'); label.textContent=et; group.appendChild(path); group.appendChild(hit); group.appendChild(labelBg); group.appendChild(label); edgeLayer.appendChild(group); }}); nodeList.forEach(n => {{ const p=positions[n.id]; const colors=colorMap[n.type] || colorMap.requirement; const g=document.createElementNS('http://www.w3.org/2000/svg','g'); g.setAttribute('class','node-card' + (edgeList.length && !edgeNodeIds.has(n.id) ? ' dimmed' : '')); g.setAttribute('transform',`translate(${{p.x}} ${{p.y}})`); g.setAttribute('data-node-id', n.id); g.setAttribute('role','button'); g.setAttribute('tabindex','0'); g.innerHTML=`<rect width="150" height="44" fill="${{colors[0]}}" stroke="${{colors[1]}}"></rect><text x="12" y="18">${{escapeSvg(n.label || n.id).slice(0,22)}}</text><text x="12" y="34" fill="#667085">${{escapeSvg(n.type)}}</text>`; g.addEventListener('mousedown', ev => startNodeDrag(ev,n.id)); g.addEventListener('click', ev => {{ ev.stopPropagation(); selectNode(n); }}); g.addEventListener('keydown', ev => {{ if(ev.key==='Enter' || ev.key===' ') {{ ev.preventDefault(); selectNode(n); }} }}); nodeLayer.appendChild(g); }}); updateVisibleNodeCount(); applyZoom(); renderMinimap(ids); }}
function escapeSvg(s) {{ return String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])); }}
function startNodeDrag(ev,id) {{ ev.stopPropagation(); ev.preventDefault(); const start={{x:ev.clientX,y:ev.clientY,px:positions[id].x,py:positions[id].y}}; function move(e){{positions[id].x=start.px+(e.clientX-start.x)/panZoomState.scale; positions[id].y=start.py+(e.clientY-start.y)/panZoomState.scale; renderGraph();}} function up(){{window.removeEventListener('mousemove',move); window.removeEventListener('mouseup',up);}} window.addEventListener('mousemove',move); window.addEventListener('mouseup',up); }}
function nodeLogPath(n) {{ return n && (n.path || (n.metadata||{{}}).path || ''); }}
function edgeLogPath(e) {{ const meta=(e&&e.metadata)||{{}}; if(meta.path) return meta.path; const source=DATA.graph.nodes.find(n=>n.id===e.source); const target=DATA.graph.nodes.find(n=>n.id===e.target); return nodeLogPath(source) || nodeLogPath(target) || ''; }}
function updateViewInLogsControl() {{ const link=document.getElementById('view-in-logs'); const can=!!(selectedGraphRef && selectedGraphRef.path && DATA.file_inventory.some(f=>f.path===selectedGraphRef.path)); link.classList.toggle('disabled', !can); link.setAttribute('aria-disabled', String(!can)); link.textContent = can ? 'View in Logs →' : 'No direct log mapping'; link.title = can ? selectedGraphRef.path : 'No matching local log/artifact is indexed for this graph item.'; }}
function selectNode(n) {{ focusNodeId=n.id; selectedGraphRef={{kind:'node', id:n.id, path:nodeLogPath(n)}}; document.querySelectorAll('.node-card').forEach(el => el.classList.toggle('selected', el.dataset.nodeId===n.id)); document.querySelectorAll('.edge-control').forEach(el => el.classList.remove('selected')); document.getElementById('node-inspector').textContent=n.label || n.id; const incident=DATA.graph.edges.filter(e=>e.source===n.id || e.target===n.id).length; document.getElementById('inspector-body').innerHTML = kv({{Mode:'Node', ID:n.id, Type:n.type, Status:n.status, IncidentEdges:incident, Description:n.description || n.summary || '', Tags:(n.tags||[]).join(', '), Path:(n.path || (n.metadata||{{}}).path || '')}}); updateViewInLogsControl(); }}
function edgeById(edgeId) {{ return DATA.graph.edges.find(e => (e.id || `${{e.source}}--${{edgeType(e)}}--${{e.target}}`) === edgeId); }}
function selectEdge(edgeId) {{ const e=edgeById(edgeId); if(!e) return; const source=DATA.graph.nodes.find(n=>n.id===e.source)||{{}}; const target=DATA.graph.nodes.find(n=>n.id===e.target)||{{}}; selectedGraphRef={{kind:'edge', id:edgeId, path:edgeLogPath(e)}}; document.querySelectorAll('.edge-control').forEach(el => el.classList.toggle('selected', el.dataset.edgeId===edgeId)); document.getElementById('node-inspector').textContent=e.label || e.type || 'Edge'; document.getElementById('inspector-body').innerHTML = kv({{Mode:'Edge', ID:edgeId, Relation:e.relation || e.type, Source:e.source, Target:e.target, SourceType:source.type || 'unknown', TargetType:target.type || 'unknown', Confidence:e.confidence, LogPath:selectedGraphRef.path, Status:e.status || 'active', Metadata: JSON.stringify(e.metadata || {{}})}}); updateViewInLogsControl(); }}
function selectHub(id) {{ const node=DATA.graph.nodes.find(n=>n.id===id); if(node) {{ selectNode(node); positions[id] = positions[id] || {{x:260,y:180}}; panZoomState={{x:180-positions[id].x,y:150-positions[id].y,scale:1.35}}; renderGraph(); selectNode(node); }} }}
function renderGraphSummary() {{ const s=DATA.graph_summary; document.getElementById('node-inspector').textContent='Graph diagnostic summary'; const hubHtml=(s.hubs||[]).slice(0,5).map(h=>`<div class="hub-row" data-hub-id="${{h.id}}"><strong>${{h.label}}</strong><br><span class="subtitle">${{h.type}} · degree ${{h.degree}} · in ${{h.in_degree}} / out ${{h.out_degree}}</span></div>`).join(''); document.getElementById('inspector-body').innerHTML = `<div class="summary-grid"><div class="summary-card"><small>Density</small><strong>${{s.density}}</strong></div><div class="summary-card"><small>Components</small><strong>${{s.component_count}}</strong></div><div class="summary-card"><small>Isolated</small><strong>${{s.isolated_count}}</strong></div><div class="summary-card"><small>Broken edges</small><strong>${{s.broken_edge_count}}</strong></div></div><ol class="diagnostic-list">${{(s.diagnostics||[]).map(d=>`<li>${{d}}</li>`).join('')}}</ol><h3>Traversal hubs</h3><div class="hub-list">${{hubHtml}}</div>`; document.querySelectorAll('[data-hub-id]').forEach(row => row.onclick=()=>selectHub(row.dataset.hubId)); }}
function kv(obj) {{ return Object.entries(obj).map(([k,v]) => `<div class="kv-row"><label>${{k}}</label><span class="chip">${{String(v || '—')}}</span></div>`).join(''); }}
function startCanvasPan(ev) {{ if (!(ev.button === 0 || ev.button === 2)) return; if (ev.target.closest && ev.target.closest('.node-card,.edge-control,.edge-line,.edge-hit,.edge-label')) return; ev.preventDefault(); isCanvasPanning = true; canvasPanStart = {{x:ev.clientX, y:ev.clientY, px:panZoomState.x, py:panZoomState.y}}; document.getElementById('graph-canvas').classList.add('panning'); }}
function panCanvasMove(ev) {{ if (!isCanvasPanning || !canvasPanStart) return; ev.preventDefault(); panZoomState.x = canvasPanStart.px + (ev.clientX - canvasPanStart.x); panZoomState.y = canvasPanStart.py + (ev.clientY - canvasPanStart.y); applyZoom(); }}
function finishCanvasPan() {{ isCanvasPanning = false; canvasPanStart = null; document.getElementById('graph-canvas').classList.remove('panning'); }}
const graphCanvas = document.getElementById('graph-canvas');
graphCanvas.addEventListener('wheel', ev => {{ ev.preventDefault(); panZoomState.scale=Math.max(.35, Math.min(2.5, panZoomState.scale + (ev.deltaY < 0 ? .08 : -.08))); applyZoom(); }});
graphCanvas.addEventListener('mousedown', startCanvasPan);
graphCanvas.addEventListener('mousemove', panCanvasMove);
graphCanvas.addEventListener('mouseup', finishCanvasPan);
graphCanvas.addEventListener('mouseleave', finishCanvasPan);
graphCanvas.addEventListener('contextmenu', ev => ev.preventDefault());
document.getElementById('zoom-in').onclick=()=>{{panZoomState.scale+=.15; applyZoom();}}; document.getElementById('zoom-out').onclick=()=>{{panZoomState.scale=Math.max(.35,panZoomState.scale-.15); applyZoom();}}; document.getElementById('zoom-reset').onclick=document.getElementById('fit-view').onclick=()=>{{panZoomState={{x:20,y:20,scale:1}}; applyZoom();}};
function setGraphMode(mode) {{ activeGraphMode=mode; document.querySelectorAll('[data-graph-mode]').forEach(btn=>btn.setAttribute('aria-pressed', String(btn.dataset.graphMode===mode))); if(mode==='focus' && !focusNodeId) {{ const hub=(DATA.graph_summary.hubs||[])[0]; focusNodeId=hub && hub.id; }} renderGraph(); }}
document.querySelectorAll('[data-graph-mode]').forEach(btn=>btn.onclick=()=>setGraphMode(btn.dataset.graphMode)); document.getElementById('graph-search').addEventListener('input', renderGraph); document.getElementById('clear-graph-filters').onclick=clearGraphFilters; document.getElementById('clear-edge-filters').onclick=()=>{{activeEdgeTypes=new Set(DATA.edge_filter_types || []); renderEdgeFilters(); renderGraph();}}; document.getElementById('focus-hubs').onclick=()=>{{const hub=(DATA.graph_summary.hubs||[])[0]; if(hub) {{ focusNodeId=hub.id; setGraphMode('focus'); selectHub(hub.id); }} }}; document.getElementById('view-in-logs').onclick=(ev)=>{{ev.preventDefault(); if(ev.currentTarget.getAttribute('aria-disabled')==='true') return; viewSelectedGraphInLogs();}};
function renderMinimap(ids) {{ const mini=document.getElementById('minimap'); mini.innerHTML=''; Object.entries(positions).filter(([id]) => !ids || ids.has(id)).slice(0,80).forEach(([id,p]) => {{ const node=DATA.graph.nodes.find(n=>n.id===id)||{{type:'requirement'}}; const d=document.createElement('i'); d.className='mini-node'; d.style.left=(8+(p.x%120))+'px'; d.style.top=(10+(p.y%60))+'px'; d.style.background=(colorMap[node.type]||colorMap.requirement)[1]; mini.appendChild(d); }}); }}
function selectLogGroup(group, keepSelection=false) {{ activeLogGroup = group; if(!keepSelection) selectedFile = null; document.querySelectorAll('[data-log-group]').forEach(el => el.classList.toggle('active', el.dataset.logGroup === group)); document.getElementById('folder-title').textContent = group + '/'; renderFiles(); }}
function locateLogPath(path) {{ if(!path) return false; let file=DATA.file_inventory.find(f=>f.path===path); if(!file) return false; selectedFile=file; activeLogGroup=file.group || (file.groups||[])[0] || 'artifacts'; location.hash='#/logs'; route(); selectLogGroup(activeLogGroup, true); selectFile(file.path); setTimeout(()=>{{ const row=document.querySelector(`#file-rows tr[data-path="${{CSS.escape(file.path)}}"]`); if(row) row.scrollIntoView({{block:'center'}}); }}, 0); return true; }}
function viewSelectedGraphInLogs() {{ if(!(selectedGraphRef && locateLogPath(selectedGraphRef.path))) updateViewInLogsControl(); }}
function renderTree() {{ const groups=DATA.log_groups || ['artifacts','sessions','proposals','policies','provenance','system']; const inv=DATA.file_inventory; document.getElementById('explorer-count').textContent=inv.length+' items'; document.getElementById('file-tree').innerHTML=groups.map(g=>{{ const items=inv.filter(i=>i.group===g || (i.groups||[]).includes(g)); return `<li data-log-group="${{g}}" class="${{g===activeLogGroup?'active':''}}"><div class="folder-row">▾ 📁 ${{g}}/ <span class="badge">${{items.length}}</span></div><ul>${{items.slice(0,10).map(i=>`<li data-file-path="${{i.path}}">◇ ${{i.name}}</li>`).join('')}}</ul></li>`; }}).join(''); document.querySelectorAll('[data-log-group] > .folder-row').forEach(row => row.onclick = () => selectLogGroup(row.parentElement.dataset.logGroup)); document.querySelectorAll('[data-file-path]').forEach(row => row.onclick = (ev) => {{ ev.stopPropagation(); selectFile(row.dataset.filePath); }}); }}
function renderFiles() {{ const q=(document.getElementById('file-search').value||'').toLowerCase(); currentFileRows=DATA.file_inventory.filter(i=>(i.group===activeLogGroup || (i.groups||[]).includes(activeLogGroup)) && (!q || i.path.toLowerCase().includes(q))); document.getElementById('table-count').textContent=currentFileRows.length+' items'; document.getElementById('file-rows').innerHTML=currentFileRows.map((f,i)=>`<tr class="${{i===0?'selected':''}} level-${{f.level}}" data-path="${{f.path}}"><td>▧ ${{f.name}}</td><td>${{f.type}}</td><td>${{f.size_label}}</td><td>${{f.modified}}</td><td><span class="level-dot"></span>${{f.level}}</td></tr>`).join(''); document.querySelectorAll('#file-rows tr').forEach(row => row.onclick=()=>selectFile(row.dataset.path)); if(currentFileRows[0] && !selectedFile) selectFile(currentFileRows[0].path); }}
function selectFile(path) {{ selectedFile=DATA.file_inventory.find(f=>f.path===path); if(!selectedFile) return; document.querySelectorAll('#file-rows tr').forEach(r=>r.classList.toggle('selected', r.dataset.path===path)); document.getElementById('preview-title').textContent=selectedFile.name; document.getElementById('preview-subtitle').textContent=`${{selectedFile.type}} • ${{selectedFile.size_label}}`; showPreviewTab('preview'); renderLineage(); }}
function withLineNumbers(text) {{ return String(text || '').split('\\n').map((line,i)=>`${{String(i+1).padStart(4,' ')}} │ ${{line}}`).join('\\n'); }}
function showPreviewTab(tab) {{ if(!selectedFile) return; document.querySelectorAll('[data-preview-tab]').forEach(b=>b.classList.toggle('active', b.dataset.previewTab===tab)); let text=selectedFile.preview; if(tab==='raw') text=selectedFile.preview + (selectedFile.preview_truncated ? '\\n\\n[local preview truncated]' : ''); if(tab==='metadata') text=JSON.stringify({{path:selectedFile.path,type:selectedFile.type,size:selectedFile.size,modified:selectedFile.modified,source:selectedFile.source,level:selectedFile.level,groups:selectedFile.groups}}, null, 2); if(tab==='lineage') text=JSON.stringify(selectedFile.lineage, null, 2); document.getElementById('preview-code').textContent=withLineNumbers(text); }}
document.querySelectorAll('[data-preview-tab]').forEach(b=>b.onclick=()=>showPreviewTab(b.dataset.previewTab)); document.getElementById('file-search').addEventListener('input', renderFiles); document.getElementById('copy-path').onclick=()=>{{ if(selectedFile) navigator.clipboard && navigator.clipboard.writeText(selectedFile.path); }};
function scrollById(id, delta) {{ const el=document.getElementById(id); if(el) el.scrollBy({{top:delta, behavior:'smooth'}}); }}
document.getElementById('table-scroll-up').onclick=()=>scrollById('file-table-scroll', -260); document.getElementById('table-scroll-down').onclick=()=>scrollById('file-table-scroll', 260); document.getElementById('preview-scroll-up').onclick=()=>scrollById('preview-code', -260); document.getElementById('preview-scroll-down').onclick=()=>scrollById('preview-code', 260);
function toggleTheme() {{ document.body.classList.toggle('dark'); document.getElementById('theme-toggle').textContent = document.body.classList.contains('dark') ? '☾' : '☼'; }}
document.getElementById('theme-toggle').onclick=toggleTheme;
function renderLineage() {{ const flow=document.getElementById('lineage-flow'); const line=selectedFile.lineage || []; flow.innerHTML = line.length ? line.slice(0,4).map(l=>`<div class="lineage-node"><strong>${{l.source}}</strong><br><span>${{l.relation}} →</span><br>${{l.target}}</div>`).join('') : '<span class="subtitle">No lineage edges found.</span>'; }}
renderLegend(); renderTypeFilters(); renderEdgeFilters(); setGraphMode('overview'); renderTree(); renderFiles(); renderGraphSummary(); updateViewInLogsControl();
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
