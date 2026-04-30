from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json

DEFAULT_RAW_READ_POLICY = "evidence_deepening_only"
EVIDENCE_DEPTHS = ("none", "anchor", "excerpt", "raw-span")


def evidence_index_candidates(repo_root: Path, profile_id: str, project_id: str) -> list[Path]:
    examples = repo_root / "docs" / "examples" / "agent-memory-graph"
    return [
        examples / f"{profile_id}-{project_id}" / "raw-evidence-index.jsonl",
        examples / f"{profile_id}-{project_id}" / "raw-evidence-index.json",
        examples / project_id / "raw-evidence-index.jsonl",
        examples / project_id / "raw-evidence-index.json",
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    if not path.exists():
        return anchors
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            anchors.append(item)
    return anchors


def load_raw_evidence_index(repo_root: Path | str, profile_id: str, project_id: str) -> list[dict[str, Any]]:
    repo_root = Path(repo_root).resolve()
    for path in evidence_index_candidates(repo_root, profile_id, project_id):
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            return _read_jsonl(path)
        payload = read_json(path, default={})
        anchors = payload.get("anchors", [])
        return [item for item in anchors if isinstance(item, dict)]
    return []


def _text_tokens(text: str) -> set[str]:
    import re
    return {tok for tok in re.split(r"[^a-z0-9一-龥]+", text.lower()) if len(tok) >= 2}


def _anchor_text(anchor: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("anchor_id", "project", "profile", "span_type", "safe_excerpt", "summary"):
        value = anchor.get(key)
        if value:
            parts.append(str(value))
    for key in ("claim_ids", "tags"):
        value = anchor.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    return "\n".join(parts)


def select_raw_evidence_anchors(
    anchors: list[dict[str, Any]],
    query: str,
    *,
    evidence_depth: str = "anchor",
    max_anchors: int = 4,
    allow_raw_span: bool = False,
) -> dict[str, Any]:
    """Select small raw evidence anchors without reading historical raw sessions by default.

    depth semantics:
    - none: return no anchors.
    - anchor: return metadata only; no excerpt/raw text.
    - excerpt: include pre-redacted safe_excerpt stored in the anchor index.
    - raw-span: only returns raw_span_requests when allow_raw_span is true; the caller still
      must explicitly fetch the referenced raw span outside the default retriever.
    """
    if evidence_depth not in EVIDENCE_DEPTHS:
        return {"status": "FAIL", "anchors": [], "warnings": [], "blockers": [f"unsupported evidence_depth: {evidence_depth}"]}
    if evidence_depth == "none" or not anchors:
        return {"status": "PASS", "anchors": [], "raw_span_requests": [], "warnings": [], "blockers": []}

    q_tokens = _text_tokens(query)
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for anchor in anchors:
        if str(anchor.get("read_policy", DEFAULT_RAW_READ_POLICY)) not in {DEFAULT_RAW_READ_POLICY, "forensic_only", "explicit_forensic_only"}:
            continue
        text = _anchor_text(anchor)
        overlap = q_tokens & _text_tokens(text)
        score = len(overlap) * 10
        if str(anchor.get("span_type", "")) in {"decision", "requirement", "constraint", "implementation", "evidence"}:
            score += 3
        anchor_id = str(anchor.get("anchor_id", ""))
        if anchor_id:
            scored.append((score, anchor_id, anchor))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [item[2] for item in scored[:max_anchors] if item[0] > 0]
    if not selected:
        selected = [item[2] for item in scored[: min(max_anchors, 2)]]

    projected: list[dict[str, Any]] = []
    raw_span_requests: list[dict[str, Any]] = []
    for anchor in selected:
        item = {
            "anchor_id": anchor.get("anchor_id"),
            "profile": anchor.get("profile"),
            "project": anchor.get("project"),
            "source_session_id": anchor.get("source_session_id"),
            "claim_ids": anchor.get("claim_ids", []),
            "span_type": anchor.get("span_type"),
            "message_range": anchor.get("message_range"),
            "read_policy": anchor.get("read_policy", DEFAULT_RAW_READ_POLICY),
            "sensitivity": anchor.get("sensitivity", "internal"),
        }
        if evidence_depth in {"excerpt", "raw-span"}:
            item["safe_excerpt"] = anchor.get("safe_excerpt", "")
        if evidence_depth == "raw-span":
            request = {
                "anchor_id": anchor.get("anchor_id"),
                "raw_path": anchor.get("raw_path"),
                "message_range": anchor.get("message_range"),
                "read_policy": anchor.get("read_policy", DEFAULT_RAW_READ_POLICY),
            }
            if allow_raw_span:
                raw_span_requests.append(request)
            else:
                item["raw_span_blocked"] = True
        projected.append(item)

    warnings: list[str] = []
    blockers: list[str] = []
    if evidence_depth == "raw-span" and not allow_raw_span:
        blockers.append("raw-span evidence requires forensic budget plus explicit discovery marker; no historical raw session was read")
    return {"status": "PASS", "anchors": projected, "raw_span_requests": raw_span_requests, "warnings": warnings, "blockers": blockers}


def write_raw_evidence_index(path: Path | str, anchors: list[dict[str, Any]]) -> Path:
    """Write a deterministic JSON raw-evidence index for tests/examples."""
    payload = {"schema_version": SCHEMA_VERSION, "index_type": "raw_evidence_anchor_index", "anchors": anchors}
    return deterministic_write_json(path, payload)
