#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh) and the idea run at B1, its profile confirmed, with the
# user's earlier choice of Free (issue #106); the plan offer was made four days ago (so it is not due again).
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" ov_free_at_b1
printf '{"trendsmesh_mode": "free", "at": "2026-11-10T10:00:00+00:00", "offered_at": "2026-11-10T10:00:00+00:00"}\n' \
  > .trendsmesh/prefs.json
