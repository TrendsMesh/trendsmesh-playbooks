"""Issue #131 item 2: the start card is a page in every playbook (`tm page intake`, tm.start_card), the run's first
page; the run page then goes to its link with the start card's answers settled."""

import json
from datetime import date

import pytest

from tm import flow, page, run_page, start_card, state
from tm.cli import main
from tm.flow import set_level
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop

URL = "https://claude.ai/artifact/Ab3dEfGh1jKlMnOpQrStUv"


def _run(tmp_path, playbook, kind="ad"):
    r = RunFolder.create(tmp_path, "start", date(2026, 11, 5), playbook=playbook)
    set_level(r, "every_step")
    if playbook == CREATIVE_BRIEF and kind:                # what the brief is for comes first (issue #136, #156)
        flow.decide(r, "brief_kind", kind, by="user", note=None, said=f"a brief for {kind}")
    return r


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("playbook", [TREND_RESEARCH, CREATIVE_BRIEF, REFRESH_AD, CREATE_AD])
def test_every_playbook_has_a_start_card_with_its_defaults_ticked(tmp_path, capsys, playbook):
    run = _run(tmp_path, playbook)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 0, out
    assert out["folder"].startswith("04_final/intake_v") and out["chat_answers"]
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    level = next(s for s in data["sections"] if s["id"] == "level")
    assert [o["id"] for o in level["options"] if o["default"]] == ["every_step"]
    for sec in data["sections"]:                         # every question and option is worded, never its id
        assert sec["title"] != sec["id"], sec
        assert all(o["label"] for o in sec.get("options") or [])


def test_the_live_test_is_never_a_default(tmp_path):
    run = _run(tmp_path, REFRESH_AD)
    data = start_card.page_json(run, known={"outputs": ["edited_video", "live_test"]})
    outputs = next(s for s in data["sections"] if s["id"] == "outputs")
    assert [o["id"] for o in outputs["options"] if o["default"]] == ["edited_video"]


def test_known_values_prefill_and_an_unknown_question_stops(tmp_path):
    run = _run(tmp_path, TREND_RESEARCH)
    data = start_card.page_json(run, known={"category": "nail art", "market": "PL"})
    by = {s["id"]: s for s in data["sections"]}
    assert (by["category"]["text"]["value"], by["market"]["text"]["value"]) == ("nail art", "PL")
    with pytest.raises(Stop, match="does not ask"):
        start_card.page_json(run, known={"budget": 3})


def test_organic_video_keeps_its_own_intake_page(tmp_path, capsys):
    run = _run(tmp_path, ORGANIC_VIDEO)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 2 and "tm organic page intake" in out["message"]


def test_the_answers_are_read_and_the_run_page_shows_them_settled_on_the_same_link(tmp_path, capsys):
    run = _run(tmp_path, REFRESH_AD)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 0
    page.record_published(run, "intake", None, "v1", URL)
    chat = run.path / "03_wip" / "chat_start.txt"
    chat.write_text("product: Night cream\nThe market: PL\noutputs: edited_video, ai_video\n", encoding="utf-8")
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path), "--read", "--text", "03_wip/chat_start.txt")
    assert code == 0, out
    answers = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))["answers"]
    assert (answers["product"], answers["market"], answers["outputs"]) == ("Night cream", "PL",
                                                                           ["edited_video", "ai_video"])
    built = run_page.build(run)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert "Answered on the start card" in html and "Night cream" in html and "The edited video" in html
    assert built["published"]["url"] == URL                 # the run page goes to the start card's link


def test_a_creative_briefs_g0_stage_shows_the_start_card(tmp_path, capsys):
    run = _run(tmp_path, CREATIVE_BRIEF)
    _cli(capsys, "page", "intake", "--run", str(run.path))
    chat = run.path / "03_wip" / "chat_start.txt"
    chat.write_text("product: Night School e-book\noff_limits: no sleep claims\n", encoding="utf-8")
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path), "--read", "--text", "03_wip/chat_start.txt")
    assert code == 0, out
    ask = run.path / "03_wip" / "ask_G0.json"
    ask.write_text(json.dumps({"checkin": "G0", "title": "The intake card", "question": "Is it right?",
                               "options": [{"choice": "accept", "label": "Yes", "recommended": True}]}),
                   encoding="utf-8")
    built = run_page.build(run, ask, local=True)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert built["open"] == ["G0"] and "no sleep claims" in html and "Answered on the start card" not in html


