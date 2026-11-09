"""The posting kit (organic video, shared): `kit.check` on the reference ExampleEdu kits and on kits broken one
rule at a time, `kit.to_md`, and `tm kit check|md` with the context read from the run."""

import copy
import json

import pytest

import exampleedu
from tm import config, kit, manifest, stepchecks
from tm.cli import main
from tm.runfolder import RunFolder

PL = dict(language="pl", platforms=("tiktok", "instagram", "youtube", "facebook"), account_type="creator",
          product_level="not shown", ai_label="not_required")


def _ctx(**over):
    return kit.KitContext(**{**PL, **over})


def _what(problems):
    return " | ".join(f"{p.field}: {p.what}" for p in problems)


def _m1():
    return exampleedu.kit("M1_kit_v02")


@pytest.mark.private_data
def test_m1_kit_v02_passes():
    assert kit.check(_m1(), _ctx()) == []


@pytest.mark.private_data
def test_m1_kit_v01_with_sources_refused():
    problems = kit.check(exampleedu.kit("M1_kit_v01"), _ctx())
    fields = {p.field for p in problems}
    assert {"platforms.tiktok.caption", "platforms.instagram.caption", "platforms.youtube.description"} <= fields
    assert all("sources" in p.what for p in problems)


@pytest.mark.private_data
def test_m5_pl_kit_ai_host_label_required():
    m5 = exampleedu.kit("M5_pl_kit_v01")
    assert kit.check(m5, _ctx(ai_label="required")) == []
    m5["plugin"]["ai_label"] = False
    problems = kit.check(m5, _ctx(ai_label="required"))
    assert [p.field for p in problems] == ["plugin.ai_label"] and "must be on" in problems[0].what
    assert kit.check(m5, _ctx(ai_label="not_required")) == []


@pytest.mark.private_data
def test_instagram_sixth_hashtag_refused():
    k = _m1()
    k["platforms"]["instagram"]["hashtags"].append("#szkola")
    problems = kit.check(k, _ctx())
    assert [p.field for p in problems] == ["platforms.instagram.hashtags"] and "6 hashtags" in problems[0].what


@pytest.mark.private_data
def test_hashtag_counts_on_tiktok_youtube_facebook():
    k = _m1()
    k["platforms"]["tiktok"]["hashtags"] = ["#a", "#b"]
    k["platforms"]["facebook"]["hashtags"] = ["#a", "#b", "#c", "#d"]
    k["platforms"]["youtube"]["description"] = "Krótko. #a #b #c #d"
    assert {p.field for p in kit.check(k, _ctx())} == {"platforms.tiktok.hashtags", "platforms.facebook.hashtags",
                                                       "platforms.youtube.description"}


@pytest.mark.private_data
def test_youtube_title_101_chars_refused():
    k = _m1()
    k["platforms"]["youtube"]["title"] = "ą" * 100
    assert kit.check(k, _ctx()) == []                     # characters, not bytes
    k["platforms"]["youtube"]["title"] = "ą" * 101
    problems = kit.check(k, _ctx())
    assert [p.field for p in problems] == ["platforms.youtube.title"] and "101 characters" in problems[0].what


@pytest.mark.private_data
def test_instagram_first_line_126_refused():
    k = _m1()
    k["platforms"]["instagram"]["caption"] = "ł" * 125 + "\nDrugi wiersz może być długi."
    assert kit.check(k, _ctx()) == []
    k["platforms"]["instagram"]["caption"] = "ł" * 126 + "\nDrugi"
    problems = kit.check(k, _ctx())
    assert [p.field for p in problems] == ["platforms.instagram.caption"] and "126 characters" in problems[0].what


@pytest.mark.private_data
@pytest.mark.parametrize("caption", [
    "Zobacz to wideo. Skomentuj, co myślisz!", "Please tag a friend who games.", "Obserwuj po więcej o grach.",
    "Share this with every parent.", "Like if you agree", "Daj lajka jeśli tak",
    "Comments below please", "We are commenting", "Tags a friend", "Tagged someone", "Sharing this with you",
    "Follows for more", "Likes if you agree", "Skomentujcie niżej", "Oznaczcie znajomych", "Oznacz kogoś",
    "Udostępnijcie dalej", "Obserwujcie po więcej", "Dajcie lajka"])
