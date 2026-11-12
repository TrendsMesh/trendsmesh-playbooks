"""Create an ad (playbook 05), G4 and S7: the takes' QA and their acceptance (CA8, CA11), and the edit's QA before
every showing (CA11). The measures come from `tm tool take_qa`, organic video's take QA; here its files are written
by hand."""

import json
import os
import time

import pytest

from tm import create_plan, create_qa, flow, i18n, state, stepchecks
from tm.flow import decide

from test_create_plan import _check, _new, _ready_for, _write, storyboard

TAKE = "03_wip/presenter-take_v01_0.mp4"
LINES = "Nobody told me briefs could take three minutes You answer five questions and it writes the brief"


def _words(text, start=0.0, step=0.3):
    out = []
    for n, w in enumerate(text.split()):
        out.append({"word": " " + w, "start": round(start + n * step, 2), "end": round(start + n * step + 0.25, 2)})
    return out


def _qa(run, take=TAKE, *, words=None, match=0.98, lufs=-16.0, peak=-2.0, cuts=(), version=1, transcript=True):
    stem = take.rsplit("/", 1)[1].rsplit(".", 1)[0]
    folder = take.rsplit("/", 1)[0] + "/qa"
    tr = None
    if transcript:
        tr = f"{folder}/{stem}_transcript_v{version:02d}.json"
        _write(run, tr, {"segments": [{"words": _words(LINES) if words is None else words}]})
    qa = {"take": take, "transcript": tr, "match": match if transcript else None, "words": 18,
          "speech_seconds": 5.3, "wps": 3.2, "tail_silence": 0.5, "cuts": list(cuts), "cut_offsets": [],
          "lufs": lufs, "peak": peak, "contact_sheet": f"{folder}/{stem}_contact_v{version:02d}.png"}
    return _write(run, f"{folder}/{stem}_qa_v{version:02d}.json", qa)


def _take(run, version=1, status="done"):
    out = [f"presenter-take_v{version:02d}_0.mp4"] if status == "done" else []
    _write(run, f"03_wip/presenter-take_v{version:02d}.run.json", {"status": status, "outputs": out})
    if out:
        (run.path / "03_wip" / out[0]).write_bytes(b"video")


@pytest.fixture
def run(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)
    videos = storyboard()["videos"]
    videos[0]["speaks"] = True     # the plan's route is the user's VO; this take still says the lines
    assert _check(run, create_plan.STORYBOARD, storyboard(videos=videos)) == []
    return run


def _at_takes(run):
    """Put the run at the takes check-in (every step before it done; the checks are this file's subject)."""
    s = state.load(run)
    s.step = "S6"
    state.save(run, s)


# --- G4: each take has its QA -------------------------------------------------------

def test_each_take_needs_its_qa_before_g4_is_done(run):
    assert "has no take yet" in stepchecks.run("ad_takes_checked", run)
    _take(run)
    assert "take QA" in stepchecks.run("ad_takes_checked", run)
    _qa(run, transcript=False)
    gap = stepchecks.run("ad_takes_checked", run)
    assert "carries the spoken lines" in gap and "--script" in gap
    _qa(run, version=2)
    assert stepchecks.run("ad_takes_checked", run) is None


def test_a_failed_take_leaves_the_earlier_take_as_the_one_to_qa(run):
    _take(run)
    _qa(run)
    _take(run, version=2, status="failed")         # cost nothing, made nothing
    assert stepchecks.run("ad_takes_checked", run) is None


def test_a_take_that_does_not_speak_needs_no_transcript(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)
    assert _check(run, create_plan.STORYBOARD, storyboard()) == []   # the user's VO: the take is silent
    _take(run)
    _qa(run, transcript=False, lufs=None, peak=None)
    assert stepchecks.run("ad_takes_checked", run) is None
    assert stepchecks.run("ad_takes_accepted", run) is None


