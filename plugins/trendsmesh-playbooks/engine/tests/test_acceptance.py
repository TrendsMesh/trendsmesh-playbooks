"""`tm acceptance`: the human-run acceptance of the re-cuts, with the agent as the operator."""

import json
import re
from datetime import date

import pytest

from tm import acceptance, page, state, trend_spool
from tm.cli import main
from tm.runfolder import RunFolder

CASES = [f"H{n}" for n in range(1, 10)]
JUDGED = {"H2", "H4", "H5", "H6", "H7", "H9"}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace with spaces and Polish letters, and a fixed day."""
    path = tmp_path / "Moje reklamy Łódź"
    path.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(path))
    monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 6))
    return path


def _tm(capsys, *argv):
    code = main(["acceptance", *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _saved(ws):
    return json.loads((ws / "acceptance" / "2026-11-06_recuts" / "acceptance.json")
                      .read_text(encoding="utf-8"))


def test_start_lists_all_nine_cases_as_todo(ws, capsys):
    code, out = _tm(capsys, "start", "--suite", "recuts")
    assert code == 0 and out["status"] == "done" and out["resumed"] is False
    folder = ws / "acceptance" / "2026-11-06_recuts"
    assert out["path"] == str(folder)
    data = _saved(ws)
    assert data["suite"] == "recuts" and data["budget"] == {"ai_usd": 4, "voice_credits": 3000}
    assert data["playbook"] == out["playbook"] == "01-refresh-ad"
    assert [c["id"] for c in data["cases"]] == CASES
    assert all(c["status"] == "todo" for c in data["cases"])
    for c in data["cases"]:
        assert set(c["needs"]) <= {"file", "key", "budget", "meta", "human_verdict"} and c["needs"]
        assert c["title"] and c["proves"] and c["steps"] and c["pass"]
        assert (c["judge"] is not None) == (c["id"] in JUDGED), c["id"]
        assert ("human_verdict" in c["needs"]) == (c["id"] in JUDGED), c["id"]
        assert bool(c["kinds"]) == ("budget" in c["needs"]), c["id"]
        # a run folder per case, made the way the playbook makes one, ready for `tm next`
        run = RunFolder.open(folder / c["run"])
        s = state.load(run)
        assert s.playbook == "01-refresh-ad" and s.step is None and s.spend == {}
        assert run.path.parent.parent.parent == folder
    unknown = main(["acceptance", "start", "--suite", "nope", "--json"])
    assert unknown == 1 and "recuts" in json.loads(capsys.readouterr().out)["message"]


def test_next_returns_first_todo_after_resume(ws, capsys):
    _tm(capsys, "start", "--suite", "recuts")
    code, out = _tm(capsys, "next")
    assert code == 0 and out["status"] == "case" and out["case"]["id"] == "H1"
    assert out["case"]["needs"] == ["meta"] and out["case"]["steps"]
    assert out["budget"]["left"] == {"ai_usd": 4, "voice_credits": 3000}
    assert out["budget"]["approved"] is False
    assert out["position"] == {"case": 1, "of": 9, "todo": 9}
    assert _tm(capsys, "record", "H1", "pass", "--note", "R2: hook; R2b: p75/p50 in 4 of 4")[0] == 0

    # a new session, the same day: start resumes, nothing is overwritten
    code, out = _tm(capsys, "start", "--suite", "recuts")
    assert code == 0 and out["resumed"] is True and "1 of 9" in out["message"]
    assert _saved(ws)["cases"][0]["status"] == "pass"
    # a new session: next finds the suite from acceptance.json alone
    code, out = _tm(capsys, "next")
    assert out["case"]["id"] == "H2" and out["case"]["judge"]
    assert set(out["case"]["needs"]) >= {"file", "budget", "human_verdict"}
    assert out["case"]["run"].endswith("2026-11-06_H2")
    assert out["position"] == {"case": 2, "of": 9, "todo": 8}


def test_judged_case_needs_by_person(ws, capsys):
    _tm(capsys, "start", "--suite", "recuts")
    for verdict in ("pass", "fail"):
        code, out = _tm(capsys, "record", "H2", verdict, "--note", "sounds fine to me")
        assert code == 1 and out["status"] == "error"
        assert "person" in out["message"] and "--by person" in out["message"]
    code, _ = _tm(capsys, "record", "H2", "pass", "--note", "the music runs on", "--by", "agent")
    assert code == 1
    assert _saved(ws)["cases"][1]["status"] == "todo"
    code, out = _tm(capsys, "record", "H2", "pass", "--by", "person",
                    "--note", "Ola: no joint heard at 11.1 s")
    assert code == 0 and out["case"] == "H2" and out["result"] == "pass"
    saved = _saved(ws)["cases"][1]
    assert saved["status"] == "pass" and saved["by"] == "person"
    # a case proven by recorded numbers is recorded by the agent
    assert _tm(capsys, "record", "H1", "fail", "--note", "R2 said middle")[0] == 0
    assert _tm(capsys, "record", "H12", "pass", "--note", "x")[0] == 1


def test_blocked_needs_a_note(ws, capsys):
    _tm(capsys, "start", "--suite", "recuts")
    code, out = _tm(capsys, "record", "H9", "blocked")
    assert code == 1 and "missing" in out["message"]
    assert _tm(capsys, "record", "H9", "blocked", "--note", "   ")[0] == 1
    assert _saved(ws)["cases"][8]["status"] == "todo"
    code, out = _tm(capsys, "record", "H9", "blocked", "--note", "No Windows machine (Ola)")
    assert code == 0
    saved = _saved(ws)["cases"][8]
    assert saved["status"] == "blocked" and saved["note"] == "No Windows machine (Ola)"


def test_report_totals_spend_against_suite_budget(ws, capsys):
    _tm(capsys, "start", "--suite", "recuts")
    assert _tm(capsys, "approve", "--note", "Ola: yes, $4 and 3,000 credits")[0] == 0
    folder = ws / "acceptance" / "2026-11-06_recuts"
    data = _saved(ws)
    runs = {c["id"]: RunFolder.open(folder / c["run"]) for c in data["cases"]}
    for cid, spend in (("H2", {"voice_credits": 586.0}), ("H5", {"ai_usd": 0.95, "voice_credits": 0.0})):
        s = state.load(runs[cid])
        s.spend = spend
        state.save(runs[cid], s)
    copy = runs["H2"].path / "showcase" / "review_tc" / "R1 15s E_v01.mp4"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(b"x")

    code, out = _tm(capsys, "next")
    assert out["budget"]["spent"] == {"ai_usd": 0.95, "voice_credits": 586}
    assert out["budget"]["left"] == {"ai_usd": 3.05, "voice_credits": 2414}
    assert out["budget"]["approved"] is True

    assert _tm(capsys, "record", "H1", "pass", "--note", "hook; p75/p50 in 4 uploads")[0] == 0
    assert _tm(capsys, "record", "H2", "pass", "--by", "person", "--note", "no joint at 11.1 s",
               "--evidence", str(copy))[0] == 0
    assert _tm(capsys, "record", "H3", "pass", "--note", "x", "--evidence", str(folder / "nope.mp4"))[0] == 1
    assert _tm(capsys, "record", "H9", "blocked", "--note", "No Windows machine")[0] == 0

    code, out = _tm(capsys, "report")
    assert code == 0 and out["path"] == str(folder / "report_v01.md")
    assert out["counts"] == {"pass": 2, "fail": 0, "blocked": 1, "todo": 6}
    text = (folder / "report_v01.md").read_text(encoding="utf-8")
    assert "no joint at 11.1 s" in text and "No Windows machine" in text
    # evidence inside the acceptance folder is shown relative to it (the user keeps the report or sends it privately)
    assert "`runs/01-refresh-ad/2026-11-06_H2/showcase/review_tc/R1 15s E_v01.mp4`" in text
    assert str(ws) not in text
    assert "586 of 3000 ElevenLabs credits" in text and "0.95 of 4 USD" in text
    assert "2414 left" in text and "3.05 left" in text
    assert "Ola: yes, $4 and 3,000 credits" in text
    assert "not run yet" in text            # nothing is left out silently
    assert not re.search(r"\$\{?[a-z_]", text)  # every placeholder filled
    # a second report is a new version; the first is never overwritten
    _tm(capsys, "record", "H3", "fail", "--note", "a take was generated")
    assert _tm(capsys, "report")[1]["path"] == str(folder / "report_v02.md")
    assert (folder / "report_v01.md").read_text(encoding="utf-8") == text

    # over the suite budget: the next case that needs a budget stops (exit 2) and says what to do
    assert _tm(capsys, "record", "H4", "pass", "--by", "person", "--note", "title never covered")[0] == 0
    s = state.load(runs["H5"])
    s.spend = {"ai_usd": 4.5}
    state.save(runs["H5"], s)
    code, out = _tm(capsys, "next")
    assert code == 2 and out["status"] == "stop"
    assert out["case"]["id"] == "H5"
    assert "4.5 of 4 USD" in out["message"] and "same place" in out["message"]


def _finish(capsys, *ids):
    for cid in ids:
        assert _tm(capsys, "record", cid, "blocked", "--note", "not today")[0] == 0


def test_find_uses_the_suite_start_resumes(ws, capsys, monkeypatch):
    """Day 1 left unfinished, day 2 started fresh and finished: start, next and report all work in
    day 1, the newest folder with a case still to do."""
    _tm(capsys, "start", "--suite", "recuts")                      # day 1, nothing recorded
    day1 = ws / "acceptance" / "2026-11-06_recuts"
    monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 7))
    code, out = _tm(capsys, "start", "--suite", "recuts", "--new")
    day2 = ws / "acceptance" / "2026-11-07_recuts"
    assert out["path"] == str(day2) and out["resumed"] is False
    _finish(capsys, *CASES)                                        # finishes day 2, the one with todos
    assert all(c["status"] == "blocked" for c in json.loads((day2 / "acceptance.json").read_text(encoding="utf-8"))["cases"])

    code, out = _tm(capsys, "next")
    assert code == 0 and out["path"] == str(day1) and out["case"]["id"] == "H1"
    code, out = _tm(capsys, "report")
    assert out["path"] == str(day1 / "report_v01.md") and not (day2 / "report_v01.md").exists()
    code, out = _tm(capsys, "start", "--suite", "recuts")
    assert out["path"] == str(day1) and out["resumed"] is True
    # once day 1 is finished too, the newest folder (day 2) is the one
    monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 6))
    _finish(capsys, *CASES)
    assert _tm(capsys, "next")[1]["path"] == str(day2)


def test_unreadable_spend_is_never_counted_as_zero(ws, capsys):
    _tm(capsys, "start", "--suite", "recuts")
    folder = ws / "acceptance" / "2026-11-06_recuts"
    cases = {c["id"]: folder / c["run"] for c in _saved(ws)["cases"]}
    s = state.load(RunFolder.open(cases["H2"]))
    s.spend = {"voice_credits": 586.0}
    state.save(RunFolder.open(cases["H2"]), s)
    (cases["H3"] / "run.json").write_text("{not json", encoding="utf-8")

    _finish(capsys, "H1")
    code, out = _tm(capsys, "next")                 # H2 spends: what is left can't be told
    assert code == 2 and out["status"] == "stop" and out["case"]["id"] == "H2"
    assert "H3" in out["message"] and "same place" in out["message"]
    assert out["budget"]["unreadable"] == ["H3"]
    assert out["budget"]["left"] == {"ai_usd": None, "voice_credits": None}
    assert out["budget"]["spent"]["voice_credits"] == 586

    code, out = _tm(capsys, "report")
    text = (folder / "report_v01.md").read_text(encoding="utf-8")
    assert "**could not be read**" in text and "The spend of H3 could not be read" in text
    assert "at least 586 of 3000 ElevenLabs credits" in text and "2414 left" not in text
    assert "except a case run on another machine (H9), whose spend is in its note" in text

    # repaired: what is left is told again
    (cases["H3"] / "run.json").write_text(json.dumps({"run_id": "x", "playbook": "01-refresh-ad",
                                                      "created": "2026-11-06"}), encoding="utf-8")
    code, out = _tm(capsys, "next")
    assert code == 0 and out["budget"]["unreadable"] == []
    assert out["budget"]["left"] == {"ai_usd": 4, "voice_credits": 2414}


def test_over_budget_stops_only_cases_that_spend_that_kind(ws, capsys, tmp_path, monkeypatch):
    _tm(capsys, "start", "--suite", "recuts")
    folder = ws / "acceptance" / "2026-11-06_recuts"
    cases = {c["id"]: c for c in _saved(ws)["cases"]}
    assert cases["H2"]["kinds"] == ["voice_credits"] and cases["H5"]["kinds"] == ["ai_usd"]
    assert set(cases["H7"]["kinds"]) == {"voice_credits", "ai_usd"} and cases["H1"]["kinds"] == []
    run = RunFolder.open(folder / cases["H2"]["run"])
    s = state.load(run)
    s.spend = {"voice_credits": 3100.0}             # voice credits over, AI dollars untouched
    state.save(run, s)
    _finish(capsys, "H1", "H2", "H3", "H4")
    code, out = _tm(capsys, "next")
    assert code == 0 and out["status"] == "case" and out["case"]["id"] == "H5"   # H5 spends ai_usd
    assert out["budget"]["over"] == ["voice_credits"]
    _finish(capsys, "H5", "H6")
    code, out = _tm(capsys, "next")
    assert code == 2 and out["case"]["id"] == "H7" and "3100 of 3000 ElevenLabs credits" in out["message"]

    # load_suite: kinds are known budget kinds, given exactly when needs has budget
    suites = tmp_path / "suites"
    suites.mkdir()
    monkeypatch.setattr(acceptance, "_suites", lambda: suites)
    base = {"id": "X1", "title": "t", "proves": "p", "steps": ["s"], "pass": "p", "judge": None}
    for case, says in (({**base, "needs": ["budget"]}, "exactly when"),
                       ({**base, "needs": ["file"], "kinds": ["ai_usd"]}, "exactly when"),
                       ({**base, "needs": ["budget"], "kinds": ["gold"]}, "kinds"),
                       ({**base, "needs": ["budget"], "kinds": []}, "kinds")):
        (suites / "bad.yaml").write_text(json.dumps({"budget": {"ai_usd": 1}, "cases": [case]}),
                                         encoding="utf-8")
        with pytest.raises(ValueError, match=says):
            acceptance.load_suite("bad")


def test_a_finished_suite_is_resumed_until_its_report_is_written(ws, capsys, monkeypatch):
    """All cases recorded, no report yet: the next day's start resumes it and next says done (so
    the command writes the report); once it is reported, a new start makes a new suite."""
    _tm(capsys, "start", "--suite", "recuts")
    day1 = ws / "acceptance" / "2026-11-06_recuts"
    _finish(capsys, *CASES)
    monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 7))
    code, out = _tm(capsys, "start", "--suite", "recuts")
    assert code == 0 and out["path"] == str(day1) and out["resumed"] is True
    assert "9 of 9" in out["message"]
    assert not (ws / "acceptance" / "2026-11-07_recuts").exists()
    code, out = _tm(capsys, "next")
    assert code == 0 and out["status"] == "done" and out["path"] == str(day1)
    assert "report" in out["message"]
    assert _tm(capsys, "report")[1]["path"] == str(day1 / "report_v01.md")

    code, out = _tm(capsys, "start", "--suite", "recuts")
    day2 = ws / "acceptance" / "2026-11-07_recuts"
    assert out["path"] == str(day2) and out["resumed"] is False
    assert _tm(capsys, "next")[1]["case"]["id"] == "H1"


# --- a suite for another playbook (trend research, plan Task 3) ----------------------------

_CASE = {"title": "t", "proves": "p", "steps": ["s"], "pass": "p", "judge": None}


@pytest.fixture
def suites(tmp_path, monkeypatch):
    path = tmp_path / "suites"
    path.mkdir()
    monkeypatch.setattr(acceptance, "_suites", lambda: path)

    def write(name, data):
        (path / f"{name}.yaml").write_text(json.dumps(data), encoding="utf-8")
    return write


def test_suite_with_playbook_creates_runs_under_its_folder(ws, capsys, suites):
    suites("trends", {"playbook": "trend-research", "cases": [
        {**_CASE, "id": "T1", "needs": ["trendsmesh"]},
        {**_CASE, "id": "T7", "needs": ["artifacts", "human_verdict"], "judge": "the person says yes or no"}]})
    code, out = _tm(capsys, "start", "--suite", "trends")
    assert code == 0 and out["budget"] == {} and out["playbook"] == "04-trend-research"
    folder = ws / "acceptance" / "2026-11-06_trends"
    data = json.loads((folder / "acceptance.json").read_text(encoding="utf-8"))
    assert data["playbook"] == "04-trend-research"
    for c, name in zip(data["cases"], ("T1", "T7")):
        assert c["run"] == f"runs/04-trend-research/2026-11-06_{name}"
        assert state.load(RunFolder.open(folder / c["run"])).playbook == "04-trend-research"
    assert not (folder / "runs" / "01-refresh-ad").exists()
    code, out = _tm(capsys, "next")
    assert code == 0 and out["case"]["id"] == "T1" and out["budget"]["left"] == {}
    # resumed: the run folders are reopened where they are
    assert _tm(capsys, "start", "--suite", "trends")[1]["resumed"] is True
    # the report's template is the suite's playbook's own
    _tm(capsys, "record", "T1", "pass", "--note", "ok")
    _tm(capsys, "record", "T7", "pass", "--note", "yes", "--by", "person")
    code, out = _tm(capsys, "report")
    assert code == 0 and out["path"].endswith("report_v01.md")     # Task 16 gave the playbook its template
    assert acceptance._template_path("01-refresh-ad").parts[-3:] == (
        "refresh-ad", "templates", "acceptance_report_template.md")


def test_suite_playbook_defaults_to_refresh_ad_and_must_be_known(suites):
    suites("plain", {"budget": {"ai_usd": 1}, "cases": [{**_CASE, "id": "X1", "needs": ["file"]}]})
    assert acceptance.load_suite("plain")["playbook"] == "01-refresh-ad"
    suites("odd", {"playbook": "nope", "cases": [{**_CASE, "id": "X1", "needs": ["file"]}]})
    with pytest.raises(ValueError, match="odd.yaml.*not a playbook"):
        acceptance.load_suite("odd")


def test_suite_without_budget_loads(suites):
    case = {**_CASE, "id": "X1", "needs": ["file"]}
    suites("none", {"cases": [case]})
    suites("empty", {"budget": {}, "cases": [case]})
    assert acceptance.load_suite("none")["budget"] == {} == acceptance.load_suite("empty")["budget"]
    # a case that spends still needs the budget it spends from
    for budget in ({}, None):
        data = {"cases": [{**case, "needs": ["budget"], "kinds": ["ai_usd"]}]}
        suites("spends", {**data, **({"budget": budget} if budget is not None else {})})
        with pytest.raises(ValueError, match="budget"):
            acceptance.load_suite("spends")
    suites("bad", {"budget": [], "cases": [case]})
    with pytest.raises(ValueError, match="budget"):
        acceptance.load_suite("bad")


def test_needs_accept_trendsmesh_and_artifacts(suites):
    suites("needs", {"cases": [{**_CASE, "id": "X1", "needs": ["trendsmesh", "artifacts", "meta"]}]})
    assert acceptance.load_suite("needs")["cases"][0]["needs"] == ["trendsmesh", "artifacts", "meta"]
    suites("other", {"cases": [{**_CASE, "id": "X1", "needs": ["foreplay"]}]})
    with pytest.raises(ValueError, match="trendsmesh, artifacts"):
        acceptance.load_suite("other")


# --- the trends suite (trend research, plan Task 16) -----------------------------------------

TRENDS = [f"T{n}" for n in (1, 2, 3, 4, 5, 7, 8, 9, 6)]   # T6 waits for day 7: last
TRENDS_JUDGED = {"T2", "T3", "T4", "T5", "T7"}


def test_trends_suite_loads_with_nine_cases_and_no_budget():
    suite = acceptance.load_suite("trends")
    assert suite["playbook"] == "04-trend-research" and suite["budget"] == {}
    assert [c["id"] for c in suite["cases"]] == TRENDS
    for c in suite["cases"]:
        assert c["title"] and c["proves"] and c["steps"] and c["pass"]
        assert "budget" not in c["needs"] and "kinds" not in c, c["id"]
        assert (c["judge"] is not None) == (c["id"] in TRENDS_JUDGED) == ("human_verdict" in c["needs"]), c["id"]
    needs = {c["id"]: c["needs"] for c in suite["cases"]}
    assert needs["T1"] == ["trendsmesh"] and needs["T4"] == ["meta", "human_verdict"]
    assert needs["T5"] == ["artifacts", "human_verdict"] and needs["T9"] == ["trendsmesh"]
    assert "tm trends check-fields" in next(c for c in suite["cases"] if c["id"] == "T1")["pass"]
    # the default suite of the command stays the re-cut one
    assert "(when empty: `recuts`)" in (acceptance.Path(__file__).parents[2] / "commands" / "acceptance.md"
                                       ).read_text(encoding="utf-8")


def test_trends_start_makes_runs_under_04_trend_research(ws, capsys):
    code, out = _tm(capsys, "start", "--suite", "trends")
    assert code == 0 and out["playbook"] == "04-trend-research" and out["budget"] == {}
    folder = ws / "acceptance" / "2026-11-06_trends"
    data = json.loads((folder / "acceptance.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cases"]] == TRENDS and data["budget"] == {}
    for c in data["cases"]:
        assert c["run"] == f"runs/04-trend-research/2026-11-06_{c['id']}"
        s = state.load(RunFolder.open(folder / c["run"]))
        assert s.playbook == "04-trend-research" and s.spend == {}
    assert not (folder / "runs" / "01-refresh-ad").exists()
    code, out = _tm(capsys, "next")
    assert code == 0 and out["case"]["id"] == "T1" and out["budget"]["left"] == {}
    assert out["position"] == {"case": 1, "of": 9, "todo": 9}


def test_report_without_spend_lines(ws, capsys):
    _tm(capsys, "start", "--suite", "trends")
    assert _tm(capsys, "record", "T1", "pass", "--note", "search_trends and get_trend_videos saved")[0] == 0
    assert _tm(capsys, "record", "T2", "pass", "--by", "person", "--note", "the map is right")[0] == 0
    assert _tm(capsys, "record", "T9", "blocked", "--note", "no time")[0] == 0
    code, out = _tm(capsys, "report")
    assert code == 0 and out["counts"] == {"pass": 2, "fail": 0, "blocked": 1, "todo": 6}
    text = (ws / "acceptance" / "2026-11-06_trends" / "report_v01.md").read_text(encoding="utf-8")
    assert text.startswith("## Acceptance: trends (2026-11-06)")
    assert "the map is right" in text and "not run yet" in text and "#### T9" in text
    assert not re.search(r"\$\{?[a-z_]", text)                       # every placeholder filled
    for gone in ("Spend", "spend", "budget", "Budget", "Replicate", "ElevenLabs", "credits", "USD", "H9"):
        assert gone not in text, gone


def test_trends_next_reaches_t7_before_t6(ws, capsys):
    _tm(capsys, "start", "--suite", "trends")
    for cid in ("T1", "T2", "T3", "T4", "T5"):
        by = ("--by", "person") if cid != "T1" else ()
        assert _tm(capsys, "record", cid, "pass", "--note", "ok", *by)[0] == 0
    assert _tm(capsys, "next")[1]["case"]["id"] == "T7"


def test_trends_cases_are_worked_from_the_suite_folder(ws, capsys, monkeypatch):
    """The trends case runs belong to the suite folder, not to the workspace the person opened
    (final review of PR D, Important 1): from there the collector's marker, T6's weekly run after
    T2 and T8's seeds land where they are looked for, and `tm acceptance` itself still works."""
    _tm(capsys, "start", "--suite", "trends")
    folder = ws / "acceptance" / "2026-11-06_trends"
    t1, t2 = (folder / "runs" / "04-trend-research" / f"2026-11-06_{c}" for c in ("T1", "T2"))
    assert trend_spool.workspace_of(RunFolder.open(t2)) == folder.resolve()
    after = ["run", "new", "--playbook", "trend-research", "--name", "T2", "--after",
             "runs/04-trend-research/2026-11-06_T2", "--json"]
    seeds = ["seeds", "list", "--source", "pb4", "--json"]
    (folder / "library").mkdir()
    (folder / "library" / "seeds.jsonl").write_text('{"seed_id": "s1", "source": "pb4"}\n', encoding="utf-8")
    t2_run = RunFolder.open(t2)
    (page.new_folder(t2_run, "report") / "index.html").write_text("<!DOCTYPE html>", encoding="utf-8")
    page.record_published(t2_run, "report", "art_t2", "ver_1")

    # from the workspace the person opened, none of the three reaches the case runs
    assert main(["trends", "collect", "on", "--run", str(t1), "--json"]) == 1
    assert main(after) == 1
    capsys.readouterr()
    assert main(seeds) == 0 and json.loads(capsys.readouterr().out)["seeds"] == []

    # from the suite folder, each does
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    assert main(["trends", "collect", "on", "--run", str(t1), "--json"]) == 0
    capsys.readouterr()
    assert (folder / ".trendsmesh" / "collect.json").is_file() and not (ws / ".trendsmesh").exists()
    assert main(after) == 0
    weekly = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    assert weekly.path.parent == t2.parent
    assert state.load(weekly).previous_run == "runs/04-trend-research/2026-11-06_T2"
    assert page.published(weekly, "report")["slug"] == "art_t2"      # T6's page: T2's link
    assert main(seeds) == 0 and [r["seed_id"] for r in json.loads(capsys.readouterr().out)["seeds"]] == ["s1"]

    # `tm acceptance` from inside the suite folder works in it and never nests a second one
    code, out = _tm(capsys, "next")
    assert code == 0 and out["path"] == str(folder) and out["case"]["run"] == str(t1)
    code, out = _tm(capsys, "start", "--suite", "trends")
    assert code == 0 and out["path"] == str(folder) and out["resumed"] is True
    assert not (folder / "acceptance").exists()
    assert _tm(capsys, "next", "--suite", "recuts")[0] == 1          # another suite is not here


