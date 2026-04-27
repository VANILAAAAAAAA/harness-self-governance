from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CONTROL_PLANE_HARD_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
CONTROL_PLANE_WARNING_BYTES = 3 * 1024 * 1024 * 1024
DEFAULT_ARCHIVE_ROOT = "archive-proposals"
SKIP_DIR_NAMES = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', 'dist', 'build', '.venv', 'venv'}


@dataclass(frozen=True)
class StorageRootStat:
    path: str
    exists: bool
    bytes: int = 0
    files: int = 0
    dirs: int = 0
    errors: list[str] | None = None


@dataclass(frozen=True)
class StorageAuditReport:
    generated_at: str
    mode: str
    active_roots: list[StorageRootStat]
    archive_root: StorageRootStat
    total_active_bytes: int
    warning_threshold_bytes: int
    hard_limit_bytes: int
    capacity_status: str
    read_only: bool = True
    actions: list[str] | None = None


def _iter_paths(root: Path) -> Iterable[Path]:
    for path in root.rglob('*'):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        yield path


def stat_root(path: str) -> StorageRootStat:
    root = Path(path).expanduser().resolve()
    errors: list[str] = []
    if not root.exists():
        return StorageRootStat(str(root), False, 0, 0, 0, [])
    total = 0
    files = 0
    dirs = 0
    for item in _iter_paths(root):
        try:
            if item.is_dir():
                dirs += 1
            elif item.is_file():
                files += 1
                total += item.stat().st_size
        except OSError as exc:
            errors.append(f'{item}: {exc}')
    return StorageRootStat(str(root), True, total, files, dirs, errors[:20])


def classify_capacity(total_bytes: int, warning_bytes: int = CONTROL_PLANE_WARNING_BYTES, hard_limit_bytes: int = CONTROL_PLANE_HARD_LIMIT_BYTES) -> str:
    if total_bytes > hard_limit_bytes:
        return 'above_hard_limit'
    if total_bytes >= warning_bytes:
        return 'warning_to_hard_limit'
    return 'below_warning'


def storage_audit(active_roots: list[str], archive_root: str = DEFAULT_ARCHIVE_ROOT, warning_bytes: int = CONTROL_PLANE_WARNING_BYTES, hard_limit_bytes: int = CONTROL_PLANE_HARD_LIMIT_BYTES) -> StorageAuditReport:
    """Return capacity-only storage statistics. No archive, move, delete, or graph mutation is performed."""
    root_stats = [stat_root(p) for p in active_roots]
    archive_stat = stat_root(archive_root)
    total_active = sum(s.bytes for s in root_stats)
    return StorageAuditReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mode='storage_audit_capacity_only',
        active_roots=root_stats,
        archive_root=archive_stat,
        total_active_bytes=total_active,
        warning_threshold_bytes=warning_bytes,
        hard_limit_bytes=hard_limit_bytes,
        capacity_status=classify_capacity(total_active, warning_bytes, hard_limit_bytes),
        read_only=True,
        actions=['stat_capacity_only', 'no_delete', 'no_move', 'no_archive_apply'],
    )


def raw_archive_proposal(active_roots: list[str], archive_root: str = DEFAULT_ARCHIVE_ROOT, hard_limit_bytes: int = CONTROL_PLANE_HARD_LIMIT_BYTES) -> dict:
    """Generate a proposal-only archive plan. It intentionally contains no executable move/delete commands."""
    audit = storage_audit(active_roots, archive_root=archive_root, hard_limit_bytes=hard_limit_bytes)
    return {
        'generated_at': audit.generated_at,
        'mode': 'raw_archive_proposal_only',
        'proposal_only': True,
        'applied': False,
        'human_approval_required_for_apply': True,
        'archive_root': audit.archive_root.path,
        'archive_root_exists': audit.archive_root.exists,
        'capacity_status': audit.capacity_status,
        'total_active_bytes': audit.total_active_bytes,
        'hard_limit_bytes': audit.hard_limit_bytes,
        'candidate_policy': [
            'capacity statistics only in storage-audit',
            'proposal may identify roots/classes but must not move raw files',
            'raw archive apply remains HUMAN_APPROVAL_REQUIRED',
            'no delete, no quarantine, no rehydrate, no graph/events mutation',
        ],
        'active_roots': [asdict(s) for s in audit.active_roots],
        'recommended_next_gate': 'HUMAN_APPROVAL_REQUIRED' if audit.capacity_status == 'above_hard_limit' else 'continue_AUTO_validation',
    }


def blocked_raw_archive_apply() -> dict:
    return {
        'allowed': False,
        'code': 'HUMAN_APPROVAL_REQUIRED',
        'reason': 'raw archive apply is destructive/relocating and is never executed by autopilot',
        'applied': False,
    }
