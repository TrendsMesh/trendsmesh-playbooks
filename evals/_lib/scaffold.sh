#!/bin/bash
# Shared scaffold for the cases: runs in the empty workspace before the agent starts (needs --scaffold).
#   scaffold.sh <scenario|none>
# - finds a Python >= 3.11 with PyYAML (or builds a venv with it), for the engine
# - writes ./tm.sh: the engine, run from the plugin's source with that Python. `bin/tm` is not used in an
#   eval: the sandbox hides the plugin's data folder, where its pixi environment lives.
# - builds the run folder for the scenario (build_run.py)
set -euo pipefail
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$LIB/../.." && pwd)"
WS="$PWD"

pick_python() {
  for c in "${TM_PY:-}" python3.12 python3.11 python3; do
    [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c 'import sys, yaml; sys.exit(sys.version_info < (3, 11))' 2>/dev/null && { command -v "$c"; return 0; }
  done
  # no suitable Python: a venv in the workspace
  for c in python3.12 python3.11 python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null || continue
    "$c" -m venv "$WS/.venv" >&2 && "$WS/.venv/bin/pip" install -q pyyaml requests >&2 && { echo "$WS/.venv/bin/python"; return 0; }
  done
  echo "scaffold: need Python 3.11 or newer" >&2; return 1
}

PY="$(pick_python)"
export TM_PY="$PY" TM_PLUGIN_ROOT="$ROOT" TM_PLUGIN_DATA="$WS/.tmdata"
mkdir -p "$TM_PLUGIN_DATA"

cat > "$WS/tm.sh" <<SH
#!/bin/sh
# The engine of the trendsmesh-playbooks plugin, for the eval sandbox. Same code as bin/tm runs.
export PYTHONPATH="$ROOT/engine/src" PYTHONDONTWRITEBYTECODE=1
export TM_PLUGIN_ROOT="$ROOT" TM_PLUGIN_DATA="$WS/.tmdata" TM_WORKSPACE="$WS"
[ -f "$WS/.plans.json" ] && export TM_PLANS_FILE="$WS/.plans.json"  # a case's public plans answer
[ -f "$WS/.tm-env" ] && . "$WS/.tm-env"  # a case's own environment (the report-issue fakes: report_fakes.sh)
exec "$PY" -m tm "\$@"
SH
chmod +x "$WS/tm.sh"

[ "${1:-none}" = none ] || "$PY" "$LIB/build_run.py" "$1" "$WS"
