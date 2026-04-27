# Security Policy

## Reporting vulnerabilities

Report vulnerabilities through a private maintainer channel or repository security advisory when available.

## Do not include sensitive data in issues

Do not include tokens, credentials, private paths, raw datasets, or sensitive exported artifacts in public issues.

## Approval-gated actions

The following actions remain behind explicit human approval in v1.0: commit, push, tag, release, publish, raw archive apply, delete, move, graph/events mutation, quarantine, rehydrate, provenance upgrade, and sensitive export.

## Token and private path handling

Public-facing docs, templates, tests, and package metadata must not contain token-like strings, credentials, private profile paths, or machine-specific absolute paths.
