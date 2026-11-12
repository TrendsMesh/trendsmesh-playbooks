"""Create an ad's run pages (issue #17, on the shared run page of #19): one test per page builder, each built from
made-up run files, and the choices saved on a page (a pick, a choice per item, notes, pinned notes, edited copy)
read back by `tm page decision` and recorded as an answer from chat."""

import json
import re

import pytest

from tm import budget, checkins, create_copy, create_upload, flow, i18n, manifest, run_page, state, stepchecks
from tm.cli import main
from tm.playbooks import CREATE_AD
from tm.run_page import create_ad, detail, template, words
from tm.stops import Stop

from test_create_copy import KEY, _choices, ad
from test_create_plan import CLAIMS, _check, _new, _write, board, concepts, plan, storyboard
from test_create_qa import _edit_qa, _qa as _take_qa
from test_create_upload import _propose, proposal
from test_run_page import _artifact_list, _publish, _read

SRC = create_ad.__file__


def _ask(run, checkin, options=None, n=1):
    cat = checkins.load(playbook=CREATE_AD)
    choices = cat.checkins[checkin].choices if checkin in cat.checkins else ["accept"]
    body = {"checkin": checkin, "title": f"{checkin}: what is new", "question": "Shall we go on?",
            "options": options or [{"choice": c, "label": c.capitalize()} for c in choices]}
    path = run.path / "03_wip" / f"my_ask_{checkin}_{n}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _html(run, built) -> str:
    return (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")


def _now(html) -> str:
    m = re.search(r'<section class="panel now".*?<section class="decision"', html, re.S)
    return m.group(0) if m else ""


def _built(run, built) -> dict:
    return json.loads((run.path / built["folder"] / run_page.BUILD_FILE).read_text(encoding="utf-8"))


def _media(run, rel, data=b"x"):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def _checked_values(html) -> dict[str, list[str]]:
    """The radios selected in advance, by the first key of their detail path."""
    out: dict[str, list[str]] = {}
    for tag in re.findall(r'<input type="radio"[^>]*\bchecked\b[^>]*>', html):
        path = json.loads(re.search(r'data-detail="([^"]+)"', tag).group(1).replace("&quot;", '"'))
        out.setdefault(path[0], []).append(re.search(r'value="([^"]*)"', tag).group(1))
    return out


def _paths(html) -> set[str]:
    return {json.loads(p.replace("&quot;", '"'))[0] for p in re.findall(r'data-detail="([^"]+)"', html)}


@pytest.fixture
def run(tmp_path):
    return _new(tmp_path)


def _checked_through(run, last):
    """Check the run's files in order up to `last` (concepts, claims, board, plan, storyboard)."""
    order = [("concepts", concepts(model_ads=[
        {"id": "m1", "name": "The selfie complaint", "source": "guess", "why": "the selfie complaint opener",
         "clip": _media(run, "02_research/clips/m1_15s.mp4"), "run_days": 41},
        {"id": "m2", "source": "user", "why": "their own best ad"}],
        trends=[{"id": "t1", "type": "hook", "source": "guess", "name": "the 'nobody told me' opener",
                 "thumbs": [_media(run, "02_research/thumbs/t1_a.jpg")]},
                {"id": "t2", "type": "sound", "source": "guess", "licence": "inspiration"}])),
             ("claims", CLAIMS), ("board", board()), ("production_plan", plan())]
    for stem, data in order:
        assert _check(run, stem, data) == [], stem
        if stem == last:
            return
    for n in (1, 2, 3):
        _media(run, f"03_wip/frame_{n}.png")
    _media(run, "03_wip/edit_placeholder_v01.mp4")
    assert _check(run, "storyboard", storyboard()) == []


# --- one test per page ------------------------------------------------------------------------------

def test_the_concepts_page_shows_model_ads_trends_and_concepts_with_a_pick(run):
    _checked_through(run, "concepts")
    built = run_page.build(run, _ask(run, "concept"))
    html = _html(run, built)
    now = _now(html)
    assert built["open"] == ["concept"] and built["title"] == "Create an ad: 2026-11-11_planner"
    assert "Model ads" in now and "The selfie complaint" in now and "What to take from it: the selfie complaint opener" in now
    assert "Running for 41 days" in now and "assets/media/01_m1_15s.mp4" in now      # the model ad's clip
    assert "the &#x27;nobody told me&#x27; opener" in now and "My guess, not TrendsMesh data" in now
    assert "assets/media/02_t1_a.jpg" in now and "Inspiration only" in now
    assert "Nobody told me" in now and "Before and after" in now and "18 s" in now and "2–4 USD" in now
    assert "Why this length: Reels" in now and "How it combines them: the opener on the brief tool" in now
    assert "Pick this concept" in now and _paths(now) == {"concept"}
    assert _built(run, built)["offer"]["concept"] == {"concept": {"type": "pick", "values": ["c1", "c2"], "default": "c1"}}
    assert _checked_values(now) == {"concept": ["c1"]}               # the recommended (first) concept, in advance
    assert (run.path / built["folder"] / "assets/media/01_m1_15s.mp4").is_file()


def test_the_script_board_page_shows_each_scene_and_takes_a_note_per_scene(run):
    _checked_through(run, "board")
    built = run_page.build(run, _ask(run, "board"))
    now = _now(_html(run, built))
    assert "The script-board" in now and "0–3 s" in now and "Nobody told me this" in now
    assert "the brief screen on the site" in now and "from the site" in now and "your file: logo.svg" in now
    assert "Words spoken" in now and _paths(now) == {"scene_notes"}
    assert _built(run, built)["offer"]["board"]["scene_notes"]["keys"] == ["1", "2", "3"]


def test_the_plan_page_shows_models_prices_dates_own_files_and_totals(run):
    _checked_through(run, "production_plan")
    built = run_page.build(run, _ask(run, "plan"))
    html = _html(run, built)
    now = _now(html)
    assert "gpt-image-2" in now and "flux" in now and "elevenlabs-music" in now and "ElevenLabs credits" in now
    assert "before the video" in now and "priced again on the storyboard" in now
    assert "Before the video (USD)" in now and "The video, estimated (USD)" in now and "your voice-over recording" in now
    assert "Source: 03_wip/production_plan_v01.json" in now
    assert "What your own files replace" in now
    assert _paths(now) == {"line_notes"}


def test_board_and_plan_on_one_card_at_just_the_big_calls(tmp_path):
    run = _new(tmp_path, level="big_calls")
    _checked_through(run, "production_plan")
    built = run_page.build(run, _ask(run, "board_and_plan", options=[{"choice": "accept", "label": "Go"}]))
    now = _now(_html(run, built))
    assert "Script-board and plan" in now and "Nobody told me this" in now and "gpt-image-2" in now
    assert set(_built(run, built)["offer"]["board_and_plan"]) == {"scene_notes", "line_notes"}


@pytest.mark.parametrize("checkin,files,shown", [
    ("visual", ["03_wip/casting_v01_0.png", "03_wip/casting_v01_1.png"], ["Casting, option 1", "Casting, option 2"]),
    ("audio", ["03_wip/audio/music_v01.mp3"], ["Music", "900 ElevenLabs credits"]),
])
def test_the_visual_and_audio_gates_show_the_batch_raw_with_a_choice_each(run, checkin, files, shown):
    _checked_through(run, "production_plan")
    for f in files:
        _media(run, f)
    if checkin == "visual":                                           # the outputs of the item's latest Replicate run
        _write(run, "03_wip/casting_v01.run.json", {"status": "done", "outputs": [f.rsplit("/", 1)[1] for f in files]})
    _media(run, "03_wip/unrelated_v01_1.png")                         # not an item of this gate
    built = run_page.build(run, _ask(run, checkin))
    now = _now(_html(run, built))
    for text in shown:
        assert text in now
    assert "unrelated" not in now and "Accept" in now and "Redo" in now and "Drop" in now
    offer = _built(run, built)["offer"][checkin]["items"]
    assert offer["keys"] == [f.rsplit("/", 1)[1].rsplit(".", 1)[0] for f in files]
    assert offer["defaults"] == {k: "accept" for k in offer["keys"]}             # no item left empty (issue #97)
    assert _checked_values(now) == {"items": ["accept"] * len(files)}


def test_the_takes_gate_shows_each_take_with_its_transcript_qa_and_what_fails(run):
    _checked_through(run, "storyboard")
    videos = storyboard()["videos"]
    videos[0]["speaks"] = True                                         # this take says the board's lines
    assert _check(run, "storyboard", storyboard(videos=videos)) == []
    take = "03_wip/presenter-take_v01_0.mp4"                          # replicate_run's name for presenter_take
    _write(run, "03_wip/presenter-take_v01.run.json", {"status": "done", "outputs": ["presenter-take_v01_0.mp4"]})
    _media(run, take)
    words = [{"word": " " + w, "start": n * 0.3, "end": n * 0.3 + 0.25}
             for n, w in enumerate("Nobody told told me briefs could take three minutes".split())]
    _take_qa(run, take, words=words, lufs=-14.2, peak=-1.8)
    _media(run, "03_wip/qa/presenter-take_v01_0_contact_v01.png")
    built = run_page.build(run, _ask(run, "takes"))
    now = _now(_html(run, built))
    assert "Fails QA" in now and "the word “told” is heard twice in a row" in now        # create_qa's words
    assert "Transcript matches the script" in now and "Loudness (LUFS)" in now and "Cuts found" in now
    assert "presenter-take_v01_0_contact_v01.png" in now and "gemini-omni" in now
    assert _built(run, built)["offer"]["takes"]["items"]["keys"] == ["presenter-take_v01_0"]
    assert _built(run, built)["offer"]["takes"]["items"]["defaults"] == {"presenter-take_v01_0": "redo"}   # it fails QA
    assert _checked_values(now) == {"items": ["redo"]}


def test_the_storyboard_page_shows_one_scene_at_a_time_with_the_exact_prompt_and_price(run):
    _checked_through(run, "storyboard")
    built = run_page.build(run, _ask(run, "storyboard"))
    now = _now(_html(run, built))
    assert now.count('class="scene"') == 3 and now.count(" hidden") >= 2       # one scene shown, the others hidden
    assert "← Previous" in now and "Next →" in now and 'class="pg-n on"' in now and "arrow keys" in now
    assert "Nobody told me this" in now and "_frame_1.png" in now and "The placeholder render" in now
    assert "a different, non-identifiable person, handheld, natural light, says: ..." in now      # the exact prompt
    assert "1.50 USD, price checked" in now and "Prompt rules: references/model-prompting/x.md" in now
    assert _paths(now) == {"scene_notes"}
    assert "ArrowLeft" in template.SCRIPT and "pg.step" in template.SCRIPT


def test_the_review_page_shows_up_to_four_versions_with_a_pick_and_pinned_notes(run):
    for n in range(1, 6):
        _media(run, f"03_wip/edit_v{n:02d}.mp4")
    _take_qa(run, "03_wip/edit_v05.mp4", lufs=-14.2, peak=-1.8)
    assert _edit_qa(run, edit="03_wip/edit_v05.mp4", qa="03_wip/qa/edit_v05_qa_v01.json") == []
    built = run_page.build(run, _ask(run, "review"))
    now = _now(_html(run, built))
    assert "Version 1" not in now and all(f"Version {n}" in now for n in (2, 3, 4, 5))
    assert 'style="--n:4"' in now and "Pin to {version} at {time}" in now and "Your notes" in now
    assert "What was checked: Version 5" in now and "True peak (dBFS)" in now       # create_qa.edit_report
    assert "Motion at every cut" in now and "looked at cuts" in now and "Source: 03_wip/edit_qa_v01.json" in now
    assert _paths(now) == {"version", "pins"}
    offer = _built(run, built)["offer"]["review"]
    assert offer["pins"]["versions"] == ["edit_v02", "edit_v03", "edit_v04", "edit_v05"]
    assert offer["version"]["default"] == "edit_v05" and _checked_values(now) == {"version": ["edit_v05"]}


def test_the_copy_page_shows_every_text_editable_with_its_live_count_and_keep_tick(run):
    assert _check(run, "claims", CLAIMS) == []
    _write(run, "03_wip/copy_v01.json", {"ads": [ad()]})
    assert create_copy.check(run, "03_wip/copy_v01.json")[1] == []
    built = run_page.build(run, _ask(run, "copy"))
    now = _now(_html(run, built))
    assert "Planner brief tool, freelancers, nobody told me" in now and "LEARN_MORE" in now and "planner.example.com" in now
    assert now.count('class="copy-text"') == 15 and 'data-limit="125"' in now and 'data-limit="40"' in now
    assert "33 of 125 characters" in now and "Keep" in now                       # "Write a client brief in 3 minutes"
    assert _built(run, built)["offer"]["copy"]["copy"]["ads"] == {KEY: {"primary_texts": 5, "headlines": 5,
                                                                      "descriptions": 5}}
    local = _html(run, run_page.build(run, local=True))
    assert 'class="copy-text"' not in local and "33 of 125 characters" in local    # read-only without saving


def _uploaded(run):
    assert _check(run, "claims", CLAIMS) == []
    _write(run, "03_wip/copy_v01.json", {"ads": [ad()]})
    assert create_copy.check(run, "03_wip/copy_v01.json")[1] == []
    assert create_copy.accept(run, _choices(run, keep_primary=(1, 2, 3)))[1] == []
    for rel in (f"04_final/{KEY}_v01.mp4", f"04_final/{KEY}_thumb_v01.jpg"):
        _media(run, rel)
        manifest.record(run, rel, "04_final", "the edit")
    for rel in ("02_research/meta_pages_v01.json", "02_research/meta_pixel_v01.json", "05_results/answers_v01.json"):
        _write(run, rel, {"saved": "an MCP answer"})


def test_the_upload_pages_show_the_paused_proposal_and_take_only_go_ahead_or_skip(run):
    _uploaded(run)
    offer = _now(_html(run, run_page.build(run, _ask(run, "upload_offer"))))
    assert "nothing runs and nothing is spent" in offer and f"{KEY}_thumb_v01.jpg" in offer
    s = state.load(run)                                   # the offer is decided before the proposal is written
    s.decisions.append({"checkin": "upload_offer", "choice": "propose", "by": "user", "at": "2999-01-01T00:00:00+00:00"})
    state.save(run, s)
    assert _propose(run, proposal()) == []
    built = run_page.build(run, _ask(run, "upload"))
    now = _now(_html(run, built))
    for text in ("act_0000", "page_a", "Planner brief tool launch, sign-ups", "OUTCOME_LEADS", "COMPLETE_REGISTRATION",
                 "20 USD a day", "(you said: 20 a day)", "PL", "advantage_plus", "media made or edited with generative AI",
                 "PAUSED", "Video ads show no description", "Write a client brief in 3 minutes"):
        assert text in now, text
    assert _paths(now) == set() and "upload" not in _built(run, built)["offer"]   # nothing to save but go ahead or skip
    assert "ads_activate" not in now and "ACTIVE" not in now


# --- the choice saved on the page, read back ---------------------------------------------------------

def _to(run, checkin):
    """Walk the flow (every step check passing) up to `checkin`'s ask."""
    real = stepchecks.run
    stepchecks.run = lambda name, folder: None if name.startswith("ad_") else real(name, folder)
    try:
        for _ in range(60):
            nxt = flow.next(run)
            if nxt.action == "work":
                flow.complete(run, nxt.step)
            elif nxt.action in ("ask", "auto") and checkin in nxt.checkin.ids:
                return
            elif nxt.action in ("ask", "auto"):
                for cid in nxt.checkin.ids:
                    choice = checkins.load(playbook=CREATE_AD).checkins[cid].choices[0]
                    flow.decide(run, cid, choice, by="user", note=None)
            elif nxt.action == "stop" and state.load(run).planned:     # the plan's yes is given: approve its amounts
                for kind, amount in state.load(run).planned.items():
                    try:
                        budget.approve(run, kind, amount)
                    except flow.Held:                          # the stop is about the other kind first
                        continue
            else:
                raise AssertionError(nxt)
    finally:
        stepchecks.run = real
    raise AssertionError("never reached " + checkin)


def _doc(checkin, ask, choice, note="", **detail_):
    return {"id": checkin, "data": {"checkin": checkin, "ask": ask, "choice": choice, "label": "x", "note": note,
                                    "detail": detail_, "saved_at": "2026-11-11T14:23:00Z"}}


def test_a_concept_picked_on_the_page_is_read_back_and_recorded_with_its_name(run, capsys):
    _checked_through(run, "concepts")
    _to(run, "concept")
    run_page.build(run, _ask(run, "concept"))
    _publish(run)
    _read(run, _doc("concept", "concept_v01", "accept", note="mix in the split screen", concept="c2"))
    got = run_page.decision(run, "concept")
    assert got["detail"] == {"concept": "c2"} and got["note"] == "mix in the split screen"
    assert main(["page", "decision", "concept", "--run", str(run.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["recorded_note"] == "mix in the split screen\nConcept: Before and after (from the page)"
    last = state.load(run).decisions[-1]
    assert (last["checkin"], last["choice"], last["by"]) == ("concept", "accept", "user")
    answer = json.loads((run.path / out["files"]["answer"]).read_text(encoding="utf-8"))
    assert answer["detail"] == {"concept": "c2"} and answer["ask"] == "concept_v01"
    html = _html(run, run_page.build(run))                    # settled: a read-only summary, no inputs left
    assert 'data-detail="' not in html and "Concept: Before and after" in html


def test_items_left_as_selected_in_advance_are_recorded_with_their_recommended_choice(run, capsys):
    """Issue #97: the takes' halves came back with no verdict. What the page selected in advance and the user did not
    change is the recorded choice for that item."""
    _checked_through(run, "production_plan")
    _to(run, "visual")
    for n in (0, 1):
        _media(run, f"03_wip/casting_v01_{n}.png")
    _write(run, "03_wip/casting_v01.run.json", {"status": "done", "outputs": ["casting_v01_0.png", "casting_v01_1.png"]})
    run_page.build(run, _ask(run, "visual"))
    _publish(run)
    _read(run, _doc("visual", "visual_v01", "accept", items={"casting_v01_1": "drop"}))     # one changed, one left
    got = run_page.decision(run, "visual")
    assert got["detail"] == {"items": {"casting_v01_0": "accept", "casting_v01_1": "drop"}}
    assert main(["page", "decision", "visual", "--run", str(run.path), "--record", "--json"]) == 0
    note = json.loads(capsys.readouterr().out)["recorded_note"]
    assert "casting_v01_0: Accept" in note and "casting_v01_1: Drop" in note


def test_what_the_page_did_not_offer_is_refused(run):
    _checked_through(run, "concepts")
    _to(run, "concept")
    run_page.build(run, _ask(run, "concept"))
    _publish(run)
    _read(run, _doc("concept", "concept_v01", "accept", concept="c9"))
    with pytest.raises(Stop, match="did not offer"):
        run_page.decision(run, "concept")
    _read(run, _doc("concept", "concept_v01", "accept", items={"x": "redo"}), at="2999-01-02T00:00:00+00:00")
    with pytest.raises(Stop, match="did not offer"):
        run_page.decision(run, "concept")


def test_the_copy_edited_on_the_page_becomes_the_choices_tm_ad_copy_accept_takes(run, capsys):
    _checked_through(run, "production_plan")
    _to(run, "copy")
    _write(run, "03_wip/copy_v01.json", {"ads": [ad()]})
    assert create_copy.check(run, "03_wip/copy_v01.json")[1] == []
    run_page.build(run, _ask(run, "copy"))
    _publish(run)
    edits = {KEY: {"primary_texts": {"1": {"text": "Client briefs in 3 minutes", "keep": True},
                                     "2": {"text": "Client briefs in 3 minutes flat", "keep": False}},
                   "headlines": {str(n): {"text": ad()["headlines"][n - 1]["text"], "keep": n == 1} for n in range(1, 6)}}}
    _read(run, _doc("copy", "copy_v01", "accept", copy=edits))
    assert main(["page", "decision", "copy", "--run", str(run.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "1 edited, 5 dropped" in out["recorded_note"] and "tm ad copy accept" in out["message"]
    rel = out["files"]["copy_decisions"]
    assert rel == "03_wip/copy_decisions_v01.json"
    path, problems = create_copy.accept(run, rel)
    assert problems == []
    kept = create_copy.accepted(run)["ads"][0]
    assert [t["text"] for t in kept["primary_texts"]][0] == "Client briefs in 3 minutes"
    assert len(kept["primary_texts"]) == 4 and len(kept["headlines"]) == 1 and len(kept["descriptions"]) == 5


def test_review_notes_pinned_at_a_time_and_gate_choices_go_into_the_note(run, capsys):
    for n in (1, 2):
        _media(run, f"03_wip/edit_v{n:02d}.mp4")
    _to(run, "review")
    run_page.build(run, _ask(run, "review"))
    _publish(run)
    pins = [{"version": "edit_v02", "t": 3.24, "text": "the logo comes in late"},
            {"version": "edit_v01", "t": 61.0, "text": "keep this ending"}]
    _read(run, _doc("review", "review_v01", "fix", version="edit_v02", pins=pins))
    got = run_page.decision(run, "review")
    assert [p["version"] for p in got["detail"]["pins"]] == ["edit_v01", "edit_v02"]          # in the versions' order
    assert run_page.record(run, "review")["recorded_note"] == (
        "Version picked: Version 2\nVersion 1 at 1:01.0: keep this ending\n"
        "Version 2 at 0:03.2: the logo comes in late (from the page)")


# --- the shared rules ------------------------------------------------------------------------------

def test_detail_takes_only_what_was_offered():
    offer = {"items": {"type": "each", "keys": ["a"], "values": ["accept", "redo", "drop"]},
             "scene_notes": {"type": "notes", "keys": ["1"]}}
    assert detail.check(offer, {"items": {"a": "redo"}, "scene_notes": {"1": "  "}}) == ({"items": {"a": "redo"}}, [])
    assert detail.check(offer, {"items": {"a": "pay"}})[1] and detail.check(offer, {"budget": 9})[1]
    assert detail.check({}, {}) == ({}, []) and detail.check({}, None) == ({}, [])


def test_detail_fills_only_what_the_page_left_empty_with_the_offered_default():
    offer = {"items": {"type": "each", "keys": ["a", "b"], "values": ["accept", "redo"], "defaults": {"a": "accept",
                                                                                                    "b": "redo"}},
             "version": {"type": "pick", "values": ["v1", "v2"], "default": "v2"},
             "concept": {"type": "pick", "values": ["c1"]}}
    assert detail.fill(offer, {"items": {"b": "accept"}}) == {"items": {"a": "accept", "b": "accept"}, "version": "v2"}
    assert detail.fill(offer, {"version": "v1"})["version"] == "v1"            # what the user chose wins
    old = {"items": {"type": "each", "keys": ["a"], "values": ["accept"]}, "v": {"type": "pick", "values": ["x"]}}
    assert detail.fill(old, {}) == {}                                          # a page built before the defaults
    assert detail.fill({"v": {"type": "pick", "values": ["x"], "default": "gone"}}, {}) == {}


def test_a_choice_selected_in_advance_is_rendered_checked_only_in_a_live_stage():
    choose = {"path": ["items", "a"], "label": "A", "default": "redo",
              "options": [{"value": "accept", "label": "Accept"}, {"value": "redo", "label": "Redo"}]}
    live = template._choose(choose, True)
    assert _checked_values(live) == {"items": ["redo"]} and live.count(" checked") == 1
    assert template._choose(choose, False) == ""
    assert " checked" not in template._choose({**choose, "default": None}, True)


def test_the_page_script_saves_the_detail_with_the_choice():
    s = template.SCRIPT
    assert "detail: detailOf(stage)" in s and "restore(stage, v.detail)" in s
    assert "[data-detail]" in s and "addEventListener('change', () => save({}))" in s


def test_every_create_ad_page_word_is_in_the_table():
    text = open(SRC, encoding="utf-8").read()
    keys = {"ad.page." + k for k in re.findall(r'_w\((?:ctx|lang), ["\']([a-z0-9_.]+)["\']', text) if not k.endswith(".")}
    keys |= {f"ad.page.{k}.{form}" for k in re.findall(r'_wn\(ctx, "([a-z0-9_.]+)"', text) for form in ("one", "other")}
    keys |= {f"ad.page.type.{k}" for k in create_ad.VISUAL_TYPES + create_ad.AUDIO_TYPES + ("hook", "format", "topic",
                                                                                              "sound", "hashtag", "visual")}
    keys |= {f"ad.page.item.{k}" for k in create_ad.ITEM_CHOICES} | {f"ad.page.gate.{k}" for k in ("visual", "audio", "takes")}
    keys |= {f"ad.page.fact.{k}" for k in create_ad.FACTS} | {"ad.page.route.native", "ad.page.source.trendsmesh"}
    keys |= {f"run_page.stage.{c}" for c in checkins.load(playbook=CREATE_AD).checkins} | {"run_page.playbook.create_ad"}
    families = {"source": ("trendsmesh", "ad_library", "user", "guess", "generate", "site"),
                "licence": ("ads", "inspiration"), "stage": ("pre_video", "video"), "budget": ("ai_usd", "voice_credits"),
                "route": ("native", "elevenlabs_voice", "user_vo", "clone_take"), "qa": ("match", "wps", "lufs", "peak"),
                "cadence": ("daily", "lifetime"), "ai": ("OPT_IN", "OPT_OUT"), "type": ("upscale", "transcription"),
                "col": ("name", "on_screen_text", "sound", "source")}
    keys |= {f"ad.page.{group}.{k}" for group, names in families.items() for k in names}
    en = i18n.english()
    assert not [k for k in sorted(keys) if k not in en]
    assert not [k for k in sorted(en) if k.startswith("ad.page.") and k not in keys]      # no word left unused


def test_the_copys_character_count_takes_the_form_of_its_limit():
    """Issue #3: "{n} of {limit} characters" is a count by its limit; {n} stays for the page's live count."""
    assert words.plural("ad.copy.count", 1) == "{n} of {limit} character"
    assert words.plural("ad.page.run_days", 1, n=1) == "Running for 1 day"
    assert words.plural("ad.copy.over", 125) == "{n} of {limit} characters: too long"
    block = {"ads": [{"title": "Ad", "facts": [], "lists": [
        {"label": "Headline", "limit": 1, "count": words.plural("ad.copy.count", 1),
         "over": words.plural("ad.copy.over", 1), "items": [{"n": 1, "text": "Hi", "count": 2, "path": ["copy"]}]}]}],
        "keep": "Keep"}
    html = template._copy(block, template.Datasets(), "en", True)
    assert "2 of 1 character: too long" in html and 'data-ok="{n} of {limit} character"' in html
    assert {"ad.copy.count.few", "ad.copy.count.many", "ad.copy.over.many"} <= set(i18n.wanted("pl", ["ad"]))


def test_a_create_ad_page_needs_the_ad_words_translated_too(run):
    words.reset()
    assert "ad" in words.AREAS[CREATE_AD]
    assert words.page_lang(run).lang == "en"
