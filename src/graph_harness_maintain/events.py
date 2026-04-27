from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from .schema import GraphSchema, GraphEvent, ValidationError
from .store import iter_jsonl


def load_events(path: str, schema_path: str | None = None) -> list[GraphEvent]:
    schema = GraphSchema.from_file(schema_path)
    return [GraphEvent.from_record(r, schema) for r in iter_jsonl(path)]

def validate_event_log(events: list[GraphEvent]) -> dict:
    ids = set(); errors=[]
    for e in events:
        if e.id in ids: errors.append(f"duplicate event id {e.id}")
        ids.add(e.id)
    return {"ok": not errors, "errors": errors, "counts": dict(Counter(e.type for e in events))}

def event_features(events: list[GraphEvent]) -> dict:
    node_usage = Counter(); rehydrations=Counter(); failures=0; corrections=0
    for e in events:
        for n in e.used_nodes: node_usage[n] += 1
        if e.type == "rehydration":
            for n in e.outcome.get("rehydrated_nodes", []): rehydrations[n] += 1
        failures += int(e.type == "task_failure" or not e.outcome.get("success", True))
        corrections += int(e.type == "user_correction" or e.outcome.get("user_correction", False))
    return {"node_usage": dict(node_usage), "rehydrations": dict(rehydrations), "failures": failures, "user_corrections": corrections}

def propose_event(event_type: str, profile: str, task: str, used_nodes=None, changed_nodes=None, changed_edges=None, outcome=None, notes: str = "") -> GraphEvent:
    schema = GraphSchema()
    if event_type not in schema.event_types:
        raise ValidationError(f"invalid event type {event_type}")
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return GraphEvent(f"event:{ts}:{event_type}", event_type, profile, task, list(used_nodes or []), list(changed_nodes or []), list(changed_edges or []), dict(outcome or {}), ts, notes)
