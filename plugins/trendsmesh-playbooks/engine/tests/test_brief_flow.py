"""Creative brief (playbook 02) in the step engine: its steps, the checks they require, and its
check-ins at each level."""

import json
import sys
import types
from datetime import date

import pytest
import yaml

from tm import checkins, evidence, flow, paths, playbooks, state, stepchecks, stops
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder

ALL = ["review_pack", "briefs", "animatics", "page"]
STEP_IDS = ["A0", "A1", "B1", "B2", "B3", "B4", "C1", "D1", "D2", "D3", "E1", "E2"]
TABLE = {  # id: (title, outputs, checkins, requires), the plan's Task 1
    "A0": ("Stack check and run folder", ALL, [], []),
    "A1": ("Product and intake card", ALL, ["G0"], ["intake_written"]),
    "B1": ("Account context and persona", ALL, ["G1"], ["audience_picked"]),
    "B2": ("Customer voice", ALL, [], ["voice_checked"]),
    "B3": ("Rising trends", ALL, [], ["trends_or_guess"]),
    "B4": ("Fit scoring and saturation", ALL, [], ["scores_and_saturation"]),
    "C1": ("Concepts and the review pack", ["review_pack", "briefs"], ["G2"],
           ["concepts_checked", "page_built"]),
    "D1": ("Briefs", ["briefs"], [], ["concepts_chosen", "brief_checked"]),
    "D2": ("Animatics", ["animatics"], [], ["animatics_rendered"]),
    "D3": ("Page with briefs and animatics", ["briefs"], ["G3"], ["page_built"]),
    "E1": ("Production views", ["briefs"], ["G4"], ["production_checked", "page_built"]),
    "E2": ("Hand-off", ALL, [], ["concepts_chosen", "handed_off"]),
}


@pytest.fixture
def checks_pass(monkeypatch):
    """Every required check passes; the names asked, in order, are recorded."""
    asked = []

    def run(name, _run):
        asked.append(name)
        return None
    monkeypatch.setattr(stepchecks, "run", run)
    return asked


def _brief(tmp_path, level, outputs=ALL):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    set_level(run, level)
    return run


def _walk(run, until=None, notices=None):
    """Do each step's work and answer each check-in with its first choice (by rule when the
    engine says auto) until the run is done or stops, or `until` is the step to work on next.
    Returns the check-ins seen as (step, action, ids, card), the steps worked, and the last next().
    `notices`, when given, collects (step, action, ids) of every next() that carries a notice."""
    seen, worked = [], []
    cat = checkins.load(playbook=CREATIVE_BRIEF)
    for _ in range(100):
        nxt = flow.next(run)
        if notices is not None and nxt.notice:
            notices.append((nxt.step, nxt.action, nxt.checkin.ids if nxt.checkin else None))
        if nxt.action in ("done", "stop") or (nxt.action == "work" and nxt.step == until):
            return seen, worked, nxt
        if nxt.action == "work":
            worked.append(nxt.step)
            complete(run, nxt.step)
            continue
        assert nxt.action in ("ask", "auto"), nxt
        seen.append((nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card))
        by, note = ("rule", "test data") if nxt.action == "auto" else ("user", None)
        if nxt.checkin.card:
            decide(run, nxt.checkin.card, cat.checkins[nxt.checkin.ids[0]].choices[0], by=by, note=note)
        else:
            for cid in nxt.checkin.ids:
                decide(run, cid, cat.checkins[cid].choices[0], by=by, note=note)
    raise AssertionError("the run never ended")


# --- the registry, steps and catalogue --------------------------------------------

def test_creative_brief_is_registered():
    pb = playbooks.get("creative-brief")
    assert (pb.id, pb.name, pb.skill, pb.guess) == (CREATIVE_BRIEF, "Creative brief", "creative-brief", True)
    assert pb.data_dir == paths.bundled_data() / "creative-brief"
    assert {p.id: p.guess for p in playbooks.all_playbooks()} == {
        REFRESH_AD: True, CREATIVE_BRIEF: True, ORGANIC_VIDEO: False, TREND_RESEARCH: False, CREATE_AD: True}


