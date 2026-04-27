# Project status

`graph-harness-maintain` is currently a **pre-release** public source project.

## Current scope

The current source tree is intended for review and testing before any v1.0 or v1.1 publication decision.

The v1.0 line focuses on a read-only, graph-governed maintenance adapter for agent harnesses:

- validate graph-harness records;
- inspect graph and sidecar health;
- retrieve small dependency-closed subgraphs;
- produce sanitized dry-run exports;
- run capacity-only storage audits;
- generate proposal-only raw archive plans.

## Explicit non-goals before release

The project does not publish or execute:

- GitHub Releases;
- PyPI packages;
- git tags;
- apply workflows;
- delete workflows;
- quarantine workflows;
- rehydrate workflows;
- provenance upgrade workflows;
- raw archive apply workflows.

## Review gates before v1.0 or v1.1

Before deciding whether to publish v1.0 or continue to v1.1, require:

1. full test pass;
2. leak scan with zero blocking findings;
3. package build check pass;
4. storage guard check below the 4 GiB hard limit;
5. independent review of the CLI safety boundary;
6. review of documentation accuracy;
7. explicit human approval for any release, tag, or package publication.

## Current recommendation

Keep the repository as public pre-release source only until review and testing are complete.
