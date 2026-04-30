#!/usr/bin/env bash
set -euo pipefail

# Verify that the graph-memory Hermes plugin is installed into a Hermes profile.
# Usage:
#   ./adapters/hermes/verify.sh /home/vanila/.hermes/profiles/general
#   HERMES_HOME=/home/vanila/.hermes/profiles/general ./adapters/hermes/verify.sh

TARGET_HOME="${1:-${HERMES_HOME:-$HOME/.hermes}}"
PLUGIN_DST="$TARGET_HOME/plugins/graph-memory"
CONFIG_PATH="$TARGET_HOME/config.yaml"

status=0
if [[ -f "$PLUGIN_DST/plugin.yaml" && -f "$PLUGIN_DST/__init__.py" ]]; then
  echo "PASS plugin files: $PLUGIN_DST"
else
  echo "FAIL plugin files missing: $PLUGIN_DST" >&2
  status=1
fi

if [[ -f "$CONFIG_PATH" ]]; then
  if grep -q "graph-memory" "$CONFIG_PATH" && grep -q "graph_memory:" "$CONFIG_PATH"; then
    echo "PASS config references graph-memory: $CONFIG_PATH"
  else
    echo "WARN config does not appear to enable graph-memory: $CONFIG_PATH" >&2
  fi
else
  echo "WARN config missing: $CONFIG_PATH" >&2
fi

if [[ -d "$TARGET_HOME/graph-memory-traces" ]]; then
  echo "PASS trace dir exists: $TARGET_HOME/graph-memory-traces"
else
  echo "WARN trace dir not found yet: $TARGET_HOME/graph-memory-traces"
fi

exit "$status"
