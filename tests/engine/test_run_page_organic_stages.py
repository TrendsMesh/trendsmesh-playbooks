"""Issue #131 item 3: Organic AI video's channel profile, script draft and pack as stages of the run page: the
profile's fields, the picked idea with its voiceover script line by line (a new check-in, `script_draft`, before
the style, voice and music), and the pack's paid items at the registry's price, the total and the budget cap."""

import json

import pytest

from test_run_page_organic import _new, _pack
from tm import checkins, run_page
from tm.playbooks import ORGANIC_VIDEO


def _ask(run, checkin):
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    path = run.path / "03_wip" / f"my_ask_{checkin}.json"
    path.write_text(json.dumps({"checkin": checkin, "title": "A made-up title", "question": "Go on?",
                                "options": [{"choice": c, "label": c.capitalize() + "!"}
                                            for c in cat.checkins[checkin].choices]}), encoding="utf-8")
    return path


def _html(run, built):
    return (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")


def test_the_script_draft_is_its_own_check_in_before_the_taste():
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    c = cat.checkins["script_draft"]
    assert (c.card, c.route, c.choices) == ("plan", {"every_step": "own", "big_calls": "card", "hands_off": "rule"},
                                            ("accept",))
    assert cat.checkins["script"].name == "Accept the script to film"      # another check-in


def test_the_script_draft_shows_the_idea_and_each_line_with_its_time(tmp_path):
    run = _new(tmp_path)
    _pack(run)
    html = _html(run, run_page.build(run, _ask(run, "script_draft"), local=True))
    assert "Mało kto wie, że Fortnite ma PEGI 12" in html                     # the picked idea
    assert "Młodsi nie mają tam czatu głosowego od razu." in html and "3–6 s" in html


def test_the_pack_shows_each_paid_item_the_total_and_the_cap(tmp_path):
    run = _new(tmp_path)
    _pack(run)
    html = _html(run, run_page.build(run, _ask(run, "pack"), local=True))
    assert "What is paid, item by item" in html and "minimax/h3" in html and "openai/gpt-image-2" in html
    assert "$1.30" in html and "Budget cap per run" in html


def test_the_profile_stage_shows_the_drafted_profile(tmp_path):
    from tm import brand, trend_spool
    run = _new(tmp_path)
    (run.path / "config.yaml").write_text("channels: [cat-corner]\n", encoding="utf-8")
    folder = trend_spool.workspace_of(run) / brand.CHANNEL_DIR / "cat-corner"
    folder.mkdir(parents=True)
    profile = {"schema": "channel/1", "kind": "channel", "channel": "Cat Corner", "store": None,
               "platforms": ["tiktok", "youtube"], "account_type": "business", "audience_language": "en",
               "context": {"topic": "cat care for new owners", "audience": "first-time owners",
                           "style": "calm, kind", "performed_links": []},
               "product_role": "not_shown", "content_rules": ["no medical claims"], "video_style": "paper cut-out"}
    (folder / "channel_v01.json").write_text(json.dumps(profile), encoding="utf-8")
    html = _html(run, run_page.build(run, _ask(run, "profile"), local=True))
    for text in ("Cat Corner", "TikTok, YouTube", "cat care for new owners", "paper cut-out", "no medical claims"):
        assert text in html, text
    assert "not_shown" not in html                                     # a stored value said in words


@pytest.mark.parametrize("lang", ["pl"])
def test_the_new_stages_are_in_polish_too(tmp_path, lang):
    run = _new(tmp_path, lang=lang)
    _pack(run)
    built = run_page.build(run, _ask(run, "pack"), local=True)
    html = _html(run, built)
    assert "Co płatne, pozycja po pozycji" in html and "language_warning" not in built
