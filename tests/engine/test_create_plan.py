"""Create an ad (playbook 05), S1 to G3: the checks of the concepts, claims, script-board, production plan and
filled storyboard; the money they plan (the plan's yes, then the storyboard's); the paid guard (never an automatic
video redo)."""

import json
from datetime import date

import pytest

from tm import budget, create_config, create_plan, flow, state, stepchecks
from tm.flow import complete, decide
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder

from test_create_config import ANSWERS, INVENTORY

TODAY = date.today().isoformat()


def _write(run, rel, data):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _new(tmp_path, level="every_step", answers=None, inventory=INVENTORY, evidence="guess"):
    (tmp_path / "w").mkdir(exist_ok=True)
    run = RunFolder.create(tmp_path / "w", "planner", date(2026, 11, 11), playbook=CREATE_AD)
    create_config.write_from_intake(run, {**(answers or ANSWERS), "level": level})
    _write(run, "03_wip/assets_v01.json", inventory)
    _write(run, "02_research/prices_v01.json", {"saved": "a price answer"})
    if evidence:
        flow.set_evidence(run, evidence, "no Agent plan")
    return run


@pytest.fixture
def run(tmp_path):
    return _new(tmp_path)


def concepts(**over):
    base = {"model_ads": [{"id": "m1", "source": "guess", "why": "the selfie complaint opener"},
                          {"id": "m2", "source": "user", "why": "their own best ad"}],
            "trends": [{"id": "t1", "type": "hook", "source": "guess", "name": "the 'nobody told me' opener"},
                       {"id": "t2", "type": "sound", "source": "guess", "licence": "inspiration"}],
            "concepts": [{"key": "c1", "name": "Nobody told me", "model_ad": "m1", "trends": ["t1"],
                          "combine": "the opener on the brief tool", "beats": [{"t": "0-3", "picture": "creator"}],
                          "length_s": 18, "length_why": "Reels", "cost_usd": [2, 4]},
                         {"key": "c2", "name": "Before and after", "model_ad": "m2", "trends": ["t1", "t2"],
                          "combine": "a split screen", "beats": [{"t": "0-2", "picture": "split"}],
                          "length_s": 16, "length_why": "Stories", "cost_usd": [1, 3]}]}
    base.update(over)
    return base


CLAIMS = {"claims": [{"id": "k1", "text": "Writes a client brief in 3 minutes", "source": "site",
                      "ref": "https://planner.example.com/features"},
                     {"id": "k2", "text": "Made for freelance designers", "source": "user", "ref": "the intake"}]}


def board(**over):
    base = {"model_ad_wpm": 160, "scenes": [
        {"n": 1, "start": 0, "end": 3, "picture": "creator to camera", "on_screen_text": "Nobody told me this",
         "line": "Nobody told me briefs could take three minutes", "speaker": "presenter", "source": "generate",
         "claims": ["k1"]},
        {"n": 2, "start": 3, "end": 12, "picture": "the brief screen on the site", "line": "You answer five questions "
         "and it writes the brief", "speaker": "presenter", "source": "site", "claims": ["k1"]},
        {"n": 3, "start": 12, "end": 18, "picture": "logo sting", "source": "asset:00_raw/logo.svg"}]}
    base.update(over)
    return base


def plan(**over):
    line = {"checked": TODAY, "price_file": "02_research/prices_v01.json"}
    base = {"voice_route": "user_vo", "presenter": {"situation": "exact_wording"}, "lines": [
        {"item": "casting", "type": "still", "stage": "pre_video", "model": "gpt-image-2", "alternative": "flux",
         "cost": 0.4, "budget": "ai_usd", **line},
        {"item": "music", "type": "music", "stage": "pre_video", "model": "elevenlabs-music", "alternative": "user's",
         "seconds": 10, "cost": 900, "budget": "voice_credits", **line},
        {"item": "presenter_take", "type": "presenter", "stage": "video", "model": "gemini-omni",
         "alternative": "seedance-2.0", "cost": 1.5, "budget": "ai_usd", **line}]}
    base.update(over)
    return base


