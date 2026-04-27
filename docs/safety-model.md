# Safety model

## v1.0 command boundary

Allowed public commands:

- `validate`
- `inspect`
- `retrieve`
- `export-sanitized-dry-run`
- `storage-audit`
- `raw-archive-proposal`

These commands are read-only or proposal-only.

## Explicitly out of scope

v1.0 does not execute:

- apply;
- delete;
- quarantine;
- rehydrate;
- raw archive apply;
- provenance upgrade;
- graph/events mutation;
- release publish.

## Sanitization

Public exports redact local absolute paths and deny sensitive labels such as credentials or patient-level records. Sidecar records are allowed to contain internal pointer fields while loaded, but serialized diagnostic copies must remove pointer keys and private path-like values.

## Provenance discipline

Weak associations are annotations only. They do not become strict provenance without separate human confirmation and a future approved upgrade workflow.

## Synthetic test data

Tests use synthetic fixtures. They may contain strings that look like private paths or sensitive vocabulary only to prove redaction and policy behavior.
