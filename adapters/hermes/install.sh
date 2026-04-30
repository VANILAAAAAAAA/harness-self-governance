#!/usr/bin/env bash
set -euo pipefail

# Install the graph-memory Hermes plugin into a Hermes profile/user plugin dir.
# Usage:
#   ./adapters/hermes/install.sh /home/vanila/.hermes/profiles/general
#   HERMES_HOME=/home/vanila/.hermes/profiles/general ./adapters/hermes/install.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/plugins/graph-memory"

TARGET_HOME="${1:-${HERMES_HOME:-$HOME/.hermes}}"
PLUGIN_DST="$TARGET_HOME/plugins/graph-memory"
CONFIG_PATH="$TARGET_HOME/config.yaml"

if [[ ! -f "$PLUGIN_SRC/plugin.yaml" || ! -f "$PLUGIN_SRC/__init__.py" ]]; then
  echo "ERROR: plugin source missing at $PLUGIN_SRC" >&2
  exit 1
fi

mkdir -p "$PLUGIN_DST"
cp "$PLUGIN_SRC/plugin.yaml" "$PLUGIN_DST/plugin.yaml"
cp "$PLUGIN_SRC/__init__.py" "$PLUGIN_DST/__init__.py"

cat <<EOF
Installed graph-memory plugin:
  source: $PLUGIN_SRC
  target: $PLUGIN_DST

Next, enable in config:
  config: $CONFIG_PATH

Required YAML:

plugins:
  enabled:
    - graph-memory

graph_memory:
  enabled: true
  mode: inject
  default_budget: fast
  default_evidence_depth: anchor
  max_context_chars: 6000
  auto_skill_mounts: true
  skill_mount_mode: summary
  max_skill_chars: 1600
  trace: true
  trace_dir: $TARGET_HOME/graph-memory-traces
  memory_root: $TARGET_HOME/home/.agent-memory-graph
  repo_roots:
    - /home/vanila/code/graph-harness-maintain
  repo_project_hints:
    /home/vanila/code/graph-harness-maintain:
      profile: general
      project: harness-self-governance
  raw_span_enabled: false
  capture_pending_updates: false
EOF
