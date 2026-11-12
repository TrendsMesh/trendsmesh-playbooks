"""The posting kit's platform rules (issue #91): the dated limits in data/organic-video/platform_rules.yaml and
references/posting-kit.md, the one text to paste per platform (YouTube's three), the posting steps, `rules_read`,
the search phrase, the AI label by production type and the fields the kit does not use. A made-up kit of an
education channel's animated explainer, so these run without the private data."""

import copy
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from tm import kit
from tm.organic_pages import gate

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DOC = PLUGIN_ROOT / "references" / "posting-kit.md"
CTX = dict(language="en", platforms=("tiktok", "instagram", "youtube", "facebook"), account_type="creator",
           product_level="not shown", ai_label="not_required")


def _ctx(**over):
    return kit.KitContext(**{**CTX, **over})


def _kit() -> dict:
    return {
        "id": "V1", "version": "v01", "date": "2026-11-12", "channel": "Science Bites", "language": "en",
        "video": "04_final/V1_final_v01_upload.mp4",
        "cover": {"file": "04_final/kits/cover_V1_v01.jpg", "frame_sec": 2.0, "text": "How volcanoes erupt"},
        "product": "none",
        "rules_read": kit.RULES["as_of"],
        "search_phrase": "how volcanoes erupt",
        "platforms": {
            "tiktok": {"caption": "How volcanoes erupt, in 30 seconds 🌋\nWhich volcano should we draw next?",
                       "hashtags": ["#volcano", "#science", "#geology"],
                       "cover": "Pick the frame at 2 s and add the words “How volcanoes erupt”.",
                       "ai_label": "Off: the video is a clearly drawn animation. You can switch it on under More options.",
                       "sound": "Keep the original sound. If you add a trending sound in the app, turn it down under the voiceover."},
            "instagram": {"caption": "How volcanoes erupt, in 30 seconds 🌋",
                          "hashtags": ["#volcano", "#science"],
                          "cover": "Upload cover_V1_v01.jpg: the words sit in the middle, safe for the 3:4 grid."},
            "youtube": {"title": "How volcanoes erupt, in 30 seconds",
                        "description": "Magma rises, gas pushes, the top gives way. #volcano #science",
                        "tags": ["volcano", "how volcanoes erupt", "geology for kids"],
                        "cover": "No thumbnail: the Shorts feed shows the opening frame as its cover."},
            "facebook": {"caption": "How volcanoes erupt, in 30 seconds.", "hashtags": ["#volcano"]}},
        "plugin": {"ai_label": False, "trending_sound": None, "business_alternative": None,
                   "platforms": ["tiktok", "instagram", "youtube", "facebook"], "youtube_thumbnail": False}}


def _fields(problems):
    return [p.field for p in problems]


# --- the rules, dated ---------------------------------------------------------------------------------

def test_every_limit_names_its_source_and_the_day_it_was_checked():
    rules = kit.RULES
    assert date.fromisoformat(str(rules["as_of"])) and rules["max_age_days"] > 0
    for name, limits in rules["platforms"].items():
        assert name in kit.PLATFORMS
        for limit, spec in limits.items():
            assert str(spec["source"]).startswith("https://"), (name, limit)
            assert date.fromisoformat(str(spec["checked"])) <= date.fromisoformat(str(rules["as_of"])), (name, limit)


def test_the_documents_date_is_the_rules_date():
    title = DOC.read_text(encoding="utf-8").splitlines()[0]
    assert re.search(r"as of (\d{4}-\d{2}-\d{2})", title).group(1) == str(kit.RULES["as_of"])


def test_the_document_is_written_for_every_niche():
    text = DOC.read_text(encoding="utf-8").lower()
    assert "dog" not in text and "pet store" not in text
    for kind in ("creator", "education", "shop"):
        assert kind in text


def test_the_limits_are_the_rules_files():
    assert kit.HASHTAGS == {"tiktok": (3, 5), "instagram": (0, 5), "facebook": (1, 3)}
    assert (kit.YOUTUBE_HASHTAGS, kit.YOUTUBE_TITLE_MAX, kit.INSTAGRAM_LINE_MAX) == ((2, 3), 100, 125)


def test_old_rules_warn_and_still_check():
    as_of = date.fromisoformat(str(kit.RULES["as_of"]))
    assert kit.stale_rules(as_of + timedelta(days=kit.RULES["max_age_days"])) is None
    warning = kit.stale_rules(as_of + timedelta(days=kit.RULES["max_age_days"] + 1))
    assert warning and str(as_of) in warning


