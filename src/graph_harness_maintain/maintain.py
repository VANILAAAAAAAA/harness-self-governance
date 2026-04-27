from __future__ import annotations

from .schema import FactorFinding
from .factors import evaluate_deletion_risk_guard


def analyze_cold_candidates(store, events=None, policy=None):
    return {"candidates": [n.id for n in store.nodes.values() if n.state == "cold"], "mutated": False}

def analyze_missing_provenance(store, sidecar=None, policy=None):
    missing=[]
    for n in store.nodes.values():
        if n.type in {"knowledge_claim", "wiki_page", "result"} and not store.provenance_edges(n.id, strict=True):
            missing.append({"node_id": n.id, "sidecar_candidates": len(sidecar.candidates_for_object(n.id)) if sidecar else 0, "strict_provenance": False})
    return {"missing": missing, "mutated": False}

def analyze_weak_association_sidecar(store, sidecar, policy=None):
    return {"weak_associations": len(sidecar.weak_associations), "annotation_only": True, "mutated": False}

def analyze_uncertain_causal_edges(store, policy=None):
    risks=[]
    for e in store.edges.values():
        if e.type == "caused_by" and not e.evidence_refs:
            risks.append(e.id)
    return {"causal_risk_edges": risks, "no_new_caused_by": True, "mutated": False}

def propose_quarantine(profile, constraints, store, sidecar=None, policy=None):
    candidates = [store.nodes[c] for c in constraints.get("candidate_ids", []) if c in store.nodes]
    finding = evaluate_deletion_risk_guard(candidates, store, policy)
    return {"profile": profile, "proposal_only": True, "allowed": not finding.hard_fail, "finding": finding.__dict__, "applied": False}

def propose_rehydration(tombstone_id, target_profile, store, policy=None):
    return {"tombstone_id": tombstone_id, "target_profile": target_profile, "proposal_only": True, "applied": False, "safety_regret_update": "described_only_no_mutation"}
