"""The text sets (a `look` in the text style): one look per set of captions + overlays, drawn by
remotion/src/CaptionLooks.tsx and OverlayLooks.tsx; the engine writes the look, the accent and the overlay kind into
the OrganicCaptions props, groups the words by the look's limits and checks the fonts the look draws with."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tm import organic_edit as oe
from tm import video_fonts as vf

SRC = Path(__file__).resolve().parents[2] / "remotion" / "src"


def _words(*items: tuple[str, float, float]) -> list[dict]:
    return [{"word": w, "start": s, "end": e} for w, s, e in items]


def test_the_looks_are_the_same_in_the_engine_and_the_compositions():
    caption_type = re.search(r"export type Look = ([^;]+);", (SRC / "CaptionLooks.tsx").read_text(encoding="utf-8"))
    assert caption_type is not None
    assert set(re.findall(r'"(\w+)"', caption_type.group(1))) == set(oe.LOOKS)
    assert set(oe.LOOK_WORDS) == set(oe.LOOK_CHARS) == set(oe.LOOK_SIZE) == set(oe.LOOKS)
    assert oe.DEFAULT_LOOK in oe.LOOKS
    overlay = (SRC / "OverlayLooks.tsx").read_text(encoding="utf-8")
    kinds = re.search(r"export type OverlayKind = ([^;]+);", overlay)
    assert kinds is not None and set(re.findall(r'"(\w+)"', kinds.group(1))) == set(oe.OVERLAY_KINDS)


@pytest.mark.parametrize("look", oe.LOOKS)
def test_a_default_style_with_a_look_can_be_used(look):
    style = oe.default_style(caption="I check what's rising", overlay="How I find ideas", look=look,
                             accent="#FFD84D")
    assert oe.style_problems(style) == []
    assert style["look"] == look and style["accent"] == "#FFD84D"
    assert style["captions"]["words"] == oe.LOOK_WORDS[look]
    assert style["captions"]["fontSize"] == oe.LOOK_SIZE[look]


def test_a_style_without_a_look_is_unchanged():
    style = oe.default_style(caption="a", overlay="b")
    assert "look" not in style and "accent" not in style and oe.style_problems(style) == []


def test_an_unknown_look_or_a_bad_accent_is_refused():
    style = oe.default_style(caption="a", overlay="b")
    problems = oe.style_problems({**style, "look": "neon", "accent": "yellow"})
    assert any(p.startswith("look must be one of") for p in problems)
    assert any(p.startswith("accent must be a colour") for p in problems)


def test_a_caption_in_a_look_carries_the_look_and_the_accent():
    style = oe.default_style(caption="a", overlay="b", look="pill", accent="#22AA88")
    words = [{"text": "pick", "from": 1.0, "to": 1.2}, {"text": "one", "from": 1.2, "to": 1.5, "key": True}]
    entry = oe.caption_entry("captions", style["captions"], "pick one", 1.0, 1.8, words, look="pill",
                             accent="#22AA88")
    assert entry["look"] == "pill" and entry["highlight"] == "#22AA88" and entry["words"] == words
    plain = oe.caption_entry("captions", oe.default_style(caption="a", overlay="b")["captions"], "pick one", 1, 2)
    assert "look" not in plain and "highlight" not in plain


def test_an_overlay_in_a_look_says_its_kind_and_family():
    group = oe.default_style(caption="a", overlay="b")["overlays"]
    hook = oe.caption_entry("overlays", group, "How I find ideas", 0, 2.7, look="native")
    assert hook["overlay"] == {"kind": "hook", "family": "native"} and "fontSize" not in hook
    number = oe.caption_entry("overlays", group, "+212%", 4.8, 7, look="outline", accent="#FFD84D",
                              overlay={"kind": "number", "sub": "rising this week", "brand": " "})
    assert number["overlay"] == {"kind": "number", "family": "outline", "accent": "#FFD84D",
                                 "sub": "rising this week"}
    odd = oe.caption_entry("overlays", group, "x", 0, 1, look="block", overlay={"kind": "banner"})
    assert odd["overlay"]["kind"] == "hook"
    plain = oe.caption_entry("overlays", group, "x", 0, 1)
    assert "overlay" not in plain and plain["fontSize"] == group["fontSize"]


def test_a_look_keeps_its_groups_short():
    words = _words(("I", 0.0, 0.2), ("stopped", 0.2, 0.5), ("scrolling", 0.5, 0.9), ("for", 0.9, 1.0),
                   ("ideas.", 1.0, 1.4))
    assert [len(g) for g in oe.caption_groups(words, 2, 3)] == [3, 2]
    # "I stopped scrolling for" is 23 letters: past the outline look's 20, so "for" starts the next group
    assert [[w["word"] for w in g] for g in oe.caption_groups(words, 1, 3, max_chars=oe.LOOK_CHARS["outline"])] == [
        ["I", "stopped", "scrolling"], ["for", "ideas."]]
    # with a look the min is 1, so a comma closes a group even after one word
    said = _words(("Honestly,", 0.0, 0.5), ("I", 0.6, 0.7), ("check", 0.7, 0.9))
    assert [len(g) for g in oe.caption_groups(said, *oe.LOOK_WORDS["outline"], max_chars=20)] == [1, 2]
    assert [len(g) for g in oe.caption_groups(words, 1, 1, max_chars=oe.LOOK_CHARS["pop"])] == [1, 1, 1, 1, 1]


def test_the_native_look_is_checked_in_tiktok_sans_and_its_extra_lines_too():
    data = {"captions": [
        {"text": "How I find ideas", "style": "hook", "overlay": {"kind": "hook", "family": "native"}},
        {"text": "I check", "style": "caption", "look": "native"},
        {"text": "+212%", "style": "hook", "overlay": {"kind": "number", "family": "outline", "sub": "this week"}},
        {"text": "scrolling", "style": "caption", "look": "pop"},
        {"text": "plain", "style": "caption"},
    ]}
    got = vf.texts("OrganicCaptions", data)
    assert ("captions[0].text", "How I find ideas", "TikTokSans") in got
    assert ("captions[1].text", "I check", "TikTokSans") in got
    assert ("captions[2].overlay.sub", "this week", "Montserrat") in got
    assert ("captions[3].text", "SCROLLING", "Montserrat") in got     # pop is drawn in capitals
    assert ("captions[4].text", "plain", "Montserrat") in got
    assert "TikTokSans" in vf.table()["families"]