def storyboard(**over):
    base = {"frames": [{"scene": n, "file": f"03_wip/frame_{n}.png"} for n in (1, 2, 3)],
            "placeholder_render": "03_wip/edit_placeholder_v01.mp4",
            "videos": [{"item": "presenter_take", "model": "gemini-omni", "prompt": "a different, non-identifiable "
                        "person, handheld, natural light, says: ...", "prompt_rules": "references/model-prompting/x.md",
                        "cost": 1.5, "budget": "ai_usd", "checked": TODAY,
                        "price_file": "02_research/prices_v01.json"}]}
    base.update(over)
    return base


def _check(run, stem, data):
    path = _write(run, str(run.next_version("03_wip", stem, "json").relative_to(run.path)), data)
    return create_plan.check(run, stem, path)[1]


def _fields(problems):
    return {p.field for p in problems}


def _ready_for(run, stem):
    """Check everything before `stem`, in order."""
    for earlier, data in ((create_plan.CONCEPTS, concepts()), (create_plan.CLAIMS, CLAIMS),
                          (create_plan.BOARD, board()), (create_plan.PLAN, plan())):
        if earlier == stem:
            return
        assert _check(run, earlier, data) == []
    if stem == create_plan.STORYBOARD:
        for n in (1, 2, 3):
            _write(run, f"03_wip/frame_{n}.png", {})
        _write(run, "03_wip/edit_placeholder_v01.mp4", {})


# --- S1 to S4 --------------------------------------------------------------------

def test_concepts_need_the_evidence_recorded(tmp_path):
    run = _new(tmp_path, evidence=None)
    assert "evidence is recorded" in stepchecks.run("ad_concepts_checked", run)
    assert "evidence" in _fields(_check(run, "concepts", concepts()))


def test_good_concepts_pass_and_the_step_check_follows_the_latest(run):
    assert _check(run, "concepts", concepts()) == []
    assert stepchecks.run("ad_concepts_checked", run) is None
    _write(run, "03_wip/concepts_v02.json", concepts())   # a newer version, not checked
    assert "changed" in stepchecks.run("ad_concepts_checked", run) or "checked" in stepchecks.run(
        "ad_concepts_checked", run)


@pytest.mark.parametrize("over,field", [
    ({"concepts": concepts()["concepts"] * 2}, "concepts"),                                  # 2 to 3 on the page
    ({"trends": [{"id": "t1", "type": "hook", "source": "trendsmesh"}]}, "trends[1]"),       # a guess run has none
    ({"trends": [{"id": "t1", "type": "hook", "source": "guess"},
                 {"id": "t2", "type": "sound", "source": "guess"}]}, "trends[2]"),            # a sound needs a licence
    ({"model_ads": [{"id": "m1", "source": "ad_library", "why": "x"},
                    {"id": "m2", "source": "user", "why": "y"}]}, "model_ads[1]"),           # saved answer
])
def test_concepts_refused(run, over, field):
    assert field in _fields(_check(run, "concepts", concepts(**over)))


def test_a_concept_outside_the_chosen_length_is_refused(run):
    data = concepts()
    data["concepts"][0]["length_s"] = 44   # the model ad's length is not the ad's
    assert "concepts[1].length_s" in _fields(_check(run, "concepts", data))


def test_not_live_claims_say_how(tmp_path):
    answers = json.loads(json.dumps(ANSWERS))
    answers["intake"].update({"live": False, "not_live": "a waitlist"})
    run = _new(tmp_path, answers=answers)
    assert "not_live_said" in _fields(_check(run, "claims", CLAIMS))
    assert _check(run, "claims", {**CLAIMS, "not_live_said": "Join the waitlist"}) == []


def test_a_good_board_passes(run):
    _ready_for(run, "board")
    assert _check(run, "board", board()) == []
    assert stepchecks.run("ad_board_checked", run) is None


def test_the_board_holds_the_word_budget_and_one_take(run):
    _ready_for(run, "board")
    long = board()
    long["scenes"][1]["line"] = " ".join(["word"] * 60)
    problems = _check(run, "board", long)
    texts = " ".join(p.what for p in problems)
    assert "over the word budget" in texts and "one take carries all speech" in texts


