#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), no run, and the user's earlier choice of Free
# (issue #106), with the plan offer made four days ago (so it is not due again).
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" none
mkdir -p .trendsmesh
printf '{"trendsmesh_mode": "free", "at": "2026-11-10T10:00:00+00:00", "offered_at": "2026-11-10T10:00:00+00:00"}\n' \
  > .trendsmesh/prefs.json
