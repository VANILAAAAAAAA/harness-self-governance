from __future__ import annotations

from pathlib import Path
import re
from .schema import PolicyDecision, GraphNode

SAFE_COMMANDS = {
    "validate",
    "inspect",
    "retrieve",
    "export-sanitized-dry-run",
    "storage-audit",
    "raw-archive-proposal",
    "proposal",
    "templates",
    "adapter-report",
}
BLOCKED_COMMANDS = {"raw-archive-apply", "apply"}
BLOCKED_OUTPUT_NAMES = {"graph.jsonl", "events.jsonl", "shared-skills.jsonl", "shared-tools.jsonl", "graph.schema.yaml"}
SENSITIVE_LABELS = {"phi_or_patient_level", "credential"}

class Policy:
    def __init__(self, profile: str = "ehrlab", mode: str = "report_only", repo_root: str | None = None, export_scope: str = "public"):
        self.profile = profile; self.mode = mode or "report_only"; self.repo_root = Path(repo_root or Path.cwd()).resolve(); self.export_scope = export_scope

    def check_mode_command(self, command: str) -> PolicyDecision:
        if command in BLOCKED_COMMANDS:
            return PolicyDecision(False, f"command {command} requires explicit human approval", "HUMAN_APPROVAL_REQUIRED")
        if command not in SAFE_COMMANDS:
            return PolicyDecision(False, f"command {command} is not available in limited read-only core", "blocked_command")
        return PolicyDecision(True, "allowed")

    def check_output_path(self, path: str | None) -> PolicyDecision:
        if not path:
            return PolicyDecision(True, "no output path")
        p = Path(path).resolve()
        if p.name in BLOCKED_OUTPUT_NAMES:
            return PolicyDecision(False, f"refuse writing protected file name {p.name}", "unsafe_output")
        allowed_roots = [(self.repo_root / "artifacts").resolve(), (self.repo_root / "tests" / "fixtures").resolve()]
        if not any(str(p).startswith(str(root) + "/") or p == root for root in allowed_roots):
            return PolicyDecision(False, f"output must be under repo artifacts/ or tests/fixtures/: {p}", "unsafe_output")
        return PolicyDecision(True, "output path allowed")

    def check_sidecar_upgrade(self, human_confirmation_required: bool, upgrade_allowed: bool) -> PolicyDecision:
        if human_confirmation_required:
            return PolicyDecision(False, "human_confirmation_required is a hard gate", "human_confirmation_required")
        if not upgrade_allowed:
            return PolicyDecision(False, "upgrade_allowed=false is a hard gate", "upgrade_not_allowed")
        return PolicyDecision(True, "upgrade would require future explicit mode")

    def check_export_node(self, node: GraphNode) -> PolicyDecision:
        if node.sensitivity in SENSITIVE_LABELS:
            return PolicyDecision(False, f"sensitive node blocked from export: {node.id}", "sensitive_export_block")
        if node.sensitivity not in {"none", "internal", "sensitive"}:
            return PolicyDecision(False, f"unknown sensitivity label: {node.sensitivity}", "unknown_sensitivity")
        if self.export_scope == "public" and node.profile_scope not in {self.profile, "shared"}:
            return PolicyDecision(False, f"profile boundary block: {node.id}", "profile_boundary")
        return PolicyDecision(True, "export allowed")

def looks_absolute_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    patterns = [
        r"file:///(?:[A-Za-z]:/|/)?[^\s\"']+",
        r"(?:^|[\s\"'=:\[,])/(?:home|mnt|tmp|Users)/[^\s\"'\],}]+",
        r"(?:^|[\s\"'=:\[,])/[A-Za-z0-9._-]+/[^\s\"'\],}]+",
        r"(?:^|[\s\"'=:\[,])[A-Za-z]:[\\/]+[^\s\"'\],}]+",
        r"(?:^|[\s\"'=:\[,])\\\\+(?:wsl\$|wsl\.localhost)[\\/]+[^\s\"'\],}]+",
    ]
    return any(re.search(pattern, value) for pattern in patterns)