def test_an_ad_without_video_has_no_takes(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)
    assert _check(run, create_plan.STORYBOARD, storyboard(videos=[], no_video_reason="slides")) == []
    assert stepchecks.run("ad_takes_checked", run) is None
    assert stepchecks.run("ad_takes_accepted", run) is None


def test_speaks_must_be_true_or_false(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)
    videos = storyboard()["videos"]
    videos[0]["speaks"] = "yes"
    assert "videos[1].speaks" in {p.field for p in _check(run, create_plan.STORYBOARD, storyboard(videos=videos))}


# --- the takes' rubric -----------------------------------------------------------------

def test_a_repeated_word_the_script_says_once_fails(run):
    _take(run)
    heard = _words("Nobody told me me briefs could take three minutes")
    _qa(run, words=heard)
    row, = create_qa.take_rows(run)
    assert any("twice in a row" in f and "“me”" in f for f in row["fails"])
    # the script itself saying a word twice is no stutter
    assert create_qa.repeats(heard, "told me me briefs") == []


def test_a_word_twice_its_expected_length_is_a_possible_hidden_repeat(run):
    _take(run)
    heard = _words(LINES)
    heard[4] = {**heard[4], "end": heard[4]["start"] + 2.0}   # "could" lasts 2 s
    _qa(run, words=heard)
    row, = create_qa.take_rows(run)
    assert not row["fails"]
    assert any("possible hidden repeat" in f and "“could”" in f for f in row["findings"])


def test_internal_cuts_are_a_finding_and_a_low_transcript_a_fail(run):
    _take(run)
    _qa(run, match=0.6, cuts=[4.2])
    row, = create_qa.take_rows(run)
    assert any("transcript matches 60%" in f for f in row["fails"])
    assert any("internal cut" in f and "4.2" in f for f in row["findings"])
    assert row["contact_sheet"].endswith("_contact_v01.png") and row["transcript"]


def test_the_rows_speak_the_pages_language(run):
    _take(run)
    _qa(run, words=_words("Nobody told me me briefs"))
    tr = i18n.translator(i18n.ENGLISH)
    assert create_qa.take_rows(run, tr)[0]["fails"] == create_qa.take_rows(run)[0]["fails"]


# --- accepting the takes (the takes check-in) ------------------------------------------

def test_accept_needs_every_take_to_pass_or_the_users_word_after_its_qa(run):
    _take(run)
    _qa(run, words=_words("Nobody told me me briefs could take three minutes"))
    gap = stepchecks.run("ad_takes_accepted", run)
    assert "fails its QA" in gap and "fails_qa" in gap
    _at_takes(run)
    s = state.load(run)
    s.decisions.append({"checkin": "takes", "choice": "fails_qa", "by": "user", "at": flow._now()})
    state.save(run, s)
    assert stepchecks.run("ad_takes_accepted", run) is None
    # a new QA of the take after the user saw it: their word was on the older QA
    path = _qa(run, version=2, words=_words("Nobody told me me briefs"))
    os.utime(path, (time.time() + 5, time.time() + 5))
    assert "fails its QA" in stepchecks.run("ad_takes_accepted", run)


def test_the_takes_check_in_refuses_accept_while_a_take_fails(run):
    _take(run)
    _qa(run, match=0.5)
    s = state.load(run)
    s.step = "S6"
    s.level = "every_step"
    state.save(run, s)
    with pytest.raises(ValueError, match="fails its QA"):
        decide(run, "takes", "accept", by="user", note=None)
    _qa(run, version=2)
    decide(run, "takes", "accept", by="user", note=None)
    assert state.load(run).decisions[-1]["choice"] == "accept"


# --- S7: the edit's QA ------------------------------------------------------------------

EDIT = "03_wip/edit_v01.mp4"