def test_bait_refused(caption):
    k = _m1()
    k["platforms"]["facebook"]["caption"] = caption
    problems = kit.check(k, _ctx())
    assert [p.field for p in problems] == ["platforms.facebook.caption"] and "bait" in problems[0].what


@pytest.mark.private_data
def test_bait_and_two_questions_refused():
    k = _m1()
    k["platforms"]["tiktok"]["caption"] = "Co to jest brainrot? Czy Twoje dziecko go zna? A Ty? Skomentuj!"
    whats = _what(kit.check(k, _ctx()))
    assert "engagement bait" in whats and "more than one question" in whats
    k["platforms"]["tiktok"]["caption"] = "Co to jest brainrot? Czy Twoje dziecko go zna?"
    assert kit.check(k, _ctx()) == []                   # the hook question is the search phrase


@pytest.mark.private_data
def test_bait_is_a_word_not_a_substring():
    k = _m1()
    k["platforms"]["facebook"]["caption"] = "Ten commentary o grach pomaga."
    assert kit.check(k, _ctx()) == []


@pytest.mark.private_data
@pytest.mark.parametrize("text", ["Zobacz https://x.pl/a", "Wejdź na www.gry", "Strona gry.com jest dobra", "Pisz: ala@szkola.example.com"])
def test_links_and_domains_refused(text):
    k = _m1()
    k["platforms"]["facebook"]["caption"] = text
    assert "link or a domain" in _what(kit.check(k, _ctx()))
    k = _m1()
    k["platforms"]["tiktok"]["hashtags"][0] = "#gry.com"
    assert "link or a domain" in _what(kit.check(k, _ctx()))


@pytest.mark.private_data
def test_business_account_needs_commercial_alternative():
    k = _m1()
    k["plugin"]["trending_sound"] = {"name": "Sound X", "evidence": "https://example.test/x", "replaces_track": False}
    assert kit.check(k, _ctx(account_type="creator")) == []
    problems = kit.check(k, _ctx(account_type="business"))
    assert [p.field for p in problems] == ["plugin.business_alternative"]
    k["plugin"]["business_alternative"] = "Mixkit 595 Secret Garden"
    assert kit.check(k, _ctx(account_type="business")) == []


@pytest.mark.private_data
def test_replacing_sound_needs_the_nosound_file():
    k = _m1()
    k["plugin"]["trending_sound"] = {"name": "Sound X", "evidence": "e", "replaces_track": True}
    assert [p.field for p in kit.check(k, _ctx())] == ["video"]
    k["video"] = "04_final/M1_final_v01_nosound.mp4"
    assert kit.check(k, _ctx()) == []


@pytest.mark.private_data
def test_kit_language_must_be_audience_language():
    problems = kit.check(_m1(), _ctx(language="en"))
    assert [p.field for p in problems] == ["language"] and "'pl'" in problems[0].what


@pytest.mark.private_data
def test_only_the_ticked_platforms():
    k = _m1()
    k["plugin"]["platforms"] = ["tiktok", "youtube"]
    whats = _what(kit.check(k, _ctx()))
    assert "instagram, facebook, which is not ticked" in whats
    del k["platforms"]["instagram"], k["platforms"]["facebook"]
    assert kit.check(k, _ctx()) == []
    del k["platforms"]["youtube"]
    assert "has no youtube, which is ticked" in _what(kit.check(k, _ctx()))
    k["plugin"]["platforms"] = ["tiktok", "youtube"]
    assert "not among the run's platforms" in _what(kit.check(k, _ctx(platforms=("tiktok",))))


@pytest.mark.private_data
@pytest.mark.parametrize("level,ok", [("not shown", True), ("soft mention", True), ("incidental", False),
                                      ("featured", False), ("hero", False)])
def test_brand_disclosure_by_product_level(level, ok):
    k = _m1()
    assert (kit.check(k, _ctx(product_level=level)) == []) is ok
    k["platforms"]["tiktok"]["product"] = "Opis → Dodaj link → Twoja marka"
    assert kit.check(k, _ctx(product_level=level)) == []


