from __future__ import annotations

import subprocess
from pathlib import Path

from .base import MaintenanceAdapter


class GitRepoAdapter(MaintenanceAdapter):
    def _run(self, *command: str) -> str:
        proc = subprocess.run(list(command), cwd=self.repo_root, text=True, capture_output=True)
        return proc.stdout.strip()

    def inspect(self) -> dict:
        return {
            "adapter": "git_repo",
            "branch": self._run("git", "branch", "--show-current"),
            "head": self._run("git", "rev-parse", "HEAD"),
            "status_lines": self._run("git", "status", "--short").splitlines(),
        }

    def list_paths(self) -> list[str]:
        tracked = self._run("git", "ls-files").splitlines()
        return sorted(line for line in tracked if line)

    def read_text(self, path: str) -> str:
        return (self.repo_root / path).read_text(encoding="utf-8", errors="replace")

    def locate_evidence(self) -> list[dict]:
        interesting = []
        for rel in self.list_paths():
            if rel in {"README.md", "pyproject.toml", "SECURITY.md"} or rel.startswith(("tests/", "src/graph_harness_maintain/")):
                interesting.append({"path": rel, "kind": "tracked"})
        return interesting

    def propose_actions(self) -> list[dict]:
        return [
            {"action": "read_only_audit", "requires_human_approval": False},
            {"action": "git_push", "requires_human_approval": True},
            {"action": "git_tag", "requires_human_approval": True},
        ]
