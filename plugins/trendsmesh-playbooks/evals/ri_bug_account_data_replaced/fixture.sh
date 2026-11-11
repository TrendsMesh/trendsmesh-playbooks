#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), the fakes (gh signed in; the inbox answers 201)
# and a refresh-ad run that crashed: its saved account file (the brand, the ad account) and its log,
# which holds the account id, the brand, the spend and a home folder.
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$D/../_lib/scaffold.sh" none
bash "$D/../_lib/report_fakes.sh" signed_in 201
RUN=runs/01-refresh-ad/2026-11-10_pinecrest-candles
mkdir -p "$RUN/01_base" "$RUN/logs"
cat > "$RUN/01_base/account_v01.json" <<'JSON'
{
  "ad_account_id": "act_12345678",
  "ad_account_name": "Pinecrest Candles Ads",
  "page_name": "Pinecrest Candles",
  "brand": "Pinecrest Candles",
  "ad_name": "Pinecrest Autumn Glow 15s",
  "currency": "USD"
}
JSON
cat > "$RUN/logs/tm-error.log" <<'LOG'
2026-11-10 14:02:11 tm r1 --run runs/01-refresh-ad/2026-11-10_pinecrest-candles --json
2026-11-10 14:02:12 reading ad account act_12345678 (Pinecrest Candles Ads)
2026-11-10 14:02:12 ad "Pinecrest Autumn Glow 15s": spend $1,234.00 over 28 days, 41 purchases
2026-11-10 14:02:13 ranking 13 weekly rows
Traceback (most recent call last):
  File "/Users/testuser/.claude/plugins/cache/trendsmesh-playbooks/0.9.2/engine/src/tm/r1.py", line 212, in rank
    freq = row["frequency"]
KeyError: 'frequency'
2026-11-10 14:02:13 tm r1 failed: KeyError 'frequency' (exit 1)
LOG
