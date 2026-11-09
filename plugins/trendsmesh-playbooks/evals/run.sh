#!/bin/bash
# Runs the plugin evals. Flags the cases need:
#   --scaffold       each case builds its workspace (the engine shim ./tm.sh and a run folder; _lib/scaffold.sh)
#   --allow-tools    Bash (the engine, in the OS sandbox), Write and Edit (the agent's own files)
#   --trust-plugin   no prompt for this plugin directory
# The real TrendsMesh MCP is never started (--mocks record is passed explicitly; --allow-real-servers and --mocks are refused).
# The Meta Ads MCP is the user's own connector, not part of the plugin: its mocks sit in each case's mocks/meta.
# Extra arguments pass through, for example:  evals/run.sh --case doctor_reports_missing_replicate
#
# `claude plugin eval` refuses a plugin folder of more than 20000 entries, and a developer's
# env/.pixi (the pixi environments, git-ignored) has far more. This script moves it aside for the
# run and puts it back afterwards. The evals do not use it: ./tm.sh runs the engine from source.
set -euo pipefail

# The cases run on recorded answers only: never against real servers.
for arg in "$@"; do
  case "$arg" in
    --allow-real-servers|--mocks)
      echo "evals/run.sh: $arg is not allowed here; the evals always run with --mocks record (no real servers)." >&2
      exit 2 ;;
  esac
done

PLUGIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PLUGIN/../.."
PIXI_DIR="$PLUGIN/env/.pixi"

# An earlier run that was killed leaves its environments in a .pixi-aside.* folder.
for old in "$PLUGIN"/../.pixi-aside.*; do
  if [ -e "$old" ]; then
    echo "evals/run.sh: an earlier run was stopped before it put env/.pixi back: $old" >&2
    echo "Move it back first:  mv \"$old/.pixi\" \"$PIXI_DIR\" && rmdir \"$old\"" >&2
    exit 1
  fi
done

ASIDE=""
restore() {
  # pixi links env/.pixi/envs to the detached environments of the eval's sandbox, which is gone
  # once the run ends: remove that dead link (and the folder, if it holds nothing else).
  if [ -L "$PIXI_DIR/envs" ] && [ ! -e "$PIXI_DIR/envs" ]; then
    rm "$PIXI_DIR/envs" && rmdir "$PIXI_DIR" 2>/dev/null || true
  fi
  if [ -n "$ASIDE" ] && [ -d "$ASIDE/.pixi" ]; then
    mv "$ASIDE/.pixi" "$PIXI_DIR" && rmdir "$ASIDE"
  fi
}
# Set the trap before anything is moved, so an interrupt at any point puts it back.
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [ -d "$PIXI_DIR" ] && [ ! -L "$PIXI_DIR" ]; then
  ASIDE="$(mktemp -d "$PLUGIN/../.pixi-aside.XXXXXX")"
  mv "$PIXI_DIR" "$ASIDE/.pixi"
fi
claude plugin eval plugins/trendsmesh-playbooks --runs 1 --max-cost-usd 15 --no-publish \
  --mocks record --scaffold --allow-tools Bash Write Edit --trust-plugin "$@"
