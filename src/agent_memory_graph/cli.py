from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archive import archive_session
from .bootstrap import bootstrap_repo, validate_repo
from .export import export_repo_projection
from .repo_adapter import init_repo_manifest


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
        report = bootstrap_repo(Path(args.repo), args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "validate":
        report = validate_repo(Path(args.repo), args.memory_root)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "archive-session":
        report = archive_session(args.memory_root or "~/.agent-memory-graph", args.profile, args.project, args.input)
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "export":
        report = export_repo_projection(Path(args.repo), args.memory_root or "~/.agent-memory-graph")
        _print(report)
        return 0 if report["status"] == "PASS" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
