"""Proposals (organic video C1 to C3): `tm organic proposals check` on the ExampleEdu walkthrough's
proposals with the plugin blocks, the decisions read from the original's per-proposal page documents, and
`tm organic start`, one production run per idea marked produce.

`03_wip/decisions_proposals_vNN.json` is written by Task 7 from the page; until then these tests write
it themselves (`_decided`), through `organic_proposals.decisions` (preflight row 16)."""

import copy
import json
import re
from datetime import date, timedelta

import pytest

import exampleedu
from tm import (brand, config, manifest, organic, organic_config, organic_proposals, organic_research, state, stepchecks,
                trends)
from tm.cli import main
from tm.runfolder import RunFolder
from tm.stops import AGAIN

pytestmark = pytest.mark.private_data

TODAY = date(2026, 11, 7)   # the day start runs on: run names begin with it
ALL_GATES = ["pack", "images", "video", "edit"]


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(organic_proposals, "_today", lambda: TODAY)


def _next_day(monkeypatch, days=1):
    monkeypatch.setattr(organic_proposals, "_today", lambda: TODAY + timedelta(days=days))


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _idea_run(tmp_path, level="big_calls", stack=None):
    """The ExampleEdu run as an idea run (outputs proposals) at `level`, with its stack recorded."""
    run = exampleedu.build(tmp_path / "ws")
    s = state.load(run)
    s.outputs, s.level = ["proposals"], level
    state.save(run, s)
    organic.record_stack(run, **(stack or {"replicate": "ok", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"}))
    return run


def _write(run, data):
    """A new version of the proposals file, as the agent writes it."""
    path = run.next_version("03_wip", "proposals", "json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _problems(run, data):
    return organic_proposals.check(run, data, config.load(run))


def _fields(problems):
    return [p.field for p in problems]


def _checked(run, capsys, data=None):
    path = _write(run, data or exampleedu.proposals())
    code, out = _cli(capsys, "organic", "proposals", "check", "--run", str(run.path), "--file", str(path))
    assert code == 0, out
    return path


def _decided(run, docs, carried=()):
    """03_wip/decisions_proposals_vNN.json from the original's page documents (Task 7 writes it from the page)."""
    rel = state.load(run).checked["proposals"]["file"]
    data = json.loads((run.path / rel).read_text(encoding="utf-8"))
    rows = organic_proposals.decisions(list(docs.items()), data, organic_proposals.profile_defaults(run, data))
    for pid in carried:
        rows[pid]["carried"] = True
    path = run.next_version("03_wip", organic_proposals.DECISIONS_STEM, "json")
    path.write_text(json.dumps({"page": "proposals", "proposals": rel, "decisions": rows}), encoding="utf-8")
    return path


def _doc(decision="produce", updated_at="2026-11-07T10:00:00Z", **kw):
    return {"decision": decision, "mode": "gates", "gates": ALL_GATES, "answers": {}, "note": "",
            "platforms": ["tiktok", "instagram", "youtube", "facebook"], "output": "script",
            "updated_at": updated_at, **kw}


def _production_runs(run):
    return sorted(p for p in run.path.parent.iterdir() if p != run.path and (p / "run.json").is_file())


def _start(capsys, run, *flags):
    return _cli(capsys, "organic", "start", "--run", str(run.path), *flags)


# --- C1: the proposals check ------------------------------------------------------------------------

def test_exampleedu_proposals_v02_pass(tmp_path, capsys):
    run = _idea_run(tmp_path)
    assert organic_proposals.checked_gap(run) is not None
    path = _write(run, exampleedu.proposals())
    code, out = _cli(capsys, "organic", "proposals", "check", "--run", str(run.path), "--file",
                     "03_wip/" + path.name)   # run-relative, as the skill writes it
    assert code == 0, out
    assert out["proposals"] == 6 and "6 proposals" in out["message"]
    assert state.load(run).checked["proposals"]["file"] == "03_wip/proposals_v03.json"
    assert organic_proposals.checked_gap(run) is None
    assert stepchecks.run("proposals_checked", run) is None
    path.write_text(path.read_text(encoding="utf-8").replace("Tung", "Tang"), encoding="utf-8")
    assert "changed after it was checked" in organic_proposals.checked_gap(run)

    data = exampleedu.proposals()
    del data["proposals"][0]["plugin"]                                  # the plugin block is required
    data["proposals"][1]["plugin"]["production"] = "puppets"
    assert {"proposals[0]", "proposals[1].plugin.production"} <= set(_fields(_problems(run, data)))
    code, out = _cli(capsys, "organic", "proposals", "check", "--run", str(run.path), "--file", str(_write(run, data)))
    assert code == 2 and out["status"] == "stop" and out["message"].endswith(AGAIN + ".")

    data = exampleedu.proposals()
    data["proposals"] = data["proposals"][:3]                           # 4 to 6 per page
    data["proposals"][1]["id"] = "M1"                                   # ids unique
    data["proposals"][2]["channel"] = "kotki"                           # one of the run's channels
    data["lang"] = "en"                                                 # the run's page language is pl
    data["proposals"][0]["cost"] = {"low": 0.5, "high": 0.2, "note": "x"}
    data["proposals"][0]["product"]["level"] = "hero"                   # a channel with no store shows none
    data["data_note"] += " Nie znaleziono trendu dla zapytania 17."      # never "no trend found"
    found = _problems(run, data)
    assert {"proposals", "proposals[1].id", "m3.channel", "lang", "m1.cost", "m1.product.level", "data_note"} <= set(_fields(found))
    assert any("not shown" in p.what for p in found if p.field == "m1.product.level")
    data["proposals"][0]["product"]["level"] = "big"
    assert any("one of not shown, incidental, featured, soft mention, hero" in p.what
               for p in _problems(run, data) if p.field == "m1.product.level")


def test_recreate_needs_two_evidence_videos(tmp_path):
    run = _idea_run(tmp_path)
    data = exampleedu.proposals()
    m3 = data["proposals"][2]                                           # Odtworzenie (Recreate)
    m3["trends"][0]["pick"] = [0]
    found = _problems(run, data)
    assert _fields(found) == ["m3.trends"] and "two evidence videos" in found[0].what
    m3["trends"][0]["pick"] = [0, 0]                                    # the same video twice is one
    assert _fields(_problems(run, data)) == ["m3.trends"]
    m3["trends"][0]["pick"] = [0, 12]                                   # 12 videos saved: 0 to 11
    found = _problems(run, data)
    assert _fields(found) == ["m3.trends[0].pick"] and "12" in found[0].what
    m3["trends"][0]["pick"] = [0, 11]
    assert _problems(run, data) == []

    data["proposals"][0]["plugin"]["weak_link"] = None                  # Inspire needs its weak link
    data["proposals"][5]["plugin"]["transfer"] = True                   # so does a transfer (M6 is Recreate)
    data["proposals"][1]["approach"] = "Adapt"
    assert set(_fields(_problems(run, data))) == {"m1.plugin.weak_link", "m6.plugin.weak_link", "m2.approach"}


def test_unknown_or_ambiguous_prefix_refused(tmp_path):
    run = _idea_run(tmp_path)
    full = exampleedu.full_ids()["c20bfd65"]
    data = exampleedu.proposals()
    data["proposals"][0]["trends"][1]["id"] = "deadbeef"                # no saved card
    data["proposals"][1]["trends"][0]["id"] = "9a17 a078"               # not a trend id
    found = {p.field: p.what for p in _problems(run, data)}
    assert set(found) == {"m1.trends[1].id", "m2.trends[0].id"}
    assert "No saved card of the trend deadbeef" in found["m1.trends[1].id"] and AGAIN not in found["m1.trends[1].id"]
    other = "c20bfd65" + "f" * 24                                       # a second card with the same 8 characters
    trends.save_answer(run, "get_trend", {"trend_id": other}, {**exampleedu._json(exampleedu.TRENDS / "card_c20bfd65.json"),
                                                               "id": other})
    found = {p.field: p.what for p in _problems(run, exampleedu.proposals())}
    assert set(found) == {"m1.trends[1].id"} and "matches 2 saved cards" in found["m1.trends[1].id"]
    data = exampleedu.proposals()
    data["proposals"][0]["trends"][1]["id"] = full                      # the full id is one card
    assert _problems(run, data) == []


def test_error_answer_card_does_not_resolve(tmp_path):
    run = _idea_run(tmp_path)
    full = exampleedu.full_ids()["9a17a078"]
    trends.save_answer(run, "get_trend", {"trend_id": full}, {"error": "Trend not found"})   # the newest fetch failed
    found = _problems(run, exampleedu.proposals())
    assert _fields(found) == ["m2.trends[0].id"] and "error answer" in found[0].what


def test_hidden_production_refused_without_replicate(tmp_path, animatic_ready):
    run = _idea_run(tmp_path, stack={"replicate": "missing", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"})
    found = _problems(run, exampleedu.proposals())
    assert _fields(found) == ["m2.plugin.production", "m3.plugin.production", "m5.plugin.production"]
    assert all("Replicate" in p.what for p in found)
    assert "is a talking character as an AI video" in found[0].what and "is AI footage as an AI video" in found[1].what
    assert not any(re.search(r"talking_character|ai_footage|stills_motion", p.what + p.todo) for p in found)  # N2
    organic.record_stack(run, replicate="ok", elevenlabs="missing", artifacts="ok", browser="missing")
    found = _problems(run, exampleedu.proposals())
    assert _fields(found) == ["m1.plugin.production", "m4.plugin.production"]
    assert all("Chrome or Edge" in p.what for p in found)
    s = state.load(run)
    s.organic = {k: v for k, v in s.organic.items() if k != "stack"}
    state.save(run, s)
    assert _fields(_problems(run, exampleedu.proposals())) == ["stack"]   # what the stack hides is unknown


def test_hidden_types_bind_only_an_ai_video_a_filmed_script_takes_any(tmp_path):
    """PR B ruling I2: the stack hides production types for an AI video (output `video`) only. With
    Replicate and the browser both missing, ExampleEdu's six ideas as scripts to film all pass; the
    same talking character proposed as an AI video is refused."""
    run = _idea_run(tmp_path, stack={"replicate": "missing", "elevenlabs": "missing", "artifacts": "ok",
                                     "browser": "missing"})
    data = exampleedu.proposals()
    for p in data["proposals"]:
        p["plugin"]["output"] = "script"
    assert {p["plugin"]["production"] for p in data["proposals"]} >= {"talking_character", "ai_footage", "animation"}
    assert _problems(run, data) == []
    data["proposals"][1]["plugin"]["output"] = "video"                     # m2, a talking character
    found = _problems(run, data)
    assert _fields(found) == ["m2.plugin.production"]
    assert "is a talking character as an AI video" in found[0].what and "talking_character" not in found[0].what
    assert "script to film" in found[0].todo


def test_stack_message_says_the_types_are_hidden_for_an_ai_video(tmp_path, capsys):
    run = _idea_run(tmp_path)
    code, out = _cli(capsys, "organic", "stack", "--run", str(run.path), "--replicate", "missing",
                     "--elevenlabs", "ok", "--artifacts", "ok", "--browser", "ok")
    assert code == 0 and out["hidden_types"] == ["ai_footage", "talking_character"]
    assert "Hidden for an AI video: ai_footage, talking_character; a script to film may use any type." in out["message"]


def test_used_trend_refused_unless_series(tmp_path):
    run = _idea_run(tmp_path)
    workspace = run.path.parents[2]
    full = exampleedu.full_ids()["c20bfd65"]
    organic_research.record_used(workspace, "ExampleEdu", [{"trend_id": full, "name": "Tung Tung Tung Sahur",
                                                          "kind": "topic_trend", "run": "2026-11-01_exampleedu-m2",
                                                          "video": "m2"}])
    found = _problems(run, exampleedu.proposals())
    assert _fields(found) == ["m1.plugin.series"] and "2026-11-01_exampleedu-m2" in found[0].what
    data = exampleedu.proposals()
    data["proposals"][0]["plugin"]["series"] = "Co daje gra"
    assert _problems(run, data) == []


def test_percentage_in_risk_refused(tmp_path):
    run = _idea_run(tmp_path)
    data = exampleedu.proposals()
    data["proposals"][1]["risk"]["items"][0] = "native Polish speech works in about 70 % of takes"
    data["proposals"][2]["plugin"]["risk_hits"][0]["mitigation"] = "one take; 90% of faces hold"
    assert set(_fields(_problems(run, data))) == {"m2.risk.items[0]", "m3.plugin.risk_hits[0].mitigation"}

    data = exampleedu.proposals()
    data["proposals"][0]["risk"]["level"] = "high"                      # no hit: low
    data["proposals"][1]["risk"]["level"] = "low"                       # two hits: not low
    data["proposals"][2]["plugin"]["risk_hits"][1]["mitigation"] = "  "
    assert set(_fields(_problems(run, data))) == {"m1.risk.level", "m2.risk.level", "m3.plugin.risk_hits[1].mitigation"}


def test_seeded_trend_needs_a_kept_seed(tmp_path):
    run = _idea_run(tmp_path)
    full = exampleedu.full_ids()["5f1691dd"]
    (run.path / "00_raw" / "seed.json").write_text(json.dumps({"seed_id": "s1", "trend_id": full}), encoding="utf-8")
    s = state.load(run)
    s.organic = {**s.organic, "seed": "s1"}
    state.save(run, s)
    found = _problems(run, exampleedu.proposals())
    assert _fields(found) == ["m3.trends"] and "not re-checked" in found[0].what
    assert "tm organic seed-check" in found[0].todo
    s.organic["seed_check"] = {"verdict": "drop", "why": "falling"}
    state.save(run, s)
    assert _fields(_problems(run, exampleedu.proposals())) == ["m3.trends"]
    s.organic["seed_check"] = {"verdict": "keep", "why": "rising"}
    state.save(run, s)
    assert _problems(run, exampleedu.proposals()) == []


# --- C2: the decisions on the page ------------------------------------------------------------------

def test_decisions_map_original_modes_to_levels():
    data = exampleedu.proposals()
    defaults = {"exampleedu": {"level": "big_calls", "output": "script", "platforms": ["tiktok", "youtube"]}}
    docs = [("m1", _doc(mode="auto", gates=["pack"])),                       # A-Z -> Hands-off
            ("m2", _doc(gates=ALL_GATES)),                                   # every check-in -> Check every step
            ("m3", _doc(gates=["pack", "video"], decision="later")),         # some -> Just the big calls
            ("m4", _doc(level="hands_off", mode="gates", gates=ALL_GATES)),  # the plugin's page writes the level
            ("m5", {"decision": "produce", "updated_at": "2026-11-07T09:00:00Z"}),   # the rest from the profile,
            ("m5", {"decision": "skip", "updated_at": "2026-11-07T08:00:00Z"}),      # the output its own; an older save
            ("m6", {"decision": "maybe", "note": "ask me", "answers": {"q1": "blue"}}),
            ("x9", _doc())]                                                  # not a proposal of this page
    got = organic_proposals.decisions(docs, data, defaults)
    assert set(got) == {"m1", "m2", "m3", "m4", "m5", "m6"}
    assert [got[p]["level"] for p in ("m1", "m2", "m3", "m4", "m5")] == [
        "hands_off", "every_step", "big_calls", "hands_off", "big_calls"]
    assert got["m3"]["decision"] == "later" and got["m5"]["decision"] == "produce" and got["m6"]["decision"] is None
    assert got["m5"]["output"] == "video" and got["m5"]["platforms"] == ["tiktok", "youtube"]   # plugin.output
    assert got["m1"]["platforms"] == ["tiktok", "instagram", "youtube", "facebook"]
    assert got["m6"] == {"decision": None, "level": "big_calls", "output": "video", "platforms": ["tiktok", "youtube"],
                         "answers": {"q1": "blue"}, "note": "ask me", "carried": False}
    del data["proposals"][5]["plugin"]["output"]                        # no output of its own: the file's default
    data["default_output"] = "script"
    assert organic_proposals.decisions(docs, data, {"exampleedu": {"output": "video"}})["m6"]["output"] == "script"
    del data["default_output"]                                          # then the run's config
    assert organic_proposals.decisions(docs, data, {"exampleedu": {"output": "video"}})["m6"]["output"] == "video"
    assert organic_proposals.decisions([], data)["m1"]["level"] is None     # no profile given: nothing invented


# --- C3: starting the picked videos -----------------------------------------------------------------

def test_start_makes_one_run_per_produced_idea(tmp_path, capsys, monkeypatch):
    run = _idea_run(tmp_path)
    workspace = run.path.parents[2]
    _checked(run, capsys)
    assert "tm organic decisions" in organic_proposals.started_gap(run)
    _decided(run, {"m1": {k: v for k, v in _doc().items() if k != "platforms"},   # platforms from the profile
                   "m5": _doc(mode="auto", platforms=["tiktok", "instagram"])})
    assert "Mało kto wie" in organic_proposals.started_gap(run)

    monkeypatch.chdir(workspace)                                        # the run as the skill names it
    code, out = _cli(capsys, "organic", "start", "--run", run.path.relative_to(workspace).as_posix())
    assert code == 0, out
    made = _production_runs(run)
    assert [p.name for p in made] == ["2026-11-07_exampleedu-m1", "2026-11-07_exampleedu-m5"]
    assert [x["proposal"] for x in out["started"]] == ["m1", "m5"]
    parent = run.path.relative_to(workspace).as_posix()
    full = exampleedu.full_ids()
    for path, pid, level, platforms in ((made[0], "m1", "every_step", exampleedu.PROFILE["platforms"]),
                                        (made[1], "m5", "hands_off", ["tiktok", "instagram"])):
        prod = RunFolder.open(path)
        s = state.load(prod)
        assert (s.level, s.outputs) == (level, ["script_to_film"])
        assert s.organic == {"parent": parent, "proposal": pid, "channel": "exampleedu",
                             "key": organic_proposals.idea_key(exampleedu.proposals()["proposals"][int(pid[1]) - 1])}
        cfg = config.load(prod)
        assert (cfg["kind"], cfg["output"], cfg["channels"], cfg["platforms"]) == ("production", "script", ["exampleedu"],
                                                                                  platforms)
        assert cfg["page_lang"] == "pl" and cfg["mode"]["variant"] == ("az" if level == "hands_off" else "gated")
        assert organic_config.validate(prod) == []
        kept = json.loads((path / "00_raw" / "proposal.json").read_text(encoding="utf-8"))
        assert kept["proposal"]["id"] == pid and kept["decision"]["level"] == level and kept["channel"] == "exampleedu"
        rows = [r for r in manifest.rows(prod) if r["file"] == "00_raw/proposal.json"]
        assert len(rows) == 1 and rows[0]["source"] == "tm organic start"
    m5 = json.loads((made[1] / "00_raw" / "proposal.json").read_text(encoding="utf-8"))
    assert m5["trend_ids"] == [full["7d60086a"], full["3abc109a"]] and m5["product_level"] == "not shown"

    used = organic_research.used(workspace, "exampleedu")
    assert set(used) == {full["0112ede8"], full["c20bfd65"], full["7d60086a"], full["3abc109a"]}
    assert used[full["7d60086a"]]["run"] == made[1].name and used[full["7d60086a"]]["kind"] == "hook_trend"
    history = organic_research.history(workspace, "exampleedu")
    assert history["decisions"] == 2       # M2-M4 and M6 are undecided: no decision is recorded
    assert history["by_production"] == {"animation": {"produce": 1, "later": 0, "skip": 0, "redo": 0},
                                        "talking_character": {"produce": 1, "later": 0, "skip": 0, "redo": 0}}
    assert set(history["by_approach"]) == {"Inspire"}
    assert organic_proposals.started_gap(run) is None
    assert stepchecks.run("videos_started", run) is None
    _checked(run, capsys)                                               # proposals checked again after the page
    assert "taken on 03_wip/proposals_v03.json" in organic_proposals.started_gap(run)


def test_same_idea_never_started_twice_or_for_two_channels(tmp_path, capsys, monkeypatch):
    run = _idea_run(tmp_path)
    workspace = run.path.parents[2]
    brand.save(workspace, {**copy.deepcopy(exampleedu.PROFILE), "channel": "Rodzice Graczy"}, run=run)
    cfg = config.load(run)
    cfg["channels"] = ["exampleedu", "rodzice-graczy"]                    # one run, two channels
    config.save(run, cfg)
    data = exampleedu.proposals()
    data["channels"].append({"id": "rodzice", "name": "Rodzice Graczy", "niche": "rodzice graczy"})
    _checked(run, capsys, data)
    _decided(run, {"m1": _doc()})
    code, out = _start(capsys, run)
    assert code == 0 and [x["run"] for x in out["started"]] == ["2026-11-07_exampleedu-m1"]
    assert state.load(RunFolder.open(_production_runs(run)[0])).organic["channel"] == "exampleedu"
    assert not (workspace / "library" / "organic" / "rodzice-graczy").exists()

    for decided in ({"m1": _doc()}, {"m1": _doc(updated_at="2026-11-08T10:00:00Z", note="again")}):
        _decided(run, decided)                                          # the same decisions, then a re-save
        code, out = _start(capsys, run)
        assert code == 2 and "already started" in out["message"] and _production_runs(run)[0].name in out["message"]
        assert "M1" not in out["message"].replace("(m1)", "")           # named by its title
        assert len(_production_runs(run)) == 1
    _next_day(monkeypatch)
    _decided(run, {"m1": _doc(), "m2": _doc(decision="later")})         # the next day, one more decision
    code, out = _start(capsys, run)
    assert code == 2 and "already started" in out["message"] and len(_production_runs(run)) == 1
    assert organic_research.history(workspace, "exampleedu")["by_production"]["talking_character"]["later"] == 1
    _decided(run, {"m1": _doc(), "m4": _doc()})                         # a new pick starts; M1 is not started again
    code, out = _start(capsys, run)
    assert code == 0 and [x["proposal"] for x in out["started"]] == ["m4"]
    assert [x["proposal"] for x in out["already_started"]] == ["m1"]
    assert len(_production_runs(run)) == 2
    assert organic_research.history(workspace, "exampleedu")["decisions"] == 3   # M1 once, M2 later, M4 once


def test_every_output_ready_at_0_6_0(tmp_path, capsys):
    """PR C (Task 18): an idea marked produce as an AI video starts an AI video production run, beside a script
    to film; PR E (Task 21, preflight P3-F8): the weekly pack is built too, so every output is ready and a week run
    is accepted at the intake."""
    assert organic_config.OUTPUTS_READY == ("script", "ai_video", "weekly_pack")
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m3": _doc(output="video"), "m6": _doc()})
    code, out = _start(capsys, run)
    assert code == 0, out
    got = {x["proposal"]: x for x in out["started"]}
    assert (got["m3"]["output"], got["m6"]["output"]) == ("video", "script")
    assert "an AI video" in out["message"] and "a script to film" in out["message"]
    video = RunFolder.open(run.path.parent / got["m3"]["run"])
    assert state.load(video).outputs == ["organic_video"] and config.load(video)["output"] == "ai_video"
    assert "output" not in {p.field for p in organic_config.validate(video)}
    cfg = config.load(video)
    cfg["output"] = "weekly_pack"
    config.save(video, cfg)
    assert "output" not in {p.field for p in organic_config.validate(video)}
    week = exampleedu.build(tmp_path / "week")
    organic_config.write_from_intake(week, {"channels": [exampleedu.CHANNEL], "outputs": ["weekly_plan"],
                                            "level": "big_calls"})
    assert state.load(week).outputs == ["weekly_plan"] and config.load(week)["kind"] == "weekly_plan"


def test_ai_video_of_a_type_the_stack_hides_is_not_started(tmp_path, capsys):
    """PR B's carry (Task 18): the page can switch an idea checked as a script to an AI video, so tm organic start
    checks the idea run's stack again for each AI video. Without a Replicate key AI footage is hidden: nothing
    starts (all or nothing), and the same idea as a script to film does. D1's recipe check refuses it again in
    the production run (test_organic_pack's test_hidden_production_type_refused)."""
    run = _idea_run(tmp_path, stack={"replicate": "missing", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"})
    data = exampleedu.proposals()
    for p in data["proposals"]:
        p["plugin"]["output"] = "script"                                # a filmed script may be any type
    _checked(run, capsys, data)
    _decided(run, {"m3": _doc(output="video"), "m5": _doc(output="video"), "m6": _doc()})
    code, out = _start(capsys, run)
    assert code == 2 and out["status"] == "stop" and out["message"].endswith(AGAIN + ".")
    assert "Impostor" in out["message"] and "is AI footage, which needs" in out["message"]
    assert "ChatGPT" in out["message"] and "is a talking character, which needs" in out["message"]
    assert "ai_footage" not in out["message"] and "talking_character" not in out["message"]   # plain words (T18 M2)
    assert "REPLICATE_API_TOKEN" in out["message"] and "script to film" in out["message"]
    assert "Zgadnij" not in out["message"]                             # a filmed script needs no Replicate key
    assert _production_runs(run) == []
    assert organic_research.history(run.path.parents[2], "exampleedu")["decisions"] == 0
    _decided(run, {"m3": _doc(output="script"), "m5": _doc(output="script"), "m6": _doc()})
    code, out = _start(capsys, run)
    assert code == 0, out
    assert {x["proposal"]: x["output"] for x in out["started"]} == {"m3": "script", "m5": "script", "m6": "script"}


def test_quiz_and_sections_start_as_an_ai_video(tmp_path, capsys, animatic_ready):
    """Task 20 lifts PR C's refusal: stills with motion graphics (ExampleEdu's M6 quiz) and a video in sections start as
    AI videos with every tool there, and without a Replicate key too (plan Decision 16: a quiz is not hidden, its cards
    can be the user's own pictures; a section's own type is checked at the recipe, test_organic_sections); AI footage
    still waits for its key (all or nothing)."""
    run = _idea_run(tmp_path)                                           # every tool there
    data = exampleedu.proposals()
    {p["id"]: p for p in data["proposals"]}["m2"]["plugin"]["production"] = "sections"
    _checked(run, capsys, data)
    _decided(run, {"m2": _doc(output="video"), "m6": _doc(output="video")})
    code, out = _start(capsys, run)
    assert code == 0, out
    assert {x["proposal"]: x["output"] for x in out["started"]} == {"m2": "video", "m6": "video"}
    run = _idea_run(tmp_path / "no-key", stack={"replicate": "missing", "elevenlabs": "ok", "artifacts": "ok",
                                                "browser": "ok"})
    data = exampleedu.proposals()
    for p in data["proposals"]:
        p["plugin"]["output"] = "script"                                # checked as scripts, switched on the page
    _checked(run, capsys, data)
    _decided(run, {"m3": _doc(output="video"), "m6": _doc(output="video")})
    code, out = _start(capsys, run)
    assert code == 2 and "is AI footage, which needs" in out["message"] and "Zgadnij" not in out["message"]
    assert "later version" not in out["message"] and _production_runs(run) == []
    _decided(run, {"m3": _doc(output="script"), "m6": _doc(output="video")})
    code, out = _start(capsys, run)
    assert code == 0 and {x["proposal"]: x["output"] for x in out["started"]} == {"m3": "script", "m6": "video"}, out


def test_hidden_type_hint_names_only_what_can_be_made(tmp_path, monkeypatch):
    """PR C re-review N2: a type the stack hides is refused in plain words, and the hint suggests only the kinds of AI
    video this stack can make: without Replicate an animation (when the Atlas renderer can draw) and stills with motion
    graphics on the user's own pictures; never AI footage, a video in sections or a type's id."""
    from tm import atlas
    monkeypatch.setattr(atlas, "missing", lambda: None)
    run = _idea_run(tmp_path, stack={"replicate": "missing", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"})
    data = exampleedu.proposals()
    for p in data["proposals"]:
        p["plugin"]["output"] = "script"
    data["proposals"][1]["plugin"]["output"] = "video"                   # m2, a talking character
    found = _problems(run, data)
    assert _fields(found) == ["m2.plugin.production"]
    todo = found[0].todo
    assert "an animation" in todo and "stills with motion graphics (a quiz or a ranking) on the user's own pictures" in todo
    for word in ("AI footage", "a talking character", "a video in sections", "stills_motion", "sections need"):
        assert word not in todo, word
    monkeypatch.setattr(atlas, "missing", lambda: ("tier", "The animatic tools are not installed.", "install them"))
    todo = _problems(run, data)[0].todo
    assert "an animation" not in todo and "own pictures" in todo


def test_carried_produce_needs_keep_carried(tmp_path, capsys):
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc(), "m4": _doc()}, carried=["m1"])
    code, out = _start(capsys, run)
    assert code == 2 and "carried over" in out["message"] and "--keep-carried" in out["message"]
    assert "Tung Tung Tung Sahur" in out["message"] and _production_runs(run) == []
    code, out = _start(capsys, run, "--keep-carried")
    assert code == 0 and [x["proposal"] for x in out["started"]] == ["m1", "m4"]
    assert out["kept_carried"] == ["m1"]
    started = state.load(run).organic["started"]
    assert {x["proposal"]: x["kept_carried"] for x in started.values()} == {"m1": True, "m4": False}


def test_start_needs_checked_proposals_and_decisions(tmp_path, capsys):
    run = _idea_run(tmp_path)
    code, out = _start(capsys, run)
    assert code == 2 and "tm organic proposals check" in out["message"]
    _checked(run, capsys)
    code, out = _start(capsys, run)
    assert code == 2 and "decisions" in out["message"] and out["message"].endswith(AGAIN + ".")
    _decided(run, {"m2": _doc(decision="skip")})
    code, out = _start(capsys, run)
    assert code == 0 and out["started"] == [] and "No idea is marked produce" in out["message"]
    assert organic_proposals.started_gap(run) is None                   # nothing to start: C3 is done
    assert organic_research.history(run.path.parents[2], "exampleedu")["by_production"] == {
        "talking_character": {"produce": 0, "later": 0, "skip": 1, "redo": 0}}


# --- a start that fails, and an idea written again ---------------------------------------------------

def test_blank_series_refused_and_nothing_started(tmp_path, capsys):
    run = _idea_run(tmp_path)
    data = exampleedu.proposals()
    data["proposals"][0]["plugin"]["series"] = "  "                     # record_used would refuse it later
    data["proposals"][1]["plugin"]["weak_link"] = ""
    assert set(_fields(_problems(run, data))) == {"m1.plugin.series", "m2.plugin.weak_link"}
    code, out = _cli(capsys, "organic", "proposals", "check", "--run", str(run.path), "--file", str(_write(run, data)))
    assert code == 2
    _decided_anyway = run.next_version("03_wip", organic_proposals.DECISIONS_STEM, "json")
    _decided_anyway.write_text(json.dumps({"page": "proposals", "decisions": {"m1": {"decision": "produce"}}}),
                               encoding="utf-8")
    code, out = _start(capsys, run)
    assert code == 2 and "tm organic proposals check" in out["message"] and _production_runs(run) == []


def test_card_without_kind_stops_before_any_run(tmp_path, capsys):
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc(), "m5": _doc()})
    full = exampleedu.full_ids()["3abc109a"]                              # M5's second trend, fetched again
    card = exampleedu._json(exampleedu.TRENDS / "card_3abc109a.json")
    trends.save_answer(run, "get_trend", {"trend_id": full}, {k: v for k, v in card.items() if k != "kind"})
    code, out = _start(capsys, run)
    assert code == 2 and "used trends" in out["message"] and "Nothing was started" in out["message"]
    assert _production_runs(run) == [] and not (state.load(run).organic or {}).get("started")   # not even M1


def _failing_record_used(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(organic_research, "record_used", fail)


def test_failed_start_removes_its_run_and_never_duplicates(tmp_path, capsys, monkeypatch):
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc()})
    real = organic_research.record_used
    _failing_record_used(monkeypatch)                                   # fails after the folder is made
    code, out = _start(capsys, run)
    assert code == 1 and "disk full" in out["message"]
    assert "runs/03-organic-ai-video/2026-11-07_exampleedu-m1 was not kept" in out["message"]
    assert _production_runs(run) == [] and not state.load(run).organic.get("started")
    assert organic_research.used(run.path.parents[2], "exampleedu") == {}
    monkeypatch.setattr(organic_research, "record_used", real)
    code, out = _start(capsys, run)                                     # the same day: it starts now
    assert code == 0 and [x["run"] for x in out["started"]] == ["2026-11-07_exampleedu-m1"]
    _next_day(monkeypatch)
    code, out = _start(capsys, run)                                     # the next day: never a second run
    assert code == 2 and "already started" in out["message"]
    assert [p.name for p in _production_runs(run)] == ["2026-11-07_exampleedu-m1"]


def test_failed_cleanup_says_so_and_blocks_a_duplicate(tmp_path, capsys, monkeypatch):
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc()})
    real_used, real_rmtree = organic_research.record_used, organic_proposals.shutil.rmtree
    _failing_record_used(monkeypatch)

    def held(path, *args, **kwargs):
        raise OSError("a file is held open")
    monkeypatch.setattr(organic_proposals.shutil, "rmtree", held)
    code, out = _start(capsys, run)
    assert code == 1 and "could not be removed" in out["message"] and "a file is held open" in out["message"]
    assert "runs/03-organic-ai-video/2026-11-07_exampleedu-m1" in out["message"] and "\\" not in out["message"]
    assert len(_production_runs(run)) == 1 and not state.load(run).organic.get("started")
    monkeypatch.setattr(organic_research, "record_used", real_used)
    monkeypatch.setattr(organic_proposals.shutil, "rmtree", real_rmtree)
    _next_day(monkeypatch)
    code, out = _start(capsys, run)                                     # the folder left behind is found
    assert code == 2 and "stopped half way" in out["message"] and "2026-11-07_exampleedu-m1" in out["message"]
    assert len(_production_runs(run)) == 1
    real_rmtree(_production_runs(run)[0])                               # the user deletes it
    code, out = _start(capsys, run)
    assert code == 0 and [x["run"] for x in out["started"]] == ["2026-11-08_exampleedu-m1"]


def test_rewritten_idea_is_new(tmp_path, capsys):
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc()})
    assert _start(capsys, run)[0] == 0
    data = exampleedu.proposals()
    data["proposals"][0]["risk"]["items"].append("ton: bez oceniania")   # a fix to the same idea
    _checked(run, capsys, data)
    _decided(run, {"m1": _doc()})
    code, out = _start(capsys, run)
    assert code == 2 and "already started" in out["message"]
    data["proposals"][0]["title"] = "Co daje dziecku nowa gra w Roblox"   # another idea, the same id
    found = _problems(run, data)                                        # its trends are used now: by another idea
    assert _fields(found) == ["m1.plugin.series", "m1.plugin.series"]
    data["proposals"][0]["plugin"]["series"] = "Co daje gra"
    _checked(run, capsys, data)
    _decided(run, {"m1": _doc()})
    code, out = _start(capsys, run)
    assert code == 0 and [x["run"] for x in out["started"]] == ["2026-11-07_exampleedu-m1-2"]
    assert organic_research.history(run.path.parents[2], "exampleedu")["decisions"] == 2


def test_page_without_output_takes_the_proposals_own(tmp_path, capsys):
    run = _idea_run(tmp_path)
    cfg = config.load(run)
    data = exampleedu.proposals()
    data["proposals"][0]["plugin"]["output"] = "script"                 # the idea's own output
    _checked(run, capsys, data)
    cfg["output"] = "ai_video"                                          # the run's default says video
    config.save(run, cfg)
    _decided(run, {"m1": {k: v for k, v in _doc().items() if k != "output"}})
    code, out = _start(capsys, run)
    assert code == 0 and out["started"][0]["output"] == "script"
