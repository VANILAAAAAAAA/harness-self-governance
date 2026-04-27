# Contributing

## Local setup

```bash
python3 -m pip install -e ".[dev]"
```

## Tests

```bash
pytest
```

## Pipeline command

```bash
ghm pipeline local-rc
```

## Identity rule

Before edits intended for review or any future commit attempt, verify:

```bash
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
git config --local user.name
git config --local user.email
```

Expected local identity:

- must be user-owned and repository-local
- must not resolve to `Hermes Agent <hermes-agent@users.noreply.github.com>`
- verify with `ghm identity-check` before any future commit or push approval request

## Approval rules

The v1.0 pipeline never performs commit, push, tag, release, publish, delete, move, raw archive apply, graph/events mutation, quarantine, rehydrate, provenance upgrade, or sensitive export without explicit human approval.

## Sensitive material

Do not add tokens, credentials, local absolute paths, or sensitive exports to public-facing files.
