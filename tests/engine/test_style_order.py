"""Issue #116: every style's preview (a poster and a loop, `data/styles/previews/`), its tags, and the order styles are
suggested in: the channel's own style first, then the styles of the channel's type ranked by the topic's tone, a style
the user rejected for the channel last (`atlas_prompt.ranked`, `tm organic atlas-styles`)."""

from __future__ import annotations

import hashlib
import json
import re

import pytest

from tm import atlas_prompt, brand, organic_proposals, organic_research, page, paths, run_page

PREVIEWS = paths.bundled_data() / "styles" / "previews"


# --- the previews ---------------------------------------------------------------------------------------------

def test_every_style_has_a_poster_and_a_loop_made_from_its_current_module_and_card():
    """A changed style can't ship with a stale preview: its hash is the module's and the card's, as
    atlas/previews.mjs makes it (re-run it after changing a style)."""
    index = atlas_prompt.previews()
    cards = atlas_prompt.styles()
    assert sorted(index) == sorted(s["styleId"] for s in cards)          # no preview without its style, nor the reverse
    for s in cards:
        entry = index[s["styleId"]]
        poster, loop = atlas_prompt.preview_files(s)
        assert poster.name == entry["poster"] == f"{s['order']:02d}_{s['styleId']}.jpg"
        assert loop.name == entry["loop"] == f"{s['order']:02d}_{s['styleId']}.mp4"
        assert poster.read_bytes()[:3] == b"\xff\xd8\xff", poster.name                     # a JPEG
        assert loop.read_bytes()[4:8] == b"ftyp", loop.name                               # an MP4
        assert entry["order"] == s["order"]
        assert entry["hash"] == atlas_prompt.preview_hash(s), (
            f"{s['styleId']}: its module or card changed since its preview was made; run node atlas/previews.mjs "
            "--browser <chrome> and commit the new files")
    assert sorted(p.name for p in PREVIEWS.iterdir()) == sorted(
        [f"{s['order']:02d}_{s['styleId']}.{x}" for s in cards for x in ("jpg", "mp4")] + ["previews.json"])


