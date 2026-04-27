from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable
import json

DEFAULT_NODE_TYPES = {
    "profile","knowledge_raw","knowledge_claim","wiki_page","skill","tool","harness_module",
    "experiment","result","decision","factor","event","tombstone","export_summary","user_preference"
}
DEFAULT_EDGE_TYPES = {
    "profile_owns","profile_uses","profile_exports","profile_imports","governs","proposes_change","applies_change",
    "derived_from","cites","supports","refutes","contradicts","supersedes","depends_on","invokes","reads","writes",
    "caused_by","confounds","precedes","pruned_to","rehydrates"
}
DEFAULT_EVENT_TYPES = {"task_success","task_failure","tool_error","user_correction","rehydration","prune","quarantine","supersession","audit","export","proposal"}
DEFAULT_STATES = {"hot","warm","cold","quarantine","delete_candidate","deleted","pinned"}
DEFAULT_SENSITIVITY = {"none","internal","sensitive","phi_or_patient_level","credential"}
DEFAULT_DELETION_POLICIES = {"immutable","confirm","quarantine","delete_derivatives_only"}

class ValidationError(ValueError):
    pass

@dataclass(frozen=True)
class GraphSchema:
    version: str = "0.2.0"
    node_types: set[str] = field(default_factory=lambda: set(DEFAULT_NODE_TYPES))
    edge_types: set[str] = field(default_factory=lambda: set(DEFAULT_EDGE_TYPES))
    event_types: set[str] = field(default_factory=lambda: set(DEFAULT_EVENT_TYPES))
    states: set[str] = field(default_factory=lambda: set(DEFAULT_STATES))
    sensitivity_labels: set[str] = field(default_factory=lambda: set(DEFAULT_SENSITIVITY))
    deletion_policies: set[str] = field(default_factory=lambda: set(DEFAULT_DELETION_POLICIES))

    @classmethod
    def from_file(cls, path: str | None) -> "GraphSchema":
        if not path:
            return cls()
        text = open(path, "r", encoding="utf-8").read()
        data = _parse_tiny_yaml(text)
        return cls(
            version=str(data.get("version", "0.2.0")),
            node_types=set(data.get("node_types", DEFAULT_NODE_TYPES)),
            edge_types=set(data.get("edge_types", DEFAULT_EDGE_TYPES)),
            event_types=set(data.get("event_types", DEFAULT_EVENT_TYPES)),
            states=set(data.get("states", DEFAULT_STATES)),
            sensitivity_labels=set(data.get("sensitivity_labels", DEFAULT_SENSITIVITY)),
            deletion_policies=set(data.get("deletion_policies", DEFAULT_DELETION_POLICIES)),
        )

