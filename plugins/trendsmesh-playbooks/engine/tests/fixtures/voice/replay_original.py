"""Run the handoff's own voice_mine.py offline on the LD dry run's Reddit raw files: writes golden_v01.json.

    python -I plugins/trendsmesh-playbooks/engine/tests/fixtures/voice/replay_original.py \
        handoff/creative-brief_v02 plugins/trendsmesh-playbooks/engine/tests/fixtures/voice/golden_v01.json

For each `03_wip/tool_tests/voice_mine/reddit_*.json`, a fake archive answers from that file's own
records (those with lo <= created_utc < hi, newest first, at most `limit`), and the tool is run
unchanged with the file's own parameters, `--before 2026-11-05` (every record is older, and the
window no longer depends on today) and `--out`. Scenario "slow" makes the archive answer HTTP 422
"Timeout. Maybe slow down a bit" for any window over 30 days, so the warm-up retry, the halving and
the growing back are run too. The golden keeps, per file and scenario, what the tool wrote except
the records themselves (their ids, in order) and its time stamp; and the items it printed.
"""

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

SLOW_OVER = 30 * 86400
BEFORE = "2026-11-05"


class Answer:
    def __init__(self, url, status, body):
        self.url, self.status_code, self._body, self.headers = url, status, body, {}
        self.text = json.dumps(body)

    def json(self):
        return self._body


def archive(records, slow):
    def get(url, params=None, headers=None, timeout=None):
        full = url + "?" + urlencode(params)
        lo, hi, limit = params["after"], params["before"], params["limit"]
        if slow and hi - lo > SLOW_OVER:
            return Answer(full, 422, {"error": "Timeout. Maybe slow down a bit"})
        hits = [d for d in records if lo <= d["created_utc"] < hi]
        return Answer(full, 200, {"data": sorted(hits, key=lambda d: d["created_utc"], reverse=True)[:limit]})
    return get


def argv_for(raw: dict, out: Path) -> list[str]:
    p = raw["_params"]
    kind = "posts" if raw["_source"] == "arctic_shift_posts" else "comments"
    argv = [f"reddit-{kind}", "--subreddit", p["subreddit"], "--limit", str(p["limit"]),
            "--after", p["after"], "--before", BEFORE, "--out", str(out)]
    if kind == "posts":
        field = next(f for f in ("title", "selftext", "query") if f in p)
        argv += ["--query", p[field], "--field", field]
    else:
        argv += ["--query", p["body"]]
    if "fields" not in p:
        argv.append("--all-fields")
    return argv


def main(handoff: Path, target: Path, scratch: Path) -> None:
    spec = importlib.util.spec_from_file_location("voice_mine", handoff / "tools/pb2/voice_mine.py")
    vm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vm)
    vm.time.sleep = lambda s: None
    folder = handoff / "examples/ld-en-dry-run/03_wip/tool_tests/voice_mine"
    golden = {}
    for f in sorted(folder.glob("reddit_*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        for scenario in ("plain", "slow"):
            vm.requests.get = archive(raw["data"], scenario == "slow")
            out = scratch / f"{f.stem}_{scenario}.json"
            out.unlink(missing_ok=True)
            argv = argv_for(raw, out)
            plain = [a for a in argv if a not in ("--out", str(out))]
            printed, log = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(log):
                assert vm.main(argv) == 0, log.getvalue()
            # with --out the items are not printed: the same run again without it prints them
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
                assert vm.main(plain) == 0
            wrote = json.loads(out.read_text(encoding="utf-8"))
            items = [json.loads(line) for line in printed.getvalue().splitlines() if line.strip()]
            entry = golden.setdefault(f.name, {"items": {}, "runs": {}})
            for it in items:   # the same record gives the same item in both scenarios
                assert entry["items"].setdefault(it["id"], it) == it
            entry["runs"][scenario] = {
                "argv": plain,
                "data_ids": [d["id"] for d in wrote["data"]],
                "item_ids": [it["id"] for it in items],
                **{k: wrote[k] for k in ("_query_url", "_source", "_params", "_stats", "_chunks")},
            }
    target.write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        main(Path(sys.argv[1]), Path(sys.argv[2]), Path(tmp))