# --- one text to paste per platform ---------------------------------------------------------------------

def test_tiktok_instagram_facebook_paste_one_description_with_its_hashtags():
    k = _kit()
    assert kit.paste("tiktok", k["platforms"]["tiktok"]) == [
        ("description", "How volcanoes erupt, in 30 seconds 🌋\nWhich volcano should we draw next?\n\n"
                        "#volcano #science #geology")]
    block = {"caption": "Lava is hot #volcano", "hashtags": ["#Volcano", "#science"]}
    assert kit.paste("instagram", block) == [("description", "Lava is hot #volcano\n\n#science")]   # not twice


def test_youtube_pastes_title_description_and_tags():
    k = _kit()
    assert kit.paste("youtube", k["platforms"]["youtube"]) == [
        ("title", "How volcanoes erupt, in 30 seconds"),
        ("description", "Magma rises, gas pushes, the top gives way. #volcano #science"),
        ("tags", "volcano, how volcanoes erupt, geology for kids")]


def test_steps_are_the_instructions_not_text_to_paste():
    k = _kit()
    steps = kit.steps("tiktok", k["platforms"]["tiktok"])
    assert [f for f, _ in steps] == ["cover", "ai_label", "sound"]


# --- the checks ---------------------------------------------------------------------------------------------

def test_the_made_up_kit_passes():
    assert kit.check(_kit(), _ctx()) == []
    assert kit.posting_problems(_kit(), _ctx()) == []


def test_youtube_tags_are_counted_as_youtube_counts_them():
    assert kit.tags_length(["Foo-Baz"]) == 7 and kit.tags_length(["Foo Baz"]) == 9
    assert kit.tags_length(["a", "b"]) == 3 and kit.tags_length([]) == 0
    k = _kit()
    k["platforms"]["youtube"]["tags"] = ["x" * 250, "y" * 249]            # 250 + 1 + 249 = 500
    assert kit.check(k, _ctx()) == []
    k["platforms"]["youtube"]["tags"] = ["x" * 250, "y y" + "y" * 245]   # 250 + 1 + 248 + 2 quotes = 501
    problems = kit.check(k, _ctx())
    assert _fields(problems) == ["platforms.youtube.tags"] and "501" in problems[0].what


def test_hashtags_are_counted_in_the_text_to_paste():
    k = _kit()
    k["platforms"]["instagram"]["caption"] = "Lava #a #b #c #d"
    k["platforms"]["instagram"]["hashtags"] = ["#a", "#e"]               # 5 different ones in the text
    assert kit.check(k, _ctx()) == []
    k["platforms"]["instagram"]["hashtags"] = ["#e", "#f"]
    assert _fields(kit.check(k, _ctx())) == ["platforms.instagram.hashtags"]


def test_youtube_hashtags_count_in_the_description_with_its_list():
    k = _kit()
    k["platforms"]["youtube"]["description"] = "Magma rises."
    k["platforms"]["youtube"]["hashtags"] = ["#volcano", "#science"]
    assert kit.check(k, _ctx()) == []


def test_tiktok_text_counts_utf16_and_instagram_characters():
    k = _kit()
    k["platforms"]["tiktok"]["caption"] = "How volcanoes erupt\n" + "🌋" * 1080              # 20 + 2160 + 2 + 26
    assert _fields(kit.check(k, _ctx())) == ["platforms.tiktok.caption"]
    k = _kit()
    k["platforms"]["instagram"]["caption"] = "a\n" + "b" * 2200
    assert _fields(kit.check(k, _ctx())) == ["platforms.instagram.caption"]


def test_youtube_description_counts_bytes_and_refuses_angle_brackets():
    k = _kit()
    k["platforms"]["youtube"]["description"] = "ą" * 2490 + " #a #b"                       # 4980 + 6 bytes
    assert kit.check(k, _ctx()) == []
    k["platforms"]["youtube"]["description"] = "ą" * 2500 + " #a #b"
    assert _fields(kit.check(k, _ctx())) == ["platforms.youtube.description"]
    k = _kit()
    k["platforms"]["youtube"]["title"] = "Lava <3"
    assert _fields(kit.check(k, _ctx())) == ["platforms.youtube.title"]