def test_trends_prose_works_from_the_suite_folder_and_t6_follows_t2():
    """The operator is told to cd into the suite folder, T6 follows T2's case run by name (never
    T1's, which has the same category), and T8 lists the suite folder's seeds."""
    root = acceptance.Path(__file__).parents[2]
    command = (root / "commands" / "acceptance.md").read_text(encoding="utf-8")
    assert "`cd` into it" in command and "`tm acceptance` works from there too" in command
    steps = {c["id"]: " ".join(c["steps"]) for c in acceptance.load_suite("trends")["cases"]}
    assert "--after <T2's case run>" in steps["T6"] and "never T1's" in steps["T6"]
    assert "run_scheduled_task" in steps["T6"]
    assert "from the suite folder" in steps["T8"]
    assert "T6 follows T2's run" in steps["T1"]


# --- the briefs suite (creative brief, plan Task 18) -----------------------------------------

BRIEFS = [f"B{n}" for n in range(1, 10)]
BRIEFS_JUDGED = {"B1", "B3", "B5", "B6", "B7", "B9"}


def test_briefs_suite_loads_with_nine_cases_and_no_budget():
    suite = acceptance.load_suite("briefs")
    assert suite["playbook"] == "02-creative-brief" and suite["budget"] == {}
    assert [c["id"] for c in suite["cases"]] == BRIEFS
    for c in suite["cases"]:
        assert c["title"] and c["proves"] and c["steps"] and c["pass"]
        assert "budget" not in c["needs"] and "kinds" not in c, c["id"]
        assert (c["judge"] is not None) == (c["id"] in BRIEFS_JUDGED) == ("human_verdict" in c["needs"]), c["id"]
    needs = {c["id"]: c["needs"] for c in suite["cases"]}
    assert needs["B1"] == ["meta", "human_verdict"] and needs["B2"] == ["meta"]
    assert needs["B4"] == ["trendsmesh"] and needs["B6"] == ["artifacts", "human_verdict"]
    # a brief run reads the account at A1
    assert needs["B8"] == ["meta", "trendsmesh"] and needs["B9"] == ["meta", "human_verdict"]
    by_id = {c["id"]: c for c in suite["cases"]}
    assert "tm config check" in by_id["B1"]["pass"] and "tm audience pick" in by_id["B2"]["pass"]
    assert "tm trends check-fields" in by_id["B4"]["pass"]
    assert "00_raw/seed.json" in by_id["B8"]["pass"]
    # B8 is worked from the trends suite's folder (its seeds and the run), and recorded in this suite
    b8 = " ".join(by_id["B8"]["steps"])
    assert "acceptance/<date>_trends/" in b8 and "tm run new --playbook creative-brief" in b8 and "--seed" in b8
    assert "tm acceptance record" in b8
    assert all("Note in the report" not in step for step in by_id["B4"]["steps"])
    # the two notes the controller asked for
    assert "first reply" in " ".join(by_id["B1"]["steps"]) and "output too large" in " ".join(by_id["B4"]["steps"])
    # the report template is the playbook's own and has no spend lines
    assert acceptance._template_path("02-creative-brief").is_file()
    # the report is kept by the user or sent to the TrendsMesh team privately, never posted on an issue
    command = (acceptance.Path(__file__).parents[2] / "commands" / "acceptance.md").read_text(encoding="utf-8")
    words = " ".join(command.split())
    assert "they keep it" in words and "send the file to the team privately" in words
    assert "Never suggest posting it anywhere public (an issue" in words
    assert not re.search(r"issue #\d+|/issues\b", words)


