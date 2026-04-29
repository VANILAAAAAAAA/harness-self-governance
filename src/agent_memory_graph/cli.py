from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archive import archive_session
from .bootstrap import bootstrap_repo, validate_repo
from .context_gaps import list_context_gaps
from .context_index import build_context_index
from .export import export_repo_projection
from .pending_updates import capture_pending_update
from .repo_adapter import init_repo_manifest
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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