def test_creative_brief_steps_match_the_plan():
    every = flow.steps(CREATIVE_BRIEF)
    assert flow.output_ids(CREATIVE_BRIEF) == ALL
    assert [st.id for st in every] == STEP_IDS
    assert flow.flows(CREATIVE_BRIEF) == set()
    for st in every:
        assert (st.title, list(st.outputs), list(st.checkins), list(st.requires)) == TABLE[st.id], st.id
        assert not st.spends and st.budget is None and not st.before and not st.skip_when, st.id
        assert st.ref == f"skills/creative-brief/references/flow.md#{st.id.lower()}"
    named = {name for pb in (CREATIVE_BRIEF, ORGANIC_VIDEO, CREATE_AD) for st in flow.steps(pb) for name in st.requires}
    chosen = {name for pb in (CREATIVE_BRIEF, ORGANIC_VIDEO, CREATE_AD)
              for c in checkins.load(playbook=pb).checkins.values()
              for effect in c.on_choice.values() for name in effect.get("requires") or ()}
    assert chosen == {"profile_confirmed", "week_in_budget",   # organic video's reuse_profile reuse, week approve
                      "ad_upload_proposed"}                    # create an ad's upload create
    assert set(stepchecks.NAMES) == named | chosen   # every check is required; none registered unused
    assert not any(st.requires for pb in (REFRESH_AD, TREND_RESEARCH) for st in flow.steps(pb))


def test_creative_brief_catalogue():
    cat = checkins.load(playbook=CREATIVE_BRIEF)
    assert list(cat.checkins) == ["G0", "G1", "G2", "G3", "G4"]
    assert cat.levels == checkins.load(playbook=TREND_RESEARCH).levels
    assert {c.id: (c.name, c.ask) for c in cat.cards.values()} == {
        "approve_setup": ("Approve the setup", "last"),
        "approve_briefs": ("Approve the briefs", "last")}
    big = {"every_step": "own", "big_calls": "card", "hands_off": "rule"}
    want = {
        "G0": ("Confirm the intake card", "approve_setup", big,
               "logged: the card as derived (FLOWS A1, AUTO: logged)"),
        "G1": ("Accept the persona and target segment", "approve_setup", big,
               "≥ 10 results per segment (lowest cost per result), else the thin-data fallback: "
               "largest directional cluster, cross-checked, marked directional (`tm audience pick`)"),
        "G2": ("Choose the concepts", None, {"every_step": "own", "big_calls": "own", "hands_off": "rule"},
               "top N by score, diversity passed (`tm brief pick`)"),
        "G3": ("Accept the briefs and animatics", "approve_briefs", big, "published as is"),
        "G4": ("Accept the production views", "approve_briefs", big, "published as is"),
    }
    for cid, (name, card, route, rule) in want.items():
        c = cat.checkins[cid]
        assert (c.name, c.card, c.route, c.rule, c.choices, c.money) == (
            name, card, route, rule, ("accept",), False), cid


@pytest.mark.parametrize("bad", ["true", "yes", 1, 0, None, []])
def test_guess_flag_must_be_boolean(tmp_path, monkeypatch, bad):
    rows = [{"id": "01-refresh-ad", "name": "Refresh an ad", "skill": "refresh-ad", "data": ".",
             "guess": True},
            {"id": "04-trend-research", "name": "Trend research", "skill": "trend-research",
             "data": "trend-research"}]
    registry = tmp_path / "playbooks.yaml"
    registry.write_text(yaml.safe_dump({"playbooks": rows}), encoding="utf-8")
    monkeypatch.setattr(playbooks, "_registry_path", lambda: registry)
    assert playbooks.get("refresh-ad").guess is True
    assert playbooks.get("trend-research").guess is False   # no flag: no guess mode
    rows[1]["guess"] = bad
    bad_registry = tmp_path / "bad.yaml"   # a new path: the registry is cached per file
    bad_registry.write_text(yaml.safe_dump({"playbooks": rows}), encoding="utf-8")
    monkeypatch.setattr(playbooks, "_registry_path", lambda: bad_registry)
    with pytest.raises(ValueError, match="row 2") as no:
        playbooks.get("refresh-ad")
    assert "guess must be true or false" in str(no.value) and "bad.yaml" in str(no.value)


def test_unknown_required_check_refused_at_load(tmp_path):
    folder = paths.bundled_data() / "creative-brief"
    data = yaml.safe_load((folder / "steps.yaml").read_text(encoding="utf-8"))
    data["steps"][2]["requires"] = ["audience_picked", "persona_guessed"]
    steps_path = tmp_path / "steps.yaml"
    steps_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="B1") as no:
        flow._load_steps(steps_path, folder / "checkins.yaml")
    assert "persona_guessed" in str(no.value) and "steps.yaml" in str(no.value)