def test_instagram_twenty_mentions_at_most():
    k = _kit()
    k["platforms"]["instagram"]["caption"] = "How volcanoes erupt\nThanks " + " ".join(f"@user{i}" for i in range(20))
    assert kit.check(k, _ctx()) == []
    k["platforms"]["instagram"]["caption"] += " @user20"
    problems = kit.check(k, _ctx())
    assert _fields(problems) == ["platforms.instagram.caption"] and "21 accounts" in problems[0].what


def test_rules_read_is_required_and_must_be_the_current_rules():
    k = _kit()
    del k["rules_read"]
    problems = kit.posting_problems(k, _ctx())
    assert _fields(problems) == ["rules_read"] and "posting-kit.md" in problems[0].todo
    k["rules_read"] = "2026-01-01"
    problems = kit.posting_problems(k, _ctx())
    assert _fields(problems) == ["rules_read"] and str(kit.RULES["as_of"]) in problems[0].what
    assert kit.check(k, _ctx()) == []                  # the script's kit (E3) is checked without it


def test_the_search_phrase_leads_tiktoks_first_line():
    k = _kit()
    del k["search_phrase"]
    assert _fields(kit.posting_problems(k, _ctx())) == ["search_phrase"]
    k["search_phrase"] = "volcano facts"
    problems = kit.posting_problems(k, _ctx())
    assert _fields(problems) == ["platforms.tiktok.caption"] and "volcano facts" in problems[0].what
    k = _kit()
    del k["platforms"]["tiktok"], k["search_phrase"]
    k["plugin"]["platforms"] = ["instagram", "youtube", "facebook"]
    assert kit.posting_problems(k, _ctx()) == []       # no TikTok, no search phrase needed


def test_a_search_phrase_outside_the_trend_data_is_a_warning():
    k = _kit()
    assert kit.search_warning(k, "Volcanoes: how they erupt, explained for kids") is None
    assert kit.search_warning(k, None) is None          # no trend data in the run: nothing to compare
    k["search_phrase"] = "how volcanoes erupt"
    warning = kit.search_warning(k, "Space facts: the moon and the stars")
    assert warning and "how volcanoes erupt" in warning and "Creator Search Insights" in warning


def test_an_animated_video_has_the_label_off_unless_the_user_asks():
    k = _kit()
    k["plugin"]["ai_label"] = True
    problems = kit.check(k, _ctx())
    assert "plugin.ai_label" in _fields(problems) and "animated" in " ".join(p.what for p in problems)
    k["plugin"]["ai_label_request"] = "Please put the AI label on, to be open about it."
    for block in k["platforms"].values():
        block["ai_label"] = "Turn on the AI-generated content setting."
    assert kit.check(k, _ctx()) == []
    assert kit.check(k, _ctx(ai_label="on")) == []      # the --ai-label on flag says so too


def test_a_photoreal_video_has_the_label_on_with_a_step_on_every_platform():
    k = _kit()
    problems = kit.check(k, _ctx(ai_label="on"))
    assert _fields(problems) == ["plugin.ai_label"]
    k["plugin"]["ai_label"] = True
    problems = kit.check(k, _ctx(ai_label="on"))
    assert _fields(problems) == ["platforms.instagram.ai_label", "platforms.youtube.ai_label",
                                 "platforms.facebook.ai_label"]    # TikTok has its step
    for block in k["platforms"].values():
        block["ai_label"] = "Turn on the AI label."
    assert kit.check(k, _ctx(ai_label="required")) == []
    assert kit.check(k, _ctx(ai_label="required", filmed_by_person=True)) == []


def test_fields_the_kit_does_not_use_are_warned_about():
    k = _kit()
    assert kit.unused(k) == []
    k["rules"] = "resources/posting-kit/best_practices_2026-11.md"          # the handoff's
    k["ai_label"] = "not required"
    k["platforms"]["tiktok"]["title"] = "A title"
    k["platforms"]["tiktok"]["pinned_comment"] = "Hi"
    k["platforms"]["youtube"]["caption"] = "Also a caption"
    k["plugin"]["extra"] = 1
    k["cover"]["size"] = "big"
    assert kit.unused(k) == ["rules", "ai_label", "cover.size", "platforms.tiktok.title",
                             "platforms.tiktok.pinned_comment", "platforms.youtube.caption", "plugin.extra"]
    assert kit.check(k, _ctx()) == []                   # a warning, not a refusal