@pytest.mark.parametrize("change,field", [
    (lambda b: b["scenes"][0].pop("on_screen_text"), "scenes[1].on_screen_text"),   # the hook's text, first second
    (lambda b: b["scenes"][1].update(claims=["k9"]), "scenes[2].claims"),            # only checked claims (CA3)
    (lambda b: b["scenes"][2].update(end=40), "scenes"),                             # the length is the user's
    (lambda b: b["scenes"][1].update(start=4), "scenes[2].start"),
])
def test_board_refused(run, change, field):
    _ready_for(run, "board")
    data = board()
    change(data)
    assert field in _fields(_check(run, "board", data))


# --- S5 the plan, G3 the storyboard, and the money ---------------------------------

def test_the_plan_plans_only_the_pre_video_money(run):
    _ready_for(run, "production_plan")
    assert _check(run, "production_plan", plan()) == []
    s = state.load(run)
    assert s.planned == {"ai_usd": 0.4, "voice_credits": 900.0} and s.planned_at


@pytest.mark.parametrize("change,field", [
    (lambda p: p["lines"][0].update(checked="2020-01-01"), "lines[1].checked"),     # a price with its recent date
    (lambda p: p["lines"][0].update(alternative="gpt-image-2"), "lines[1].alternative"),
    (lambda p: p.update(voice_route="native"), "voice_route"),                     # the user's VO fixes the route
    (lambda p: p["lines"].append({**p["lines"][0], "item": "vo", "type": "voice"}), "lines[4]"),  # replaced by VO
])
def test_plan_refused(run, change, field):
    _ready_for(run, "production_plan")
    data = plan()
    change(data)
    assert field in _fields(_check(run, "production_plan", data))


# --- issue #95: the talking person from CA5's table, one take per speaker -------------------------------------

def _take(item="presenter_take", model="google/gemini-omni-1.2-flash", **over):
    alternative = "google/gemini-omni-1.2-flash" if "h3" in model else "minimax/h3"
    return {"item": item, "type": "presenter", "stage": "video", "model": model, "alternative": alternative,
            "cost": 1.58, "budget": "ai_usd", "checked": TODAY, "price_file": "02_research/prices_v01.json", **over}


def _casting():
    return {**_take("casting", "openai/gpt-image-2", stage="pre_video", cost=0.38), "alternative": "flux"}


def _plan_with(*talking, **presenter):
    data = plan()
    data["lines"] = [*data["lines"][:2], *talking]
    data["presenter"] = presenter
    return data


@pytest.mark.parametrize("situation,model", [
    ("described", "bytedance/seedance-2.0"), ("specific_person", "minimax/h3"), ("own_voice", "minimax/h3"),
    ("exact_wording", "google/gemini-omni-1.2-flash"), ("exact_wording", "gemini-omni"),
])
def test_the_plan_takes_the_presenter_from_the_table(run, situation, model):
    _ready_for(run, "production_plan")
    assert _check(run, "production_plan", _plan_with(_take(model=model), situation=situation)) == []


def test_the_plan_names_the_situation_and_follows_its_row(run):
    _ready_for(run, "production_plan")
    problems = _check(run, "production_plan", _plan_with(_take()))
    assert _fields(problems) == {"presenter.situation"}
    assert "Ask the user which situation applies, before any casting" in problems[0].todo
    # the run's first plan: ElevenLabs with Kling Avatar for a specific person, where the table says MiniMax H3
    wrong = _take(model="kwaivgi/kling-avatar-v2")
    problems = _check(run, "production_plan", _plan_with(wrong, situation="specific_person"))
    assert _fields(problems) == {"presenter"} and "with h3" in problems[0].what
    # suggest, never impose: the user picked another model
    assert _check(run, "production_plan", _plan_with(wrong, situation="specific_person", user_choice=True)) == []
    # the fallback only with what the review showed
    assert _fields(_check(run, "production_plan", _plan_with(wrong, situation="fallback"))) == {"presenter.why"}
    assert _check(run, "production_plan", _plan_with(wrong, situation="fallback", why="the native voice is weak "
                                                     "and the mouth drifts in take 1")) == []