def test_the_hash_is_the_module_and_the_card():
    s = atlas_prompt.find_style(7)
    module = atlas_prompt.module_path(s).read_bytes()
    card = json.dumps(s, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert atlas_prompt.preview_hash(s) == hashlib.sha256(module + card).hexdigest()[:16]
    assert atlas_prompt.preview_hash({**s, "name": "Changed"}) != atlas_prompt.preview_hash(s)


# --- the tags -------------------------------------------------------------------------------------------------

def test_every_card_has_tags_from_the_fixed_lists():
    assert set(atlas_prompt.CHANNEL_TYPES) == set(brand.CHANNEL_TYPES) - {brand.OTHER_TYPE}
    for s in atlas_prompt.styles():
        t = s["tags"]
        assert set(t) == {"channels", "tone", "energy", "numbers"}, s["styleId"]
        # 2 to 4 types as the issue says; 31 Newsprint is the news channel's alone (re-tagging it re-makes its preview)
        assert 1 <= len(t["channels"]) <= 4 and set(t["channels"]) <= set(atlas_prompt.CHANNEL_TYPES), s["styleId"]
        assert 2 <= len(t["tone"]) <= 3 and set(t["tone"]) <= set(atlas_prompt.TONES), s["styleId"]
        assert t["energy"] in atlas_prompt.ENERGIES and isinstance(t["numbers"], bool), s["styleId"]


# --- the order ------------------------------------------------------------------------------------------------

def _ids(rows):
    return [r["styleId"] for r in rows]


def test_the_channels_type_comes_first_ranked_by_the_topics_tone():
    rows = atlas_prompt.ranked(channel_type="music_dance", tone=["bold", "edgy"])
    assert len(rows) == len(atlas_prompt.styles()) and len(set(_ids(rows))) == len(rows)
    head = [r for r in rows if r["reason"] == "type"]
    assert head and all("music_dance" in r["tags"]["channels"] for r in head)
    assert rows[:len(head)] == head                                              # the type's styles first
    shared = [len(r["shared_tone"]) for r in head]
    assert shared == sorted(shared, reverse=True)                                # most tone words in common first
    assert all(r["shared_tone"] == [w for w in ("bold", "edgy") if w in r["tags"]["tone"]] for r in rows)
    rest = rows[len(head):]
    assert all("music_dance" not in r["tags"]["channels"] for r in rest)
    assert all(r["reason"] in ("tone", "other") for r in rest)


def test_a_key_number_puts_the_styles_that_show_numbers_first_among_equals():
    rows = atlas_prompt.ranked(channel_type="news_explainers", tone=["serious"], numbers=True)
    head = [r for r in rows if r["reason"] == "type"]
    for a, b in zip(head, head[1:]):
        key = lambda r: (-len(r["shared_tone"]), not r["tags"]["numbers"])     # noqa: E731
        assert key(a) <= key(b)
    without = atlas_prompt.ranked(channel_type="news_explainers", tone=["serious"])
    assert sorted(_ids(without)) == sorted(_ids(rows))


def test_a_channel_of_type_other_is_ranked_by_tone_only():
    rows = atlas_prompt.ranked(channel_type="other", tone=["retro", "nostalgic"])
    assert all(r["reason"] in ("tone", "other") for r in rows)
    shared = [len(r["shared_tone"]) for r in rows]
    assert shared == sorted(shared, reverse=True)
    assert rows[0]["shared_tone"] == ["retro", "nostalgic"]
    assert _ids(atlas_prompt.ranked(tone=["retro", "nostalgic"])) == _ids(rows)     # no type: the same


def test_the_channels_own_style_first_and_a_rejected_one_last():
    rows = atlas_prompt.ranked(channel_type="howto_education", tone=["friendly"], own="40",
                               rejected=["1 Flat Explainer", "whiteboard", "40"])
    assert rows[0]["styleId"] == "editorial-collage" and rows[0]["reason"] == "channel"   # never moved for a rejection
    assert _ids(rows[-2:]) == ["flat-explainer", "whiteboard"] and {r["reason"] for r in rows[-2:]} == {"rejected"}
    assert len(rows) == len(atlas_prompt.styles())


def test_no_tone_and_no_type_keeps_the_librarys_order():
    assert _ids(atlas_prompt.ranked()) == [s["styleId"] for s in atlas_prompt.styles()]


def test_an_unknown_tone_word_or_type_is_refused():
    with pytest.raises(ValueError, match="tone"):
        atlas_prompt.ranked(tone=["spooky"])
    with pytest.raises(ValueError, match="type"):
        atlas_prompt.ranked(channel_type="podcasts")


# --- the channel's history: the styles it picked and rejected -----------------------------------------------------

def _decision(idea, style, default, decision="produce", production="animation"):
    return {"at": "2026-11-10T10:00:00+00:00", "date": "2026-11-10", "run": "r", "proposal": "m1", "idea": idea,
            "decision": decision, "production": production, "style": style, "style_default": default}


def _history(tmp_path, rows):
    folder = tmp_path / organic_research.ORGANIC_DIR / "ch"
    folder.mkdir(parents=True)
    (folder / organic_research.DECISIONS).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return organic_research.style_history(tmp_path, "ch")


def test_the_styles_a_channel_picked_and_rejected(tmp_path):
    v = organic_proposals.style_value
    rows = [_decision("a", v(7), v(7)), _decision("b", v(7), v(4)), _decision("c", v(7), v(7)),
            _decision("d", v(12), v(12), decision="skip"),                   # a skipped idea picks nothing
            _decision("e", "channel", "channel"),                            # the channel's own words: no card
            {"idea": "f", "decision": "produce", "production": "animation"},   # a row written before #116
            _decision("g", v(9), v(9)), _decision("g", v(14), v(9))]          # the idea's latest row counts
    got = _history(tmp_path, rows)
    assert got["picked"] == {v(7): 3, v(14): 1}
    assert got["rejected"] == [v(4), v(9)]
    assert organic_research.habit_style(got) == v(7)
    assert organic_research.habit_style({"picked": {v(7): 2}, "rejected": []}) is None


def test_no_history_is_empty(tmp_path):
    assert organic_research.style_history(tmp_path, "nobody") == {"picked": {}, "rejected": []}


def test_a_decision_row_keeps_the_style_picked_and_the_one_picked_in_advance():
    v = organic_proposals.style_value
    p = _proposal("animation", styles=_styles(7, 4))
    assert organic_proposals.style_fields(p, {"style": v(4)}, {}) == {"style": v(4), "style_default": v(7)}
    assert organic_proposals.style_fields(_proposal("ai_footage"), {"style": None}, {}) == {}


# --- the page's styles: the channel's own first, a rejected one last ---------------------------------------------

def _proposal(production, **plugin):
    from test_organic_look import _proposal as make
    return make(production, **plugin)


def _styles(*keys):
    return [{"style": k, "why": f"fits ({k})"} for k in keys]


def _values(options):
    return [o["value"] for o in options]


def test_the_channel_style_shows_the_nearest_card():
    v = organic_proposals.style_value
    p = _proposal("animation", styles=_styles(7), channel_style={"style": 40, "why": "torn paper, engravings"})
    own = organic_proposals.style_options(p, {"video_style": "paper cut-out collage, old engravings"})
    assert _values(own) == ["channel", v(7)]
    assert own[0]["channel"] and own[0]["text"] == "paper cut-out collage, old engravings"
    assert own[0]["style"]["styleId"] == "editorial-collage" and own[0]["why"] == "torn paper, engravings"
    assert not own[1].get("channel")


def test_without_its_own_words_the_channel_style_is_the_card_it_picks():
    """No video_style: the card the agent named as the channel's (a style picked 3 times or more), else the one the
    channel picked 3 times or more, first and picked in advance."""
    v = organic_proposals.style_value
    named = _proposal("animation", styles=_styles(7), channel_style={"style": 14, "why": "picked 4 times"})
    got = organic_proposals.style_options(named, {"video_style": None})
    assert _values(got) == [v(14), v(7)] and got[0]["channel"] and got[0]["why"] == "picked 4 times"
    habit = organic_proposals.style_options(_proposal("animation", styles=_styles(7, 4)), {"habit_style": v(4)})
    assert _values(habit) == [v(4), v(7)] and habit[0]["channel"]                     # never offered twice
    assert organic_proposals.default_style(_proposal("animation", styles=_styles(7, 4)), {"habit_style": v(4)}) == v(4)


def test_a_style_rejected_for_the_channel_goes_last():
    v = organic_proposals.style_value
    got = organic_proposals.style_options(_proposal("animation", styles=_styles(7, 4, 9)), {"rejected_styles": [v(7)]})
    assert _values(got) == [v(4), v(9), v(7)]
    assert organic_proposals.default_style(_proposal("animation", styles=_styles(7, 4)), {"rejected_styles": [v(7)]}) \
        == v(4)


def test_the_channel_style_is_checked():
    def look(**plugin):
        out = []
        p = _proposal("animation", **plugin)
        organic_proposals._look(p, p["id"], out)
        return [x.field for x in out]

    assert look(styles=_styles(7), channel_style={"style": 40, "why": "nearest"}) == []
    assert look(styles=_styles(7, 4), channel_style={"style": 40, "why": "nearest"}) == []
    assert look(styles=_styles(7, 4, 9), channel_style={"style": 40, "why": "x"}) == ["m1.plugin.styles"]   # 4 in all
    assert look(styles=_styles(7)) == ["m1.plugin.styles"]                           # 1 without the channel's
    assert look(styles=_styles(7), channel_style={"style": "nope", "why": "x"}) == ["m1.plugin.channel_style.style"]
    assert look(styles=_styles(7), channel_style={"style": 40, "why": " "}) == ["m1.plugin.channel_style.why"]
    assert look(styles=_styles(40), channel_style={"style": 40, "why": "x"}) == ["m1.plugin.styles[0].style"]
    out = []
    p = _proposal("ai_footage", styles=_styles(7), channel_style={"style": 40, "why": "x"})
    organic_proposals._look(p, p["id"], out)
    assert out == []                         # issue #138 item 3: a style is picked for every production type


def test_a_style_picked_from_the_gallery_is_kept():
    v = organic_proposals.style_value
    p = _proposal("animation", styles=_styles(7, 4))
    data = {"proposals": [p], "default_output": "video"}
    defaults = {"ch": {"level": "every_step", "output": "video", "platforms": ["tiktok"], "video_style": None}}
    doc = {"decision": "produce", "style": v(33), "updated_at": "2026-11-12T10:00:00Z"}
    assert organic_proposals.decisions([("m1", doc)], data, defaults)["m1"]["style"] == v(33)
    odd = {**doc, "style": "no such style"}
    assert organic_proposals.decisions([("m1", odd)], data, defaults)["m1"]["style"] == v(7)


# --- tm organic atlas-styles -------------------------------------------------------------------------------------

def _cli(capsys, *argv):
    from tm.cli import main
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_atlas_styles_gives_the_tags_and_the_previews(capsys):
    code, out = _cli(capsys, "organic", "atlas-styles")
    assert code == 0 and [s["order"] for s in out["styles"]] == list(range(1, len(atlas_prompt.styles()) + 1))
    row = out["styles"][39]
    assert row["tags"] == atlas_prompt.find_style(40)["tags"]
    poster, loop = atlas_prompt.preview_files(atlas_prompt.find_style(40))
    assert row["poster"] == str(poster) and row["loop"] == str(loop)
    assert "reason" not in row                                              # no order asked: the library's


def test_atlas_styles_lists_the_channel_types_styles_first(capsys):
    code, out = _cli(capsys, "organic", "atlas-styles", "--channel-type", "music_dance", "--tone", "bold,edgy",
                     "--numbers")
    assert code == 0
    want = atlas_prompt.ranked(channel_type="music_dance", tone=["bold", "edgy"], numbers=True)
    assert [s["styleId"] for s in out["styles"]] == [s["styleId"] for s in want]
    assert out["styles"][0]["reason"] == "type" and "music_dance" in out["styles"][0]["tags"]["channels"]
    code, out = _cli(capsys, "organic", "atlas-styles", "--tone", "spooky")
    assert code == 1 and "spooky" in out["message"]


def test_atlas_styles_for_a_channel_reads_its_profile_and_history(tmp_path, capsys, monkeypatch):
    from exampleedu import PROFILE
    from tm import library
    v = organic_proposals.style_value
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    brand.save(tmp_path, {**PROFILE, "channel": "Cat Corner", "type": "music_dance", "video_style": None}, run=None)
    library.append_jsonl(tmp_path / "library" / "organic" / "cat-corner" / "decisions.jsonl",
                         [_decision(i, v(27), v(27)) for i in "abc"] + [_decision("d", v(27), v(39))])
    code, out = _cli(capsys, "organic", "atlas-styles", "--channel", "Cat Corner", "--tone", "bold")
    assert code == 0, out
    assert out["styles"][0]["order"] == 27 and out["styles"][0]["reason"] == "channel"
    assert out["styles"][-1]["order"] == 39 and out["styles"][-1]["reason"] == "rejected"
    assert out["styles"][1]["reason"] == "type"
    assert out["channel"] == {"channel": "cat-corner", "type": "music_dance", "video_style": None,
                              "own": v(27), "picked": {v(27): 4}, "rejected": [v(39)]}
    code, out = _cli(capsys, "organic", "atlas-styles", "--channel", "Cat Corner", "--channel-type", "news_explainers")
    assert out["styles"][1]["reason"] == "type" and "news_explainers" in out["styles"][1]["tags"]["channels"]
    code, out = _cli(capsys, "organic", "atlas-styles", "--channel", "exampleedo")
    assert code == 1 and "exampleedo" in out["message"]


# --- the previews on the run page: the proposals (C2) and the style, voice and music (D2) -----------------------

@pytest.fixture
def animated(tmp_path, monkeypatch):
    """test_run_page_organic_plan's idea run, its M1 an animation with two suggested styles and the channel's own."""
    import test_run_page_organic_plan as plan_tests
    from tm.organic_pages import proposals as proposals_page
    monkeypatch.setattr(page, "fetch_image", lambda url, dest, timeout=30: False)
    monkeypatch.setattr(organic_proposals.envtiers, "installed", lambda tier: True)   # no plugin folders in CI
    monkeypatch.setattr(proposals_page, "_trends", plan_tests._trends)
    data = plan_tests._proposals()
    data["proposals"][0]["plugin"] = {"production": "animation", "output": "video", "styles": _styles(14, 7),
                                      "channel_style": {"style": 40, "why": "torn paper and engravings"}}
    real = organic_proposals.profile_defaults
    monkeypatch.setattr(organic_proposals, "profile_defaults", lambda run, d: {
        k: {**v, "video_style": "paper cut-out collage, old engravings", "rejected_styles": []}
        for k, v in real(run, d).items()})
    run = plan_tests._run(tmp_path, "proposals")
    plan_tests._checked(run, "proposals_v01.json", data)
    plan_tests._to(run, "proposals")
    return run


def _styles_html(html):
    return html.split('id="sty-m1"', 1)[1].split("</details>", 1)[0] if 'id="sty-m1"' in html else ""


def test_the_proposals_stage_plays_the_suggested_styles_and_shows_every_style(animated):
    from test_run_page_organic import _ask, _built, _html
    built = run_page.build(animated, _ask(animated, "proposals"))
    html, folder = _html(animated, built), animated.path / built["folder"]
    v = organic_proposals.style_value
    for s in atlas_prompt.styles():                                   # every poster and loop is on the page
        poster, loop = atlas_prompt.preview_files(s)
        assert (folder / "assets" / "media" / "styles" / poster.name).read_bytes() == poster.read_bytes()
        assert (folder / "assets" / "media" / "styles" / loop.name).is_file()
    block = _styles_html(html)
    suggested = block.split('class="sty-all"', 1)[0]
    assert suggested.count("<video") == 3 and suggested.count(" autoplay") == 3 and " loop" in suggested
    assert "assets/media/styles/40_editorial-collage.mp4" in suggested            # the channel's words, its card's loop
    assert "paper cut-out collage, old engravings" in suggested and "Your channel’s style" in suggested
    assert "assets/media/styles/14_halftone-comic.mp4" in suggested and "fits (14)" in suggested
    gallery = block.split('class="sty-all"', 1)[1]
    families = list(dict.fromkeys(s["category"] for s in atlas_prompt.styles()))
    assert all(f">{f}<" in gallery for f in families)
    assert gallery.count('loading="lazy"') == len(atlas_prompt.styles())          # posters; a loop plays on click
    assert "<video" not in gallery
    values = re.findall(r'name="ovp-s-m1" value="([^"]+)"', html)
    assert len(values) == len(set(values)) == len(atlas_prompt.styles()) - 2 + 3  # no style twice: 49 - 2 + 3
    assert values[:3] == ["channel", v(14), v(7)]
    offer = _built(animated, built)["offer"]["proposals"]["styles"]
    assert set(offer["values"]) == {"channel"} | {v(s["order"]) for s in atlas_prompt.styles()}
    assert offer["defaults"] == {"m1": "channel"}
    listed = {f["as"] for f in page.files(folder)}                     # what the Artifact tool publishes, in its limits
    assert {f"assets/media/styles/{p.name}" for s in atlas_prompt.styles() for p in atlas_prompt.preview_files(s)} \
        <= listed


def test_a_style_picked_from_the_gallery_is_the_decision(animated, capsys):
    from test_run_page_organic_plan import _answer
    from test_run_page_organic import _ask
    from tm.cli import main
    v = organic_proposals.style_value
    run_page.build(animated, _ask(animated, "proposals"))
    _answer(animated, "proposals", "proposals_v01", "accept", decision={"m1": "produce", "m2": "skip"},
            styles={"m1": v(33)})
    page.await_(animated, run_page.PAGE, "1700000001-abcd")
    assert main(["page", "decision", "proposals", "--run", str(animated.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    body = json.loads((animated.path / out["files"]["decisions"]).read_text(encoding="utf-8"))
    assert body["decisions"]["m1"]["style"] == v(33)


@pytest.fixture
def tasting(tmp_path):
    """test_run_page_organic's production run at the taste check-in, offering two of our styles."""
    import test_run_page_organic as t
    from tm import organic_pack
    run = t._new(tmp_path)
    organic_pack.record(run, run.path / "03_wip" / "pack_v01.json", t._pack(run), stage="recipe")
    t._taste_options(run)
    opts_path = run.path / "03_wip" / "taste_options_v01.json"
    opts = json.loads(opts_path.read_text(encoding="utf-8"))
    opts["styles"] = [{"id": "14", "why": "bold dots for the number", "recommended": True},
                      {"id": "paper-layers", "label": "Paper, layered", "why": "warm and calm"}]
    opts_path.write_text(json.dumps(opts), encoding="utf-8")
    t._to(run, "taste")
    return run


def _taste_built(run):
    from test_run_page_organic import _ask
    return run_page.build(run, _ask(run, "taste"))


def test_the_taste_stage_plays_our_styles_and_shows_the_gallery(tasting):
    from test_run_page_organic import _built, _html
    v = organic_proposals.style_value
    built = _taste_built(tasting)
    html, folder = _html(tasting, built), tasting.path / built["folder"]
    assert (folder / "assets" / "media" / "styles" / "14_halftone-comic.mp4").is_file()
    suggested = html.split('class="sty-all"', 1)[0]
    assert "assets/media/styles/14_halftone-comic.mp4" in suggested and "assets/media/styles/07_paper-layers.mp4" \
        in suggested and "bold dots for the number" in suggested and v(14) in suggested
    gallery = html.split('class="sty-all"', 1)[1]
    assert gallery.count('loading="lazy"') == len(atlas_prompt.styles())               # the suggested ones marked
    values = re.findall(r'name="ovs-style" value="([^"]+)"', html)
    assert len(values) == len(set(values)) == len(atlas_prompt.styles())             # 2 suggested + 47 in the gallery
    offer = _built(tasting, built)["offer"]["taste"]["picks"]
    assert "g-low-poly" in offer["values"]


def test_a_style_picked_from_the_taste_gallery_goes_into_the_pack(tasting, capsys):
    from test_run_page_organic import _answered
    from tm.cli import main
    _taste_built(tasting)
    _answered(tasting, "taste", "taste_v01", "accept", picks={"style": "g-low-poly", "voice": "v1", "music": "none"})
    assert main(["page", "decision", "taste", "--run", str(tasting.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    picks = json.loads((tasting.path / out["files"]["taste"]).read_text(encoding="utf-8"))
    assert picks["style"] == organic_proposals.style_value(33)
    pack = json.loads((tasting.path / out["files"]["pack"]).read_text(encoding="utf-8"))
    assert pack["taste"]["style"] == organic_proposals.style_value(33)


def test_old_taste_options_keep_their_own_preview(tasting):
    from tm.organic_pages import taste
    opts_path = tasting.path / "03_wip" / "taste_options_v01.json"
    opts = json.loads(opts_path.read_text(encoding="utf-8"))
    (tasting.path / "02_research" / "look.jpg").write_bytes(b"made-up picture")
    opts["styles"] = [{"id": "house-look", "label": "Our house look", "preview": "02_research/look.jpg"}]
    opts_path.write_text(json.dumps(opts), encoding="utf-8")
    sec = next(s for s in taste.page_json(tasting)["sections"] if s["id"] == "style")
    assert sec["options"][0]["media"] == [{"src": "02_research/look.jpg", "caption": "Our house look"}]
    assert sec["options"][0]["label"] == "Our house look" and "style" not in sec["options"][0]
    assert len(sec["options"]) == 1 + len(atlas_prompt.styles())                     # and every style of ours to pick