@pytest.mark.private_data
def test_schema_and_plugin_shape_refused():
    k = _m1()
    del k["plugin"]
    assert [p.field for p in kit.check(k, _ctx())] == ["plugin"]
    k = _m1()
    k["plugin"]["ai_label"] = "yes"
    del k["id"]
    assert kit.check(k, _ctx())
    k = _m1()
    k["platforms"]["x"] = {}
    assert kit.check(k, _ctx())


@pytest.mark.private_data
def test_md_has_every_ticked_platform():
    k = _m1()
    text = kit.to_md(k, "pl")
    for name in ("TikTok", "Instagram Reels", "YouTube Shorts", "Facebook Reels"):
        assert f"## {name}" in text
    assert text.startswith("# Zestaw do publikacji M1 v02 (ExampleEdu)") and "#brainrot #rodzice" in text
    del k["platforms"]["instagram"], k["platforms"]["facebook"]
    en = kit.to_md({**k, "language": "en"}, "en")
    assert "## Instagram Reels" not in en and "## YouTube Shorts" in en and "# Posting kit M1 v02" in en
    assert "**Title:**" in en and "**AI label:**" in en
    k["plugin"]["trending_sound"] = {"name": "Sound X", "evidence": "e", "replaces_track": False}
    assert "Sound X" in kit.to_md(k, "en")


# --- the command line ---------------------------------------------------------------------------------

def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _run(tmp_path, *, output="script", proposal=True):
    run = exampleedu.build(tmp_path / "ws")
    cfg = config.load(run)
    cfg.update({"kind": "production", "output": output})
    config.save(run, cfg)
    if proposal:
        (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"product_level": "not shown"}), encoding="utf-8")
    (run.path / "04_final" / "kits").mkdir(parents=True, exist_ok=True)
    return run


def _write(run, data, name="M1_kit_v02.json"):
    (run.path / "04_final" / "kits" / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"04_final/kits/{name}"


@pytest.mark.private_data
def test_cli_check_reads_the_context_and_marks_the_file(tmp_path, capsys):
    run = _run(tmp_path)
    rel = _write(run, _m1())
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)
    assert (code, out["status"], out["platforms"]) == (0, "done", ["tiktok", "instagram", "youtube", "facebook"])
    assert stepchecks.fresh(RunFolder.open(run.path), "kit", "04_final/kits", "M1_kit", "json") is None
    k = _m1()
    k["language"] = "en"
    rel = _write(run, k, "M1_kit_v03.json")
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)
    assert code == 2 and out["status"] == "stop" and out["problems"][0]["field"] == "language"
    assert stepchecks.fresh(RunFolder.open(run.path), "kit", "04_final/kits", "M1_kit", "json")   # v03 not marked


@pytest.mark.private_data
def test_cli_flags_win_over_the_run(tmp_path, capsys):
    run = _run(tmp_path)
    rel = _write(run, exampleedu.kit("M5_pl_kit_v01") | {"id": "M5"}, "M5_kit_v01.json")
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel, "--ai-label", "required")
    assert code == 0
    k = exampleedu.kit("M5_pl_kit_v01")
    k["plugin"]["ai_label"] = False
    rel = _write(run, k, "M5_pl_kit_v02.json")
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel, "--ai-label", "required")
    assert code == 2
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel, "--product-level", "hero",
                     "--audience-language", "pl", "--ai-label", "not_required")
    assert code == 2 and "Your brand" in out["problems"][0]["what"]


@pytest.mark.private_data
def test_cli_product_level_from_the_proposal(tmp_path, capsys):
    run = _run(tmp_path)
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"product_level": "featured"}), encoding="utf-8")
    rel = _write(run, _m1())
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)
    assert code == 2 and out["problems"][0]["field"] == "platforms.tiktok.product"