def test_seedance_gets_no_paid_casting(run):
    """Seedance refuses a photoreal face (E005): a casting still is money for a face the take cannot use."""
    _ready_for(run, "production_plan")
    seedance = _take(model="bytedance/seedance-2.0")
    problems = _check(run, "production_plan", _plan_with(_casting(), seedance, situation="described"))
    assert _fields(problems) == {"lines"}
    assert "cannot use a casting face" in problems[0].what and "casting" in problems[0].what
    assert "cast from a description" in problems[0].todo
    # also when the user picked Seedance for a specific person
    problems = _check(run, "production_plan", _plan_with(_casting(), seedance, situation="specific_person",
                                                         user_choice=True))
    assert _fields(problems) == {"lines"}
    # a casting is fine for a model that takes the face (Gemini as a reference, H3 reference mode)
    assert _check(run, "production_plan", _plan_with(_casting(), _take(), situation="exact_wording")) == []


def test_one_speaker_is_one_take_when_the_lines_fit(run):
    """The live run: one creator in a corner window and a whispered close-up, planned as two takes; the board's
    17 words fit one 15 s take, so the plan is refused."""
    _ready_for(run, "production_plan")
    two = (_take("creator_window"), _take("creator_closeup"))
    problems = _check(run, "production_plan", _plan_with(*two, situation="exact_wording"))
    assert _fields(problems) == {"lines"}
    assert "presenter's lines (17 words) fit one take" in problems[0].what
    assert "creator_window, creator_closeup" in problems[0].what and "hard cut" in problems[0].todo
    assert _check(run, "production_plan", _plan_with(two[0], situation="exact_wording")) == []


def test_each_speaker_has_one_take_of_their_own(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, "board")
    scenes = board()["scenes"]
    # two speakers, each with a take of their own; one of them with two takes is refused, as its lines fit one
    duo = board(scenes=[{**scenes[0], "speaker": "creator"}, {**scenes[1], "speaker": "friend"}, scenes[2]])
    assert _check(run, "board", duo) == []
    own = (_take("creator_take", speaker="creator"), _take("friend_take", speaker="friend"))
    assert _check(run, "production_plan", _plan_with(*own, situation="exact_wording")) == []
    extra = _take("creator_take_2", speaker="creator")
    problems = _check(run, "production_plan", _plan_with(*own, extra, situation="exact_wording"))
    assert _fields(problems) == {"lines"} and "creator's lines" in problems[0].what


def _walk_to(run, step):
    for _ in range(40):
        nxt = flow.next(run)
        if nxt.step == step and nxt.action in ("work", "stop"):
            return nxt
        if nxt.action == "work":
            complete(run, nxt.step)
        elif nxt.action == "ask":
            for cid in nxt.checkin.ids:
                choice = flow.checkins.load(playbook=CREATE_AD).checkins[cid].choices[0]
                decide(run, cid, choice, by="user", note=None)
        elif nxt.action == "auto":
            for cid in nxt.checkin.ids:
                choice = flow.checkins.load(playbook=CREATE_AD).checkins[cid].choices[0]
                decide(run, cid, choice, by="rule", note="the rule's data")
        else:
            return nxt
    raise AssertionError("never reached " + step)


def _checked_through(run, stem):
    _ready_for(run, stem)
    if stem == create_plan.STORYBOARD:
        assert _check(run, stem, storyboard()) == []


def test_the_plan_yes_approves_the_pre_video_money_and_the_storyboard_yes_the_video(run):
    _ready_for(run, "storyboard")
    nxt = _walk_to(run, "G1")
    assert nxt.action == "stop"                                 # the plan said yes; the budget is not approved yet
    assert "Confirm the production plan and its cost" in nxt.message and "pack" not in nxt.message
    budget.approve(run, "ai_usd", 0.4)
    assert _walk_to(run, "G1").action == "stop"                # now the credits
    budget.approve(run, "voice_credits", 900)
    assert _walk_to(run, "G3").action == "work"
    for n in (1, 2, 3):
        _write(run, f"03_wip/frame_{n}.png", {})
    _write(run, "03_wip/edit_placeholder_v01.mp4", {})
    s = state.load(run)   # the plan's yes came seconds before the storyboard (timestamps are whole seconds)
    for d in s.decisions:
        d["at"] = "2026-01-01T00:00:00+00:00"
    state.save(run, s)
    assert _check(run, "storyboard", storyboard()) == []
    assert state.load(run).planned == {"ai_usd": 1.9, "voice_credits": 900.0}
    with pytest.raises(ValueError, match="Approve the filled storyboard"):
        budget.approve(run, "ai_usd", 1.9)                      # the plan's yes is older than the re-plan
    complete(run, "G3")
    decide(run, "storyboard", "approve", by="user", note=None)
    budget.approve(run, "ai_usd", 1.9)
    assert state.load(run).budgets["ai_usd"] == 1.9


