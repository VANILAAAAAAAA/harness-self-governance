from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ApprovalRequiredError(RuntimeError):
    pass


@dataclass
class MaintenanceAdapter:
    repo_root: Path

    def inspect(self) -> dict:
        raise NotImplementedError

    def list_paths(self) -> list[str]:
        raise NotImplementedError

    def read_text(self, path: str) -> str:
        raise NotImplementedError

    def locate_evidence(self) -> list[dict]:
        raise NotImplementedError

    def propose_actions(self) -> list[dict]:
        raise NotImplementedError

    def mutate(self, *_args, **_kwargs) -> None:
        raise ApprovalRequiredError("Mutation requires explicit human approval in v1.0")