@pytest.mark.private_data
def test_cli_stops_without_context(tmp_path, capsys):
    run = _run(tmp_path, proposal=False)
    rel = _write(run, _m1())
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)
    assert code == 2 and "product level" in out["message"]
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel, "--product-level", "not shown")
    assert code == 0
    video = _run(tmp_path / "v", output="ai_video")
    rel = _write(video, _m1())
    code, out = _cli(capsys, "kit", "check", "--run", str(video.path), "--file", rel)
    assert code == 2 and "--ai-label" in out["message"]


@pytest.mark.private_data
def test_cli_bad_file_is_a_stop_or_an_error(tmp_path, capsys):
    run = _run(tmp_path)
    (run.path / "04_final" / "kits" / "bad_kit_v01.json").write_text("{nope", encoding="utf-8")
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", "04_final/kits/bad_kit_v01.json")
    assert code == 2 and "not valid JSON" in out["message"]
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", "04_final/kits/none.json")
    assert code == 1
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}", encoding="utf-8")
    code, out = _cli(capsys, "kit", "check", "--run", str(run.path), "--file", str(outside))
    assert code == 1 and "not inside the run" in out["message"].replace("\\", "/")


@pytest.mark.private_data
def test_cli_md_writes_beside_the_json(tmp_path, capsys):
    run = _run(tmp_path)
    rel = _write(run, _m1())
    assert _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)[0] == 0
    code, out = _cli(capsys, "kit", "md", "--run", str(run.path), "--file", rel)
    assert (code, out["file"]) == (0, "04_final/kits/M1_kit_v02.md")
    written = (run.path / out["file"]).read_bytes()
    assert "## TikTok" in written.decode("utf-8") and b"\r" not in written   # written LF on every system


@pytest.mark.private_data
def test_cover_text_two_to_seven_words():
    k = _m1()
    for text, ok in (("Jedno", False), ("Dwa słowa", True), ("Czy twoje dziecko też zna ten trend?", True),
                     ("raz dwa trzy cztery pięć sześć siedem", True), ("raz dwa trzy cztery pięć sześć siedem osiem", False),
                     ("Smartfon przed snem? Sprawdź 👀", True), ("", True)):
        k["cover"]["text"] = text
        assert (kit.check(k, _ctx()) == []) is ok, text


@pytest.mark.private_data
def test_instagram_first_line_counts_without_the_carriage_return():
    k = _m1()
    k["platforms"]["instagram"]["caption"] = "ł" * 125 + "\r\nDrugi wiersz"
    assert kit.check(k, _ctx()) == []
    k["platforms"]["instagram"]["caption"] = "ł" * 126 + "\r\nDrugi"
    assert [p.field for p in kit.check(k, _ctx())] == ["platforms.instagram.caption"]
    k["platforms"]["instagram"]["caption"] = ""
    assert kit.check(k, _ctx()) == []


@pytest.mark.private_data
def test_every_brief_bait_phrase_has_its_form_and_commentary_passes():
    for words in kit.BAIT.values():
        for phrase in words:
            assert kit._BAIT_MATCH(phrase), phrase
    for honest in ("A commentary on games", "Komentarz eksperta", "oznaczenie wiekowe", "Udostępnienie danych"):
        k = _m1()
        k["platforms"]["facebook"]["caption"] = honest
        assert kit.check(k, _ctx()) == [], honest


@pytest.mark.private_data
@pytest.mark.parametrize("where,value", [("cover", "Okładka gry.com"), ("product", "Kup na www.sklep"),
                                         ("sound", "Dodaj dźwięk, oznacz znajomych")])
def test_platform_cover_product_and_sound_are_post_text(where, value):
    k = _m1()
    k["platforms"]["tiktok"][where] = value
    assert [p.field for p in kit.check(k, _ctx())] == [f"platforms.tiktok.{where}"]


@pytest.mark.private_data
def test_kit_level_cover_text_and_product_are_post_text():
    k = _m1()
    k["cover"]["text"] = "Zobacz gry.com teraz"
    k["product"] = "Źródła: x"
    assert {p.field for p in kit.check(k, _ctx())} == {"cover.text", "product"}