def test_briefs_start_makes_runs_under_02_creative_brief(ws, capsys):
    code, out = _tm(capsys, "start", "--suite", "briefs")
    assert code == 0 and out["playbook"] == "02-creative-brief" and out["budget"] == {}
    folder = ws / "acceptance" / "2026-11-06_briefs"
    data = json.loads((folder / "acceptance.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cases"]] == BRIEFS and data["budget"] == {}
    for c in data["cases"]:
        assert c["run"] == f"runs/02-creative-brief/2026-11-06_{c['id']}"
        s = state.load(RunFolder.open(folder / c["run"]))
        assert s.playbook == "02-creative-brief" and s.spend == {}
    assert not (folder / "runs" / "01-refresh-ad").exists()
    code, out = _tm(capsys, "next")
    assert code == 0 and out["case"]["id"] == "B1" and out["position"] == {"case": 1, "of": 9, "todo": 9}


# --- the organic suite (organic video plan Task 23) ------------------------------------------

ORGANIC = [f"O{n}" for n in range(1, 11)]
# the brief's needs per case, written out (not derived from the suite)
ORGANIC_NEEDS = {
    "O1": ["trendsmesh", "human_verdict"], "O2": ["trendsmesh", "artifacts", "human_verdict"],
    "O3": ["artifacts", "human_verdict"], "O4": ["key", "budget", "human_verdict"],
    "O5": ["key", "budget", "human_verdict"], "O6": ["key", "budget", "human_verdict"],
    "O7": ["key", "budget", "human_verdict"], "O8": ["key", "budget", "human_verdict"],
    "O9": ["trendsmesh", "artifacts", "human_verdict"], "O10": ["human_verdict"]}