def test_run_new_offers_creative_brief_now_its_skill_ships(tmp_path, monkeypatch, capsys):
    """The plugin's own skills folder holds the creative-brief skill, so `tm run new` offers it with
    no fixture; a root without it still refuses it as coming in a later version."""
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    assert (playbooks.skills_root() / "creative-brief" / "SKILL.md").is_file()
    assert main(["run", "new", "--playbook", "creative-brief", "--name", "ld", "--json"]) == 0
    run = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    assert run.path.parent == ws / "runs" / CREATIVE_BRIEF
    s = state.load(run)
    assert (s.playbook, s.brief, s.checked) == (CREATIVE_BRIEF, None, {})
    root = tmp_path / "skills"
    (root / "refresh-ad").mkdir(parents=True)
    (root / "refresh-ad" / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
    monkeypatch.setattr(playbooks, "skills_root", lambda: root)
    assert main(["run", "new", "--playbook", "creative-brief", "--name", "ld", "--json"]) == 1
    assert "Creative brief comes in a later version" in json.loads(capsys.readouterr().out)["message"]


# --- the intake: the product first, the level and outputs on A1's card ---------------

def test_a0_of_a_brief_needs_no_level_or_outputs_and_asks_only_for_the_product(tmp_path, capsys):
    """A creative brief chooses its level and outputs on A1's card (`intake_written` checks them),
    so A0 is done without them, and `tm next` asks for the product only, never the intake in one
    batch."""
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin) == ("A0", "work", None)
    assert "which product" in nxt.message and "one batch" not in nxt.message
    assert main(["done", "A0", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()
    s = state.load(run)
    assert (s.step, s.level, s.outputs) == ("A1", None, [])
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A1", "work")
    assert "which product" in nxt.message and "intake card" in nxt.message and "one batch" not in nxt.message
    # A1 still needs them: the generic guard holds, so the card's answers must set them, and it says
    # how (the intake answers and tm config write), not `tm level`
    with pytest.raises(ValueError, match="level of involvement is not set") as refused:
        complete(run, "A1")
    assert "tm config write" in str(refused.value) and "tm level" not in str(refused.value)
    set_level(run, "every_step")
    with pytest.raises(ValueError, match="outputs are not set") as refused:
        complete(run, "A1")
    assert "tm config write" in str(refused.value)
    s = state.load(run)
    s.level = None
    state.save(run, s)
    with pytest.raises(ValueError):                      # A0 is done: never twice
        complete(run, "A0")
    assert state.load(run).step == "A1"
    set_level(run, "every_step")
    s = state.load(run)
    s.outputs = list(ALL)
    state.save(run, s)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A1", "work") and nxt.checkin.ids == ["G0"]


def test_other_playbooks_still_need_the_intake_at_a0(tmp_path):
    """Refresh-ad and trend research are unchanged: A0 is the intake in one batch, and it is not
    done without the level and the outputs."""
    for pb in (REFRESH_AD, TREND_RESEARCH):
        ws = tmp_path / pb
        ws.mkdir()
        run = RunFolder.create(ws, "x", date(2026, 11, 7), playbook=pb)
        nxt = flow.next(run)
        assert nxt.step == "A0" and "one batch" in nxt.message
        with pytest.raises(ValueError, match="level of involvement is not set") as refused:
            complete(run, "A0")
        assert "tm level" in str(refused.value)


# --- the skill ----------------------------------------------------------------------

PLUGIN = paths.bundled_data().parent
SKILL = PLUGIN / "skills" / "creative-brief"


def test_every_step_ref_has_its_anchor_in_the_skill():
    """Each step's ref is a section of the bundled skill's flow.md, one anchor per step, in step order."""
    import re
    for st in flow.steps(CREATIVE_BRIEF):
        assert st.ref.startswith("skills/creative-brief/references/flow.md#"), st.ref
    flow_md = (SKILL / "references" / "flow.md").read_text(encoding="utf-8")
    anchors = re.findall(r'<a id="([a-z0-9]+)"></a>', flow_md)
    assert anchors == [st.ref.split("#")[1] for st in flow.steps(CREATIVE_BRIEF)]


def _tm_commands(text: str) -> list[str]:
    """Every `tm …` command written in backticks."""
    import re
    return [m.group(1).strip() for m in re.finditer(r"`(tm [^`]+)`", text)]


def _leaf(parser, words: list[str]):
    """Walk the subcommands named by `words`; return the parser reached and the words not used. A
    word with `*` (`reddit-*`) must match at least one subcommand: the first match is followed."""
    import argparse
    import fnmatch
    rest = list(words)
    while rest:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            break
        word = rest[0]
        names = [n for n in subs[0].choices if fnmatch.fnmatchcase(n, word)] if "*" in word else \
            ([word] if word in subs[0].choices else [])
        if not names:
            raise AssertionError(f"no subcommand {word!r}; known: {sorted(subs[0].choices)}")
        parser, rest = subs[0].choices[names[0]], rest[1:]
    return parser, rest


def test_skill_names_only_commands_and_flags_tm_has():
    """Every `tm …` in the creative-brief skill and the plugin's shared references is a real
    command path, and every --flag it writes is an option of that command."""
    import re
    from tm import cli
    parser = cli.build_parser()
    files = sorted(SKILL.rglob("*.md")) + sorted((PLUGIN / "references").glob("*.md"))
    seen = 0
    for f in files:
        for cmd in _tm_commands(f.read_text(encoding="utf-8")):
            words = cmd.split()[1:]
            path = [w for w in words if re.fullmatch(r"[a-z][a-z0-9*-]*", w)]
            leaf, rest = _leaf(parser, path[:3])
            choices = [a.choices for a in leaf._actions if not a.option_strings and a.choices]
            if choices and rest:                     # `tm trends collect on`, `tm evidence guess`
                assert rest[0] in choices[0], f"{f.name}: `{cmd}`: {rest[0]!r} is not one of {choices[0]}"
            options = {o for a in leaf._actions for o in a.option_strings}
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", cmd):
                assert flag in options, f"{f.name}: `{cmd}`: {flag} is not an option ({sorted(options)})"
            seen += 1
    assert seen > 50


# --- the levels ---------------------------------------------------------------------

def test_every_step_asks_g0_to_g4_one_by_one(tmp_path, checks_pass):
    run = _brief(tmp_path, "every_step")
    seen, worked, end = _walk(run)
    assert seen == [("A1", "ask", ["G0"], None), ("B1", "ask", ["G1"], None),
                    ("C1", "ask", ["G2"], None), ("D3", "ask", ["G3"], None),
                    ("E1", "ask", ["G4"], None)]
    assert worked == STEP_IDS and end.action == "done"
    assert all(d["by"] == "user" for d in state.load(run).decisions)
    assert checks_pass == [name for sid in STEP_IDS for name in TABLE[sid][3]]  # each, in order


def test_big_calls_asks_setup_card_after_b1_g2_alone_and_briefs_card_after_e1(tmp_path, checks_pass):
    run = _brief(tmp_path, "big_calls")
    seen, worked, nxt = _walk(run, until="B1")
    assert seen == [] and worked == ["A0", "A1"]   # G0 waits for the setup card
    assert (nxt.checkin.ids, nxt.checkin.card) == (["G0", "G1"], "approve_setup")
    complete(run, "B1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.name) == (
        "B1", "ask", ["G0", "G1"], "Approve the setup")
    seen, worked, nxt = _walk(run, until="E1")
    assert seen == [("B1", "ask", ["G0", "G1"], "approve_setup"), ("C1", "ask", ["G2"], None)]
    assert worked == ["B2", "B3", "B4", "C1", "D1", "D2", "D3"]   # G3 waits for the briefs card
    assert (nxt.checkin.ids, nxt.checkin.card) == (["G3", "G4"], "approve_briefs")
    complete(run, "E1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.name) == (
        "E1", "ask", ["G3", "G4"], "Approve the briefs")
    seen, worked, end = _walk(run)
    assert seen == [("E1", "ask", ["G3", "G4"], "approve_briefs")]
    assert worked == ["E2"] and end.action == "done"
    assert [(d["checkin"], d["choice"], d["by"]) for d in state.load(run).decisions] == [
        (cid, "accept", "user") for cid in ("G0", "G1", "G2", "G3", "G4")]


def test_hands_off_decides_all_by_rule(tmp_path, checks_pass):
    run = _brief(tmp_path, "hands_off")
    seen, worked, end = _walk(run)
    assert seen == [("A1", "auto", ["G0"], None), ("B1", "auto", ["G1"], None),
                    ("C1", "auto", ["G2"], None), ("D3", "auto", ["G3"], None),
                    ("E1", "auto", ["G4"], None)]
    assert worked == STEP_IDS and end.action == "done"
    cat = checkins.load(playbook=CREATIVE_BRIEF)
    decisions = state.load(run).decisions
    assert [(d["checkin"], d["by"]) for d in decisions] == [
        (cid, "rule") for cid in ("G0", "G1", "G2", "G3", "G4")]
    assert all(d["rule"] == cat.checkins[d["checkin"]].rule for d in decisions)


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_review_pack_only_run_skips_d1_to_e1(tmp_path, checks_pass, level):
    run = _brief(tmp_path, level, ["review_pack", "page"])
    seen, worked, end = _walk(run)
    assert worked == ["A0", "A1", "B1", "B2", "B3", "B4", "C1", "E2"]   # C1 -> G2 -> E2
    assert [ids for _, _, ids, _ in seen] == (
        [["G0", "G1"], ["G2"]] if level == "big_calls" else [["G0"], ["G1"], ["G2"]])
    assert seen[-1][0] == "C1" and end.action == "done"
    assert {d["checkin"] for d in state.load(run).decisions} == {"G0", "G1", "G2"}


# --- checks a step requires -------------------------------------------------------

def test_done_refused_until_required_check_passes(tmp_path, monkeypatch, capsys):
    gaps = ["x is checked"]
    fake = types.ModuleType("fake_brief_checks")
    fake.gap = lambda run: gaps[0]
    monkeypatch.setitem(sys.modules, "fake_brief_checks", fake)
    monkeypatch.setitem(stepchecks.NAMES, "intake_written", "fake_brief_checks:gap")
    run = _brief(tmp_path, "every_step")
    assert main(["done", "A0", "--run", str(run.path), "--json"]) == 0   # A0 requires nothing
    capsys.readouterr()
    assert main(["done", "A1", "--run", str(run.path), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "stop", "message": "A1 (Product and intake card) is done once x is "
                                                "checked; the run continues from the same place."}
    assert state.load(run).step == "A1"   # nothing moved
    with pytest.raises(stops.Stop):
        complete(run, "A1")
    gaps[0] = None
    assert main(["done", "A1", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["next_step"] == "B1"


def test_a_check_answering_no_words_gives_one_json_error(tmp_path, monkeypatch, capsys):
    fake = types.ModuleType("fake_brief_checks")
    fake.gap = lambda run: ""
    monkeypatch.setitem(sys.modules, "fake_brief_checks", fake)
    monkeypatch.setitem(stepchecks.NAMES, "intake_written", "fake_brief_checks:gap")
    run = _brief(tmp_path, "every_step")
    assert main(["done", "A0", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()
    assert main(["done", "A1", "--run", str(run.path), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)   # one object, no traceback
    assert out["status"] == "error" and out["message"].startswith("The step check intake_written answered ''")
    assert state.load(run).step == "A1"


def test_the_first_gap_of_several_stops_the_step(tmp_path, monkeypatch):
    run = _brief(tmp_path, "hands_off")
    asked = []

    def run_check(name, _run):
        asked.append(name)
        return {"concepts_checked": None, "page_built": "a page is built from the latest brief"}.get(name)
    monkeypatch.setattr(stepchecks, "run", run_check)
    _, worked, nxt = _walk(run, until="C1")
    assert worked == STEP_IDS[:STEP_IDS.index("C1")]
    asked.clear()
    with pytest.raises(stops.Stop, match="C1 .Concepts and the review pack. is done once a page is built"):
        complete(run, "C1")
    assert asked == ["concepts_checked", "page_built"] and state.load(run).step == "C1"


# --- guess mode: the evidence window B3 to C1 and the notice at G2 (Task 4) -------------------

CB_NOTICE = ("Without live trend data, the hooks in these concepts are my best guess from your "
             "customers' own words, your ads and the Ad Library, not proof from what is rising now. "
             "With TrendsMesh (the Agent plan) each concept rides a hook or topic that is rising "
             "right now.")
CB_NOTICE_SHORT = CB_NOTICE[:CB_NOTICE.index("rising now.") + len("rising now.")]


def test_brief_notice_is_the_plans_text():
    n = evidence.NOTICES[CREATIVE_BRIEF]
    assert (n.at, n.text, n.short) == (frozenset({"G2"}), CB_NOTICE, CB_NOTICE_SHORT)
    assert n.repeat_at_end is False and evidence.NOTICES[REFRESH_AD].repeat_at_end is True
    assert evidence.NOTICES[REFRESH_AD] == evidence.Notice(
        evidence.NOTICE_AT, evidence.NOTICE, evidence.NOTICE_SHORT)


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_guess_recorded_on_brief_run_and_notice_at_g2_only(tmp_path, checks_pass, capsys, level):
    run = _brief(tmp_path, level)
    assert main(["evidence", "guess", "--run", str(run.path), "--why", "no Agent plan", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "evidence": "guess"}
    s = state.load(run)
    assert s.evidence == "guess" and s.evidence_log[0]["why"] == "no Agent plan"
    notices = []
    seen, _, done = _walk(run, notices=notices)
    asked = [(step, ids) for step, action, ids in notices if action != "done"]
    # of all the check-ins, only G2 when it is shown to the user; never one decided by rule
    assert asked == ([] if level == "hands_off" else [("C1", ["G2"])])
    # once in all: at G2 when it is asked, else in the final report (Hands-off)
    assert done.action == "done"
    assert done.notice == (CB_NOTICE if level == "hands_off" else None)
    assert len(notices) == 1
    assert ("C1", "ask" if level != "hands_off" else "auto", ["G2"], None) in seen
    assert state.load(run).register is None


@pytest.mark.parametrize("first,then", [("hands_off", "every_step"), ("every_step", "hands_off")])
def test_notice_once_when_the_level_changes_after_g2(tmp_path, checks_pass, first, then):
    """What happened at G2 counts, not the level at the end: a run switched after G2 still hears
    the notice exactly once."""
    run = _brief(tmp_path, first)
    evidence.record(run, "guess", "no Agent plan")
    notices = []
    _walk(run, until="D1", notices=notices)          # G2 is decided (by rule in Hands-off)
    set_level(run, then)
    _, _, done = _walk(run, notices=notices)
    assert done.action == "done"
    assert len(notices) == 1
    assert notices[0][0] == ("E2" if first == "hands_off" else "C1")


def test_trendsmesh_brief_run_has_no_notice(tmp_path, checks_pass):
    run = _brief(tmp_path, "every_step")
    evidence.record(run, "trendsmesh", "Agent plan")
    notices = []
    _, _, done = _walk(run, notices=notices)
    assert done.action == "done" and notices == []


def test_evidence_refused_after_c1(tmp_path, checks_pass):
    run = _brief(tmp_path, "hands_off")
    evidence.record(run, "guess", "no Agent plan")
    _walk(run, until="B4")   # B3 is done: a switch to TrendsMesh needs the trends saved
    with pytest.raises(ValueError, match="Switching to TrendsMesh after B3 needs the trends saved"):
        evidence.record(run, "trendsmesh", "the user bought the plan")
    assert state.load(run).evidence == "guess"
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    evidence.record(run, "trendsmesh", "the user bought the plan")
    _walk(run, until="C1")   # C1 not done yet: still changeable
    evidence.record(run, "guess", "TrendsMesh stopped answering")
    _walk(run, until="D1")   # C1 is done: the concepts rest on what was recorded
    for value in ("trendsmesh", "guess"):
        with pytest.raises(ValueError) as no:
            evidence.record(run, value, "late change")
        assert str(no.value) == ("C1 (Concepts and the review pack) is done, so what this run "
                                 "rests on stays guess. For concepts on other evidence, start a new "
                                 "run (`tm run new --playbook creative-brief`); this run goes on "
                                 "from the same place.")
    s = state.load(run)
    assert s.evidence == "guess" and [e["evidence"] for e in s.evidence_log] == [
        "guess", "trendsmesh", "guess"]
    assert [e["at_step"] for e in s.evidence_log][1:] == ["B4", "C1"]


def test_evidence_refused_after_c1_in_a_review_pack_run(tmp_path, checks_pass):
    run = _brief(tmp_path, "hands_off", outputs=["review_pack"])
    _, worked, nxt = _walk(run, until="E2")
    assert "D1" not in worked and nxt.step == "E2"
    with pytest.raises(ValueError, match="^C1 .Concepts and the review pack. is done, so what this "
                                         "run rests on stays unrecorded. For concepts on other evidence"):
        evidence.record(run, "guess", "late")
