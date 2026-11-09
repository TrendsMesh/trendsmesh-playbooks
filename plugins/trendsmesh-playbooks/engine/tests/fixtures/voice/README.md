# Voice golden file

`golden_v01.json` is the output of the reference tool,
`handoff/creative-brief_v02/tools/pb2/voice_mine.py` (unchanged), run offline on 2026-11-07 with the
dev environment's Python 3.11 from the repo root:

```
python -I plugins/trendsmesh-playbooks/engine/tests/fixtures/voice/replay_original.py \
  handoff/creative-brief_v02 plugins/trendsmesh-playbooks/engine/tests/fixtures/voice/golden_v01.json
```

No network is used: `replay_original.py` replaces `requests.get` with a fake archive that answers
from each Reddit raw file in `examples/ld-en-dry-run/03_wip/tool_tests/voice_mine/` (the records
with `after <= created_utc < before`, newest first, at most `limit`). It runs the tool with the
file's own `_params`, `--before 2026-11-05` (so the window does not depend on the day the script
runs) and, in scenario `slow`, an archive that answers HTTP 422 "Timeout. Maybe slow down a bit" to
any window over 30 days, so the warm-up retry, the halving, the growing back and the 25-call stop
are run as well.

Per raw file the golden keeps the items the tool printed (by id) and, per scenario, the argv, the
ids of the records it wrote (in order), the ids of its items (in order), and its `_query_url`,
`_source`, `_params`, `_stats` and `_chunks`.

`test_voice.py` runs `tm.voice.fetch_reddit` on the same fake archive and compares. The items of a
saved raw file are also compared with the package's own `items.jsonl`: that file was appended by the
tool, run after run, de-duplicated by id, so an id's row there is the item of the first file (by
`_fetched_at`) that held it. A later file can give the same id another item (a comment fetched with
the compact field set has no thread title), which is why the per-file oracle is the replay.