ORGANIC_KINDS = {"O4": ["ai_usd"], "O5": ["voice_credits"], "O6": ["ai_usd"], "O7": ["ai_usd"], "O8": ["ai_usd"]}
_TM_CMD = re.compile(r"`(tm [^`]+)`")


def _case(suite, cid):
    return next(c for c in acceptance.load_suite(suite)["cases"] if c["id"] == cid)


def _prose(case):
    return " ".join([*case["steps"], case["pass"], case["judge"] or ""])


def test_organic_suite_loads_with_ten_cases_and_its_budget():
    suite = acceptance.load_suite("organic")
    assert suite["playbook"] == "03-organic-ai-video"
    assert suite["budget"] == {"ai_usd": 10, "voice_credits": 5000}
    assert [c["id"] for c in suite["cases"]] == ORGANIC
    for c in suite["cases"]:
        assert c["title"] and c["proves"] and c["steps"] and c["pass"] and c["judge"], c["id"]
        assert c["needs"] == ORGANIC_NEEDS[c["id"]], c["id"]
    # the carries tests could not prove are asked of the live run, each in its own case
    assert "read_declaration" in _prose(_case("organic", "O2")) and "CAPABILITIES" in _prose(_case("organic", "O2"))
    assert "read_declaration" in _case("organic", "O3")["pass"]
    assert "normalized_alignment" in _case("organic", "O5")["pass"]
    o6 = _prose(_case("organic", "O6"))
    assert "seedance-1.5-pro" in o6 and "seedance-2.5" in o6 and "did not fit the budget" in _case("organic", "O6")["pass"]
    assert "number words" in _case("organic", "O4")["pass"]
    assert "drop-slot" in _case("organic", "O9")["pass"]
    o2 = _case("organic", "O2")
    assert "04_final/proposals_v" in " ".join(o2["steps"]) and "if that step was run" in o2["pass"].lower()
    o8 = _case("organic", "O8")
    assert "not the host image" in " ".join(o8["steps"]) and "not proved" in " ".join(o8["steps"])
    assert "tm kit check --run" in " ".join(_case("organic", "O3")["steps"])
    # PR E review I3: a paid case starts its own production run from O2's page (a case run is an idea or week run)
    o4 = " ".join(_case("organic", "O4")["steps"])
    assert "O2's proposals page" in o4 and "tm organic start --run <O2's run>" in o4 and "O3's run folder" not in o4
    assert "at Hands-off" in o4 and "A to Z" not in o4 + _case("organic", "O4")["title"]          # N3: the page's level
    o8 = " ".join(_case("organic", "O8")["steps"])
    assert "a person described in text" in o8 and "Seedance 2.0, the top quality tier" in o8 and "O7" not in o8   # N4
    for cid in ("O5", "O6", "O7", "O8"):
        assert "O2's" in " ".join(_case("organic", cid)["steps"]) and "start it" in " ".join(_case("organic", cid)["steps"]), cid
    # m7: O1 runs A0 and A1; m6: O9 can deliver (one script day, one to drop, the rest skipped)
    o1 = " ".join(_case("organic", "O1")["steps"])
    assert "A0" in o1 and "A1" in o1 and "D1" not in o1
    o9 = _case("organic", "O9")
    assert "every other day skip" in " ".join(o9["steps"]) and "tm organic deliver-week" in " ".join(o9["steps"])
    assert "spent nothing; the week's total is unchanged" in o9["pass"]
    # the default suite of the command stays the re-cut one, and it lists organic
    cmd = (acceptance.Path(__file__).parents[2] / "commands" / "acceptance.md").read_text(encoding="utf-8")
    assert "(when empty: `recuts`)" in cmd and "`03-organic-ai-video` with the \"Organic video\" skill" in cmd
    assert acceptance._template_path("03-organic-ai-video").is_file()