def test_a_kit_saved_before_the_change_still_loads_and_checks():
    """A kit of 0.12.0: no rules_read, search_phrase or tags, the handoff's `rules` and kit-level `ai_label`."""
    k = _kit()
    for key in ("rules_read", "search_phrase"):
        del k[key]
    del k["platforms"]["youtube"]["tags"]
    k |= {"rules": "resources/posting-kit/best_practices_2026-11.md", "ai_label": "not required"}
    assert kit.check(k, _ctx()) == []                    # the shape and the platform rules hold
    assert _fields(kit.posting_problems(k, _ctx())) == ["rules_read", "search_phrase"]
    assert kit.paste("youtube", k["platforms"]["youtube"])[-1][0] == "description"
    html = gate.kit_html("v1", k)
    assert "#volcano #science #geology" in html and "Tags" not in html


# --- the page ------------------------------------------------------------------------------------------------

def _copies(html: str, platform: str) -> list[str]:
    block = html.split(f'id="pf-v1-{platform}"', 1)[1].split('<div class="pf"', 1)[0]
    return re.findall(r'<span class="k">([^<]*?) <button class="copy"', block)


def test_the_delivery_page_has_one_copy_per_platform_and_youtubes_three():
    html = gate.kit_html("v1", _kit())
    assert _copies(html, "tiktok") == ["Description to paste (with hashtags)"]
    assert _copies(html, "instagram") == ["Description to paste (with hashtags)"]
    assert _copies(html, "facebook") == ["Description to paste (with hashtags)"]
    assert _copies(html, "youtube") == ["Title", "Description (with hashtags)", "Tags"]
    assert "volcano, how volcanoes erupt, geology for kids" in html
    assert "\n\n#volcano #science #geology</pre>" in html


def test_the_posting_steps_are_a_list_without_copy():
    html = gate.kit_html("v1", _kit())
    tiktok = html.split('id="pf-v1-tiktok"', 1)[1].split('<div class="pf"', 1)[0]
    steps = tiktok.split("At posting", 1)[1]
    assert "copy" not in steps and steps.count("<li>") == 4               # cover, AI label, sound, search phrase
    assert "turn it down under the voiceover" in steps
    assert "how volcanoes erupt" in steps and "Creator Search Insights" in steps
    assert "Sound" not in html.split("At posting", 1)[0].split("Posting kit", 1)[1]   # no Copy for the sound


def test_the_platform_row_says_the_user_posts():
    row = gate.platform_row("v1")
    assert '<span class="lbl">Posting kit for</span>' in row and "Post to" not in row
    assert "you post the video yourself" in row.lower()


def test_the_page_escapes_the_kits_texts():
    k = _kit()
    k["platforms"]["tiktok"]["sound"] = "<b>loud</b>"
    k["platforms"]["tiktok"]["caption"] = "How volcanoes erupt </pre><script>"
    html = gate.kit_html("v1", k)
    assert "<b>loud</b>" not in html and "</pre><script>" not in html


def test_a_kit_with_no_text_to_paste_shows_no_empty_copy():
    k = copy.deepcopy(_kit())
    k["platforms"]["facebook"] = {"cover": "Upload the cover."}
    html = gate.kit_html("v1", k)
    assert _copies(html, "facebook") == []


def test_the_pages_english_is_the_string_tables():
    """The page is built in English, then each Frag's English is put in the page language: the two must agree."""
    from tm import i18n, organic_pages
    en = i18n.translator(i18n.ENGLISH)
    assert en("organic.post_to") == "Posting kit for" and en("organic.post_note") == organic_pages.POST_NOTE
    assert (en("organic.kit.search_check"), en("organic.kit.you_post")) == (gate.SEARCH_CHECK, gate.YOU_POST)
    assert en("organic.kit.paste") == gate.PASTE_LABELS["description"]
    assert [en(f"organic.kit.{k}") for k in ("title", "description_hashtags", "tags")] == list(gate.YOUTUBE_LABELS.values())
    assert [en(f"organic.kit.{k}") for k in gate.STEP_LABELS] == list(gate.STEP_LABELS.values())


def test_the_polish_page_has_no_english_left_in_the_kit():
    html = gate.localize(gate.kit_html("v1", _kit()) + gate.platform_row("v1"), "pl")
    for english in ("Description to paste", "At posting", "Search phrase", "Creator Search Insights before you post",
                    "You post the video yourself", "Posting kit for", "Tags <button"):
        assert english not in html, english
    assert "Opis do wklejenia (z hashtagami)" in html and "Przy publikacji" in html
