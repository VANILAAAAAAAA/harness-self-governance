from __future__ import annotations

import argparse, json, sys
from dataclasses import asdict
from pathlib import Path

from .store import GraphStore
from .sidecar import SidecarIndex
from .policy import Policy
from .retrieve import retrieve_minimal_subgraph
from .export import export_sanitized_summary, write_export, redact_paths
from .score import score_subgraph
from .events import validate_event_log
from .storage import DEFAULT_ARCHIVE_ROOT, storage_audit, raw_archive_proposal


def _common(p):
    p.add_argument("--schema", required=True); p.add_argument("--graph", required=True); p.add_argument("--events", required=True)
    p.add_argument("--evidence-candidates"); p.add_argument("--weak-associations"); p.add_argument("--profile", default="lab"); p.add_argument("--mode", default="report_only")

def _load(args):
    store = GraphStore.from_paths(args.graph, args.events, args.schema)
    sidecar = SidecarIndex.from_paths(args.evidence_candidates, args.weak_associations) if (args.evidence_candidates or args.weak_associations) else SidecarIndex()
    return store, sidecar

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="graph-harness-maintain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate"); _common(p)
    p = sub.add_parser("inspect"); _common(p)
    p = sub.add_parser("retrieve"); _common(p); p.add_argument("--task", required=True); p.add_argument("--budget", type=int, default=40); p.add_argument("--out")
    p = sub.add_parser("export-sanitized-dry-run"); _common(p); p.add_argument("--out")
    p = sub.add_parser("storage-audit"); p.add_argument("--active-root", action="append", required=True); p.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT); p.add_argument("--out")
    p = sub.add_parser("raw-archive-proposal"); p.add_argument("--active-root", action="append", required=True); p.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT); p.add_argument("--out")
    args = ap.parse_args(argv)
    policy = Policy(profile=getattr(args, "profile", "lab"), mode=getattr(args, "mode", "report_only"), repo_root=Path.cwd(), export_scope="public")
    dec = policy.check_mode_command(args.cmd)
    if not dec.allowed:
        print(json.dumps(asdict(dec)), file=sys.stderr); return 2
    if args.cmd in {"storage-audit", "raw-archive-proposal"}:
        out = storage_audit(args.active_root, args.archive_root) if args.cmd == "storage-audit" else raw_archive_proposal(args.active_root, args.archive_root)
        rendered = json.dumps(asdict(out) if hasattr(out, "__dataclass_fields__") else out, indent=2, sort_keys=True)
        if args.out:
            od = policy.check_output_path(args.out)
            if not od.allowed: print(json.dumps(asdict(od)), file=sys.stderr); return 4
            Path(args.out).parent.mkdir(parents=True, exist_ok=True); Path(args.out).write_text(rendered + "\n", encoding="utf-8")
            print(json.dumps({"ok": True, "path": str(Path(args.out).resolve()), "mode": args.cmd}, indent=2, sort_keys=True)); return 0
        print(rendered); return 0
    try:
        store, sidecar = _load(args)
        integrity = store.validate_integrity(); gates = sidecar.validate_gates(); ev = validate_event_log(store.events)
        if args.cmd == "validate":
            out = {"mode": args.mode, "policy_status": "read_only", "store": asdict(integrity), "sidecar": gates, "events": ev}
            print(json.dumps(out, indent=2, sort_keys=True)); return 0 if integrity.ok and gates["ok"] and ev["ok"] else 1
        if args.cmd == "inspect":
            out = {"mode": args.mode, "counts": integrity.counts, "sidecar_counts": gates["counts"]}
            print(json.dumps(out, indent=2, sort_keys=True)); return 0
        if args.cmd == "retrieve":
            sg, report = retrieve_minimal_subgraph(args.task, args.profile, args.budget, store, sidecar, policy)
            out = {"mode": args.mode, "subgraph": sg.to_dict(), "score_report": {"status": report.status, "score": report.score, "findings": [asdict(f) for f in report.findings]}}
            if args.out:
                od = policy.check_output_path(args.out)
                if not od.allowed: print(json.dumps(asdict(od)), file=sys.stderr); return 4
                Path(args.out).parent.mkdir(parents=True, exist_ok=True); Path(args.out).write_text(json.dumps(redact_paths(out, policy), indent=2, sort_keys=True)+"\n", encoding="utf-8")
            else:
                print(json.dumps(redact_paths(out, policy), indent=2, sort_keys=True))
            return 0 if report.status != "blocked" else 2
        if args.cmd == "export-sanitized-dry-run":
            summary = export_sanitized_summary(args.profile, store, sidecar, policy)
            if args.out:
                wr = write_export(summary, args.out, policy)
                if not wr["ok"]: print(json.dumps(wr), file=sys.stderr); return 4
                print(json.dumps({"mode": args.mode, "dry_run": True, **wr}, indent=2, sort_keys=True)); return 0
            print(json.dumps(redact_paths(asdict(summary), policy), indent=2, sort_keys=True)); return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr); return 3
    return 5

if __name__ == "__main__":
    raise SystemExit(main())
