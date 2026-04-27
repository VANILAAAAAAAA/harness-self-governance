from __future__ import annotations

from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Any
from .schema import EvidenceCandidateSidecarRow, WeakAssociationSidecarRow, ValidationError
from .store import iter_jsonl
from .policy import looks_absolute_path

RAW_POINTER_FIELDS = {"candidate_ref", "source_path", "target_path", "raw_path", "path", "file", "uri"}

@dataclass
class RedactedEvidenceCandidateSidecarRow:
    object_id: str
    human_confirmation_required: bool
    upgrade_allowed: bool
    evidence_strength: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

def _is_pointer_key(key: Any) -> bool:
    normalized = str(key).lower()
    return normalized in RAW_POINTER_FIELDS or normalized.endswith("_path") or normalized.endswith("_ref")

FILE_URI_PREFIX = "file:" + "//"

def _is_private_pointer_value(value: str) -> bool:
    return FILE_URI_PREFIX in value.lower() or looks_absolute_path(value)

def _redact_raw_pointers(raw: Any) -> Any:
    """Return sidecar metadata with raw pointer fields and values removed.

    Sidecar rows are allowed to carry candidate/provenance pointers internally, but a
    redacted copy must be safe to serialize for diagnostics.  Keep only non-pointer
    gate/status fields and recursively drop common raw pointer field names
    fail-closed.  String values that look like absolute paths or file URIs are
    replaced so nested non-pointer metadata cannot leak private locations.
    """
    if isinstance(raw, dict):
        return {k: _redact_raw_pointers(v) for k, v in raw.items() if not _is_pointer_key(k)}
    if isinstance(raw, list):
        return [_redact_raw_pointers(v) for v in raw]
    if isinstance(raw, tuple):
        return tuple(_redact_raw_pointers(v) for v in raw)
    if isinstance(raw, str) and _is_private_pointer_value(raw):
        return "[REDACTED_PATH]"
    return raw

@dataclass
class SidecarIndex:
    evidence_candidates: list[EvidenceCandidateSidecarRow] = field(default_factory=list)
    weak_associations: list[WeakAssociationSidecarRow] = field(default_factory=list)
    by_object: dict[str, list[EvidenceCandidateSidecarRow]] = field(default_factory=lambda: defaultdict(list))
    weak_by_edge: dict[str, list[WeakAssociationSidecarRow]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_paths(cls, evidence_candidate_path: str | None = None, weak_association_path: str | None = None) -> "SidecarIndex":
        idx = cls()
        if evidence_candidate_path:
            for rec in iter_jsonl(evidence_candidate_path):
                row = EvidenceCandidateSidecarRow.from_record(rec)
                idx.evidence_candidates.append(row); idx.by_object[row.object_id].append(row)
        if weak_association_path:
            for rec in iter_jsonl(weak_association_path):
                row = WeakAssociationSidecarRow.from_record(rec)
                idx.weak_associations.append(row); idx.weak_by_edge[row.edge_id].append(row)
        return idx

    def candidates_for_object(self, object_id: str):
        return list(self.by_object.get(object_id, []))

    def weak_annotation_for_edge(self, edge_id: str):
        return list(self.weak_by_edge.get(edge_id, []))

    def validate_gates(self) -> dict:
        errors=[]
        for r in self.evidence_candidates:
            if not r.human_confirmation_required: errors.append(f"{r.object_id}: human_confirmation_required false")
            if r.upgrade_allowed: errors.append(f"{r.object_id}: upgrade_allowed true")
        for r in self.weak_associations:
            if not r.human_confirmation_required: errors.append(f"{r.edge_id}: human_confirmation_required false")
            if r.upgrade_allowed: errors.append(f"{r.edge_id}: upgrade_allowed true")
            if r.evidence_strength != "insufficient": errors.append(f"{r.edge_id}: evidence_strength not insufficient")
            if r.apply_status != "not_applied": errors.append(f"{r.edge_id}: apply_status not_applied required")
        return {"ok": not errors, "errors": errors, "counts": self.counts()}

    def counts(self) -> dict:
        return {
            "evidence_candidates": len(self.evidence_candidates),
            "weak_associations": len(self.weak_associations),
            "evidence_strength": dict(Counter(r.evidence_strength for r in self.evidence_candidates + self.weak_associations)),
        }

    def redacted_copy(self):
        # Public/debug-safe copy: no raw candidate_ref/source_path/target_path or
        # raw pointer fields are retained. Aggregate-only behavior belongs to export.
        idx = SidecarIndex()
        for r in self.evidence_candidates:
            row = RedactedEvidenceCandidateSidecarRow(
                object_id=r.object_id,
                human_confirmation_required=r.human_confirmation_required,
                upgrade_allowed=r.upgrade_allowed,
                evidence_strength=r.evidence_strength,
                raw=_redact_raw_pointers(r.raw),
            )
            idx.evidence_candidates.append(row)
            idx.by_object[row.object_id].append(row)
        for r in self.weak_associations:
            row = WeakAssociationSidecarRow(
                edge_id=r.edge_id,
                object_id=r.object_id,
                human_confirmation_required=r.human_confirmation_required,
                upgrade_allowed=r.upgrade_allowed,
                evidence_strength=r.evidence_strength,
                apply_status=r.apply_status,
                raw=_redact_raw_pointers(r.raw),
            )
            idx.weak_associations.append(row)
            idx.weak_by_edge[row.edge_id].append(row)
        return idx