def _parse_tiny_yaml(text: str) -> dict[str, Any]:
    """Parse the simple schema YAML used by this adapter; JSON is also accepted."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    out: dict[str, Any] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, val = line.split(":", 1)
            key = key.strip(); val = val.strip()
            current = key
            if val.startswith("[") and val.endswith("]"):
                out[key] = [x.strip() for x in val[1:-1].split(",") if x.strip()]
            elif val:
                out[key] = val.strip('"')
            else:
                out[key] = []
        elif current and line.strip().startswith("-"):
            out.setdefault(current, []).append(line.strip()[1:].strip())
    return out

@dataclass
class GraphNode:
    id: str
    type: str
    label: str = ""
    profile_scope: str = ""
    path: str | None = None
    state: str = "warm"
    owner: str = "agent"
    sensitivity: str = "internal"
    deletion_policy: str = "confirm"
    summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    weight: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, rec: dict[str, Any], schema: GraphSchema) -> "GraphNode":
        rid = str(rec.get("id", ""))
        if not rid: raise ValidationError("node missing id")
        typ = str(rec.get("type", ""))
        if typ not in schema.node_types: raise ValidationError(f"{rid}: invalid node type {typ}")
        scope = str(rec.get("profile_scope", ""))
        if not scope: raise ValidationError(f"{rid}: missing profile_scope")
        sens = str(rec.get("sensitivity", "internal"))
        if sens not in schema.sensitivity_labels: raise ValidationError(f"{rid}: invalid sensitivity {sens}")
        pol = str(rec.get("deletion_policy", "confirm"))
        if pol not in schema.deletion_policies: raise ValidationError(f"{rid}: invalid deletion_policy {pol}")
        state = str(rec.get("state", "warm"))
        if state not in schema.states: raise ValidationError(f"{rid}: invalid state {state}")
        known = {"record_type","id","type","label","profile_scope","path","state","owner","sensitivity","deletion_policy","summary","evidence_refs","weight"}
        return cls(rid, typ, str(rec.get("label", rid)), scope, rec.get("path"), state, str(rec.get("owner", "agent")), sens, pol, str(rec.get("summary", "")), list(rec.get("evidence_refs", [])), dict(rec.get("weight", {})), {k:v for k,v in rec.items() if k not in known})

@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    type: str
    profile_scope: str = ""
    confidence: float = 0.0
    evidence_refs: list[str] = field(default_factory=list)
    weight: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, rec: dict[str, Any], schema: GraphSchema) -> "GraphEdge":
        rid = str(rec.get("id", ""))
        if not rid: raise ValidationError("edge missing id")
        typ = str(rec.get("type", ""))
        if typ not in schema.edge_types: raise ValidationError(f"{rid}: invalid edge type {typ}")
        src = str(rec.get("source", "")); tgt = str(rec.get("target", ""))
        if not src or not tgt: raise ValidationError(f"{rid}: missing endpoint")
        scope = str(rec.get("profile_scope", ""))
        if not scope: raise ValidationError(f"{rid}: missing profile_scope")
        if typ == "caused_by" and not rec.get("evidence_refs"):
            raise ValidationError(f"{rid}: caused_by requires evidence_refs")
        known = {"record_type","id","source","target","type","profile_scope","confidence","evidence_refs","weight"}
        return cls(rid, src, tgt, typ, scope, float(rec.get("confidence", 0.0) or 0.0), list(rec.get("evidence_refs", [])), dict(rec.get("weight", {})), {k:v for k,v in rec.items() if k not in known})

@dataclass
class GraphEvent:
    id: str
    type: str
    profile: str
    task: str = ""
    used_nodes: list[str] = field(default_factory=list)
    changed_nodes: list[str] = field(default_factory=list)
    changed_edges: list[str] = field(default_factory=list)
    outcome: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    notes: str = ""

    @classmethod
    def from_record(cls, rec: dict[str, Any], schema: GraphSchema) -> "GraphEvent":
        rid = str(rec.get("id", "")); typ = str(rec.get("type", ""))
        if not rid: raise ValidationError("event missing id")
        if typ not in schema.event_types: raise ValidationError(f"{rid}: invalid event type {typ}")
        return cls(rid, typ, str(rec.get("profile", rec.get("profile_scope", ""))), str(rec.get("task", "")), list(rec.get("used_nodes", [])), list(rec.get("changed_nodes", [])), list(rec.get("changed_edges", [])), dict(rec.get("outcome", {})), str(rec.get("timestamp", "")), str(rec.get("notes", "")))

@dataclass
class Tombstone:
    id: str; profile: str; original_path: str; quarantine_path: str; content_hash: str; reason: str; source_node: str; created_at: str; restore_command: str; deletion_policy: str = "quarantine"; sensitivity: str = "internal"; human_confirmation_required: bool = True

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> "Tombstone":
        missing = [k for k in ["id","profile","original_path","content_hash","reason","restore_command"] if not rec.get(k)]
        if missing: raise ValidationError(f"tombstone missing {missing}")
        return cls(str(rec["id"]), str(rec["profile"]), str(rec["original_path"]), str(rec.get("quarantine_path", "")), str(rec["content_hash"]), str(rec["reason"]), str(rec.get("source_node", "")), str(rec.get("created_at", "")), str(rec["restore_command"]), str(rec.get("deletion_policy", "quarantine")), str(rec.get("sensitivity", "internal")), bool(rec.get("human_confirmation_required", True)))

@dataclass
class EvidenceCandidateSidecarRow:
    object_id: str
    candidate_ref: str
    human_confirmation_required: bool
    upgrade_allowed: bool
    evidence_strength: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> "EvidenceCandidateSidecarRow":
        row = cls(str(rec.get("object_id", rec.get("missing_object_id", rec.get("id", "")))), str(rec.get("candidate_ref", "")), bool(rec.get("human_confirmation_required", False)), bool(rec.get("upgrade_allowed", True)), str(rec.get("evidence_strength", "")), dict(rec))
        if not row.human_confirmation_required: raise ValidationError(f"{row.object_id}: human_confirmation_required must be true")
        if row.upgrade_allowed: raise ValidationError(f"{row.object_id}: upgrade_allowed must be false")
        return row

@dataclass
class WeakAssociationSidecarRow:
    edge_id: str
    object_id: str
    human_confirmation_required: bool
    upgrade_allowed: bool
    evidence_strength: str
    apply_status: str
    raw: dict[str, Any] = field(default_factory=dict)
    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> "WeakAssociationSidecarRow":
        row = cls(str(rec.get("edge_id", "")), str(rec.get("object_id", rec.get("target_object_id", ""))), bool(rec.get("human_confirmation_required", False)), bool(rec.get("upgrade_allowed", True)), str(rec.get("evidence_strength", "")), str(rec.get("apply_status", "")), dict(rec))
        if not row.human_confirmation_required: raise ValidationError(f"{row.edge_id}: human_confirmation_required must be true")
        if row.upgrade_allowed: raise ValidationError(f"{row.edge_id}: upgrade_allowed must be false")
        if row.evidence_strength != "insufficient": raise ValidationError(f"{row.edge_id}: weak evidence_strength must be insufficient")
        if row.apply_status != "not_applied": raise ValidationError(f"{row.edge_id}: weak apply_status must be not_applied")
        return row

@dataclass
class FactorFinding:
    name: str; status: str; hard_fail: bool = False; messages: list[str] = field(default_factory=list); score_delta: float = 0.0

@dataclass
class PolicyDecision:
    allowed: bool; reason: str; code: str = "ok"

@dataclass
class Subgraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[str, GraphEdge] = field(default_factory=dict)
    annotations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    explanation: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [asdict(n) for n in self.nodes.values()], "edges": [asdict(e) for e in self.edges.values()], "annotations": self.annotations, "explanation": self.explanation}

@dataclass
class ScoreReport:
    status: str; score: float; findings: list[FactorFinding] = field(default_factory=list); details: dict[str, Any] = field(default_factory=dict)

@dataclass
class ExportSummary:
    profile: str; schema_version: str; graph_health: dict[str, Any]; sidecar: dict[str, Any]; policy_blocks: list[str] = field(default_factory=list)
