from __future__ import annotations

from .schema import Subgraph, FactorFinding, GraphNode
from .store import GraphStore, DEPENDENCY_EDGE_TYPES, STRICT_PROVENANCE_EDGE_TYPES
from .policy import Policy, SENSITIVE_LABELS

PROVENANCE_REQUIRED_NODE_TYPES = {"knowledge_claim", "wiki_page", "result"}

def evaluate_dependency_closure(subgraph: Subgraph, store: GraphStore, policy: Policy | None = None) -> FactorFinding:
    missing=[]
    for n in subgraph.nodes.values():
        for e in store.dependency_edges(n.id):
            if e.target not in subgraph.nodes:
                missing.append(f"{n.id} missing {e.type}->{e.target}")
    return FactorFinding("dependency_closure", "fail" if missing else "pass", bool(missing), missing, -10.0 if missing else 1.0)

def evaluate_provenance_integrity(subgraph: Subgraph, store: GraphStore, sidecar=None, policy: Policy | None = None) -> FactorFinding:
    missing=[]
    for n in subgraph.nodes.values():
        if n.type in PROVENANCE_REQUIRED_NODE_TYPES:
            strict = [e for e in store.provenance_edges(n.id, strict=True) if e.target in subgraph.nodes or e.target in store.nodes]
            if not strict:
                missing.append(f"{n.id} missing strict graph provenance; sidecar annotations do not satisfy this")
    return FactorFinding("provenance_integrity", "fail" if missing else "pass", bool(missing), missing, -10.0 if missing else 1.0)

def evaluate_profile_boundary(subgraph: Subgraph, policy: Policy) -> FactorFinding:
    blocks=[]
    for n in subgraph.nodes.values():
        dec = policy.check_export_node(n) if policy.export_scope == "public" else None
        if dec and not dec.allowed: blocks.append(dec.reason)
    return FactorFinding("profile_boundary", "fail" if blocks else "pass", bool(blocks), blocks, -10.0 if blocks else 1.0)

def evaluate_causal_guard(subgraph: Subgraph, store: GraphStore, policy: Policy | None = None) -> FactorFinding:
    problems=[]
    for e in subgraph.edges.values():
        if e.type == "caused_by":
            required = ["mechanism", "temporal_precedence", "confounder_check"]
            if not e.evidence_refs or not all(e.extra.get(k) for k in required):
                problems.append(f"{e.id}: caused_by lacks required causal evidence metadata")
    return FactorFinding("causal_guard", "fail" if problems else "pass", bool(problems), problems, -10.0 if problems else 0.0)

def evaluate_experiment_chain_integrity(subgraph: Subgraph, store: GraphStore, policy: Policy | None = None) -> FactorFinding:
    warnings=[]
    for n in subgraph.nodes.values():
        if n.type == "experiment" and n.state in {"hot", "pinned"}:
            outs = store.neighbors(n.id, {"precedes", "depends_on", "reads"}, "out")
            if not outs: warnings.append(f"{n.id}: active experiment has no explicit chain edge")
    return FactorFinding("experiment_chain_integrity", "warn" if warnings else "pass", False, warnings, -1.0 if warnings else 0.0)

def evaluate_rehydration_regret(subgraph: Subgraph, store: GraphStore, events, policy: Policy | None = None) -> FactorFinding:
    count=0
    for e in events or []:
        if getattr(e, "type", "") == "rehydration": count += len(e.outcome.get("rehydrated_nodes", []))
    return FactorFinding("rehydration_regret", "pass", False, [f"rehydration events observed: {count}"], float(count))

def evaluate_deletion_risk_guard(candidates: list[GraphNode], store: GraphStore, policy: Policy | None = None) -> FactorFinding:
    blocks=[]
    for n in candidates:
        if n.type == "knowledge_raw" or n.sensitivity in SENSITIVE_LABELS or n.deletion_policy == "immutable":
            blocks.append(f"{n.id}: delete/quarantine risk blocked")
    return FactorFinding("deletion_risk_guard", "fail" if blocks else "pass", bool(blocks), blocks, -10.0 if blocks else 0.0)

def evaluate_cost_budget(subgraph: Subgraph, policy: Policy | None = None, budget: int = 40) -> FactorFinding:
    total = len(subgraph.nodes) + len(subgraph.edges)
    if total > budget:
        return FactorFinding("cost_budget", "warn", False, [f"subgraph items {total} exceed budget {budget}; closure preserved"], -1.0)
    return FactorFinding("cost_budget", "pass", False, [], 1.0)

def evaluate_all(subgraph: Subgraph, store: GraphStore, sidecar, policy: Policy, budget: int = 40) -> list[FactorFinding]:
    return [
        evaluate_dependency_closure(subgraph, store, policy),
        evaluate_provenance_integrity(subgraph, store, sidecar, policy),
        evaluate_profile_boundary(subgraph, policy),
        evaluate_causal_guard(subgraph, store, policy),
        evaluate_experiment_chain_integrity(subgraph, store, policy),
        evaluate_rehydration_regret(subgraph, store, store.events, policy),
        evaluate_cost_budget(subgraph, policy, budget),
    ]