@pytest.mark.parametrize("caption,count", [
    ("Rośnie o 2.5 razy? Czy Twoje dziecko gra?", 1),
    ("Co to jest... brainrot? A Twoje dziecko?", 1),
    ("Co to jest…? A Ty? Naprawdę?", 2),
    ("Wersja 3.5? Dobra? Naprawdę?", 2),
    ("Zdanie bez pytania. Pierwsze? Drugie?", 2)])
def test_hook_question_is_found_by_the_first_sentence(caption, count):
    assert kit._questions(caption) == count


@pytest.mark.private_data
def test_filmed_by_person_needs_no_ai_label():
    m5 = exampleedu.kit("M5_pl_kit_v01")
    m5["plugin"]["ai_label"] = False
    assert kit.check(m5, _ctx(ai_label="required", filmed_by_person=True)) == []
    assert kit.check(m5, _ctx(ai_label="required")) != []


@pytest.mark.private_data
def test_context_of_a_script_is_filmed_and_uses_the_proposals_channel(tmp_path):
    run = _run(tmp_path)
    ctx = kit.context_of(run)
    assert ctx.filmed_by_person and ctx.ai_label == "not_required"
    brand_dir = run.path.resolve().parents[2]
    from tm import brand
    other = {**exampleedu.PROFILE, "channel": "Other", "audience_language": "en", "account_type": "business"}
    brand.save(brand_dir, other, run=run)
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"product_level": "not shown", "channel": "other"}),
                                                       encoding="utf-8")
    ctx = kit.context_of(run)
    assert (ctx.language, ctx.account_type) == ("en", "business")


@pytest.mark.private_data
def test_md_headings_are_the_templates():
    template = [ln for ln in exampleedu.kit_template().splitlines() if ln.startswith("## ")]
    assert template == [f"## {kit.PLATFORM_NAMES[p]}" for p in kit.PLATFORMS]
    assert [ln for ln in kit.to_md(_m1(), "en").splitlines() if ln.startswith("## ")] == template


@pytest.mark.private_data
def test_polish_labels_are_capitalised_and_distinct():
    pl = kit.LABELS["pl"]
    assert all(v[0].isupper() for v in pl.values())
    assert pl["caption"] != pl["description"]
    text = kit.to_md(_m1(), "pl")
    assert "**Okładka:**" in text and "**Opis posta:**" in text and "**Opis filmu:**" in text
    assert "okładka: `" in text and "produkt: brak" in text


@pytest.mark.private_data
def test_cli_md_records_its_row_and_never_writes_over(tmp_path, capsys):
    """PR B review Minor 2: the .md gets a manifest row with the kit as its parent (OV13), and a
    second tm kit md leaves the first .md as it is."""
    run = _run(tmp_path)
    rel = _write(run, _m1())
    assert _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)[0] == 0
    code, out = _cli(capsys, "kit", "md", "--run", str(run.path), "--file", rel)
    assert code == 0
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert (row["stage"], row["source"], row["parent"]) == ("04_final", "tm kit md", rel)
    md = run.path / out["file"]
    md.write_text("edited by hand\n", encoding="utf-8")
    code, again = _cli(capsys, "kit", "md", "--run", str(run.path), "--file", rel)
    assert code == 2 and "never written over" in again["message"]
    assert "04_final/kits/M1_kit_v02.md" in again["message"].replace("\\", "/")
    assert md.read_text(encoding="utf-8") == "edited by hand\n"
    assert [r["file"] for r in manifest.rows(run)].count(out["file"]) == 1


@pytest.mark.private_data
def test_cli_md_refuses_an_unchecked_or_changed_kit(tmp_path, capsys):
    run = _run(tmp_path)
    rel = _write(run, _m1())
    code, out = _cli(capsys, "kit", "md", "--run", str(run.path), "--file", rel)
    assert code == 2 and "has not passed tm kit check" in out["message"]
    assert _cli(capsys, "kit", "check", "--run", str(run.path), "--file", rel)[0] == 0
    changed = _m1()
    changed["platforms"]["facebook"]["caption"] = "Inny opis."
    _write(run, changed)
    assert _cli(capsys, "kit", "md", "--run", str(run.path), "--file", rel)[0] == 2
