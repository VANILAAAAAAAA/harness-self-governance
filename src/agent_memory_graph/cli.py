from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archive import archive_session
from .archive_gate import classify_archive_input, write_archive_gate_report
from .archive_triggers import evaluate_archive_trigger, write_archive_trigger_report
from .bootstrap import bootstrap_repo, validate_repo
from .context_gaps import list_context_gaps
from .context_index import build_context_index
from .export import export_repo_projection
from .maintenance import generate_archive_maintenance_proposal, validate_archive_maintenance, write_archive_maintenance_report
from .pending_updates import capture_pending_update
from .pending_lifecycle import compile_pending_updates
from .repo_adapter import init_repo_manifest
from .retrieve import retrieve_project_context
from .runtime_traces import export_graph_memory_traces
from .router import route_query
from .traversal import traverse_memory_graph
from .schemas import resolve_memory_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-graph", description="Reusable global Agent Memory Graph context tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    init_repo = sub.add_parser("init-repo", help="Create .agent/context.json for the repository")
    init_repo.add_argument("--repo", default=".")
    init_repo.add_argument("--profile", required=True)
    init_repo.add_argument("--project", required=True)
    init_repo.add_argument("--force", action="store_true")

    bootstrap = sub.add_parser("bootstrap", help="Bootstrap graph-governed context files under a memory root")
    bootstrap.add_argument("--repo", default=".")
    bootstrap.add_argument("--memory-root", default=None)
    bootstrap.add_argument("--context-budget", default="fast", choices=("fast", "normal", "deep", "forensic"))

    validate = sub.add_parser("validate", help="Validate repo manifest and memory-root coherence")
    validate.add_argument("--repo", default=".")
    validate.add_argument("--memory-root", default=None)

    archive = sub.add_parser("archive-session", help="Merge an agent-compiled session JSON into project artifacts")
    archive.add_argument("--profile", required=True)
    archive.add_argument("--project", required=True)
    archive.add_argument("--input", required=True)
    archive.add_argument("--memory-root", default=None)

    export = sub.add_parser("export", help="Project global memory artifacts back into repo-local artifacts/v2 paths")
    export.add_argument("--repo", default=".")
    export.add_argument("--memory-root", default=None)

    build_index = sub.add_parser("build-index", help="Build deterministic graph traversal context index")
    build_index.add_argument("--repo", default=".")
    build_index.add_argument("--memory-root", default=None)

    route = sub.add_parser("route", help="Route a query through the Agent Memory Graph context router")
    route.add_argument("--repo", default=".")
    route.add_argument("--query", required=True)
    route.add_argument("--memory-root", default=None)
    route.add_argument("--context-budget", default="fast", choices=("fast", "normal", "deep", "forensic"))

    retrieve = sub.add_parser("retrieve", help="Retrieve agent-readable compiled project context")
    retrieve.add_argument("--repo", default=".")
    retrieve.add_argument("--query", required=True)
    retrieve.add_argument("--memory-root", default=None)
    retrieve.add_argument("--budget", default="fast", choices=("fast", "normal", "deep", "forensic"))
    retrieve.add_argument("--evidence-depth", default="anchor", choices=("none", "anchor", "excerpt", "raw-span"))
    retrieve.add_argument("--refresh-index", action="store_true")
    retrieve.add_argument("--refresh-graph", action="store_true")
    retrieve.add_argument("--profile", default=None)
    retrieve.add_argument("--project", default=None)

    traverse = sub.add_parser("traverse", help="Traverse Agent Memory Graph nodes and edges")
    traverse.add_argument("--repo", default=".")
    traverse.add_argument("--node", required=True)
    traverse.add_argument("--max-depth", type=int, default=2)
    traverse.add_argument("--memory-root", default=None)

    capture = sub.add_parser("capture-update", help="Capture new information as a pending archive update")
    capture.add_argument("--repo", default=".")
    capture.add_argument("--text", required=True)
    capture.add_argument("--profile", required=True)
    capture.add_argument("--project", required=True)
    capture.add_argument("--memory-root", default=None)

    gaps = sub.add_parser("list-gaps", help="List graph traversal context gaps")
    gaps.add_argument("--repo", default=".")
    gaps.add_argument("--memory-root", default=None)

    archive_gate = sub.add_parser("archive-gate", help="Archive lifecycle boundary classification and reporting")
    archive_gate_sub = archive_gate.add_subparsers(dest="archive_gate_command", required=True)
    archive_gate_classify = archive_gate_sub.add_parser("classify", help="Classify an input as transient, pending update, compiled candidate, or forensic only")
    archive_gate_classify.add_argument("--input", required=True)
    archive_gate_classify.add_argument("--repo", default=".")
    archive_gate_classify.add_argument("--memory-root", default=None)
    archive_gate_report = archive_gate_sub.add_parser("report", help="Write archive gate lifecycle report")
    archive_gate_report.add_argument("--repo", default=".")
    archive_gate_report.add_argument("--memory-root", default=None)
    archive_gate_compile = archive_gate_sub.add_parser("compile-pending", help="Materialize pending updates as reviewed compiled candidates without archiving")
    archive_gate_compile.add_argument("--repo", default=".")
    archive_gate_compile.add_argument("--memory-root", default=None)
    archive_gate_compile.add_argument("--profile", default=None)
    archive_gate_compile.add_argument("--project", default=None)

    traces = sub.add_parser("runtime-traces", help="Export Hermes graph-memory runtime trace observability")
    traces_sub = traces.add_subparsers(dest="traces_command", required=True)
    traces_export = traces_sub.add_parser("export", help="Export bounded graph-memory JSONL traces into a report artifact")
    traces_export.add_argument("--trace-dir", required=True)
    traces_export.add_argument("--out", required=True)
    traces_export.add_argument("--limit", type=int, default=50)

    maintenance = sub.add_parser("maintenance", help="Archive lifecycle maintenance reporting and proposal commands")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_report = maintenance_sub.add_parser("report", help="Write archive maintenance report")
    maintenance_report.add_argument("--repo", default=".")
    maintenance_report.add_argument("--memory-root", default=None)
    maintenance_validate = maintenance_sub.add_parser("validate", help="Validate archive lifecycle maintenance posture")
    maintenance_validate.add_argument("--repo", default=".")
    maintenance_validate.add_argument("--memory-root", default=None)
    maintenance_propose = maintenance_sub.add_parser("propose", help="Write proposal-only archive maintenance actions")
    maintenance_propose.add_argument("--repo", default=".")
    maintenance_propose.add_argument("--memory-root", default=None)

    triggers = sub.add_parser("triggers", help="Archive trigger policy evaluation and reporting")
    triggers_sub = triggers.add_subparsers(dest="triggers_command", required=True)
    triggers_evaluate = triggers_sub.add_parser("evaluate", help="Evaluate a trigger event into an archive recommendation")
    triggers_evaluate.add_argument("--input", required=True)
    triggers_evaluate.add_argument("--repo", default=".")
    triggers_evaluate.add_argument("--memory-root", default=None)
    triggers_report = triggers_sub.add_parser("report", help="Write archive trigger policy report")
    triggers_report.add_argument("--repo", default=".")
    triggers_report.add_argument("--memory-root", default=None)
    return parser


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init-repo":
        report = init_repo_manifest(Path(args.repo), args.profile, args.project, force=args.force)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "bootstrap":
        report = bootstrap_repo(Path(args.repo), args.memory_root, context_budget=args.context_budget)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "validate":
        report = validate_repo(Path(args.repo), args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "archive-session":
        report = archive_session(resolve_memory_root(args.memory_root), args.profile, args.project, args.input)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "export":
        report = export_repo_projection(Path(args.repo), resolve_memory_root(args.memory_root))
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "build-index":
        report = build_context_index(Path(args.repo), args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "route":
        report = route_query(Path(args.repo), args.query, args.memory_root, context_budget=args.context_budget)
        _print(report)
        return 0 if report["status"] in {"PASS", "MISS", "AMBIGUOUS"} else 1
    if args.command == "retrieve":
        report = retrieve_project_context(
            Path(args.repo),
            args.query,
            profile_hint=args.profile,
            project_hint=args.project,
            memory_root=args.memory_root,
            budget=args.budget,
            evidence_depth=args.evidence_depth,
            refresh_index=args.refresh_index,
            refresh_graph=args.refresh_graph,
        )
        _print(report)
        return 0 if report["status"] in {"PASS", "MISS", "AMBIGUOUS", "LOW_CONFIDENCE", "NEW_INFORMATION"} else 1
    if args.command == "traverse":
        report = traverse_memory_graph(Path(args.repo), args.node, args.memory_root, max_depth=args.max_depth)
        _print(report)
        return 0 if report["status"] in {"PASS", "MISS"} else 1
    if args.command == "capture-update":
        report = capture_pending_update(Path(args.repo), args.text, args.profile, args.project, args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "list-gaps":
        report = list_context_gaps(Path(args.repo), args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "archive-gate":
        if args.archive_gate_command == "classify":
            report = classify_archive_input(args.input, args.repo, args.memory_root)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
        if args.archive_gate_command == "report":
            report = write_archive_gate_report(Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
        if args.archive_gate_command == "compile-pending":
            report = compile_pending_updates(Path(args.repo), args.memory_root, profile=args.profile, project=args.project)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
    if args.command == "runtime-traces":
        if args.traces_command == "export":
            report = export_graph_memory_traces(args.trace_dir, args.out, limit=args.limit)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
    if args.command == "maintenance":
        if args.maintenance_command == "report":
            report = write_archive_maintenance_report(Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1
        if args.maintenance_command == "validate":
            report = validate_archive_maintenance(Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1
        if args.maintenance_command == "propose":
            report = generate_archive_maintenance_proposal(Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
    if args.command == "triggers":
        if args.triggers_command == "evaluate":
            report = evaluate_archive_trigger(args.input, Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
        if args.triggers_command == "report":
            report = write_archive_trigger_report(Path(args.repo), args.memory_root)
            _print(report)
            return 0 if report["status"] == "PASS" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
