from __future__ import annotations

import json

from graph_harness_maintain.evidence import build_evidence_index


def test_required_claims_are_generated() -> None:
    stage_results = {
        "identity": {"status": "PASS", "path": "artifacts/v1/identity-check.json"},
        "git_state": {"status": "PASS", "path": "artifacts/v1/git-state.json"},
        "release_audit": {"status": "PASS", "path": "artifacts/v1/open-source-surface.json"},
        "gates": {"status": "PASS", "path": "artifacts/v1/approval-gate-check.json"},
        "tests": {"status": "PASS", "path": "artifacts/v1/test-results.json"},
        "smoke": {"status": "PASS", "path": "artifacts/v1/smoke-tests.json"},
        "leak_scan": {"status": "PASS", "path": "artifacts/v1/leak-scan.json"},
        "provenance": {"status": "PASS", "path": "artifacts/v1/provenance/current-state.json"},
        "report": {"status": "PASS", "path": "artifacts/v1/v1-local-rc-report.md"},
    }
    evidence = build_evidence_index(stage_results)
    claims = {item["claim"] for item in evidence["claims"]}
    assert "Git identity is user-owned" in claims
    assert "pipeline report generated" in claims


def test_each_claim_has_required_fields() -> None:
    evidence = build_evidence_index({})
    claim = evidence["claims"][0]
    assert {"id", "claim", "status", "category", "evidence"}.issubset(claim)
    assert isinstance(claim["evidence"], list)


def test_evidence_json_is_serializable() -> None:
    evidence = build_evidence_index({})
    payload = json.dumps(evidence, sort_keys=True)
    assert payload.startswith("{")
