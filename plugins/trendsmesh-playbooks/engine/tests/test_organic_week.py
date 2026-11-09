"""The weekly pack (organic video I2 to I5, Task 21): the week plan page against the reference page, the one approval
within the week's budget, the slot runs (the flexible day apart), the week cap of a slot's pack, the week's delivery
page and posting plan, `tm schedule` with PB04's alias, next week's run after this one, and `tm due`.

The week is ExampleEdu's dry cycle (`exampleedu.week()`: the handoff's week_v01.json with the plugin block on every idea)."""

import copy
import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import exampleedu
from tm import (brand, config, flow, mcp_saves, organic, organic_config, organic_pack, organic_proposals,
                organic_research, organic_week, organic_week_delivery, page, state, stepchecks, trends)
from tm.cli import main
from tm.organic_pages import week as week_page, worded
from tm.playbooks import ORGANIC_VIDEO, TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "organic"
TODAY = date(2026, 11, 7)            # the week run's day (Saturday before the week): slot runs begin with it
SLUG = "6d2e3f40-0000-4000-8000-000000000021"
W2_VIDEO = 1.46                      # the Wednesday video ("dad, why is _"), its cost in week_v01.json


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(organic_week, "_today", lambda: TODAY)
    monkeypatch.setattr(organic_proposals, "_today", lambda: TODAY)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _later(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def _used_m1(ws: Path) -> None:
    """M1 (Tung Tung Tung Sahur, brainrot part 1) is made: its trend is in the channel's used trends."""
    tid = exampleedu.full_ids()["c20bfd65"]
    organic_research.record_used(ws, exampleedu.CHANNEL, [
        {"trend_id": tid, "name": "Tung Tung Tung Sahur Brainrot Memes", "kind": "topic_trend",
         "run": "2026-11-06_walkthrough-exampleedu", "video": "m1", "series": "brainrot", "used": "2026-11-06"}])


def _week_run(tmp_path, level="big_calls", name=None):
    """The ExampleEdu run as a week run (outputs weekly_plan) at `level`, with r2's card saved and M1 made."""
    run = exampleedu.build(tmp_path / "ws") if name is None else _another(tmp_path / "ws", name)
    exampleedu.save_week_cards(run)
    s = state.load(run)
    s.outputs, s.level = ["weekly_plan"], level
    state.save(run, s)
    config.save(run, {**config.load(run), "kind": "weekly_plan"})
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="ok")
    if name is None:
        _used_m1(tmp_path / "ws")
    return run


