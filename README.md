# graph-harness-maintain

**Status:** pre-release / v1.0 in progress.

`graph-harness-maintain` is a graph-governed, read-only maintenance adapter for agent harnesses. The v1.0 goal is to validate a graph-harness control plane, retrieve small dependency-closed subgraphs, produce sanitized dry-run exports, and generate storage/archive proposals without applying destructive changes.

## v1.0 safety contract

This project is intentionally conservative:

- read-only by default;
- proposal-only for archive planning;
- no apply execution;
- no delete execution;
- no quarantine execution;
- no rehydrate execution;
- no provenance upgrade execution;
- no `caused_by` generation;
- no graph/event mutation;
- no prompt assembly takeover;
- no daemon, database service, or vector store.

The adapter can load graph-harness records such as `graph.jsonl`, `events.jsonl`, schema files, and sidecar indexes for validation and review, but it must not modify them.

## CLI surface

The public v1.0 CLI is limited to read-only or proposal-only commands:

```bash
graph-harness-maintain validate --schema tests/fixtures/synthetic_schema.yaml --graph tests/fixtures/synthetic_graph.jsonl --events tests/fixtures/synthetic_events.jsonl --evidence-candidates tests/fixtures/synthetic_evidence_candidate_index.jsonl --weak-associations tests/fixtures/synthetic_weak_association_sidecar_index.jsonl

graph-harness-maintain inspect --schema tests/fixtures/synthetic_schema.yaml --graph tests/fixtures/synthetic_graph.jsonl --events tests/fixtures/synthetic_events.jsonl

graph-harness-maintain retrieve --task "structured transform" --profile lab --schema tests/fixtures/synthetic_schema.yaml --graph tests/fixtures/synthetic_graph.jsonl --events tests/fixtures/synthetic_events.jsonl --out artifacts/subgraph.json

graph-harness-maintain export-sanitized-dry-run --profile lab --schema tests/fixtures/synthetic_schema.yaml --graph tests/fixtures/synthetic_graph.jsonl --events tests/fixtures/synthetic_events.jsonl --out artifacts/export.json

graph-harness-maintain storage-audit --active-root . --archive-root "$ARCHIVE_ROOT" --out artifacts/storage_audit.json

graph-harness-maintain raw-archive-proposal --active-root . --archive-root "$ARCHIVE_ROOT" --out artifacts/raw_archive_proposal.json
```

`storage-audit` reports capacity statistics only. `raw-archive-proposal` writes a proposal only. There is no public v1.0 CLI command that applies raw archive actions.

## Development checks

```bash
uv run --with pytest pytest -q
python3 scripts/release_leak_scan.py --out artifacts/release_leak_scan.json
python3 scripts/package_build_check.py --out artifacts/package_build_check.json
```

All examples use synthetic fixtures. Public exports redact absolute paths and aggregate sidecar information.

## Documentation

- [Architecture](docs/architecture.md)
- [Quickstart](docs/quickstart.md)
- [Safety model](docs/safety-model.md)
- [Storage guard](docs/storage-guard.md)
- [Roadmap](docs/roadmap.md)

## Roadmap summary

- **v1.0:** read-only graph-governed maintenance adapter; validation, inspection, retrieval, sanitized dry-run export, storage audit, and archive proposal generation.
- **v1.1:** stronger schema diagnostics, richer report formatting, and safer packaging ergonomics while preserving read-only/proposal-only boundaries.
- **v2.0:** optional apply workflows may be designed, but only behind explicit policy gates, independent review, provenance manifests, and human approval.

## License

MIT. See [LICENSE](LICENSE).
