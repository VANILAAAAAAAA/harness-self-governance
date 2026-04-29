# Changelog

## Unreleased

- No unreleased changes. v2.0 feature scope is frozen pending final review.

## 2.0.0 - 2026-04-28

### Added

- Dual Graph Architecture with a repo-wide Governance Graph and an Agent Memory Graph for graph-governed context loading.
- Profile / Project / Lineage model with `general` as the governance hub, `ehrlab` as a domain profile, and exact lineage mapping for Logs navigation.
- Portable `agent-graph` CLI commands for `init-repo`, `bootstrap`, `validate`, `archive-session`, `export`, `build-index`, `route`, `traverse`, `capture-update`, `list-gaps`, `archive-gate`, `maintenance`, and `triggers`.
- Graph + Logs dashboard with Governance Graph default view, Memory Graph visibility, Router observability, and lineage-backed artifact browsing.
- Manual archive bootstrap fixtures under `docs/examples/agent-memory-graph/harness-self-governance/` as curated `compiled-session` gold examples.
- Archive Lifecycle Governance reports and proposal-only maintenance flow.
- Recommendation-only Archive Trigger Policy with deterministic report projection to `artifacts/v2/maintenance/archive-trigger-report.json`.

### Changed

- Promoted package metadata and runtime versioning from the v1.1 baseline to `2.0.0`.
- Updated README and architecture docs to describe the frozen v2.0 scope: Graph + Logs only, local-first, no backend, no Hub-side LLM API, no model/provider UI, and no auto archival.

### Safety and scope

- Raw sessions remain local-only source material and explicit forensic-only fallback context.
- Trigger policy remains recommendation-only: `archive_auto_apply_enabled = false`, manual archive review required.
- No destructive apply, no graph mutation execution, no sensitive export, and no generated `artifacts/v2/` outputs committed.

## 1.1.0

- Hardened v1.1 release readiness, packaging metadata, README guidance, and CI defaults.
- Added v1.1 reviewed proposal baseline with proposal validation, template validation, adapter reporting, local-test provenance append, and separated `artifacts/v1.1/` outputs.

## 1.0.0

- Added v1.0 local governance pipeline.
