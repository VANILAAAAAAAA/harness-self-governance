from __future__ import annotations

from typing import Any

from .schemas import SCHEMA_VERSION

ARCHIVE_POLICY = {
    "new_information": "capture_pending_update",
    "retrieval_miss": "record_context_gap",
    "raw_sessions": "explicit_forensic_only",
}


def build_context_packet(
    profile_id: str,
    project_id: str,
    intent: str,
    budget: str,
    primary_context: list[dict[str, Any]] | None = None,
    optional_context: list[dict[str, Any]] | None = None,
    traversal_nodes: list[str] | None = None,
    traversal_edges: list[str] | None = None,
    raw_sessions_allowed: bool = False,
    routing_reason: str = "graph_traversal_context_routing",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": profile_id,
        "project": project_id,
        "intent": intent,
        "budget": budget,
        "primary_context": primary_context or [],
        "optional_context": optional_context or [],
        "traversal_nodes": traversal_nodes or [],
        "traversal_edges": traversal_edges or [],
        "do_not_read_by_default": ["sessions/raw/"],
        "raw_sessions_allowed": raw_sessions_allowed,
        "routing_reason": routing_reason,
        "archive_policy": dict(ARCHIVE_POLICY),
    }
