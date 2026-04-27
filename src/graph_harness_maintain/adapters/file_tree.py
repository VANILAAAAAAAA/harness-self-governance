from __future__ import annotations

from pathlib import Path

from .base import MaintenanceAdapter


class FileTreeAdapter(MaintenanceAdapter):
    def inspect(self) -> dict:
        return {"adapter": "file_tree", "repo_root": self.repo_root.as_posix(), "path_count": len(self.list_paths())}

    def list_paths(self) -> list[str]:
        return sorted(path.relative_to(self.repo_root).as_posix() for path in self.repo_root.rglob("*") if path.is_file() and ".git" not in path.parts)

    def read_text(self, path: str) -> str:
        target = (self.repo_root / path).resolve()
        if not str(target).startswith(str(self.repo_root.resolve())):
            raise ValueError("path escapes repo root")
        return target.read_text(encoding="utf-8", errors="replace")

    def locate_evidence(self) -> list[dict]:
        return [{"path": rel, "kind": "file"} for rel in self.list_paths() if rel.startswith(("README", "src/", "tests/", "policies/", "templates/"))]

    def propose_actions(self) -> list[dict]:
        return [
            {"action": "review_release_surface", "requires_human_approval": False},
            {"action": "git_commit", "requires_human_approval": True},
        ]
