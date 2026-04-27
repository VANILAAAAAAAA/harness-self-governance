# Quickstart

## Install for local development

```bash
uv sync
```

If you do not use `uv`, create a Python 3.10+ environment and install the project in editable mode with your preferred tooling.

## Run tests

```bash
uv run --with pytest pytest -q
```

## Validate synthetic fixtures

```bash
uv run graph-harness-maintain validate \
  --schema tests/fixtures/synthetic_schema.yaml \
  --graph tests/fixtures/synthetic_graph.jsonl \
  --events tests/fixtures/synthetic_events.jsonl \
  --evidence-candidates tests/fixtures/synthetic_evidence_candidate_index.jsonl \
  --weak-associations tests/fixtures/synthetic_weak_association_sidecar_index.jsonl
```

## Retrieve a minimal subgraph

```bash
uv run graph-harness-maintain retrieve \
  --task "structured transform" \
  --profile lab \
  --schema tests/fixtures/synthetic_schema.yaml \
  --graph tests/fixtures/synthetic_graph.jsonl \
  --events tests/fixtures/synthetic_events.jsonl \
  --out artifacts/subgraph.json
```

## Generate a sanitized dry-run export

```bash
uv run graph-harness-maintain export-sanitized-dry-run \
  --profile lab \
  --schema tests/fixtures/synthetic_schema.yaml \
  --graph tests/fixtures/synthetic_graph.jsonl \
  --events tests/fixtures/synthetic_events.jsonl \
  --out artifacts/export.json
```

Do not use real raw datasets in examples. Use synthetic fixtures only.