def test_organic_start_makes_runs_under_03_organic_ai_video(ws, capsys):
    code, out = _tm(capsys, "start", "--suite", "organic")
    assert code == 0 and out["playbook"] == "03-organic-ai-video"
    assert out["budget"]["ai_usd"] == 10 and out["budget"]["voice_credits"] == 5000
    folder = ws / "acceptance" / "2026-11-06_organic"
    data = json.loads((folder / "acceptance.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cases"]] == ORGANIC
    for c in data["cases"]:
        assert c["run"] == f"runs/03-organic-ai-video/2026-11-06_{c['id']}"
        s = state.load(RunFolder.open(folder / c["run"]))
        assert s.playbook == "03-organic-ai-video" and s.spend == {}
    assert not (folder / "runs" / "01-refresh-ad").exists()
    code, out = _tm(capsys, "next")
    assert code == 0 and out["case"]["id"] == "O1" and out["position"] == {"case": 1, "of": 10, "todo": 10}


def test_organic_production_runs_of_a_case_run_count_in_the_suite_budget(ws, capsys):
    """PR E review I3: an organic video case spends in the production runs `tm organic start` makes beside the case
    runs (organic.parent: the idea run; organic.week: the week run). Their spend counts in the suite's budget and its
    `next` stop, and the report's spend line of the case they came from names them. One that cannot be read leaves
    what is left untold."""
    from tm.playbooks import ORGANIC_VIDEO
    _tm(capsys, "start", "--suite", "organic")
    folder = ws / "acceptance" / "2026-11-06_organic"
    cases = {c["id"]: c["run"] for c in json.loads((folder / "acceptance.json").read_text(encoding="utf-8"))["cases"]}

    def child(name, spend, **organic):
        run = RunFolder.create(folder, name, date(2026, 11, 6), playbook=ORGANIC_VIDEO)
        s = state.load(run)
        s.organic, s.spend = organic, spend
        state.save(run, s)
        return run

    child("exampleedu-p2", {"ai_usd": 1.30}, parent=cases["O2"], proposal="p2")
    child("exampleedu-w1", {"ai_usd": 0.0}, parent=cases["O9"], week=cases["O9"], slot="mon")
    child("other-p9", {"ai_usd": 7.0}, parent="runs/03-organic-ai-video/2026-11-01_elsewhere")   # no case's
    _finish(capsys, "O1", "O2", "O3")
    code, out = _tm(capsys, "next")
    assert code == 0 and out["case"]["id"] == "O4"
    assert out["budget"]["spent"]["ai_usd"] == 1.30 and out["budget"]["left"]["ai_usd"] == 8.70
    week_slot = child("exampleedu-w3", {"ai_usd": 9.0}, week=cases["O9"], slot="wed")
    code, out = _tm(capsys, "next")
    assert code == 2 and out["status"] == "stop" and "10.3 of 10 USD" in out["message"]
    _tm(capsys, "report")
    text = (folder / "report_v01.md").read_text(encoding="utf-8")
    o2 = text[text.index("#### O2:"):text.index("#### O3:")]
    assert "1.3 USD" in o2 and "2026-11-06_exampleedu-p2" in o2
    assert "9 USD" in text[text.index("#### O9:"):text.index("#### O10:")]
    (week_slot.path / "run.json").write_text("{not json", encoding="utf-8")
    code, out = _tm(capsys, "next")
    assert code == 2 and out["budget"]["left"]["ai_usd"] is None
    assert "2026-11-06_exampleedu-w3" in " ".join(out["budget"]["unreadable"])

    # re-review N5: a dropped slot of O9's week whose folder is gone still counts what the week run recorded
    import shutil
    shutil.rmtree(week_slot.path)
    w9 = RunFolder.open(folder / cases["O9"])
    s = state.load(w9)
    s.organic = {"dropped": [{"day": "wed", "run": "2026-11-06_exampleedu-w3", "spent": 9.0,
                              "path": "runs/03-organic-ai-video/2026-11-06_exampleedu-w3"}]}
    state.save(w9, s)
    code, out = _tm(capsys, "next")
    assert code == 2 and out["budget"]["spent"]["ai_usd"] == 10.3 and out["budget"]["unreadable"] == []
    _tm(capsys, "report")
    text = (folder / "report_v02.md").read_text(encoding="utf-8")
    assert "`2026-11-06_exampleedu-w3` 9 USD" in text[text.index("#### O9:"):text.index("#### O10:")]


