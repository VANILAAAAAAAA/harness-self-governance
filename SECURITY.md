# Security Policy

## Pre-release scope

`graph-harness-maintain` is pre-release software. The v1.0 line is limited to read-only and proposal-only graph-harness maintenance workflows.

## Do not commit sensitive material

Do not commit or upload:

- raw EHR data;
- patient-level data;
- forbidden protected regulated records;
- credentials;
- tokens;
- API keys;
- private local sessions;
- private graph-harness reports, proposals, or artifacts;
- local absolute paths that identify private workspaces or datasets.

Use synthetic fixtures for tests and examples.

## Destructive actions are out of scope for v1.0

The v1.0 public source does not provide execution paths for:

- apply operations;
- delete operations;
- quarantine execution;
- rehydrate execution;
- raw archive apply;
- provenance upgrade;
- graph/events mutation;
- release publishing.

Any future apply-capable design must be reviewed separately and protected by explicit human approval gates.

## Reporting security issues

For public repository use, open a GitHub security advisory or private maintainer contact channel once configured. Do not include sensitive datasets, credentials, or raw private paths in public issues.
