from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json, re
from pathlib import Path
from .schema import ExportSummary
from .policy import Policy, looks_absolute_path

DENY_RE = re.compile(r"(token|secret|credential|raw|sensitive|patient|subject_id|hadm_id|icustay|mimic)", re.I)
ABS_RE = re.compile(r"(/home/[^\s\"']+|/mnt/[a-z]/[^\s\"']+|/Users/[^\s\"']+|[A-Za-z]:\\\\[^\s\"']+)")

def redact_paths(value, policy: Policy | None = None):
    if isinstance(value, str):
        s = ABS_RE.sub("${REDACTED_PATH}", value)
        s = DENY_RE.sub("[REDACTED]", s)
        return s
    if isinstance(value, list): return [redact_paths(v, policy) for v in value]
    if isinstance(value, dict): return {k: redact_paths(v, policy) for k,v in value.items() if k not in {"candidate_ref","source_path","target_path"}}
    return value

def export_sanitized_summary(profile: str, store, sidecar=None, policy: Policy | None = None) -> ExportSummary:
    policy = policy or Policy(profile=profile, export_scope="public")
    blocks=[]; exported_nodes=0
    for n in store.nodes.values():
        dec = policy.check_export_node(n)
        if dec.allowed: exported_nodes += 1
        else: blocks.append(dec.reason)
    graph_health = {
        "nodes": len(store.nodes), "edges": len(store.edges), "events": len(store.events), "exportable_nodes": exported_nodes,
        "node_types": dict(Counter(n.type for n in store.nodes.values())), "edge_types": dict(Counter(e.type for e in store.edges.values())),
        "sensitivity_counts": dict(Counter(n.sensitivity for n in store.nodes.values())),
    }
    side = sidecar.counts() if sidecar else {"evidence_candidates": 0, "weak_associations": 0}
    return ExportSummary(profile, store.schema.version, graph_health, side, sorted(set(blocks)))

def write_export(summary: ExportSummary, output_path: str, policy: Policy) -> dict:
    dec = policy.check_output_path(output_path)
    if not dec.allowed: return {"ok": False, "error": dec.reason}
    data = redact_paths(asdict(summary), policy)
    rendered = json.dumps(data, indent=2, sort_keys=True)
    if looks_absolute_path(rendered): return {"ok": False, "error": "unredacted absolute path detected"}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(rendered + "\n", encoding="utf-8")
    return {"ok": True, "path": str(Path(output_path).resolve())}
