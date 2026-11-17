#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), the fakes (gh signed in; the inbox answers 201)
# and a finished acceptance suite with its report, which holds the person's own results and spend.
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$D/../_lib/scaffold.sh" none
bash "$D/../_lib/report_fakes.sh" signed_in 201
SUITE=acceptance/2026-11-09_recuts
mkdir -p "$SUITE"
cat > "$SUITE/acceptance.json" <<'JSON'
{"suite": "recuts", "started": "2026-11-09", "ad_account_id": "act_12345678", "brand": "Pinecrest Candles"}
JSON
cat > "$SUITE/report_v01.md" <<'MD'
# Acceptance report: recuts, 2026-11-09

| Case | Result | Note |
|---|---|---|
| R1 | pass | The hook fade was found on "Pinecrest Autumn Glow 15s" (act_12345678): hook rate 31% down to 18% in 3 weeks. |
| R2 | pass | The middle re-cut kept 92% of the watch time. |
| R3 | fail | The 6 s bumper cut a word in half at 4.2 s. |

Spend: $3.20 of the $4 Replicate budget; 1,850 of 3,000 ElevenLabs credits; nothing on Meta ads.
MD
