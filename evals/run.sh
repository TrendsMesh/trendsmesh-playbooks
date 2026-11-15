#!/bin/bash
# Runs the plugin evals. Flags the cases need:
#   --scaffold       each case builds its workspace (the engine shim ./tm.sh and a run folder; _lib/scaffold.sh)
#   --allow-tools    Bash (the engine, in the OS sandbox), Write and Edit (the agent's own files)
#   --trust-plugin   no prompt for this plugin directory
# Only for the report-issue cases (ri_*): WebFetch(domain:127.0.0.1), which lets the sandboxed shell
# reach 127.0.0.1 through the sandbox's proxy, where their fake inbox listens (_lib/report_fakes.sh). It
# also opens any other local service on this machine to the cases' shell and WebFetch, so it is added
# only when a --case value starts with ri_ (evals/run.sh --case 'ri_*'), or with --report-issue (this
# script's own flag, not passed on), for example to run every case:  evals/run.sh --report-issue
# Without it, the ri_* cases' inbox graders fail.
# The real TrendsMesh MCP is never started (--mocks record is passed explicitly; --allow-real-servers and --mocks are refused).
# The Meta Ads MCP is the user's own connector, not part of the plugin: its mocks sit in each case's mocks/meta.
# Extra arguments pass through, for example:  evals/run.sh --case doctor_r8_missing
#
# The evals live here, outside the plugin folder, so the plugin ships without them (Anthropic's plugin
# directory counts every file in the plugin folder, issue #108). `claude plugin eval` only reads cases
# from inside the plugin it tests, and refuses a link that points out of it, so this script copies the
# plugin and these evals into a temporary folder with the repository's layout (the plugin, evals/ inside
# it, and tests/engine/, whose fixtures some scenarios build on), runs the cases there, and copies the
# results back to evals/results/. The copy leaves out env/.pixi (the pixi environments, git-ignored, far
# over the 20000 entries `claude plugin eval` accepts) and node_modules: the evals run the engine from
# source (./tm.sh). Links (the private cases) are copied as the files they point to.
set -euo pipefail

# The cases run on recorded answers only: never against real servers.
for arg in "$@"; do
  case "$arg" in
    --allow-real-servers|--mocks)
      echo "evals/run.sh: $arg is not allowed here; the evals always run with --mocks record (no real servers)." >&2
      exit 2 ;;
  esac
done

# The local-only grant for the report-issue cases (see above); --report-issue is dropped from the arguments.
LOCAL_GRANT=()
ARGS=()
prev=""
for arg in "$@"; do
  case "$arg" in
    --report-issue) LOCAL_GRANT=("WebFetch(domain:127.0.0.1)") ;;
    --case=ri_*) LOCAL_GRANT=("WebFetch(domain:127.0.0.1)"); ARGS+=("$arg") ;;
    *)
      [ "$prev" = "--case" ] && case "$arg" in ri_*) LOCAL_GRANT=("WebFetch(domain:127.0.0.1)") ;; esac
      ARGS+=("$arg") ;;
  esac
  prev="$arg"
done

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$EVALS")"
PLUGIN="$REPO/plugins/trendsmesh-playbooks"
cd "$REPO"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/tm-evals.XXXXXX")"
STAGED="$STAGE/plugins/trendsmesh-playbooks"
finish() {
  # Whatever the run wrote to the copy's results/ comes back here, then the copy goes.
  if [ -d "$STAGED/evals/results" ]; then
    mkdir -p "$EVALS/results"
    cp -R "$STAGED/evals/results/." "$EVALS/results/"
  fi
  rm -rf "$STAGE"
}
# Set the trap before anything is copied, so an interrupt at any point cleans up.
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

COPY_EXCLUDES=(--exclude .pixi --exclude node_modules --exclude __pycache__ --exclude .pytest_cache --exclude .DS_Store)
mkdir -p "$STAGED" "$STAGE/tests"
rsync -aL "${COPY_EXCLUDES[@]}" "$PLUGIN/" "$STAGED/"
rsync -aL "${COPY_EXCLUDES[@]}" --exclude /results "$EVALS/" "$STAGED/evals/"
rsync -aL "${COPY_EXCLUDES[@]}" "$REPO/tests/engine" "$STAGE/tests/"

claude plugin eval "$STAGED" --runs 1 --max-cost-usd 15 --no-publish \
  --mocks record --scaffold --allow-tools Bash Write Edit ${LOCAL_GRANT[@]+"${LOCAL_GRANT[@]}"} --trust-plugin \
  ${ARGS[@]+"${ARGS[@]}"}
