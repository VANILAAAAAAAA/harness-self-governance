# Storage guard

The storage guard is a capacity and proposal layer. It does not archive, move, delete, quarantine, or mutate graph records.

## Commands

```bash
uv run graph-harness-maintain storage-audit \
  --active-root . \
  --archive-root "$ARCHIVE_ROOT" \
  --out artifacts/storage_audit.json

uv run graph-harness-maintain raw-archive-proposal \
  --active-root . \
  --archive-root "$ARCHIVE_ROOT" \
  --out artifacts/raw_archive_proposal.json
```

## Thresholds

Default control-plane thresholds:

- warning: 3 GiB
- hard limit: 4 GiB

If the active knowledge/control-plane exceeds the hard limit, packaging and release advancement should stop and an archive proposal may be generated. Raw data must not be moved automatically.

## Apply boundary

There is no public v1.0 raw archive apply command. Applying an archive plan is outside this release line and requires a separately approved future workflow.
