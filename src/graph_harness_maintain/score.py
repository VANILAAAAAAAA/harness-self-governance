from __future__ import annotations

from .schema import Subgraph, ScoreReport
from .factors import evaluate_all
from .policy import Policy
from .store import GraphStore

WEIGHT_KEYS = ["utility","recency","centrality","evidence_quality","success_contribution","user_pin","safety_regret","volatility","redundancy","storage_cost","context_cost","deletion_risk"]
EDGE_WEIGHT_KEYS = ["strength","confidence","criticality","recency","causal_strength","dependency_strength","retrieval_value","safety_criticality","traversal_cost"]

def score_node(node, event_features=None, query_terms=None, policy=None) -> float:
    w = node.weight or {}
    positive = sum(float(w.get(k, 0.0) or 0.0) for k in WEIGHT_KEYS[:7])
    negative = sum(float(w.get(k, 0.0) or 0.0) for k in WEIGHT_KEYS[7:])
    text = " ".join([node.id, node.label, node.summary, node.path or ""]).lower()
    rel = sum(1 for t in (query_terms or []) if t and t.lower() in text)
    return positive - negative + rel

def score_edge(edge, event_features=None, policy=None) -> float:
    w = edge.weight or {}
    return float(w.get("strength", edge.confidence) or 0.0) + float(w.get("criticality", 0.0) or 0.0) + float(w.get("dependency_strength", 0.0) or 0.0) + float(w.get("retrieval_value", 0.0) or 0.0) - float(w.get("traversal_cost", 0.0) or 0.0)

def score_subgraph(subgraph: Subgraph, task: str, profile: str, store: GraphStore, sidecar=None, policy: Policy | None = None, budget: int = 40) -> ScoreReport:
    policy = policy or Policy(profile=profile)
    terms = [t for t in task.lower().replace(":", " ").replace("/", " ").split() if len(t) > 2]
    base = sum(score_node(n, query_terms=terms, policy=policy) for n in subgraph.nodes.values()) + sum(score_edge(e, policy=policy) for e in subgraph.edges.values())
    findings = evaluate_all(subgraph, store, sidecar, policy, budget)
    total = base + sum(f.score_delta for f in findings)
    blocked = any(f.hard_fail for f in findings)
    return ScoreReport("blocked" if blocked else "ok", total, findings, {"node_count": len(subgraph.nodes), "edge_count": len(subgraph.edges), "task": task})