# --- issue #156: each card its own playbook's, the organic brief's own, in the conversation's language ------------

NAMES = {TREND_RESEARCH: "Trend research", CREATIVE_BRIEF: "Creative brief", REFRESH_AD: "Refresh an ad",
         CREATE_AD: "Create an ad"}


def _html(run, out) -> str:
    return (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("playbook", list(NAMES))
def test_a_start_card_shows_its_own_playbooks_name(tmp_path, capsys, playbook):
    run = _run(tmp_path, playbook)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 0, out
    html = _html(run, out)
    assert f'<span class="pill dark">{NAMES[playbook]}</span>' in html
    assert "Organic AI video" not in html                  # neither the pill nor the eyebrow


def test_the_organic_brief_gets_its_own_start_card(tmp_path, capsys):
    run = _run(tmp_path, CREATIVE_BRIEF, kind="organic")
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 0, out
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["sections"]]
    assert {"channel", "platforms", "business", "bubble", "goal", "films", "recipients", "level"} <= set(ids)
    assert not {"account", "landing", "voice", "outputs", "to_set"} & set(ids)   # no ad account, landing, review pack
    recipients = next(s for s in data["sections"] if s["id"] == "recipients")
    assert "media-buyer" not in [o["id"] for o in recipients["options"]]
    assert [o["id"] for o in recipients["options"] if o["default"]] == ["decision", "creator", "editor", "publisher"]
    for sec in data["sections"]:
        assert sec["title"] != sec["id"], sec
        assert all(o["label"] != o["id"] or o["id"].isdigit() for o in sec.get("options") or []), sec


def test_the_organic_briefs_g0o_stage_shows_its_start_card(tmp_path, capsys):
    run = _run(tmp_path, CREATIVE_BRIEF, kind="organic")
    _cli(capsys, "page", "intake", "--run", str(run.path))
    chat = run.path / "03_wip" / "chat_start.txt"
    chat.write_text("channel: Night School on TikTok\nbubble: sleep tips for students\n", encoding="utf-8")
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path), "--read", "--text", "03_wip/chat_start.txt")
    assert code == 0, out
    ask = run.path / "03_wip" / "ask_G0o.json"
    ask.write_text(json.dumps({"checkin": "G0o", "title": "The start card", "question": "Is it right?",
                               "options": [{"choice": "accept", "label": "Yes", "recommended": True}]}),
                   encoding="utf-8")
    built = run_page.build(run, ask, local=True)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert built["open"] == ["G0o"] and "sleep tips for students" in html


def test_a_creative_brief_start_card_waits_for_the_kind(tmp_path, capsys):
    run = _run(tmp_path, CREATIVE_BRIEF, kind=None)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 2 and "brief_kind" in out["message"]
    assert not (run.path / "04_final" / "intake_v01").exists()


@pytest.mark.parametrize("playbook", list(NAMES))
def test_the_start_card_is_built_in_the_conversations_language(tmp_path, capsys, playbook):
    run = _run(tmp_path, playbook)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path), "--lang", "pl")
    assert code == 0, out
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    assert data["lang"] == "pl" and '<html lang="pl"' in _html(run, out)
    languages = next(s for s in data["sections"] if s["id"] == "languages")
    assert languages["text"]["value"] == "pl, pl"           # the default answer is the conversation's language
    level = next(s for s in data["sections"] if s["id"] == "level")
    assert next(o["label"] for o in level["options"] if o["id"] == "every_step") == "Sprawdzaj każdy krok"


def test_without_a_language_the_card_keeps_english(tmp_path, capsys):
    run = _run(tmp_path, TREND_RESEARCH)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    assert code == 0 and data["lang"] == "en"
    assert next(s for s in data["sections"] if s["id"] == "languages")["text"]["value"] == "en, en"
