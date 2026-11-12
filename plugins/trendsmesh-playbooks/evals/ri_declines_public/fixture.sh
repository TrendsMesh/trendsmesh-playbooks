#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), the fakes (gh signed in; the inbox answers 201),
# and the report the earlier turns saved (draft.md; history.jsonl is made from history.json and it
# by _lib/make_history.py).
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$D/../_lib/scaffold.sh" none
bash "$D/../_lib/report_fakes.sh" signed_in 201
cp "$D/draft.md" trendsmesh-report-2026-11-11-0942.md
