from __future__ import annotations

from collections import deque
from .schema import Subgraph
from .store import GraphStore, DEPENDENCY_EDGE_TYPES, STRICT_PROVENANCE_EDGE_TYPES
from .policy import Policy
from .score import score_subgraph


def lexical_seed_nodes(task: str, profile: str, store: GraphStore, limit: int = 10):
    terms = [t for t in task.lower().replace("_", " ").replace("-", " ").split() if len(t) > 2]
    scored=[]
    for n in store.iter_nodes():
        if n.profile_scope not in {profile, "shared"}: continue
        text = " ".join([n.id, n.type, n.label, n.summary, n.path or ""]).lower()
        s = sum(1 for t in terms if t in text)
        if s: scored.append((s, n.id))
    return [store.nodes[i] for _, i in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]

def expand_dependency_closure(seed_nodes, store: GraphStore, required_edge_types: set[str] | None = None, max_depth: int = 20):
    required_edge_types = required_edge_types or DEPENDENCY_EDGE_TYPES
    included = {n.id for n in seed_nodes}; edges={}; q=deque((n.id, 0) for n in seed_nodes); missing=[]
    while q:
        node_id, depth = q.popleft()
        if depth >= max_depth: continue
        for e in store.neighbors(node_id, required_edge_types, "out"):
            edges[e.id] = e
            if e.target not in store.nodes:
                missing.append(f"{e.id}: missing dependency target {e.target}"); continue
            if e.target not in included:
                included.add(e.target); q.append((e.target, depth+1))
    return included, edges, missing

def attach_strict_provenance(subgraph: Subgraph, store: GraphStore, sidecar=None, policy: Policy | None = None):
    added=[]
    for node_id in list(subgraph.nodes):
        for e in store.provenance_edges(node_id, strict=True):
            if e.target in store.nodes:
                subgraph.edges[e.id] = e; subgraph.nodes.setdefault(e.target, store.nodes[e.target]); added.append(e.id)
            # weak_association sidecar is deliberately not traversed here.
    if sidecar:
        for e in list(subgraph.edges.values()):
            anns = sidecar.weak_annotation_for_edge(e.id)
            if anns:
                subgraph.annotations.setdefault(e.id, []).extend([{"kind":"weak_association_annotation","evidence_strength": a.evidence_strength, "apply_status": a.apply_status} for a in anns])
        for n in list(subgraph.nodes):
            cands = sidecar.candidates_for_object(n)
            if cands:
                subgraph.annotations.setdefault(n, []).extend([{"kind":"evidence_candidate_annotation","evidence_strength": c.evidence_strength} for c in cands])
    return {"strict_provenance_edges_added": added}

def retrieve_minimal_subgraph(task: str, profile: str, budget: int, store: GraphStore, sidecar=None, policy: Policy | None = None) -> tuple[Subgraph, object]:
    policy = policy or Policy(profile=profile)
    seeds = lexical_seed_nodes(task, profile, store)
    node_ids, dep_edges, missing = expand_dependency_closure(seeds, store)
    sg = Subgraph(nodes={i: store.nodes[i] for i in sorted(node_ids) if i in store.nodes}, edges={i:e for i,e in dep_edges.items()}, explanation={"seed_nodes": [n.id for n in seeds], "missing_dependencies": missing})
    prov = attach_strict_provenance(sg, store, sidecar, policy)
    sg.explanation.update(prov)
    report = score_subgraph(sg, task, profile, store, sidecar, policy, budget)
    sg.explanation["score_status"] = report.status
    return sg, report

def explain_retrieval(subgraph: Subgraph, score_report) -> dict:
    return {"subgraph": subgraph.explanation, "score": score_report.details, "findings": [f.__dict__ for f in score_report.findings]}