def test_hands_off_waits_when_the_plan_is_above_the_intake_budget(tmp_path):
    answers = json.loads(json.dumps(ANSWERS))
    answers["budget"] = {"generation_usd": 0.2}
    run = _new(tmp_path, level="hands_off", answers=answers)
    _ready_for(run, "storyboard")
    nxt = _walk_to(run, "G1")
    assert nxt.action == "stop"                                 # 0.4 planned, 0.2 approved: nothing generated


# --- the paid guard ----------------------------------------------------------------

def _args(name, cost):
    return ["spec.json", "--run", "R", "--name", name, "--cost", str(cost)]


def test_the_guard_runs_only_plan_lines_at_their_cost(run):
    _ready_for(run, "storyboard")
    assert create_plan.guard(run, _args("casting", 0.4)) is None
    assert "not a line" in create_plan.guard(run, _args("b_roll", 0.4))
    assert "is not casting's line" in create_plan.guard(run, _args("casting", 0.9))
    assert "runs only from the checked filled storyboard" in create_plan.guard(run, _args("presenter_take", 1.5))
    assert "not a Replicate call" in create_plan.guard(run, _args("music", 900))


def test_the_video_waits_for_the_storyboard_yes_and_is_never_redone_automatically(run):
    _ready_for(run, "storyboard")
    _write(run, "03_wip/frame_1.png", {})
    assert _check(run, "storyboard", storyboard()) == []
    assert "waits for the yes" in create_plan.guard(run, _args("presenter_take", 1.5))
    s = state.load(run)
    s.decisions.append({"checkin": "storyboard", "choice": "approve", "by": "user", "at": flow._now()})
    state.save(run, s)
    assert create_plan.guard(run, _args("presenter_take", 1.5)) is None
    _write(run, "03_wip/presenter-take_v01.run.json", {"status": "failed"})
    assert create_plan.guard(run, _args("presenter_take", 1.5)) is None   # a failed take cost nothing
    _write(run, "03_wip/presenter-take_v02.run.json", {"status": "done"})
    assert "never regenerated automatically" in create_plan.guard(run, _args("presenter_take", 1.5))
    with pytest.raises(ValueError, match="own words"):
        create_plan.redo(run, "presenter_take", " ")
    create_plan.redo(run, "presenter_take", "the second line stutters, make it again")
    assert create_plan.guard(run, _args("presenter_take", 1.5)) is None
    _write(run, "03_wip/presenter-take_v03.run.json", {"status": "done"})
    assert "never regenerated automatically" in create_plan.guard(run, _args("presenter_take", 1.5))


def test_the_guard_is_create_ads_precheck(run, monkeypatch):
    from tm import tools
    seen = []
    monkeypatch.setattr(create_plan, "guard", lambda r, a: seen.append(a) or "held")
    assert tools._precheck(run, "replicate_run", _args("casting", 0.4)) == "held" and seen


def test_tm_ad_check_on_the_command_line(run, capsys):
    from tm.cli import main
    bad = _write(run, "03_wip/concepts_v01.json", concepts(concepts=[]))
    assert main(["ad", "check", "concepts", "--run", str(run.path), "--file", str(bad), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and any(p["field"] == "concepts" for p in out["problems"])
    good = _write(run, "03_wip/concepts_v02.json", concepts())
    assert main(["ad", "check", "concepts", "--run", str(run.path), "--file", str(good), "--json"]) == 0
    capsys.readouterr()
    assert main(["ad", "check", "concepts", "--run", str(run.path), "--file", str(bad), "--json"]) == 1   # not latest