def _another(ws: Path, name: str) -> RunFolder:
    run = RunFolder.create(ws, name, exampleedu.CREATED + timedelta(days=7), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": [exampleedu.CHANNEL], "page_lang": "pl"})
    exampleedu.save_trends(run)
    return run


def _write(run, data, stem="week"):
    path = run.next_version("03_wip", stem, "json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _checked(run, capsys, data=None):
    path = _write(run, data or exampleedu.week())
    code, out = _cli(capsys, "organic", "week", "check", "--run", str(run.path), "--file", "03_wip/" + path.name)
    assert code == 0, out
    return path


def _problems(run, data):
    return organic_week.check(run, data, config.load(run))


def _page(run, capsys):
    code, out = _cli(capsys, "organic", "page", "week", "--run", str(run.path))
    assert code == 0, out
    page.record_published(run, week_page.PAGE, SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    return out


def _doc(slot: str, **data) -> str:
    return json.dumps({"id": slot, "data": {"slot": slot, "updated_at": "2026-11-07T10:00:00.000Z", **data},
                       "version": 1}, ensure_ascii=False)


def _db(run, *docs: str, minutes=1):
    summary = json.dumps({"count": len(docs), "nextCursor": None, "notice": "Documents are in <untrusted-document-9a>."})
    text = "\n".join([summary, "<untrusted-document-9a>", *docs, "</untrusted-document-9a>"])
    return mcp_saves.save(run, "db_list", {"slug": SLUG, "collection": "week", "limit": 1000}, {"raw": text},
                          at=_later(minutes), server="claude-artifacts")


def _read(run, capsys, *docs: str, minutes=1):
    _db(run, *docs, minutes=minutes)
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "week")
    assert code == 0, out
    return out


def _at_i3(run):
    """The run past I2 (test_organic_flow walks the steps; here the week's own commands are under test)."""
    s = state.load(run)
    s.step = "I3"
    state.save(run, s)


def _approve(run):
    flow.decide(run, "week", "approve", by="user", note=None)


def _ready(run, capsys, *docs):
    """Checked, page built and published, decisions read (`docs`, else an OK for every day), past I2, approved."""
    _checked(run, capsys)
    _page(run, capsys)
    _read(run, capsys, *(docs or [_doc(k, decision="ok") for k in ("pon", "śr", "pt", "sob", "niedz")]))
    _at_i3(run)
    _approve(run)


def _slot_runs(run):
    return sorted(p for p in run.path.parent.iterdir() if p != run.path and (p / "run.json").is_file())


# --- I2: the page and the one approval -----------------------------------------------------------------

@pytest.mark.private_data
def test_week_page_matches_original_after_wording_table(tmp_path, capsys):
    """The week page the plugin builds from ExampleEdu's week (with its plugin blocks) is the reference page, made by
    the handoff's weekly_page.py under Python 3.12 (fixtures/organic/README.md), once the wording table is applied."""
    run = _week_run(tmp_path)
    assert organic_week.checked_gap(run) is not None and week_page.built_gap(run) is not None
    _checked(run, capsys)
    assert organic_week.checked_gap(run) is None and stepchecks.run("week_checked", run) is None
    out = _page(run, capsys)
    assert out["folder"] == "04_final/week_v01" and out["lang"] == "pl"
    built = (run.path / "04_final" / "week_v01" / "index.html").read_text(encoding="utf-8")
    golden = (FIXTURES / "week_golden.html").read_text(encoding="utf-8").replace("\r", "")
    assert built == worded(golden, "pl")
    assert week_page.built_gap(run) is None and stepchecks.run("week_page_built", run) is None
    week = exampleedu.week()
    week["note"] = week["note"].replace("Suchy", "Mokry")
    _checked(run, capsys, week)                                          # a new checked week: the page is stale
    assert "built from the checked week plan" in week_page.built_gap(run)
    hostile = exampleedu.week()
    hostile["slots"][0]["title"] = "</script><!-- «x» \\"
    with pytest.raises(ValueError, match="en or pl"):
        week_page.render({k: v for k, v in hostile.items() if k != "lang"})   # no Polish default
    text = week_page.render(hostile)
    script = text[text.index("<script>window.__L__"):text.index("</script>", text.index("<script>window.__L__"))]
    assert "</script><!--" not in script and "<\\/script><\\u0021--" in script


@pytest.mark.private_data
def test_over_budget_week_cannot_be_approved(tmp_path, capsys):
    """$5 for the week. The manifest's meter: $2.94 as planned, $1.48 with Wednesday as a script, $2.81 after
    Monday's swap for r2. With r2 priced at $2.46 (its host video at 1080p) that swap makes $5.40: the decisions are
    read and say so, and `tm decide week approve` is refused with the page's own words; back within the budget, the
    week is approved."""
    run = _week_run(tmp_path)
    week = exampleedu.week()
    assert organic_week.total(week, []) == exampleedu.WEEK_TOTALS[0]
    script = [("śr", {"output": "script"})]
    assert organic_week.total(week, script) == exampleedu.WEEK_TOTALS[1]
    assert organic_week.total(week, [*script, ("pon", {"idea": "r2"})]) == exampleedu.WEEK_TOTALS[2]
    assert organic_week.total(week, [("pon", {"decision": "skip"}), ("_week", {"total": 99})]) == 2.94
    with pytest.raises(ValueError, match="r9"):
        organic_week.total(week, [("pon", {"idea": "r9"})])
    with pytest.raises(ValueError, match="two days"):
        organic_week.choices(week, [("pon", {"idea": "w2"})])

    pricey = exampleedu.week()
    pricey["reserves"][1]["cost_video"] = 2.46
    _checked(run, capsys, pricey)
    _page(run, capsys)
    out = _read(run, capsys, _doc("pon", idea="r2", decision="ok"), _doc("_week", approved=True, total=5.4))
    assert out["total"] == 5.40 and out["approved"] is True
    assert organic_week.OVER_BUDGET in out["message"] and "$5.40 of $5.00" in out["message"]
    _at_i3(run)
    with pytest.raises(ValueError) as exc:
        _approve(run)
    assert organic_week.OVER_BUDGET in str(exc.value) and "nothing was decided" in str(exc.value)
    assert not [d for d in state.load(run).decisions if d["checkin"] == "week"]
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 2 and "approves the week" in out["message"] and out["message"].endswith(AGAIN + ".")

    out = _read(run, capsys, _doc("pon", idea="r2", decision="ok", output="script",
                                  updated_at="2026-11-07T11:00:00.000Z"), minutes=2)
    assert out["total"] == 2.94 and out["decisions"]["mon"]["idea"] == "r2"
    _approve(run)
    assert [d["choice"] for d in state.load(run).decisions if d["checkin"] == "week"] == ["approve"]


@pytest.mark.private_data
def test_used_trend_slot_refused_unless_series(tmp_path, capsys):
    """Sunday's brainrot part 2 builds on M1's trend, which the channel made a video from: it passes as the series
    `brainrot`, and without a series it is refused (a reserve too). The other checks: the slots on the posting days,
    the flexible day's slot flexible, the week's budget, a reserve, trends resolved to saved cards, folder-safe ids
    (the PR D rule for section ids, which the proposals check now has as well)."""
    run = _week_run(tmp_path)
    assert _problems(run, exampleedu.week()) == []
    week = exampleedu.week()
    week["slots"][4]["plugin"]["series"] = None
    week["reserves"][0]["plugin"]["trends"] = [{"id": "c20bfd65"}]
    found = {p.field: p for p in _problems(run, week)}
    assert set(found) == {"slots[4].plugin.series", "reserves[0].plugin.series"}
    assert "already made a video" in found["slots[4].plugin.series"].what
    assert "series" in found["slots[4].plugin.series"].todo
    code, out = _cli(capsys, "organic", "week", "check", "--run", str(run.path), "--file", str(_write(run, week)))
    assert code == 2 and out["status"] == "stop" and out["message"].endswith(AGAIN + ".")

    week = exampleedu.week()
    week["slots"].pop(1)                                                 # 4 slots for weekly.per_week 5
    week["slots"][1]["day"] = "wt"                                       # Tuesday is not a posting day
    week["slots"][3]["plugin"]["flexible"] = False                       # Sunday's slot is the flexible day
    week["slots"][0]["plugin"]["flexible"] = True
    week["budget"] = 7.0
    week["reserves"] = []
    week["slots"][2]["plugin"]["trends"] = [{"id": "deadbeef"}]          # no saved card
    week["lang"] = "en"
    fields = {p.field for p in _problems(run, week)}
    assert {"slots", "slots[1].day", "slots[3].plugin.flexible", "slots[0].plugin.flexible", "budget", "reserves",
            "slots[2].plugin.trends[0].id", "lang"} <= fields

    for budget in (float("nan"), float("inf"), 0.0, -5.0):              # m1: the week's yes means a real budget
        week = exampleedu.week()
        week["budget"] = budget
        assert "budget" in {p.field for p in _problems(run, week)}, budget
    week = exampleedu.week()
    week["slots"][0]["cost_video"] = float("inf")
    week["reserves"][0]["cost_script"] = float("nan")
    assert {"slots[0].cost_video", "reserves[0].cost_script"} <= {p.field for p in _problems(run, week)}

    for bad, why in (("../w1", "cannot name a folder"), ("CON", "Windows keeps"), ("W2", "in any case")):
        week = exampleedu.week()
        week["slots"][0]["id"] = bad
        assert why in " ".join(p.what for p in _problems(run, week)), bad
    idea = exampleedu.build(tmp_path / "other")
    data = exampleedu.proposals()
    data["proposals"][0]["id"] = "m1/x"
    data["proposals"][1]["id"] = "M1/X".lower().replace("/", "/")
    data["proposals"][2]["id"] = "aux"
    problems = organic_proposals.check(idea, data, config.load(idea))
    said = {p.field: p.what for p in problems if p.field.endswith(".id")}
    assert "cannot name a folder" in said["proposals[0].id"] and "used twice" in said["proposals[1].id"]
    assert "Windows keeps" in said["proposals[2].id"]


# --- I3: the slot runs and the flexible day -------------------------------------------------------------

@pytest.mark.private_data
def test_start_skips_flexible_slot_and_due_reminds(tmp_path, capsys):
    """An approved week starts one production run per OK slot but the flexible one, in day order, each naming its
    week and slot, with the slot's output, the week's level and platforms; Friday is skipped. `tm due` reminds the
    user the day before the flexible day and on the day itself (only then), until the flexible day is started from
    fresh trends."""
    run = _week_run(tmp_path, level="every_step")
    ws = tmp_path / "ws"
    _ready(run, capsys, _doc("pon", decision="ok"), _doc("śr", decision="ok", output="script"),
           _doc("pt", decision="skip"))
    assert organic_week.started_gap(run) is not None
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0, out
    assert [(x["day"], x["proposal"], x["output"]) for x in out["started"]] == [
        ("mon", "w1", "video"), ("wed", "w2", "script"), ("sat", "w4", "video")]
    assert "flexible day (sun, 2026-11-15)" in out["message"]
    ref = run.path.relative_to(ws).as_posix()
    runs = _slot_runs(run)
    assert [p.name for p in runs] == ["2026-11-07_exampleedu-w1", "2026-11-07_exampleedu-w2", "2026-11-07_exampleedu-w4"]
    for path, day, outputs in zip(runs, ("mon", "wed", "sat"), (["organic_video"], ["script_to_film"],
                                                                ["organic_video"])):
        s = state.load(RunFolder.open(path))
        assert s.organic["week"] == ref and s.organic["parent"] == ref and s.organic["slot"] == day
        assert s.outputs == outputs and s.level == "every_step"
        assert config.load(RunFolder.open(path))["platforms"] == ["tiktok", "instagram", "youtube", "facebook"]
    assert organic_week.started_gap(run) is None and stepchecks.run("slots_started", run) is None
    rows = [json.loads(x) for x in (ws / "library" / "organic" / "exampleedu" / "decisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert sorted((r["proposal"], r["decision"]) for r in rows) == [("w1", "produce"), ("w2", "produce"),
                                                                     ("w3", "skip"), ("w4", "produce")]
    assert _problems(run, exampleedu.week()) == []                     # its own slots' trends are not another use
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0 and out["started"] == [] and len(out["already_started"]) == 3
    assert len(_slot_runs(run)) == 3

    due = "Week 2026-11-09: the flexible day's video is due {}. Ask Claude to make the flexible day's video."
    assert [i["message"] for i in flow.due(ws, date(2026, 11, 14))] == [due.format("tomorrow")]
    assert [i["message"] for i in flow.due(ws, date(2026, 11, 15))] == [due.format("today")]   # m3: and on the day
    assert flow.due(ws, date(2026, 11, 13)) == [] and flow.due(ws, date(2026, 11, 16)) == []

    idea = copy.deepcopy(exampleedu.week()["reserves"][0])                 # Adopt Me, on its card fetched again
    idea.update({"id": "f1", "cost_video": 0.5})
    idea["plugin"]["flexible"] = True
    flex = _write(run, idea, stem="flexible")
    used = ws / "library" / "organic" / "exampleedu" / "used_trends.jsonl"
    kept = used.read_text(encoding="utf-8")
    used.write_text(kept + "{damaged\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file", str(flex))
    assert code == 2 and "library cannot be read" in out["message"]          # a Stop, not exit 1 (M4)
    used.write_text(kept, encoding="utf-8")
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file", str(flex))
    assert code == 2 and "no search was saved since the week was approved" in out["message"]
    trends.save_answer(run, "search_trends", {"about": "Roblox"}, [], at=_later(1))
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file", str(flex))
    assert code == 2 and "were saved before the week was approved" in out["message"]
    tid = exampleedu.full_ids()["e54e5955"]
    card = json.loads((exampleedu.TRENDS / "card_e54e5955.json").read_text(encoding="utf-8"))
    trends.save_answer(run, "get_trend", {"trend_id": tid}, card, at=_later(2))
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file", str(flex))
    assert code == 0, out
    assert out["started"]["proposal"] == "f1" and out["day"] == "sun"
    prod = RunFolder.open(ws / out["started"]["path"])
    assert state.load(prod).organic["slot"] == "sun" and state.load(prod).organic["week"] == ref
    assert flow.due(ws, date(2026, 11, 14)) == [] and flow.due(ws, date(2026, 11, 15)) == []
    rows = [json.loads(x) for x in (ws / "library" / "organic" / "exampleedu" / "decisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert [(r["proposal"], r["decision"], r["started"]) for r in rows if r["proposal"] == "f1"] == [
        ("f1", "produce", out["started"]["run"])]                       # the flexible day's idea is logged
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file", str(flex))
    assert code == 2 and "already started" in out["message"]


def _decisions_again(run, capsys, *docs, minutes):
    """The week page's decisions read again, later (`minutes` after now), as a new db_list."""
    return _read(run, capsys, *docs, minutes=minutes)


@pytest.mark.private_data
def test_one_run_per_day_a_started_day_is_not_swapped(tmp_path, capsys):
    """Fix round I1: a day has one run whatever its idea. Monday started as w1, then swapped for r1 on the page: the
    yes and the start are refused, naming Monday's run and `tm organic drop-slot`; Monday keeps one run. Once the user
    drops it (its spend still counts), the swapped week is approved again and Monday starts as r1."""
    run = _week_run(tmp_path)
    _ready(run, capsys, _doc("pon", decision="ok"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
           _doc("sob", decision="skip"))
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0 and [x["proposal"] for x in out["started"]] == ["w1"]
    _decisions_again(run, capsys, _doc("pon", decision="ok", idea="r1", updated_at="2026-11-07T11:00:00.000Z"),
                     _doc("śr", decision="skip"), _doc("pt", decision="skip"), _doc("sob", decision="skip"), minutes=2)
    with pytest.raises(ValueError) as exc:
        flow.decide(run, "week", "approve", by="user", note=None, change=True)
    said = str(exc.value).replace("\\", "/")
    assert "2026-11-07_exampleedu-w1" in said and "tm organic drop-slot" in said and "choose r1" in said
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 2 and "tm organic drop-slot" in out["message"] and out["message"].endswith(AGAIN + ".")
    assert [p.name for p in _slot_runs(run)] == ["2026-11-07_exampleedu-w1"]
    assert "drop-slot" in organic_week.started_gap(run)

    code, out = _cli(capsys, "organic", "drop-slot", "--run", str(run.path), "--day", "tue", "--note", "x")
    assert code == 1 and "No run is started for 'tue'" in out["message"]
    code, out = _cli(capsys, "organic", "drop-slot", "--run", str(run.path), "--day", "pon", "--note",
                     "make the Adopt Me one instead")
    assert code == 0 and out["day"] == "mon" and out["run"] == "2026-11-07_exampleedu-w1"
    gone = RunFolder.open(_slot_runs(run)[0])
    assert state.load(gone).status == "done" and state.load(gone).organic["dropped"]["note"].startswith("make the")
    assert organic_week.started_days(run) == {}
    flow.decide(run, "week", "approve", by="user", note=None, change=True)
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0 and [(x["day"], x["proposal"]) for x in out["started"]] == [("mon", "r1")]
    assert sorted(organic_week.started_days(run)) == ["mon"]


@pytest.mark.private_data
def test_decisions_after_the_yes_need_a_new_yes(tmp_path, capsys):
    """Fix round I2: the yes covers the decisions it was given on (the decisions file and each day's idea, output and
    OK). Friday ticked on again after the yes, or Saturday swapped for a reserve, stops the start until the user says
    yes again (`tm decide week approve --change`); a re-read that changes nothing (a note) keeps the yes."""
    run = _week_run(tmp_path)
    _ready(run, capsys, _doc("pt", decision="skip"))
    yes = organic_week.approval(run)
    assert yes["covers"]["decisions"] == "03_wip/decisions_week_v01.json" and yes["covers"]["total"] == 1.65
    _decisions_again(run, capsys, _doc("pt", decision="skip", note="later maybe",
                                       updated_at="2026-11-07T11:00:00.000Z"), minutes=2)
    assert organic_week._approval_gap(run, *organic_week._current(run)[:3]) is None      # only a note changed
    for minutes, doc in ((3, _doc("pt", decision="ok", updated_at="2026-11-07T12:00:00.000Z")),
                         (4, _doc("sob", decision="ok", idea="r1", updated_at="2026-11-07T13:00:00.000Z"))):
        _decisions_again(run, capsys, doc, minutes=minutes)
        code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
        assert code == 2 and "tm decide week approve --change" in out["message"], out
        assert "approves the week as it stands now" in out["message"] and _slot_runs(run) == []
        idea = copy.deepcopy(exampleedu.week()["reserves"][0])
        idea.update({"id": "f1"})
        idea["plugin"]["flexible"] = True
        code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file",
                         str(_write(run, idea, stem="flexible")))
        assert code == 2 and "tm decide week approve --change" in out["message"]
        flow.decide(run, "week", "approve", by="user", note=None, change=True)
        assert organic_week.approval(run)["covers"]["decisions"].endswith(f"_v0{minutes}.json")
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0 and [(x["day"], x["proposal"]) for x in out["started"]] == [
        ("mon", "w1"), ("wed", "w2"), ("fri", "w3"), ("sat", "r1")]


@pytest.mark.private_data
def test_slots_in_date_order_and_an_unknown_slot_refused(tmp_path, capsys):
    """Fix round M3: a week of any seven days in a row (Thursday to Wednesday) is in date order: Friday, Saturday,
    Sunday, then Monday and Wednesday. A slot whose day is not a day, or a slot run naming none, is refused."""
    week = exampleedu.week()
    week["week"] = "2026-11-12/2026-11-18"
    assert organic_week.order(week) == ["fri", "sat", "sun", "mon", "wed"]
    assert list(organic_week.choices(week, [])) == ["fri", "sat", "sun", "mon", "wed"]
    bad = copy.deepcopy(week)
    bad["slots"][0]["day"] = "funday"
    with pytest.raises(ValueError, match="not a day of the week"):
        organic_week.order(bad)
    run = _week_run(tmp_path)
    _ready(run, capsys, _doc("śr", decision="skip"), _doc("pt", decision="skip"), _doc("sob", decision="skip"))
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0
    prod = RunFolder.open(_slot_runs(run)[0])
    s = state.load(prod)
    s.organic = {**s.organic, "slot": "funday"}
    state.save(prod, s)
    with pytest.raises(Stop, match="not a day of the week"):
        organic_week.slot_runs(run)


def _money(prod: RunFolder, *, planned: float, spent: float, approved: float) -> None:
    s = state.load(prod)
    s.planned, s.spend, s.budgets = {"ai_usd": planned}, {"ai_usd": spent}, {"ai_usd": approved, "voice_credits": 500}
    state.save(prod, s)


@pytest.fixture
def tools_ready(tmp_path, monkeypatch):
    """`tm tool` with its keys set and its tiers installed; its child records a call, which no test here expects."""
    from tm import tools
    data = tmp_path / "plugin data"
    data.mkdir()
    (data / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_test\nELEVENLABS_API_KEY=el_test\n")
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setattr(tools.envtiers, "installed", lambda tier: True)
    calls = []
    monkeypatch.setattr(tools.subprocess, "run", lambda argv, **kw: calls.append(argv))
    return calls


@pytest.mark.private_data
def test_a_dropped_run_spends_nothing_and_its_day_starts_again(tmp_path, capsys, tools_ready):
    """Fix round 2, N1: once Monday's run is dropped, every paid tool in it is refused before anything is spent
    (Replicate and ElevenLabs alike), and its approved budgets are capped at what it spent. N2: the day starts again
    with the same idea in a new folder, and the week still counts what the dropped run spent. m1: that spend is in the
    sum the week's yes is checked against, and the refusal says so."""
    run = _week_run(tmp_path)
    ws = tmp_path / "ws"
    _ready(run, capsys, _doc("pon", decision="ok"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
           _doc("sob", decision="skip"))
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    mon = RunFolder.open(ws / out["started"][0]["path"])
    _money(mon, planned=2.0, spent=0.5, approved=2.0)
    code, out = _cli(capsys, "organic", "drop-slot", "--run", str(run.path), "--day", "mon", "--note", "again please")
    assert code == 0 and out["spent"] == 0.5
    assert state.load(mon).budgets == {"ai_usd": 0.5, "voice_credits": 0.0}
    spec = mon.path / "03_wip" / "take_spec.json"
    spec.write_text("{}", encoding="utf-8")
    for argv in (["replicate_run", "--run", str(mon.path), str(spec), "--name", "take", "--cost", "1.2"],
                 ["elevenlabs", "tts", "--run", str(mon.path), "--text", "hej", "--cost", "40"]):
        capsys.readouterr()
        code = main(["tool", *argv, "--json"])
        said = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert code == 2 and "was dropped from its week" in said["message"] and "nothing was spent" in said["message"]
        assert "the run is finished" in said["message"] and "same place" not in said["message"]          # m4
        assert f"tm organic start --run {run.path.relative_to(ws).as_posix()}" in said["message"].replace("\\", "/")
    assert tools_ready == [] and state.load(mon).spend == {"ai_usd": 0.5}

    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))       # the same idea, the same decisions
    assert code == 0, out
    assert [(x["day"], x["proposal"], x["run"]) for x in out["started"]] == [("mon", "w1", "2026-11-07_exampleedu-w1-2")]
    again = RunFolder.open(ws / out["started"][0]["path"])
    assert organic_week.week_left(again) == (5.0, 0.5, 4.5)                 # the dropped run's spend still counts
    assert organic_week.dropped_spend(run) == 0.5
    assert state.load(run).organic["dropped"][0]["spent"] == 0.5             # r1: the week run holds it
    shutil.rmtree(mon.path)                                                  # r1: the dropped folder deleted
    assert organic_week.week_left(again) == (5.0, 0.5, 4.5)
    assert organic_week.dropped_spend(run) == 0.5 and organic_week.budget_gap(run) is None

    pricey = exampleedu.week()
    pricey["slots"][0]["cost_video"] = 4.60                                  # Monday's video now at $4.60
    _checked(run, capsys, pricey)
    s = state.load(run)
    s.pages.pop("week", None)
    state.save(run, s)
    _page(run, capsys)
    _read(run, capsys, _doc("pon", decision="ok"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
          _doc("sob", decision="skip"), _doc("niedz", decision="skip"), minutes=3)
    gap = organic_week.budget_gap(run)
    assert "$5.10 of $5.00" in gap and "with $0.50 already spent on dropped days" in gap
    assert organic_week.OVER_BUDGET in gap


@pytest.mark.private_data
def test_the_week_budget_is_set_on_the_users_word(tmp_path, capsys):
    """PR E review I2: `tm organic week budget` sets the week's budget on the user's words. It is logged in the week
    run's approvals, written to its config (which every slot's pack reads) and to the checked week file (still
    checked), and the week's yes is void until the user says yes again at the new budget (`tm decide week approve
    --change`); until then a started slot's cap is the lower of the two (re-review N2). A budget below what the week's
    videos already planned, approved or spent is refused, and so is an amount that is not one."""
    run = _week_run(tmp_path)
    ws = tmp_path / "ws"
    _ready(run, capsys, _doc("pon", decision="ok"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
           _doc("sob", decision="skip"))
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    mon = RunFolder.open(ws / out["started"][0]["path"])
    _money(mon, planned=2.0, spent=0.5, approved=2.0)
    week_file = run.path / state.load(run).checked["week"]["file"]
    for usd in ("1.5", "0", "-3", "nan", "inf"):
        code, out = _cli(capsys, "organic", "week", "budget", "--run", str(run.path), "--usd", usd, "--note", "ok")
        assert code == 1 and state.load(run).approvals == [], (usd, out)
    assert "$2.00" in _cli(capsys, "organic", "week", "budget", "--run", str(run.path), "--usd", "1.5",
                           "--note", "ok")[1]["message"]
    code, out = _cli(capsys, "organic", "week", "budget", "--run", str(run.path), "--usd", "7", "--note", "  ")
    assert code == 1 and "user's own words" in out["message"]

    code, out = _cli(capsys, "organic", "week", "budget", "--run", str(run.path), "--usd", "7", "--note",
                     "yes, make it $7")
    assert code == 0, out
    assert "tm decide week approve" in out["message"] and "--change" in out["message"]
    assert config.load(run)["budget"]["per_week_usd"] == 7.0
    assert json.loads(week_file.read_text(encoding="utf-8"))["budget"] == 7.0
    assert organic_week.checked_gap(run) is None                              # the week file is still the checked one
    assert state.load(run).approvals[-1]["kind"] == "per_week_usd"
    assert state.load(run).approvals[-1]["amount"] == 7.0
    assert state.load(run).approvals[-1]["note"] == "yes, make it $7"
    assert organic_week.week_left(mon) == (5.0, 0.0, 5.0)                      # N2: not before the new yes
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 2 and "tm decide week approve --change" in out["message"] and "$7.00" in out["message"], out
    flow.decide(run, "week", "approve", by="user", note=None, change=True)
    assert organic_week.week_left(mon) == (7.0, 0.0, 7.0)                      # the yes at $7 reaches the slot
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0 and len(out["already_started"]) == 1, out
    code, out = _cli(capsys, "organic", "week", "budget", "--run", str(run.path), "--usd", "3", "--note", "less")
    assert code == 0 and organic_week.week_left(mon) == (3.0, 0.0, 3.0)        # a lower budget holds at once


@pytest.mark.private_data
def test_the_flexible_days_output_and_a_damaged_slot(tmp_path, capsys):
    """Fix round 2, m2: once the flexible day is started, a change of its output (not its idea, which is the fresh
    one) is a conflict. m3: a slot run that cannot be read is a gap of `week_in_budget`, never a raise."""
    run = _week_run(tmp_path)
    ws = tmp_path / "ws"
    _ready(run, capsys, _doc("pon", decision="skip"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
           _doc("sob", decision="skip"), _doc("niedz", decision="ok"))
    assert _cli(capsys, "organic", "start", "--run", str(run.path))[0] == 0
    trends.save_answer(run, "search_trends", {"about": "Roblox"}, [], at=_later(1))
    tid = exampleedu.full_ids()["e54e5955"]
    card = json.loads((exampleedu.TRENDS / "card_e54e5955.json").read_text(encoding="utf-8"))
    trends.save_answer(run, "get_trend", {"trend_id": tid}, card, at=_later(2))
    idea = copy.deepcopy(exampleedu.week()["reserves"][0])
    idea.update({"id": "f1"})
    idea["plugin"]["flexible"] = True
    code, out = _cli(capsys, "organic", "flexible", "--run", str(run.path), "--file",
                     str(_write(run, idea, stem="flexible")))
    assert code == 0, out
    rows = {"sun": {"idea": "w5", "output": "video", "decision": "ok"}}
    assert organic_week._conflicts(run, exampleedu.week(), rows) == []         # its idea is the fresh one: no conflict
    rows["sun"]["output"] = "script"
    found = organic_week._conflicts(run, exampleedu.week(), rows)
    assert len(found) == 1 and "sun's run" in found[0] and "a script to film" in found[0]
    prod = ws / out["started"]["path"]
    (prod / "run.json").write_text("{not json", encoding="utf-8")
    gap = organic_week.budget_gap(run)
    assert isinstance(gap, str) and "cannot be read" in gap


def _slot_production(ws: Path, week_ref: str, name: str, *, planned=0.0, spent=0.0) -> RunFolder:
    """Another slot run of the week: what it planned and spent."""
    other = RunFolder.create(ws, name, TODAY, playbook=ORGANIC_VIDEO)
    s = state.load(other)
    s.outputs, s.organic = ["organic_video"], {"week": week_ref, "parent": week_ref, "proposal": name}
    s.planned, s.spend = {"ai_usd": planned}, {"ai_usd": spent}
    state.save(other, s)
    return other


def _m5_slot(tmp_path):
    """M5's PL production run as a slot of a $5 week run: (the slot run, the week run, its ref, M5's pack)."""
    run = exampleedu.build(tmp_path / "ws")
    from petstore import save_prices
    save_prices(run)
    m5 = next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m5")
    cfg = config.load(run)
    cfg.update({"kind": "production", "output": "ai_video", "channels": [exampleedu.CHANNEL]})
    config.save(run, cfg)
    s = state.load(run)
    s.outputs = ["organic_video"]
    state.save(run, s)
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="ok")
    ws = tmp_path / "ws"
    week = RunFolder.create(ws, "exampleedu-week", TODAY, playbook=ORGANIC_VIDEO)
    config.save(week, {**organic_config.defaults(), "channels": [exampleedu.CHANNEL]})
    week_ref = week.path.relative_to(ws).as_posix()
    s = state.load(run)
    s.organic = {**s.organic, "proposal": "m5", "channel": exampleedu.CHANNEL, "week": week_ref}
    state.save(run, s)
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"proposal": m5, "channel": exampleedu.CHANNEL}),
                                                       encoding="utf-8")
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    return run, week, week_ref, pack


@pytest.mark.private_data
def test_slot_pack_capped_by_week_left(tmp_path):
    """M5's PL pack ($1.30) as a slot of a $5 week: it passes while the week's other slots have $3.70 planned or spent
    (each counts the largest of planned, approved and spent; a dropped one what it spent), exactly at the remainder
    (r5), and is refused, with the cheaper options, once they have $3.75. The week's budget is the week run's own (fix
    round M1): raised there, it reaches the slot. A week run or another slot's run.json that cannot be read is a Stop
    (M2)."""
    run, week, week_ref, pack = _m5_slot(tmp_path)
    ws = tmp_path / "ws"
    _slot_production(ws, week_ref, "w1", planned=2.00, spent=0.50)
    second = _slot_production(ws, week_ref, "w3", planned=1.00, spent=1.70)
    _slot_production(ws, "runs/03-organic-ai-video/another-week", "x9", planned=5.00)   # another week's
    dropped = _slot_production(ws, week_ref, "w4", planned=3.00, spent=0.00)   # dropped before spending
    s = state.load(dropped)
    s.organic = {**s.organic, "dropped": {"at": "2026-11-07T10:00:00+00:00", "note": "not this one"}}
    state.save(dropped, s)
    assert organic_week.week_left(run) == (5.0, 3.70, 1.30)
    assert organic_pack.check(run, pack, config.load(run), stage="pack", today=TODAY) == []   # at the remainder
    s = state.load(second)
    s.spend = {"ai_usd": 1.75}
    state.save(second, s)
    found = [p for p in organic_pack.check(run, pack, config.load(run), stage="pack", today=TODAY)
             if p.field == "cost.totals.ai_usd"]
    assert len(found) == 1 and "over the week's remainder of $1.25" in found[0].what
    assert "its other videos planned, approved or spent $3.75" in found[0].what and "Cheaper:" in found[0].todo
    assert f"tm organic week budget --run {week_ref} --usd" in found[0].todo                # I2: the route
    config.save(week, {**config.load(week), "budget": {"per_run_usd": 5, "per_week_usd": 6}})   # raised in the week
    assert config.load(run)["budget"]["per_week_usd"] == 5                    # the slot's own copy is not read
    assert organic_week.week_left(run) == (6.0, 3.75, 2.25)
    assert organic_pack.check(run, pack, config.load(run), stage="pack", today=TODAY) == []
    (dropped.path / "run.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(Stop, match="cannot be read"):
        organic_week.week_left(run)
    (dropped.path / "run.json").unlink()
    (week.path / "config.yaml").unlink()
    with pytest.raises(Stop, match="cannot be read"):
        organic_week.week_left(run)
    s = state.load(run)
    s.organic = {k: v for k, v in s.organic.items() if k != "week"}       # a video of no week: the run's budget only
    state.save(run, s)
    assert organic_week.week_left(run) is None
    assert organic_pack.check(run, pack, config.load(run), stage="pack", today=TODAY) == []


@pytest.mark.private_data
def test_week_cap_counts_what_another_slot_may_still_spend(tmp_path):
    """PR E review I1: Monday's pack was planned at $3.00 and approved, then re-checked cheaper at $1.50 with the same
    items (the yes holds, so the approval stays at $3.00). Monday may still spend $3.00, so Wednesday sees $2.00 left
    of the $5 week, not $3.50: a $2.10 pack is refused, $1.30 passes, and the two runs together cannot spend past
    $5."""
    from tm import budget
    run, _, week_ref, pack = _m5_slot(tmp_path)
    ws = tmp_path / "ws"
    mon = _slot_production(ws, week_ref, "w1")
    mon_pack = copy.deepcopy(pack)
    for total, version in ((3.00, 1), (1.50, 2)):
        mon_pack["cost"]["totals"]["ai_usd"] = total
        path = mon.path / "03_wip" / f"pack_v0{version}.json"
        path.write_text(json.dumps(mon_pack, ensure_ascii=False), encoding="utf-8")
        got = organic_pack.record(mon, path, mon_pack, stage="pack")
        if version == 1:
            s = state.load(mon)
            budget._set(mon, s, "ai_usd", 3.00, "the pack's yes")
    assert got["replanned"] is False                                          # the cheaper re-check keeps the yes
    assert state.load(mon).planned["ai_usd"] == 1.50 and state.load(mon).budgets["ai_usd"] == 3.00
    assert organic_week.week_left(run) == (5.0, 3.0, 2.0)
    assert organic_pack.check(run, pack, config.load(run), stage="pack", today=TODAY) == []
    dear = copy.deepcopy(pack)
    dear["cost"]["totals"]["ai_usd"] = 2.10
    found = [p for p in organic_pack.check(run, dear, config.load(run), stage="pack", today=TODAY)
             if "week's remainder" in p.what]
    assert len(found) == 1 and "over the week's remainder of $2.00" in found[0].what
    s = state.load(run)
    budget._set(run, s, "ai_usd", 2.00, "Wednesday's pack at the week's remainder")
    assert budget.spend(mon, "ai_usd", 2.90, "Monday's takes") == 0
    assert budget.spend(run, "ai_usd", 2.00, "Wednesday's takes") == 0
    assert budget.spend(mon, "ai_usd", 0.20, "one more") == 2                  # over Monday's own $3.00
    spent = state.load(mon).spend["ai_usd"] + state.load(run).spend["ai_usd"]
    assert spent == pytest.approx(4.90) and spent <= 5.0


# --- I4: the week's delivery page and the posting plan ----------------------------------------------------

def _made_video(prod: RunFolder) -> None:
    """A slot run's AI video as G1 to G2 leave it: the checked pack, the final and its upload copy, the kit."""
    pid = state.load(prod).organic["proposal"]
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["id"] = pid
    path = prod.path / "03_wip" / "pack_v01.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    stepchecks.mark(prod, "pack", path)
    final = prod.path / "04_final" / f"{pid}_final_v01.mp4"
    final.write_bytes(b"final " + pid.encode())
    final.with_name(f"{pid}_final_v01_upload.mp4").write_bytes(b"upload " + pid.encode())
    kit = exampleedu.kit("M5_pl_kit_v01")
    kit.update({"id": pid, "video": f"04_final/{pid}_final_v01.mp4"})
    (prod.path / "04_final" / "kits").mkdir(parents=True, exist_ok=True)
    (prod.path / "04_final" / "kits" / f"{pid}_kit_v01.json").write_text(json.dumps(kit, ensure_ascii=False),
                                                                          encoding="utf-8")


def _made_script(prod: RunFolder) -> None:
    """A slot run's script to film as E3 leaves it: the checked script and its page with the Markdown."""
    pid = state.load(prod).organic["proposal"]
    data = exampleedu.script()
    data.update({"id": pid, "lang": "pl"})
    path = prod.path / "03_wip" / f"script_{pid}_pl_v01.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    stepchecks.mark(prod, "script", path)
    folder = prod.path / "04_final" / f"{pid}_script_pl_v01"
    folder.mkdir(parents=True)
    (folder / "index.html").write_text("<p>script</p>", encoding="utf-8")
    (folder / f"{pid}_script_v01.md").write_text(f"# {pid}\n", encoding="utf-8")


@pytest.mark.private_data
def test_posting_plan_lists_every_slot(tmp_path, capsys):
    """One delivery page for the week, one item per started slot in day order (an AI video with its upload copy and
    kit, a script to film with its Markdown and the kit its blocks make), and the posting plan: one row per slot
    and platform, `{day, channel, title, file, caption, sound}`. A slot not made yet holds it; a final made again
    makes the delivery stale."""
    run = _week_run(tmp_path)
    _ready(run, capsys, _doc("pon", decision="ok", output="script"), _doc("pt", decision="skip"),
           _doc("sob", decision="ok", output="script"))
    code, out = _cli(capsys, "organic", "start", "--run", str(run.path))
    assert code == 0, out
    runs = {x["proposal"]: RunFolder.open(tmp_path / "ws" / x["path"]) for x in out["started"]}
    assert sorted(runs) == ["w1", "w2", "w4"]
    assert organic_week_delivery.delivered_gap(run) is not None
    _made_script(runs["w1"])
    code, out = _cli(capsys, "organic", "deliver-week", "--run", str(run.path))
    assert code == 2 and "has no final video yet" in out["message"]
    _made_video(runs["w2"])
    _made_script(runs["w4"])
    code, out = _cli(capsys, "organic", "deliver-week", "--run", str(run.path))
    assert code == 0, out
    assert out["folder"] == "04_final/week_delivery_v01" and out["items"] == 3
    assert out["posting_plan"] == "05_results/posting_plan_v01.json"
    plan = json.loads((run.path / out["posting_plan"]).read_text(encoding="utf-8"))
    assert all(set(r) == {"day", "channel", "title", "file", "caption", "sound"} for r in plan)
    assert [(r["day"], r["channel"]) for r in plan] == [
        (d, p) for d in ("2026-11-09", "2026-11-11", "2026-11-14") for p in ("tiktok", "instagram", "youtube",
                                                                              "facebook")]
    assert {r["title"] for r in plan if r["day"] == "2026-11-11"} == {exampleedu.week()["slots"][1]["title"]}
    video = [r for r in plan if r["day"] == "2026-11-11"]
    assert all(r["file"].startswith("exampleedu_w2_") and r["file"].endswith(".mp4") for r in video)
    kit = exampleedu.kit("M5_pl_kit_v01")
    assert video[0]["caption"].startswith(kit["platforms"]["tiktok"]["caption"].rstrip())
    assert video[0]["sound"] == kit["platforms"]["tiktok"]["sound"]
    assert all(r["file"].endswith(".md") for r in plan if r["day"] != "2026-11-11")
    md = (run.path / out["posting_plan_md"]).read_text(encoding="utf-8")
    assert md.count("## ") == len(plan)
    html = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert html.index("w1_script_v01.md") < html.index("w2_final_v01.mp4") < html.index("w4_script_v01.md")
    assert '<a class="media" href="media/w1_script_v01.md"' in html
    assert organic_week_delivery.delivered_gap(run) is None and stepchecks.run("week_delivered", run) is None

    # the week's delivery page is decided like a single delivery page, each decision acted on in its day's run
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    ids = {v["run"].rsplit("_", 1)[-1].split("-")[-1]: k for k, v in data["plugin"]["items"].items()}
    assert data["plugin"]["items"][ids["w2"]]["kind"] == "final" and data["plugin"]["items"][ids["w1"]]["kind"] == "script"
    page.record_published(run, "week_delivery", SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    docs = [json.dumps({"id": ids["w2"], "data": {"action": "redo", "note": "a calmer voice", "platforms": [
                "tiktok", "youtube", "facebook"], "updated_at": "2026-11-07T10:00:00.000Z"}}),
            json.dumps({"id": ids["w1"], "data": {"action": "accept", "updated_at": "2026-11-07T10:00:00.000Z"}})]
    summary = json.dumps({"count": 2, "nextCursor": None})
    mcp_saves.save(run, "db_list", {"slug": SLUG, "collection": "gate_edit", "limit": 1000},
                   {"raw": "\n".join([summary, "<untrusted-document-9a>", *docs, "</untrusted-document-9a>"])},
                   at=_later(1), server="claude-artifacts")
    code, got = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "week_delivery")
    assert code == 0, got
    assert got["file"] == "03_wip/decisions_week_delivery_v01.json" and got["redos"] == ["delivery:w2_final"]
    asked = state.load(runs["w2"]).organic["redos"]["delivery:w2_final"]
    assert asked[-1]["note"] == "a calmer voice" and asked[-1]["page"].endswith("03_wip/decisions_week_delivery_v01.json")
    assert "redos" not in (state.load(run).organic or {})                   # nothing in the week run itself
    assert [k["kit"] for k in got["kits"]] == ["04_final/kits/w2_kit_v02.json"]
    kit2 = json.loads((runs["w2"].path / "04_final" / "kits" / "w2_kit_v02.json").read_text(encoding="utf-8"))
    assert kit2["plugin"]["platforms"] == ["tiktok", "youtube", "facebook"] and "instagram" not in kit2["platforms"]
    assert "tm kit check --run" in got["message"]

    final = runs["w2"].path / "04_final" / "w2_final_v02.mp4"
    final.write_bytes(b"again")
    assert "latest file" in organic_week_delivery.delivered_gap(run)


# --- I5: the schedule, next week's run, tm due -------------------------------------------------------------

@pytest.mark.private_data
def test_schedule_moved_and_research_alias_kept(tmp_path, capsys):
    """`tm schedule` records how the next week run starts, for a week run and for a trend research run with the
    weekly digest; `tm research schedule` is its alias for trend research runs only, as it was."""
    run = _week_run(tmp_path)
    code, out = _cli(capsys, "schedule", "--run", str(run.path), "--how", "by_hand")
    assert code == 0 and "plan my week of videos" in out["message"]
    assert state.load(run).schedule == {"how": "by_hand"}
    code, out = _cli(capsys, "schedule", "--run", str(run.path), "--how", "desktop_task", "--id",
                     "weekly-pack-exampleedu", "--cron", "0 9 * * 0")
    assert code == 0 and state.load(run).schedule == {"how": "desktop_task", "id": "weekly-pack-exampleedu",
                                                      "cron": "0 9 * * 0"}
    for bad in (["--how", "desktop_task"], ["--how", "by_hand", "--cron", "0 9 * * 0"]):
        code, out = _cli(capsys, "schedule", "--run", str(run.path), *bad)
        assert code == 1 and out["status"] == "error"
    code, out = _cli(capsys, "research", "schedule", "--run", str(run.path), "--how", "by_hand")
    assert code == 1 and "tm research works on runs of" in out["message"]
    idea = exampleedu.build(tmp_path / "other")
    code, out = _cli(capsys, "schedule", "--run", str(idea.path), "--how", "by_hand")
    assert code == 1 and "not a week run" in out["message"]

    research = RunFolder.create(tmp_path / "ws", "beauty", TODAY, playbook=TREND_RESEARCH)
    s = state.load(research)
    s.outputs = ["category_report", "weekly_digest"]
    state.save(research, s)
    for argv in (["schedule"], ["research", "schedule"]):
        code, out = _cli(capsys, *argv, "--run", str(research.path), "--how", "by_hand")
        assert code == 0, out
        assert out["message"] == ("Recorded the schedule: by hand. The user asks Claude to update the trend report each "
                                  "week; tm due reminds them at session start once a week has passed.")
    assert state.load(research).schedule == {"how": "by_hand"}


@pytest.mark.private_data
def test_week_after_previous_reuses_profile(tmp_path, capsys):
    """Next week's run ("plan my week of videos", `tm run new --after` the last week run) copies its config, outputs
    and level (`tm config write --from-previous`), reuses the confirmed channel profile (A1 skipped), and the trends
    last week's slots were made from need a series now."""
    last = _week_run(tmp_path)
    ws = tmp_path / "ws"
    profile = brand.latest(ws, exampleedu.CHANNEL, kind="channel")
    path = ws / "library" / "channels" / exampleedu.CHANNEL
    saved = sorted(path.glob("channel_v*.json"))[-1]
    saved.write_text(json.dumps({**profile, "confirmed": "2026-11-06"}, ensure_ascii=False), encoding="utf-8")
    _ready(last, capsys, _doc("pon", decision="ok"), _doc("śr", decision="skip"), _doc("pt", decision="skip"),
           _doc("sob", decision="skip"))
    code, out = _cli(capsys, "organic", "start", "--run", str(last.path))
    assert code == 0 and [x["proposal"] for x in out["started"]] == ["w1"]
    s = state.load(last)
    s.status = "done"
    state.save(last, s)

    now = RunFolder.create(ws, "exampleedu", exampleedu.CREATED + timedelta(days=7), playbook=ORGANIC_VIDEO)
    s = state.load(now)
    s.previous_run = last.path.relative_to(ws).as_posix()
    state.save(now, s)
    code, out = _cli(capsys, "config", "write", "--run", str(now.path), "--from-previous")
    assert code == 0, out
    assert config.load(now) == config.load(last)
    assert state.load(now).outputs == ["weekly_plan"] and state.load(now).level == "big_calls"
    organic.record_stack(now, replicate="ok", elevenlabs="ok", artifacts="ok", browser="ok")
    flow.complete(now, "A0")                                                 # the intake is the copied config
    flow.decide(now, "reuse_profile", "reuse", by="user", note=None)        # the confirmed profile
    assert flow.next(now).step == "B1"                                      # A1 skipped
    exampleedu.save_trends(now)
    exampleedu.save_week_cards(now)
    found = {p.field: p.what for p in _problems(now, exampleedu.week())}
    assert set(found) == {"slots[0].plugin.series"} and "2026-11-07_exampleedu-w1" in found["slots[0].plugin.series"]
    idea = exampleedu.build(tmp_path / "other")
    s = state.load(idea)
    s.previous_run = last.path.relative_to(ws).as_posix()
    s.outputs = ["proposals"]
    state.save(idea, s)
    with pytest.raises(ValueError):                                         # another workspace's run: not found
        organic_config.write_from_previous(idea)


def test_due_lists_trend_report_and_organic_week(tmp_path):
    """`tm due` lists a done week run a week after it was made, beside PB04's weekly trend report, unchanged; a week
    run a later one follows, one a desktop task starts and one not a week old are not listed."""
    ws = tmp_path / "ws"
    ws.mkdir()

    def made(playbook, name, created, outputs, *, status="done", after=None, schedule=None):
        r = RunFolder.create(ws, name, created, playbook=playbook)
        s = state.load(r)
        s.outputs, s.status, s.schedule = list(outputs), status, schedule
        s.previous_run = after.path.relative_to(ws).as_posix() if after else None
        state.save(r, s)
        return r

    report = made(TREND_RESEARCH, "beauty", date(2026, 10, 31), ["category_report", "weekly_digest"])
    first = made(ORGANIC_VIDEO, "exampleedu", date(2026, 10, 24), ["weekly_plan"])
    second = made(ORGANIC_VIDEO, "exampleedu-w2", date(2026, 10, 31), ["weekly_plan"], after=first)
    made(ORGANIC_VIDEO, "pets", date(2026, 10, 31), ["weekly_plan"],
         schedule={"how": "desktop_task", "id": "weekly-pack-pets", "cron": "0 9 * * 0"})
    made(ORGANIC_VIDEO, "cats", date(2026, 11, 2), ["weekly_plan"])          # five days old
    made(ORGANIC_VIDEO, "ideas", date(2026, 10, 20), ["proposals"])          # an idea run
    assert flow.due(ws, date(2026, 11, 7)) == [
        {"message": f"Run {second.path.name}: next week's videos are due. Ask Claude to plan my week of videos.",
         "run": second.path.name, "date": "2026-11-07"},
        {"message": f"Run {report.path.name}: the weekly trend report is due. Ask Claude to update the trend report.",
         "run": report.path.name, "date": "2026-11-07"}]
    assert flow.due(ws, date(2026, 11, 6)) == []