def test_spending_cases_name_their_kinds():
    suite = acceptance.load_suite("organic")
    for c in suite["cases"]:
        if c["id"] in ORGANIC_KINDS:
            assert c["kinds"] == ORGANIC_KINDS[c["id"]], c["id"]
            assert set(c["kinds"]) <= set(suite["budget"])
        else:
            assert "budget" not in c["needs"] and "kinds" not in c, c["id"]


@pytest.mark.parametrize("suite", ["recuts", "trends", "briefs", "organic"])
def test_every_tm_command_a_case_names_exists(suite):
    """A step that tells the operator to run `tm ...` must name a command the engine has (organic: with
    flags it takes; the older suites mention partial commands, so only their command words are checked)."""
    from tm.cli import build_parser
    parser = build_parser()
    named = 0
    for c in acceptance.load_suite(suite)["cases"]:
        for text in [*c["steps"], c["pass"], c["judge"] or ""]:
            for cmd in _TM_CMD.findall(text):
                cmd_ = re.sub(r"<([^>|]*)\|[^>]*>", r"\1", cmd)      # <ok|missing> -> ok
                words = re.sub(r"<[^>]*>", "x", cmd_).replace("...", "").replace("\u2026", "").split()[1:]
                if not words or words[0].startswith("-"):
                    continue
                head = []
                for w in words:
                    if not re.fullmatch(r"[a-z][a-z0-9_-]*", w) or w == "x":
                        break
                    head.append(w)
                head = head[:1] if head[:1] == ["tool"] else head   # `tm tool <name>` hands the rest to the tool
                with pytest.raises(SystemExit) as stop:
                    parser.parse_args([*head, "--help"])
                assert stop.value.code == 0, f"{suite} {c['id']}: `{cmd}`"
                named += 1
                flags = [w for w in words if w.startswith("--")]
                if suite == "organic" and flags and len(head) < len(words):   # this suite's commands are whole
                    try:
                        parser.parse_args(words)
                    except SystemExit as exc:
                        raise AssertionError(f"{suite} {c['id']}: `{cmd}` does not parse ({exc.code})") from None
    assert named