def _edit_qa(run, *, edit=EDIT, qa="03_wip/qa/edit_v01_qa_v01.json", checked=None, **over):
    data = {"edit": edit, "qa": qa, "checked": checked if checked is not None else [
        {"check": k, "result": "ok", "note": f"looked at {k}"} for k in create_qa.EDIT_CHECKS]}
    data.update(over)
    return _check(run, create_qa.EDIT_QA, data)


def _edit(run, version=1):
    rel = f"03_wip/edit_v{version:02d}.mp4"
    (run.path / rel).write_bytes(b"edit")
    return rel


def test_a_green_edit_qa_passes_s7(run):
    assert "edit" in stepchecks.run("ad_edit_checked", run)
    _edit(run)
    _qa(run, EDIT, lufs=-14.2, peak=-1.8)
    assert _edit_qa(run) == []
    assert stepchecks.run("ad_edit_checked", run) is None
    report = create_qa.edit_report(run)
    assert report["edit"] == EDIT and report["lufs"] == -14.2 and len(report["checked"]) == len(create_qa.EDIT_CHECKS)
    assert all(r["label"] and r["result_label"] for r in report["checked"])
    # a new version of the edit needs its own QA
    _edit(run, 2)
    assert "edit_v02.mp4" in stepchecks.run("ad_edit_checked", run)


@pytest.mark.parametrize("qa,fragment", [
    ({"lufs": -18.0}, "-18.0 LUFS"),
    ({"peak": -0.5}, "true peak"),
    ({"lufs": None, "peak": None}, "no measurable sound"),
    ({"match": 0.5}, "transcript"),
    ({"transcript": False}, "no transcript"),
    ({"words": _words("Nobody told me me briefs")}, "twice in a row"),
])
def test_the_edit_qa_refuses_what_ca11_does_not_allow(run, qa, fragment):
    _edit(run)
    _qa(run, EDIT, **{"lufs": -14.0, "peak": -2.0, **qa})
    problems = _edit_qa(run)
    assert any(fragment in p.what for p in problems), [p.what for p in problems]


def test_every_ca11_check_is_written_and_a_problem_sends_it_back_to_the_edit(run):
    _edit(run)
    _qa(run, EDIT, lufs=-14.0)
    short = [{"check": "cuts", "result": "ok", "note": "every cut"}]
    assert any("captions" in p.what for p in _edit_qa(run, checked=short))
    bad = [{"check": k, "result": "problem" if k == "captions" else "ok", "note": "the caption hits the card at 6 s"
            if k == "captions" else "fine"} for k in create_qa.EDIT_CHECKS]
    assert any("new version" in p.todo for p in _edit_qa(run, checked=bad))
    no_note = [{"check": k, "result": "not_applicable"} for k in create_qa.EDIT_CHECKS]
    assert _edit_qa(run, checked=no_note)
    assert "edit" in {p.field for p in _edit_qa(run, edit="03_wip/edit_placeholder_v01.mp4")}


def test_the_review_accept_needs_the_latest_edit_qa(run):
    s = state.load(run)
    s.step = "S8"
    s.level = "every_step"
    state.save(run, s)
    with pytest.raises(ValueError, match="edit"):
        decide(run, "review", "accept", by="user", note=None)
    _edit(run)
    _qa(run, EDIT, lufs=-14.0)
    assert _edit_qa(run) == []
    decide(run, "review", "accept", by="user", note=None)


def test_tm_ad_check_edit_on_the_command_line(run, capsys):
    from tm.cli import main
    _edit(run)
    _qa(run, EDIT, lufs=-14.0)
    path = run.next_version("03_wip", create_qa.EDIT_QA, "json")
    path.write_text(json.dumps({"edit": EDIT, "qa": "03_wip/qa/edit_v01_qa_v01.json", "checked": [
        {"check": k, "result": "ok", "note": "fine"} for k in create_qa.EDIT_CHECKS]}), encoding="utf-8")
    assert main(["ad", "check", "edit", "--run", str(run.path), "--file", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
