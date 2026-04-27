from __future__ import annotations

import json
from pathlib import Path

from .base import MaintenanceAdapter


class ArtifactStoreAdapter(MaintenanceAdapter):
    def inspect(self) -> dict:
        artifact_root = self.repo_root / "artifacts"
        return {"adapter": "artifact_store", "artifact_root": artifact_root.as_posix(), "exists": artifact_root.exists(), "path_count": len(self.list_paths())}

    def list_paths(self) -> list[str]:
        artifact_root = self.repo_root / "artifacts"
        if not artifact_root.exists():
            return []
        return sorted(path.relative_to(self.repo_root).as_posix() for path in artifact_root.rglob("*") if path.is_file())

    def read_text(self, path: str) -> str:
        return (self.repo_root / path).read_text(encoding="utf-8", errors="replace")

    def locate_evidence(self) -> list[dict]:
        evidence = []
        for rel in self.list_paths():
            if rel.endswith((".json", ".md")):
                evidence.append({"path": rel, "kind": "artifact"})
        return evidence

    def propose_actions(self) -> list[dict]:
        return [{"action": "local_report_generation", "requires_human_approval": False}, {"action": "sensitive_export", "requires_human_approval": True}]

    def read_json(self, path: str) -> dict:
        return json.loads(self.read_text(path))
