"""tm voice: category voice (CB5 tier B) from the Reddit archive, and imported reviews (tiers A and B).

The Reddit part is the handoff's `tools/pb2/voice_mine.py`, ported. Nothing here touches the network:
the archive is a fake `get` answering from the LD dry run's saved raw files
(`examples/ld-en-dry-run/03_wip/tool_tests/voice_mine/`), or `requests.get` is replaced. The oracle
is the reference tool, run offline on the same fake archive (fixtures/voice/README.md).
"""

import ast
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import pytest
import requests

import private
from tm import library, voice
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

REPO = Path(__file__).resolve().parents[4]
HANDOFF = REPO / "handoff" / "creative-brief_v02"
ORIGINAL = HANDOFF / "tools" / "pb2" / "voice_mine.py"
DRY_RUN = HANDOFF / "examples" / "ld-en-dry-run" / "03_wip" / "tool_tests" / "voice_mine"
GOLDEN = private.json_fixture("voice/golden_v01.json", {})
SLOW_OVER = 30 * 86400   # the replay's "slow" archive times out on any window over 30 days
DAY = 86400
SOURCE = "Arctic Shift Reddit archive (arctic-shift.photon-reddit.com), not Reddit's own API"


@pytest.fixture
def run(tmp_path, monkeypatch) -> RunFolder:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(workspace))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return RunFolder.create(workspace, "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """A test that forgets its fake archive fails here instead of calling the real one."""
    def refuse(*args, **kwargs):
        raise AssertionError("test_voice.py must not touch the network: give a fake get")
    monkeypatch.setattr(voice.requests, "get", refuse)


@pytest.fixture
def sleeps(monkeypatch) -> list:
    """Every wait the port makes, recorded instead of slept."""
    waited: list = []
    monkeypatch.setattr(voice, "_sleep", waited.append)
    return waited


class Answer:
    def __init__(self, url: str, body):
        self.url, self._body = url, body

    def json(self):
        return self._body


def archive(records: list[dict], slow: bool = False, calls: list | None = None):
    """The replay's fake archive (fixtures/voice/replay_original.py), as the port's `get`."""
    def get(url, params):
        if calls is not None:
            calls.append(dict(params))
        full = url + "?" + urlencode(params)
        lo, hi, limit = params["after"], params["before"], params["limit"]
        if slow and hi - lo > SLOW_OVER:
            raise voice.ArchiveTimeout("Timeout. Maybe slow down a bit")
        hits = [d for d in records if lo <= d["created_utc"] < hi]
        return Answer(full, {"data": sorted(hits, key=lambda d: d["created_utc"], reverse=True)[:limit]})
    return get


def _raw(name: str) -> dict:
    return json.loads((DRY_RUN / name).read_text(encoding="utf-8"))


def _kind(raw: dict) -> str:
    return "posts" if raw["_source"] == "arctic_shift_posts" else "comments"


def _query(raw: dict) -> str:
    p = raw["_params"]
    return next(p[k] for k in ("title", "selftext", "query", "body") if k in p)


def _without_tier(items: list[dict]) -> list[dict]:
    assert all(it["tier"] == "B" for it in items)
    return [{k: v for k, v in it.items() if k != "tier"} for it in items]


def _call(argv: list[str]) -> dict:
    """The original tool's argv (as the golden stores it) as fetch_reddit's arguments."""
    valued = [a for a in argv[1:] if a != "--all-fields"]   # every other option takes a value
    opts = dict(zip(valued[::2], valued[1::2]))
    return {"kind": argv[0].removeprefix("reddit-"), "subreddit": opts["--subreddit"], "query": opts["--query"],
            "field": opts.get("--field", "title"), "limit": int(opts["--limit"]), "after": opts["--after"],
            "before": opts["--before"], "all_fields": "--all-fields" in argv}


# --- the port against the reference tool ------------------------------------------------------

@pytest.mark.private_data
def test_reddit_items_match_original_tool_output(run):
    files = sorted(DRY_RUN.glob("reddit_*.json"))
    assert len(files) == 12
    for f in files:
        raw = _raw(f.name)
        mine = _without_tier(voice.items_from_archive(raw, _kind(raw), _query(raw)))
        golden = GOLDEN[f.name]
        assert mine == [golden["items"][i] for i in golden["runs"]["plain"]["item_ids"]], f.name
        assert len(mine) == raw["_stats"]["items"], f.name

    # items.jsonl is what the tool appended, file after file (by _fetched_at), de-duplicated by id:
    # the port, fed the same files the same way, gives its Reddit rows exactly.
    for f in sorted(files, key=lambda f: _raw(f.name)["_fetched_at"]):
        raw = _raw(f.name)
        voice.append_items(run, voice.items_from_archive(raw, _kind(raw), _query(raw)))
    theirs = [r for r in library.read_jsonl(DRY_RUN / "items.jsonl")[0] if r["source"] != "goodreads"]
    mine = _without_tier(library.read_jsonl(run.path / voice.ITEMS)[0])
    assert len(theirs) == 43 and mine == theirs


@pytest.mark.private_data
@pytest.mark.parametrize("key", [f"{name}:{scenario}" for name in GOLDEN for scenario in ("plain", "slow")])
def test_fetch_walks_the_archive_as_the_original_tool(key, sleeps):
    name, scenario = key.split(":")
    golden, raw = GOLDEN[name], _raw(name)
    want = golden["runs"][scenario]
    call = _call(want["argv"])
    got = voice.fetch_reddit(**call, get=archive(raw["data"], slow=scenario == "slow"))
    assert [d["id"] for d in got["data"]] == want["data_ids"]
    for k in ("_query_url", "_source", "_params", "_stats", "_chunks"):
        assert got[k] == want[k], k
    items = _without_tier(voice.items_from_archive(got, call["kind"], call["query"]))
    assert items == [golden["items"][i] for i in want["item_ids"]]


def _literal(name: str):
    tree = ast.parse(ORIGINAL.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not in {ORIGINAL}")


@pytest.mark.private_data
def test_constants_are_the_originals_verbatim():
    for name in ("TIMEOUT", "RETRIES", "BACKOFF", "MAX_RATE_WAIT", "ARCTIC", "BOT_AUTHORS", "REMOVED",
                 "WARMUP_WAIT", "MIN_CHUNK_DAYS", "MAX_CALLS", "POST_FIELDS", "COMMENT_FIELDS"):
        assert getattr(voice, name) == _literal(name), name
    # The one change (issue #16): 12 months, not the original's 730 days; customer pains change slowly.
    assert _literal("DEFAULT_WINDOW_DAYS") == 730 and voice.DEFAULT_WINDOW_DAYS == 365
    assert voice.ARCHIVE_START == date(2005, 6, 1)
    assert "ARCHIVE_START = dt.date(2005, 6, 1)" in ORIGINAL.read_text(encoding="utf-8")
    assert voice.USER_AGENT == (f"trendsmesh-playbooks/{voice.__version__} "
                                "(category voice research; read-only; https://trendsmesh.com)")


# --- the archive's limits -------------------------------------------------------------------------

def _post(i: int, ts: int, **extra) -> dict:
    return {"id": f"p{i}", "title": f"title {i}", "selftext": f"body {i}", "score": i, "num_comments": 0,
            "created_utc": ts, "subreddit": "LucidDreaming", "author": f"user{i}", **extra}


def _answers_once(records: list[dict], calls: list, events: list | None = None):
    """An archive whose third call (the newest 5 days) answers; every other call times out. Each call
    is also noted in `events` (beside the waits), so their order shows."""
    def get(url, params):
        calls.append((params["after"], params["before"], params["limit"]))
        if events is not None:
            events.append("call")
        if len(calls) == 3 and params["before"] - params["after"] <= 5 * DAY:
            return archive(records)(url, params)
        raise voice.ArchiveTimeout("Timeout. Maybe slow down a bit")
    return get


def test_422_halves_the_window_and_marks_partial(run, sleeps, monkeypatch, capsys):
    lo, hi = int(voice._to_ts(date(2026, 10, 26))), int(voice._to_ts(date(2026, 11, 5)))
    records = [_post(1, hi - 3600)]
    calls: list = []
    got = voice.fetch_reddit("posts", "LucidDreaming", "first lucid", limit=10, after="2026-10-26",
                             before="2026-11-05", get=_answers_once(records, calls, sleeps))
    widths = [b - a for a, b, _ in calls]
    # 10 days time out twice (a warm-up retry), so the chunk is halved to 5 days, which answers; the
    # window now ends at the item and the chunk grows back to all that is left. That times out twice,
    # and so does each half, until the chunk would be under the 2-day minimum.
    assert widths[:3] == [10 * DAY, 10 * DAY, 5 * DAY]
    assert calls[0] == (lo, hi, 10) and calls[3] == (lo, hi - 3600, 9)     # the limit counts down
    assert widths[3:] == [widths[3]] * 2 + [widths[3] // 2] * 2 + [widths[3] // 2 // 2] * 2
    # a timeout, the 8 s warm-up, the retry's timeout, 8 s before the split, the answer, the 1 s gap ...
    assert sleeps == ["call", 8, "call", 8, "call", 1] + ["call", 8] * 5 + ["call"]
    stats = got["_stats"]
    assert stats["partial"] == "archive kept timing out even on 2-day windows"
    assert (stats["archive_calls"], stats["archive_timeouts"], stats["chunks"], stats["items"]) == (9, 8, 1, 1)
    assert isinstance(got["_query_url"], str) and len(got["_chunks"]) == 1

    # The command saves what it got and says it is partial: exit 0, partial true.
    monkeypatch.setattr(voice, "http_get", _answers_once(records, []))
    assert main(["voice", "reddit-posts", "--run", str(run.path), "--subreddit", "LucidDreaming",
                 "--query", "first lucid", "--limit", "10", "--after", "2026-10-26", "--before", "2026-11-05",
                 "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["partial"] is True and out["items_added"] == 1
    assert out["file"] == "02_research/voice/reddit_luciddreaming_posts_first_lucid_v01.json"


def test_too_many_calls_stop_partial_and_no_data_is_unavailable(sleeps):
    hi = int(voice._to_ts(date(2026, 11, 5)))
    got = voice.fetch_reddit("posts", "LucidDreaming", "x", after="all", before="2026-11-05",
                             get=archive([_post(1, hi - 10 * DAY)], slow=True))
    assert got["_stats"]["partial"] == "stopped after 25 archive calls"
    assert got["_stats"]["archive_calls"] == 25 and got["_params"]["after"] == "all"

    def never(url, params):
        raise voice.ArchiveTimeout("Timeout. Maybe slow down a bit")
    with pytest.raises(voice.SourceUnavailable, match="no data: archive kept timing out even on 2-day windows"):
        voice.fetch_reddit("comments", "LucidDreaming", "x", after="2026-10-26", before="2026-11-05", get=never)


def test_a_time_cap_keeps_what_came_back(sleeps, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(voice, "_clock", lambda: now[0])
    get, calls = _sequence(*[True] * 50)

    def slow(url, params):          # every call takes 40 s (the recorded sleeps take none)
        now[0] += 40
        return get(url, params)
    got = voice.fetch_reddit("posts", "LucidDreaming", "x", after="2025-11-05", before="2026-11-05", get=slow,
                             max_seconds=90)
    stats = got["_stats"]
    assert stats["partial"] == "stopped at the 90 s time cap"
    assert stats["archive_calls"] == 3 and stats["items"] == 3          # at 0, 40 and 80 s; none at 120 s
    # Without a cap the same archive is walked further (the original's behaviour: the golden replays).
    now[0] = 0
    calls.clear()
    assert voice.fetch_reddit("posts", "LucidDreaming", "x", after="2025-11-05", before="2026-11-05",
                              get=slow)["_stats"]["archive_calls"] == voice.MAX_CALLS


def _sequence(*answers: bool):
    """An archive answering in turn: True gives a post, False times out; past the end it times out."""
    hi = int(voice._to_ts(date(2026, 11, 5)))
    calls: list = []

    def get(url, params):
        n = len(calls)
        calls.append(params["before"])
        if n < len(answers) and answers[n]:
            return Answer(url, {"data": [_post(n, min(params["before"], hi) - DAY)]})
        raise voice.ArchiveTimeout("Timeout. Maybe slow down a bit")
    return get, calls


def test_timeouts_in_a_row_stop_early_and_a_success_resets_them(sleeps):
    window = {"after": "2026-01-01", "before": "2026-11-05", "max_timeouts_in_a_row": 4}
    get, calls = _sequence(True)
    got = voice.fetch_reddit("posts", "LucidDreaming", "x", get=get, **window)
    assert got["_stats"]["partial"] == "stopped after 4 archive timeouts in a row"
    assert len(calls) == 5 and got["_stats"]["items"] == 1
    get, calls = _sequence(False, True)          # the warm-up retry answers: the count starts again
    got = voice.fetch_reddit("posts", "LucidDreaming", "x", get=get, **window)
    assert len(calls) == 6 and got["_stats"]["archive_timeouts"] == 5
    get, calls = _sequence()
    with pytest.raises(voice.SourceUnavailable, match="no data: stopped after 4 archive timeouts in a row"):
        voice.fetch_reddit("posts", "LucidDreaming", "x", get=get, **window)
    assert len(calls) == 4


def test_the_command_caps_time_and_timeouts_by_default(run, sleeps, monkeypatch, capsys):
    seen = {}

    def fake(kind, subreddit, query, **kw):
        seen.update(kw)
        raise voice.SourceUnavailable("test")
    monkeypatch.setattr(voice, "fetch_reddit", fake)
    argv = ["voice", "reddit-posts", "--run", str(run.path), "--subreddit", "LucidDreaming", "--query", "x", "--json"]
    assert main(argv) == 2
    assert (seen["max_seconds"], seen["max_timeouts_in_a_row"]) == (voice.TIME_CAP_S, voice.TIMEOUTS_IN_A_ROW)
    assert 60 <= voice.TIME_CAP_S <= 90 and voice.TIMEOUTS_IN_A_ROW >= 3
    assert main(argv + ["--max-seconds", "60"]) == 2 and seen["max_seconds"] == 60
    capsys.readouterr()
    assert main(argv + ["--max-seconds", "5"]) == 1                     # too short to get anything
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_automoderator_dropped_removed_counted(sleeps):
    hi = int(voice._to_ts(date(2026, 11, 5)))
    posts = [
        _post(1, hi - 1 * DAY),
        _post(2, hi - 2 * DAY, author="AutoModerator"),
        _post(3, hi - 3 * DAY, selftext="[removed]"),
        _post(4, hi - 4 * DAY, selftext="", removed_by_category="moderator"),
        _post(5, hi - 5 * DAY, selftext="Fish &amp; chips\r\nnext line  "),
    ]
    got = voice.fetch_reddit("posts", "LucidDreaming", "dream", after="2026-10-26", before="2026-11-05",
                             get=archive(posts))
    assert [d["id"] for d in got["data"]] == ["p1", "p2", "p3", "p4", "p5"]       # the raw file keeps the bot
    items = voice.items_from_archive(got, "posts", "dream")
    assert [it["id"] for it in items] == ["t3_p1", "t3_p3", "t3_p4", "t3_p5"]
    assert items[1]["title"] == "title 3" and items[1]["text"] == ""              # the title is the author's words
    assert items[3]["text"] == "Fish & chips\nnext line"
    assert items[0] == {"id": "t3_p1", "source": "reddit_post", "community": "r/LucidDreaming",
                        "url": "https://www.reddit.com/r/LucidDreaming/comments/p1/", "title": "title 1",
                        "text": "body 1", "score": 1, "created_utc": hi - DAY, "query": "dream", "tier": "B"}
    s = got["_stats"]
    assert (s["fetched"], s["removed_bodies"], s["skipped"], s["bot_skipped"], s["items"]) == (5, 2, 0, 1, 4)

    skipped = voice.fetch_reddit("posts", "LucidDreaming", "dream", after="2026-10-26", before="2026-11-05",
                                 skip_removed=True, get=archive(posts))
    assert skipped["_stats"]["skipped"] == 2 and skipped["_stats"]["items"] == 2
    assert [it["id"] for it in voice.items_from_archive(skipped, "posts", "dream", skip_removed=True)] \
        == ["t3_p1", "t3_p5"]

    comments = [
        {"id": "c1", "body": "I tried everything", "score": 3, "link_id": "t3_abc", "parent_id": "t3_abc",
         "created_utc": hi - DAY, "subreddit": "LucidDreaming", "author": "someone"},
        {"id": "c2", "body": "[deleted]", "score": 1, "link_id": "t3_abc", "created_utc": hi - 2 * DAY,
         "subreddit": "LucidDreaming", "author": "gone"},
        {"id": "c3", "body": "Please read the rules", "score": 1, "link_id": "t3_abc", "created_utc": hi - 3 * DAY,
         "subreddit": "LucidDreaming", "author": "automoderator"},
        {"id": "c4", "body": "  ", "score": 1, "link_id": "t3_abc", "created_utc": hi - 4 * DAY,
         "subreddit": "LucidDreaming", "author": "blank"},
    ]
    got = voice.fetch_reddit("comments", "LucidDreaming", "tried", after="2026-10-26", before="2026-11-05",
                             get=archive(comments))
    items = voice.items_from_archive(got, "comments", "tried")
    assert [it["url"] for it in items] == ["https://www.reddit.com/r/LucidDreaming/comments/abc/_/c1/"]
    s = got["_stats"]
    assert (s["fetched"], s["removed_bodies"], s["skipped"], s["bot_skipped"], s["items"]) == (4, 2, 2, 1, 1)
    # A post search without a keyword (the newest posts) keeps an empty query, never None.
    assert voice.items_from_archive({"data": posts[:1]}, "posts", None)[0]["query"] == ""


def test_chunk_grows_back_but_never_shrinks_after_a_success(sleeps):
    lo = int(voice._to_ts(date(2026, 10, 26)))
    calls: list = []

    def get(url, params):   # the first call answers with an item a day above the window's start
        calls.append(params["before"] - params["after"])
        if len(calls) == 1:
            return Answer(url, {"data": [_post(1, lo + DAY)]})
        raise voice.ArchiveTimeout("Timeout. Maybe slow down a bit")

    got = voice.fetch_reddit("posts", "LucidDreaming", "x", after="2026-10-26", before="2026-11-05", get=get)
    # The chunk stays 10 days (the window left is 1 day), so it is halved to 5, then 2.5 days, not 0.5.
    assert calls == [10 * DAY, DAY, DAY, DAY, DAY, DAY, DAY]
    assert got["_stats"]["archive_calls"] == 7 and got["_stats"]["partial"].startswith("archive kept timing out")


def test_default_window_is_12_months_and_bad_arguments_are_errors(run, sleeps, capsys):
    got = voice.fetch_reddit("posts", "LucidDreaming", "x", get=archive([]))
    assert got["_params"]["after"] == (date.today() - timedelta(days=365)).isoformat()
    assert got["_params"]["before"] == "now" and got["_stats"]["window"][1] == "now"
    assert got["_params"]["title"] == "x" and got["_params"]["sort"] == "desc"
    assert voice.fetch_reddit("posts", "LucidDreaming", "x", field="query", get=archive([]))["_params"]["query"] == "x"
    for bad in ({"limit": 0}, {"limit": 101}, {"after": "2026-13-01"}, {"field": "body"},
                {"after": "2026-11-05", "before": "2026-11-01"}):
        with pytest.raises(ValueError) as exc:
            voice.fetch_reddit("posts", "LucidDreaming", "x", get=archive([]), **bad)
        assert not isinstance(exc.value, Stop)
    with pytest.raises(ValueError):
        voice.fetch_reddit("comments", "LucidDreaming", "  ", get=archive([]))
    assert main(["voice", "reddit-comments", "--run", str(run.path), "--subreddit", "LucidDreaming",
                 "--query", "x", "--limit", "500", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert not (run.path / "02_research" / "voice").exists()


def test_http_get_retries_honours_rate_headers_and_tells_422_apart(monkeypatch, sleeps):
    class Got:
        def __init__(self, status, body=None, headers=None):
            self.status_code, self._body, self.headers = status, body, headers or {}
            self.url, self.text = "https://arctic-shift.photon-reddit.com/api/posts/search?x=1", json.dumps(body)

        def json(self):
            if self._body is None:
                raise ValueError("no JSON")
            return self._body

    answers, seen = [], []

    def fake(url, params=None, headers=None, timeout=None):
        seen.append((headers, timeout))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(voice.requests, "get", fake)
    answers[:] = [requests.Timeout(), Got(503), Got(429, headers={"Retry-After": "3"}), Got(200, {"data": []})]
    assert voice.http_get(voice.ARCTIC + "posts/search", {}).status_code == 200
    assert sleeps == [2, 5, 4]
    assert seen[0] == ({"User-Agent": voice.USER_AGENT, "Accept-Language": "en-US,en;q=0.8"}, 30)

    answers[:] = [Got(422, {"error": "Timeout. Maybe slow down a bit"})]
    with pytest.raises(voice.ArchiveTimeout):
        voice.http_get(voice.ARCTIC + "posts/search", {})
    answers[:] = [Got(422, {"error": "Invalid parameter"})]
    with pytest.raises(voice.SourceUnavailable, match="HTTP 422"):
        voice.http_get(voice.ARCTIC + "posts/search", {})
    answers[:] = [Got(404)]
    with pytest.raises(voice.SourceUnavailable, match=r"HTTP 404 \(client error\)"):
        voice.http_get(voice.ARCTIC + "posts/search", {})
    assert answers == []                                         # a client error is not retried


# --- imports ------------------------------------------------------------------------------------

def test_import_text_csv_jsonl_and_tier_c_refused(run, tmp_path, capsys):
    text = tmp_path / "reviews.txt"
    text.write_bytes("Finally slept through the night.\r\n\r\n  \r\n"
                     "I had my first lucid dream 🤯\r\nafter a week.\r\n\r\n".encode("utf-8"))
    items = voice.import_file(text, "text", "amazon", "A")
    assert [(it["id"], it["text"], it["tier"], it["source"]) for it in items] == [
        ("amazon:1", "Finally slept through the night.", "A", "amazon"),
        ("amazon:2", "I had my first lucid dream 🤯\nafter a week.", "A", "amazon")]
    assert set(items[0]) == {"id", "source", "community", "url", "title", "text", "score", "created_utc", "query",
                             "tier"}

    table = tmp_path / "survey.csv"
    table.write_text('name,review\nAna,"Works, mostly."\nBo,\nCy,"Two\nlines"\n', encoding="utf-8")
    items = voice.import_file(table, "csv", "survey", "B", text_column="review")
    assert [(it["id"], it["text"]) for it in items] == [("survey:1", "Works, mostly."), ("survey:3", "Two\nlines")]
    with pytest.raises(ValueError, match="review"):
        voice.import_file(table, "csv", "survey", "B")            # no "text" column: the columns are named

    lines = tmp_path / "saved.jsonl"
    lines.write_text('{"text": "one"}\n\n{"text": ""}\n{"text": "three"}\n', encoding="utf-8")
    assert [(it["id"], it["text"]) for it in voice.import_file(lines, "jsonl", "page", "B")] == [
        ("page:1", "one"), ("page:3", "three")]
    lines.write_text('{"text": "one"}\nnot json\n', encoding="utf-8")
    with pytest.raises(Stop, match="line 2"):
        voice.import_file(lines, "jsonl", "page", "B")

    for tier in ("C", "c"):
        with pytest.raises(ValueError, match=r"brand voice is a hypothesis, never customer evidence \(CB5\)"):
            voice.import_file(text, "text", "brand", tier)
    with pytest.raises(ValueError):
        voice.import_file(text, "text", "  ", "A")

    assert main(["voice", "import", "--run", str(run.path), "--file", str(text), "--format", "text",
                 "--source", "brand", "--tier", "C", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error" and "never customer evidence (CB5)" in out["message"]
    assert not (run.path / voice.ITEMS).exists()

    assert main(["voice", "import", "--run", str(run.path), "--file", str(table), "--format", "csv",
                 "--source", "survey", "--tier", "B", "--text-column", "review", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["status"], out["items_added"], out["items_duplicate"]) == ("done", 2, 0)
    rows = library.read_jsonl(run.path / voice.ITEMS)[0]
    assert [r["id"] for r in rows] == ["survey:1", "survey:3"]
    assert "tm voice import" in (run.path / "manifest.md").read_text(encoding="utf-8")


def test_import_keeps_each_texts_link_and_date(run, tmp_path, capsys):
    """Reviews and discussions found on the web (B2 steps 1 and 2) carry their page and day."""
    lines = tmp_path / "rival.jsonl"
    lines.write_text('{"text": "Too hot by June", "url": "https://shop.example.com/r/1", "date": "2026-07-02"}\n'
                     '{"text": "No date here"}\n', encoding="utf-8")
    items = voice.import_file(lines, "jsonl", "rival", "B")
    assert items[0]["url"] == "https://shop.example.com/r/1"
    assert items[0]["created_utc"] == voice._to_ts(date(2026, 7, 2))
    assert (items[1]["url"], items[1]["created_utc"]) == ("", None)
    table = tmp_path / "forum.csv"
    table.write_text("text;url;date\nNothing works;https://forum.example.com/t/9;2026-03-01\n", encoding="utf-8")
    item = voice.import_file(table, "csv", "forum", "B", url="https://forum.example.com/")[0]
    assert item["url"] == "https://forum.example.com/t/9"                 # the row's own link first
    page = tmp_path / "voice_rival.txt"
    page.write_text("One review.\n\nAnother.\n", encoding="utf-8")
    got = voice.import_file(page, "text", "rivalpage", "B", url="https://shop.example.com/reviews")
    assert {it["url"] for it in got} == {"https://shop.example.com/reviews"}
    lines.write_text('{"text": "x", "date": "last June"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="record 1.*YYYY-MM-DD"):
        voice.import_file(lines, "jsonl", "rival", "B")
    with pytest.raises(ValueError, match="--url"):
        voice.import_file(page, "text", "rivalpage", "B", url="shop.example.com")
    assert main(["voice", "import", "--run", str(run.path), "--file", str(page), "--format", "text",
                 "--source", "rivalpage", "--tier", "B", "--url", "https://shop.example.com/reviews", "--json"]) == 0
    rows = library.read_jsonl(run.path / voice.ITEMS)[0]
    assert {r["url"] for r in rows} == {"https://shop.example.com/reviews"}


def _import(run: RunFolder, capsys, path: Path, fmt: str, source: str = "amazon", *extra: str) -> tuple[int, dict]:
    code = main(["voice", "import", "--run", str(run.path), "--file", str(path), "--format", fmt,
                 "--source", source, "--tier", "A", *extra, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_missing_or_empty_import_file_stops(run, tmp_path, capsys):
    manifest_before = (run.path / "manifest.md").read_text(encoding="utf-8")
    for fmt in ("text", "csv", "jsonl"):
        missing = tmp_path / f"typo.{fmt}"
        code, out = _import(run, capsys, missing, fmt)
        assert (code, out["status"]) == (2, "stop") and str(missing) in out["message"], fmt
        assert out["message"].endswith(f"{AGAIN}.")
        for content in ("", "\r\n  \r\n\n"):
            empty = tmp_path / f"empty.{fmt}"
            empty.write_text(content, encoding="utf-8")
            code, out = _import(run, capsys, empty, fmt)
            assert (code, out["status"]) == (2, "stop"), (fmt, content)
            assert f"{empty.name} has no texts to import" in out["message"]
    header_only = tmp_path / "header.csv"
    header_only.write_text("name,text\nAna,\n", encoding="utf-8")
    assert _import(run, capsys, header_only, "csv")[0] == 2
    no_texts = tmp_path / "blank.jsonl"
    no_texts.write_text('{"text": ""}\n{"other": "x"}\n', encoding="utf-8")
    assert _import(run, capsys, no_texts, "jsonl")[0] == 2
    wrong_column = tmp_path / "survey.csv"
    wrong_column.write_text("name,review\nAna,fine\n", encoding="utf-8")
    code, out = _import(run, capsys, wrong_column, "csv")
    assert (code, out["status"]) == (1, "error") and "review" in out["message"]   # the argument, not the file
    assert not (run.path / voice.ITEMS).exists()
    assert (run.path / "manifest.md").read_text(encoding="utf-8") == manifest_before   # no row for any of them


def test_second_file_under_the_same_label_stops(run, tmp_path, capsys):
    book_a, book_b = tmp_path / "book_a.txt", tmp_path / "book_b.txt"
    book_a.write_text("Loved it.\n\nToo long.\n", encoding="utf-8")
    book_b.write_text("Changed my nights.\n\nMeh.\n", encoding="utf-8")
    assert _import(run, capsys, book_a, "text", "goodreads")[1]["items_added"] == 2
    logged = (run.path / voice.ITEMS).read_bytes()

    code, out = _import(run, capsys, book_b, "text", "goodreads")
    assert (code, out["status"]) == (2, "stop")
    assert "goodreads:1" in out["message"] and "book_a.txt" in out["message"] and "--source" in out["message"]
    assert (run.path / voice.ITEMS).read_bytes() == logged                   # nothing appended

    code, out = _import(run, capsys, book_a, "text", "goodreads")           # the same file again: a no-op
    assert (code, out["items_added"], out["items_duplicate"]) == (0, 0, 2)
    assert (run.path / voice.ITEMS).read_bytes() == logged

    code, out = _import(run, capsys, book_b, "text", "goodreads-2")
    assert (code, out["items_added"]) == (0, 2)
    assert [r["id"] for r in library.read_jsonl(run.path / voice.ITEMS)[0]] == [
        "goodreads:1", "goodreads:2", "goodreads-2:1", "goodreads-2:2"]


def test_bom_and_non_utf8_imports(run, tmp_path, capsys):
    table = tmp_path / "excel.csv"
    table.write_bytes(b"\xef\xbb\xbftext,stars\r\nZdrowy sen \xc5\xbcyczliwie,5\r\n")
    assert [it["text"] for it in voice.import_file(table, "csv", "shop", "A")] == ["Zdrowy sen życzliwie"]
    lines = tmp_path / "notepad.jsonl"
    lines.write_bytes(b'\xef\xbb\xbf{"text": "one"}\r\n{"text": "two"}\r\n')
    assert [it["text"] for it in voice.import_file(lines, "jsonl", "page", "B")] == ["one", "two"]

    for fmt in ("csv", "text", "jsonl"):
        latin = tmp_path / f"cp1250.{fmt}"
        latin.write_bytes("text\nZdrowy sen życzliwie\n".encode("cp1250") if fmt != "jsonl"
                          else '{"text": "ż"}\n'.encode("cp1250"))
        code, out = _import(run, capsys, latin, fmt)
        assert (code, out["status"]) == (2, "stop") and f"{latin.name} is not UTF-8 text" in out["message"], fmt
    assert not (run.path / voice.ITEMS).exists()


def test_malformed_archive_record_is_source_unavailable(sleeps):
    for data in (["x"], [{"title": "no id", "created_utc": 1}], [{"id": "", "created_utc": 1}]):
        def get(url, params, data=data):
            return Answer(url, {"data": data})
        with pytest.raises(voice.SourceUnavailable, match="unexpected archive response shape"):
            voice.fetch_reddit("posts", "LucidDreaming", "x", after="2026-10-26", before="2026-11-05", get=get)
        with pytest.raises(ValueError, match="not an object with an id"):
            voice.items_from_archive({"data": data}, "posts", "x")


# --- the items log ------------------------------------------------------------------------------

@pytest.mark.private_data
def test_items_appended_once_by_id(run, sleeps, monkeypatch, capsys):
    raw = _raw("reddit_ld_posts_first_lucid.json")
    items = voice.items_from_archive(raw, "posts", "first lucid")
    assert voice.append_items(run, items[:4]) == (4, 0)
    assert voice.append_items(run, items + items[:1]) == (6, 5)     # within a batch too
    rows = library.read_jsonl(run.path / voice.ITEMS)[0]
    assert [r["id"] for r in rows] == [it["id"] for it in items]

    # Through the command: two fetches, two raw files, each with its manifest row; the items once.
    monkeypatch.setattr(voice, "http_get", archive(raw["data"]))
    argv = ["voice", "reddit-posts", "--run", str(run.path), "--subreddit", "LucidDreaming", "--query",
            "first lucid", "--limit", "10", "--after", "2024-11-04", "--before", "2026-11-05", "--json"]
    assert main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(argv) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["file"] == "02_research/voice/reddit_luciddreaming_posts_first_lucid_v01.json"
    assert second["file"] == "02_research/voice/reddit_luciddreaming_posts_first_lucid_v02.json"
    assert (first["items_added"], first["items_duplicate"]) == (0, 10)
    assert first["partial"] is False and second["items_duplicate"] == 10
    saved = json.loads((run.path / first["file"]).read_text(encoding="utf-8"))
    assert saved["_source"] == "arctic_shift_posts" and len(saved["data"]) == 10
    assert set(saved) >= {"_query_url", "_source", "_fetched_at", "_params", "_stats", "data", "_chunks"}
    assert len(library.read_jsonl(run.path / voice.ITEMS)[0]) == 10
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert manifest.count(SOURCE) == 2 and first["file"] in manifest and second["file"] in manifest


def test_damaged_items_line_stops(run, tmp_path, monkeypatch, capsys):
    target = run.path / voice.ITEMS
    target.parent.mkdir(parents=True)
    target.write_text('{"id": "a:1", "text": "fine"}\n{"id": "a:2", "text": "cut off\n', encoding="utf-8")
    before = target.read_bytes()
    item = {"id": "b:1", "text": "new"}
    with pytest.raises(Stop) as exc:
        voice.append_items(run, [item])
    assert "02_research/voice/items.jsonl" in str(exc.value) and "line 2" in str(exc.value)
    assert str(exc.value).endswith(f"{AGAIN}.")
    assert target.read_bytes() == before

    text = tmp_path / "r.txt"
    text.write_text("a review", encoding="utf-8")
    assert main(["voice", "import", "--run", str(run.path), "--file", str(text), "--format", "text",
                 "--source", "x", "--tier", "A", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"

    called: list = []
    monkeypatch.setattr(voice, "http_get", lambda url, params: called.append(url))
    assert main(["voice", "reddit-comments", "--run", str(run.path), "--subreddit", "LucidDreaming",
                 "--query", "tried everything", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"
    assert called == [] and target.read_bytes() == before            # no archive call, nothing appended
    assert sorted(p.name for p in target.parent.iterdir()) == ["items.jsonl"]


def test_unreachable_archive_stops_with_source_unavailable(run, sleeps, monkeypatch, capsys):
    def down(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError("no route to host")
    monkeypatch.setattr(voice.requests, "get", down)
    code = main(["voice", "reddit-posts", "--run", str(run.path), "--subreddit", "LucidDreaming",
                 "--query", "first lucid", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert set(out) == {"status", "reason", "message"}
    assert (out["status"], out["reason"]) == ("stop", "source_unavailable")
    assert "tm voice import" in out["message"] and out["message"].endswith(f"{AGAIN}.")
    assert sleeps == [2, 5, 10]                                      # three retries with backoff, then the stop
    assert not (run.path / "02_research" / "voice").exists()
    assert SOURCE not in (run.path / "manifest.md").read_text(encoding="utf-8")


def test_no_goodreads_command():
    with pytest.raises(SystemExit):
        from tm.cli import build_parser
        build_parser().parse_args(["voice", "goodreads", "--book-url", "https://www.goodreads.com/book/show/1"])
    assert not hasattr(voice, "goodreads_fetch")


def test_excel_csv_with_semicolons_imports(run, tmp_path, capsys):
    table = tmp_path / "excel.csv"
    table.write_bytes("\ufefftext;ocena\r\nDobry, naprawdę dobry sen;5\r\nŚwietne;4\r\n".encode("utf-8"))
    assert [it["text"] for it in voice.import_file(table, "csv", "shop", "A")] == ["Dobry, naprawdę dobry sen", "Świetne"]
    tabbed = tmp_path / "tabs.csv"
    tabbed.write_text("stars\ttext\n5\tFine; really, fine\n", encoding="utf-8")
    assert [it["text"] for it in voice.import_file(tabbed, "csv", "shop", "A")] == ["Fine; really, fine"]
    plain = tmp_path / "plain.csv"                                 # the default stays the comma
    plain.write_text("text\nOne; two\n", encoding="utf-8")
    assert [it["text"] for it in voice.import_file(plain, "csv", "shop", "A")] == ["One; two"]
    code, out = _import(run, capsys, table, "csv")
    assert (code, out["status"]) == (0, "done"), out


def test_non_utf8_items_log_stops_plainly(run, tmp_path, capsys):
    target = run.path / voice.ITEMS
    target.parent.mkdir(parents=True)
    target.write_bytes('{"id": "a:1", "text": "ż"}\n'.encode("cp1250"))
    before = target.read_bytes()
    text = tmp_path / "r.txt"
    text.write_text("a review", encoding="utf-8")
    code, out = _import(run, capsys, text, "text", "x")
    assert (code, out["status"]) == (2, "stop")
    assert "items.jsonl is not UTF-8 text" in out["message"] and "Traceback" not in out["message"]
    assert target.read_bytes() == before
