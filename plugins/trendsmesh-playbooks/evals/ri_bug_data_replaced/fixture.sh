#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), the fakes (gh signed in; the inbox answers 201)
# and a refresh-ad run that crashed at R1, its files in the shapes the plugin saves them: run.json and
# manifest.md (tm run new), config.yaml (tm config write: the ad account act_12345678 and the product
# Pinecrest Candles), and Meta's answers saved verbatim at R1 (flow.md, R1 steps 2 and 3): the ad's weekly
# rows (its name, Pinecrest Autumn Glow 15s) and the account's (its name, Juniper Lane Studio). The run's
# log holds the account id, the brand, the spend, a home folder and the account's name. The user never
# names the account: only `tm report check` (it reads the saved Meta answer) knows that name is private, so
# the first check is likely to find it.
set -euo pipefail
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$D/../_lib/scaffold.sh" none
bash "$D/../_lib/report_fakes.sh" signed_in 201
RUN=runs/01-refresh-ad/2026-11-10_pinecrest-candles
for stage in 00_raw 01_base 02_research 03_wip 04_final 05_results showcase logs; do mkdir -p "$RUN/$stage"; done
printf '# Manifest: 01-refresh-ad 2026-11-10_pinecrest-candles\n\n' > "$RUN/manifest.md"
cat > "$RUN/run.json" <<'JSON'
{
  "run_id": "2026-11-10_pinecrest-candles",
  "playbook": "01-refresh-ad",
  "created": "2026-11-10",
  "level": "big_calls",
  "outputs": ["creative_brief", "edited_video"],
  "step": "R1",
  "status": "active"
}
JSON
cat > "$RUN/config.yaml" <<'YAML'
mode: hitl
account:
  id: act_12345678
  market: US
  language: en
product:
  name: Pinecrest Candles
  landing_url: https://pinecrest-candles.example.com/autumn
brand:
  assets_dir: null
  rules: null
  compliance: null
outputs:
- creative_brief
- edited_video
winner:
  event: purchase
  history_days: 90
  window_days: 7
  min_results: 30
budget:
  ai_usd: 20
  voice_credits: null
  test_per_day: 30
  test_days: 7
YAML
cat > "$RUN/01_base/meta_weekly_ads_p01.json" <<'JSON'
{"data": [
  {"id": "120000000000001", "name": "Pinecrest Autumn Glow 15s", "date_start": "2026-10-13", "date_stop": "2026-10-19",
   "amount_spent": "301.50", "impressions": "41210", "cpm": "7.32", "unique_link_clicks_ctr": "1.12%",
   "video_p25_watched_actions": "9120", "video_thruplay_watched_actions": "3011",
   "results": {"values": [{"value": "11"}]}, "cost_per_result": "27.41"},
  {"id": "120000000000001", "name": "Pinecrest Autumn Glow 15s", "date_start": "2026-10-20", "date_stop": "2026-10-26",
   "amount_spent": "322.00", "impressions": "40870", "cpm": "7.88", "unique_link_clicks_ctr": "0.94%",
   "video_p25_watched_actions": "8410", "video_thruplay_watched_actions": "2602",
   "results": {"values": [{"value": "9"}]}, "cost_per_result": "35.78"}
]}
JSON
cat > "$RUN/01_base/meta_weekly_account.json" <<'JSON'
{"data": [
  {"id": "act_12345678", "name": "Juniper Lane Studio", "date_start": "2026-10-13", "date_stop": "2026-10-19",
   "amount_spent": "612.40", "impressions": "83400", "frequency": "1.71"},
  {"id": "act_12345678", "name": "Juniper Lane Studio", "date_start": "2026-10-20", "date_stop": "2026-10-26",
   "amount_spent": "621.60", "impressions": "82950", "frequency": "1.84"}
]}
JSON
cat > "$RUN/logs/tm-error.log" <<'LOG'
2026-11-10 14:02:11 tm r1 --run runs/01-refresh-ad/2026-11-10_pinecrest-candles --ads 01_base/meta_weekly_ads_p01.json --account 01_base/meta_weekly_account.json --json
2026-11-10 14:02:12 reading ad account act_12345678 (Juniper Lane Studio)
2026-11-10 14:02:12 ad "Pinecrest Autumn Glow 15s": spend $1,234.00 over 28 days, 41 purchases
2026-11-10 14:02:13 ranking 13 weekly rows for Juniper Lane Studio
Traceback (most recent call last):
  File "/Users/testuser/.claude/plugins/cache/trendsmesh-playbooks/0.9.2/engine/src/tm/r1.py", line 212, in rank
    freq = row["frequency"]
KeyError: 'frequency'
2026-11-10 14:02:13 tm r1 failed: KeyError 'frequency' (exit 1)
LOG
