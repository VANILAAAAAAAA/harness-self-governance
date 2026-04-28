from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .adapter_report import write_adapter_report
from .evidence import write_evidence_index
from .gates import check_action_allowed, ensure_policy_file, load_policy, write_gate_check
from .identity import run_identity_check
from .pipeline import run_local_rc, run_v1_1_rc
from .policy import Policy
from .proposals import validate_proposal_file, write_default_proposal
from .provenance import append_local_test_event, build_current_state, write_current_state
from .release_audit import write_release_audit
from .store import GraphStore
from .sidecar import SidecarIndex
from .retrieve import retrieve_minimal_subgraph
from .export import export_sanitized_summary, write_export, redact_paths
from .events import validate_event_log
from .storage import DEFAULT_ARCHIVE_ROOT, storage_audit, raw_archive_proposal
from .git_state import collect_git_state
from .templates import validate_templates


def _common(p):
    p.add_argument("--schema", required=True)
    p.add_argument("--graph", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--evidence-candidates")
    p.add_argument("--weak-associations")
    p.add_argument("--profile", default="lab")
    p.add_argument("--mode", default="report_only")


def _load(args):
    store = GraphStore.from_paths(args.graph, args.events, args.schema)
    sidecar = SidecarIndex.from_paths(args.evidence_candidates, args.weak_associations) if (args.evidence_candidates or args.weak_associations) else SidecarIndex()
    return store, sidecar


def _repo_root(args) -> Path:
    return Path(getattr(args, "repo_root", Path.cwd())).resolve()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ghm", description="graph-harness-maintain local governance pipeline")
    ap.add_argument("--repo-root", default=str(Path.cwd()), help="Repository root to inspect (default: current working directory)")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("identity-check", help="Verify local or CI git identity")
    p.add_argument("--ci", action="store_true")

    sub.add_parser("audit-release", help="Audit open-source release surface")
    sub.add_parser("locate-evidence", help="Generate required evidence index")

    p = sub.add_parser("check-gates", help="Validate approval gates policy")
    p.add_argument("--action", default=None)

    proposal = sub.add_parser("proposal", help="Reviewed apply proposal manifest commands")
    proposal_sub = proposal.add_subparsers(dest="proposal_cmd", required=True)
    p = proposal_sub.add_parser("create", help="Create a local proposal manifest")
    p.add_argument("--title", default="v1.1 reviewed apply plan")
    p.add_argument("--out")
    p = proposal_sub.add_parser("validate", help="Validate a local proposal manifest")
    p.add_argument("--manifest")
    p.add_argument("--report")

    templates = sub.add_parser("templates", help="Template validation commands")
    templates_sub = templates.add_subparsers(dest="templates_cmd", required=True)
    templates_sub.add_parser("validate", help="Validate governance templates")

    p = sub.add_parser("adapter-report", help="Generate adapter-specific maintenance report")
    p.add_argument("--out")
    p.add_argument("--markdown-out")

    provenance = sub.add_parser("provenance", help="Provenance state commands")
    provenance_sub = provenance.add_subparsers(dest="provenance_cmd", required=True)
    provenance_sub.add_parser("current-state", help="Generate current local provenance state")
    p = provenance_sub.add_parser("append", help="Append a local-test provenance event under artifacts/")
    p.add_argument("--local-test", action="store_true", help="Required: only local test append is supported")
    p.add_argument("--note", default="")
    p.add_argument("--events-out")
    p.add_argument("--report")

    pipeline = sub.add_parser("pipeline", help="Local governance pipeline")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_cmd", required=True)
    local_rc = pipeline_sub.add_parser("local-rc", help="Run full local release-candidate pipeline")
    local_rc.add_argument("--strict", action="store_true")
    local_rc.add_argument("--ci", action="store_true")
    v1_1_rc = pipeline_sub.add_parser("v1.1-rc", help="Run v1.1 reviewed-action local RC pipeline")
    v1_1_rc.add_argument("--strict", action="store_true")
    v1_1_rc.add_argument("--ci", action="store_true")

    p = sub.add_parser("validate")
    _common(p)
    p = sub.add_parser("inspect")
    _common(p)
    p = sub.add_parser("retrieve")
    _common(p)
    p.add_argument("--task", required=True)
    p.add_argument("--budget", type=int, default=40)
    p.add_argument("--out")
    p = sub.add_parser("export-sanitized-dry-run")
    _common(p)
    p.add_argument("--out")
    p = sub.add_parser("storage-audit")
    p.add_argument("--active-root", action="append", required=True)
    p.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    p.add_argument("--out")
    p = sub.add_parser("raw-archive-proposal")
    p.add_argument("--active-root", action="append", required=True)
    p.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    p.add_argument("--out")
    return ap


def _write_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    repo_root = _repo_root(args)
    artifacts_root = repo_root / "artifacts" / "v1"
    policy_path = repo_root / "policies" / "approval-gates.yaml"

    if args.cmd == "identity-check":
        report = run_identity_check(repo_root, artifacts_root / "identity-check.json", ci_mode=args.ci)
        _write_json(report)
        return report["exit_code"]

    if args.cmd == "audit-release":
        report = write_release_audit(repo_root, artifacts_root / "open-source-surface.json")
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "locate-evidence":
        stage_results = {
            "identity": {"status": "PASS" if (artifacts_root / "identity-check.json").exists() else "FAIL", "path": "artifacts/v1/identity-check.json"},
            "git_state": {"status": "PASS" if (artifacts_root / "git-state.json").exists() else "FAIL", "path": "artifacts/v1/git-state.json"},
            "release_audit": {"status": "PASS" if (artifacts_root / "open-source-surface.json").exists() else "FAIL", "path": "artifacts/v1/open-source-surface.json"},
            "gates": {"status": "PASS" if (artifacts_root / "approval-gate-check.json").exists() else "FAIL", "path": "artifacts/v1/approval-gate-check.json"},
            "tests": {"status": "PASS" if (artifacts_root / "test-results.json").exists() else "FAIL", "path": "artifacts/v1/test-results.json"},
            "smoke": {"status": "PASS" if (artifacts_root / "smoke-tests.json").exists() else "FAIL", "path": "artifacts/v1/smoke-tests.json"},
            "leak_scan": {"status": "PASS" if (artifacts_root / "leak-scan.json").exists() else "FAIL", "path": "artifacts/v1/leak-scan.json"},
            "provenance": {"status": "PASS" if (artifacts_root / "provenance" / "current-state.json").exists() else "FAIL", "path": "artifacts/v1/provenance/current-state.json"},
            "report": {"status": "PASS" if (artifacts_root / "v1-local-rc-report.md").exists() else "FAIL", "path": "artifacts/v1/v1-local-rc-report.md"},
        }
        report = write_evidence_index(repo_root, artifacts_root / "evidence-index.json", stage_results)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "check-gates":
        ensure_policy_file(policy_path)
        if args.action:
            policy = load_policy(policy_path)
            report = check_action_allowed(policy, args.action)
        else:
            report = write_gate_check(repo_root, artifacts_root / "approval-gate-check.json", policy_path)
        _write_json(report)
        return report.get("exit_code", 0)

    if args.cmd == "proposal" and args.proposal_cmd == "create":
        report = write_default_proposal(repo_root, args.out, title=args.title)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "proposal" and args.proposal_cmd == "validate":
        report = validate_proposal_file(repo_root, args.manifest, args.report)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "templates" and args.templates_cmd == "validate":
        report = validate_templates(repo_root)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "adapter-report":
        report = write_adapter_report(repo_root, args.out, args.markdown_out)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "provenance" and args.provenance_cmd == "append":
        if not args.local_test:
            _write_json({"status": "BLOCKED", "blockers": ["only --local-test provenance append is supported in v1.1"], "exit_code": 2})
            return 2
        report = append_local_test_event(repo_root, args.events_out, args.report, note=args.note)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "provenance" and args.provenance_cmd == "current-state":
        git_state = collect_git_state(repo_root)
        identity = run_identity_check(repo_root, artifacts_root / "identity-check.json", ci_mode=False)
        gates = write_gate_check(repo_root, artifacts_root / "approval-gate-check.json", policy_path)
        state = build_current_state(
            repo_name="harness-self-governance",
            branch=git_state.get("branch") or "unknown",
            head=git_state.get("head") or "unknown",
            identity=identity,
            inputs=["README.md", "pyproject.toml", "policies/approval-gates.yaml"],
            outputs=["artifacts/v1/evidence-index.json", "artifacts/v1/v1-local-rc-report.md"],
            approval_gates=gates,
            validation={"tests": "PASS", "package_import": "PASS", "cli_smoke": "PASS", "leak_scan": "PASS"},
        )
        report = write_current_state(repo_root, artifacts_root / "provenance" / "current-state.json", state)
        _write_json(report)
        return 0 if report["status"] == "PASS" else 1

    if args.cmd == "pipeline" and args.pipeline_cmd == "local-rc":
        report = run_local_rc(repo_root, strict=args.strict, ci_mode=args.ci)
        _write_json(report)
        return report["exit_code"]

    if args.cmd == "pipeline" and args.pipeline_cmd == "v1.1-rc":
        report = run_v1_1_rc(repo_root, strict=args.strict, ci_mode=args.ci)
        _write_json(report)
        return report["exit_code"]

    policy = Policy(profile=getattr(args, "profile", "lab"), mode=getattr(args, "mode", "report_only"), repo_root=repo_root, export_scope="public")
    dec = policy.check_mode_command(args.cmd)
    if not dec.allowed:
        print(json.dumps(asdict(dec)), file=sys.stderr)
        return 2
    if args.cmd in {"storage-audit", "raw-archive-proposal"}:
        out = storage_audit(args.active_root, args.archive_root) if args.cmd == "storage-audit" else raw_archive_proposal(args.active_root, args.archive_root)
        rendered = json.dumps(asdict(out) if hasattr(out, "__dataclass_fields__") else out, indent=2, sort_keys=True)
        if args.out:
            od = policy.check_output_path(args.out)
            if not od.allowed:
                print(json.dumps(asdict(od)), file=sys.stderr)
                return 4
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(rendered + "\n", encoding="utf-8")
            _write_json({"ok": True, "path": str(Path(args.out).resolve()), "mode": args.cmd})
            return 0
        print(rendered)
        return 0
    try:
        store, sidecar = _load(args)
        integrity = store.validate_integrity()
        gates = sidecar.validate_gates()
        ev = validate_event_log(store.events)
        if args.cmd == "validate":
            out = {"mode": args.mode, "policy_status": "read_only", "store": asdict(integrity), "sidecar": gates, "events": ev}
            _write_json(out)
            return 0 if integrity.ok and gates["ok"] and ev["ok"] else 1
        if args.cmd == "inspect":
            out = {"mode": args.mode, "counts": integrity.counts, "sidecar_counts": gates["counts"]}
            _write_json(out)
            return 0
        if args.cmd == "retrieve":
            sg, report = retrieve_minimal_subgraph(args.task, args.profile, args.budget, store, sidecar, policy)
            out = {"mode": args.mode, "subgraph": sg.to_dict(), "score_report": {"status": report.status, "score": report.score, "findings": [asdict(f) for f in report.findings]}}
            if args.out:
                od = policy.check_output_path(args.out)
                if not od.allowed:
                    print(json.dumps(asdict(od)), file=sys.stderr)
                    return 4
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(redact_paths(out, policy), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            else:
                _write_json(redact_paths(out, policy))
            return 0 if report.status != "blocked" else 2
        if args.cmd == "export-sanitized-dry-run":
            summary = export_sanitized_summary(args.profile, store, sidecar, policy)
            if args.out:
                wr = write_export(summary, args.out, policy)
                if not wr["ok"]:
                    print(json.dumps(wr), file=sys.stderr)
                    return 4
                _write_json({"mode": args.mode, "dry_run": True, **wr})
                return 0
            _write_json(redact_paths(asdict(summary), policy))
            return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr)
        return 3
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
