"""The script to film (E3): the check, the page and its Markdown download.

The page is proven against the handoff's own packaged files for the ExampleEdu walkthrough (M5's English
script): `tm organic page script` gives the same index.html and .md (the reference tool under Python 3.12
gives them too). Files are compared as text, `\\r` stripped."""

import copy
import json

import pytest

import exampleedu
from tm import config, manifest, page, state, stepchecks
from tm.cli import main
from tm.organic_pages import script

REL = "03_wip/script_M5_en_v01.json"


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _run(tmp_path, page_lang="pl"):
    run = exampleedu.build(tmp_path / "ws")
    if page_lang != "pl":
        config.save(run, {**config.load(run), "page_lang": page_lang})
    return run


def _write(run, data, name="script_M5_en_v01.json"):
    path = run.path / "03_wip" / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _check(run, capsys, data=None, name="script_M5_en_v01.json"):
    path = _write(run, data or exampleedu.script(), name)
    return _cli(capsys, "organic", "script", "check", "--run", str(run.path), "--file", str(path))


def _problems(out) -> str:
    return out["message"].replace("\\", "/")


@pytest.mark.private_data
def test_script_page_and_md_rebuild_m5_en(tmp_path, capsys):
    run = _run(tmp_path)
    code, out = _check(run, capsys)
    assert code == 0, out
    assert script.built_gap(run) is not None                      # checked, not built yet
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path), "--file", REL)
    assert code == 0, out
    assert out["folder"] == "04_final/M5_script_en_v01" and out["markdown"] == "M5_script_v01.md"
    folder = run.path / out["folder"]
    html, md = exampleedu.script_package()
    assert (folder / "index.html").read_text(encoding="utf-8").replace("\r", "") == html
    assert (folder / "M5_script_v01.md").read_text(encoding="utf-8").replace("\r", "") == md
    assert [f["as"] for f in out["files"]] == ["index.html", "M5_script_v01.md"]
    assert script.checked_gap(run) is None and script.built_gap(run) is None
    rows = [r for r in manifest.rows(run) if r["source"] == script.SOURCE]
    assert [(r["file"], r["parent"]) for r in rows] == [("04_final/M5_script_en_v01", REL)]
    # a changed script is a gap again, and a second build is a new folder
    data = exampleedu.script()
    data["goal"] += " Again."
    _write(run, data)
    assert script.checked_gap(run) is not None and script.built_gap(run) is not None
    assert _check(run, capsys, data)[0] == 0
    assert script.built_gap(run) is not None
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path))   # default: the checked file
    assert code == 0 and out["folder"] == "04_final/M5_script_en_v02" and script.built_gap(run) is None


@pytest.mark.private_data
def test_script_id_is_the_production_runs_proposal(tmp_path, capsys):
    """PR B review Minor 4: in a production run started for an idea, the script is that idea's (the
    id compared case-insensitively); a run with no proposal recorded checks the file name only."""
    run = _run(tmp_path)
    s = state.load(run)
    s.organic = {**(s.organic or {}), "proposal": "m1"}
    state.save(run, s)
    code, out = _check(run, capsys)
    assert code == 2 and "started for m1" in out["message"] and "M5" in out["message"]
    s.organic["proposal"] = "m5"
    state.save(run, s)
    code, out = _check(run, capsys)
    assert code == 0, out


@pytest.mark.private_data
def test_page_needs_the_checked_script(tmp_path, capsys):
    run = _run(tmp_path)
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path))
    assert code == 2 and "No script is checked" in out["message"]
    _write(run, exampleedu.script())
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path), "--file", REL)
    assert code == 2 and "is done once" in out["message"]
    assert not (run.path / "04_final").exists() or not list((run.path / "04_final").glob("M5_script*"))
    assert _check(run, capsys)[0] == 0
    other = _write(run, exampleedu.script(), "script_M5_en_v02.json")
    assert other.is_file()
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path), "--file", "03_wip/script_M5_en_v02.json")
    assert code == 2 and "is done once" in out["message"]          # v02 is the latest and unchecked


@pytest.mark.private_data
def test_oversize_page_refused_before_anything_is_written(tmp_path, capsys, monkeypatch):
    run = _run(tmp_path)
    assert _check(run, capsys)[0] == 0
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 100)
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path))
    assert code == 2 and "too big to publish" in out["message"] and "Nothing was written" in out["message"]
    assert not list((run.path / "04_final").glob("M5_script*"))


@pytest.mark.private_data
def test_fact_without_source_refused(tmp_path, capsys):
    run = _run(tmp_path)
    data = exampleedu.script()
    del data["facts"][0]["source"]
    code, out = _check(run, capsys, data)
    assert code == 2 and "facts[0]" in out["message"] and "lacks source" in out["message"] and "OV14" in out["message"]
    data = exampleedu.script()
    data["facts"][0]["url"] = "  "
    code, out = _check(run, capsys, data)
    assert code == 2 and "Fact 1 has no url" in out["message"]
    assert script.checked_gap(run) is not None


@pytest.mark.private_data
def test_four_words_per_second_refused(tmp_path, capsys):
    run = _run(tmp_path)
    data = exampleedu.script()
    said, end = script.words_per_second(data)
    assert end == 16.0 and said == 45 and said / end <= 3.0
    data["shots"][1]["line"] += " " + " ".join(["more"] * 20)       # 65 words in 16 s: 4.1 a second
    code, out = _check(run, capsys, data)
    assert code == 2 and "words a second" in out["message"] and "4.1" in out["message"]
    cfg = config.load(run)
    cfg["qa"]["wps_max"] = 4.5                                      # the threshold is the config's
    config.save(run, cfg)
    assert _check(run, capsys, data)[0] == 0


@pytest.mark.private_data
def test_hook_on_screen_language_and_shape(tmp_path, capsys):
    run = _run(tmp_path)
    data = exampleedu.script()
    data["hook"]["on_screen"] = " "
    code, out = _check(run, capsys, data)
    assert code == 2 and "hook.on_screen" in out["message"]
    data = exampleedu.script()
    del data["plugin"]                                              # English on a Polish run without the user's words
    code, out = _check(run, capsys, data)
    assert code == 2 and "'en'" in out["message"] and "lang_request" in out["message"]
    data["plugin"] = {"lang_request": "  "}
    assert _check(run, capsys, data)[0] == 2
    assert _check(_run(tmp_path / "en", "en"), capsys, copy.deepcopy(exampleedu.script()) | {"plugin": {}})[0] == 0
    data = exampleedu.script()
    del data["shots"]
    code, out = _check(run, capsys, data)
    assert code == 2 and "shots" in out["message"]
    # the name says what the file holds
    code, out = _check(run, capsys, exampleedu.script(), "script_M6_en_v01.json")
    assert code == 2 and "'M6'" in out["message"]
    code, out = _check(run, capsys, exampleedu.script(), "script_M5_en_v1.json")
    assert code == 2 and "03_wip/script_<id>_<lang>_vNN.json" in _problems(out)


@pytest.mark.private_data
def test_generated_cost_names_its_price_file_and_date(tmp_path, capsys):
    run = _run(tmp_path)
    data = exampleedu.script()
    data["generate_instead"]["cost"] = {"usd": 1.46}
    code, out = _check(run, capsys, data)
    assert code == 2 and "names no price file and its date" in out["message"]
    data["generate_instead"]["cost"] = {"usd": 1.46, "price_file": "02_research/models/h3.json", "price_date": "last week"}
    assert _check(run, capsys, data)[0] == 2
    data["generate_instead"]["cost"]["price_date"] = "2026-11-06"
    assert _check(run, capsys, data)[0] == 0


@pytest.mark.private_data
def test_script_kit_needs_no_ai_label(tmp_path, capsys):
    run = _run(tmp_path)
    kit_of = script._kit_of(exampleedu.script())
    assert kit_of["plugin"]["ai_label"] is False and kit_of["language"] == "en"
    assert _check(run, capsys)[0] == 0                              # M5's kit says "Not needed (filmed by you)"
    ctx = script._kit_context(run, exampleedu.script())
    assert ctx.filmed_by_person is True and ctx.ai_label == "not_required" and ctx.language == "en"
    data = exampleedu.script()                                        # a platform rule still holds
    data["kit"]["tiktok"]["hashtags"] = ["#a"]
    code, out = _check(run, capsys, data)
    assert code == 2 and "kit.platforms.tiktok.hashtags" in out["message"]
    data = exampleedu.script()
    data["kit"]["facebook"]["caption"] += " Comment below!"
    code, out = _check(run, capsys, data)
    assert code == 2 and "kit.platforms.facebook.caption" in out["message"] and "bait" in out["message"]


@pytest.mark.private_data
def test_polish_ui_strings(tmp_path, capsys):
    run = _run(tmp_path)
    data = exampleedu.script()
    data["lang"] = "pl"                                             # the run's page language: no request needed
    del data["plugin"]
    code, out = _check(run, capsys, data, "script_M5_pl_v01.json")
    assert code == 0, out
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path))
    assert code == 0 and out["folder"] == "04_final/M5_script_pl_v01" and out["lang"] == "pl"
    folder = run.path / out["folder"]
    html = (folder / "index.html").read_text(encoding="utf-8")
    md = (folder / "M5_script_v01.md").read_text(encoding="utf-8")
    assert '<html lang="pl">' in html
    for word in ("Organiczne wideo AI · skrypt do nagrania", "⬇ Pobierz skrypt (.md)", "Lista ujęć", "Kadr:", "Akcja:",
                 "Wszystkie kwestie (prompter)", "Zestaw do publikacji", "Sprawdzenie faktów", "Instagram Reels"):
        assert word in html, word
    assert "Shot list" not in html and "Download script" not in html
    for word in ("## Lista ujęć", "## Wszystkie kwestie (prompter)", "## Nagrywanie", "## Montaż", "## Zestaw do publikacji"):
        assert word in md, word
    # the original's English table is the page of an English run
    en = _run(tmp_path / "en", "en")
    assert _check(en, capsys, exampleedu.script())[0] == 0
    assert _cli(capsys, "organic", "page", "script", "--run", str(en.path))[0] == 0
    assert "Shot list" in (en.path / "04_final" / "M5_script_en_v01" / "index.html").read_text(encoding="utf-8")
    assert script.UI["pl"]["pf"] == script.UI["en"]["pf"]          # platform names are the same in both languages


def test_the_two_checks_are_registered():
    assert stepchecks.NAMES["script_checked"] == "tm.organic_pages.script:checked_gap"
    assert stepchecks.NAMES["script_page_built"] == "tm.organic_pages.script:built_gap"   # E3 requires both (test_organic_flow)


HOSTILE = 'Zażółć "gęślą" jaźń & <b>x</b> \\ back </script> <!-- <script>alert(1)</SCRIPT> <!-- <ScRiPt'


@pytest.mark.private_data
def test_hostile_text_is_escaped_and_shown_literally(tmp_path, capsys):
    import html as htmllib
    import re

    run = _run(tmp_path)
    data = exampleedu.script()
    data["title"] = HOSTILE
    data["shots"][1]["line"] = HOSTILE
    data["facts"][0]["claim"] = HOSTILE
    data["facts"][0]["url"] = 'https://example.com/?a="1"&b=</script><!--<script>'
    data["kit"]["facebook"]["caption"] = HOSTILE.replace("<", "(").replace(">", ")")   # kit rules refuse markup-like links
    data["word_count"] = 45
    code, out = _check(run, capsys, data)
    assert code == 0, out
    code, out = _cli(capsys, "organic", "page", "script", "--run", str(run.path))
    assert code == 0, out
    text = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert len(re.findall(r"<script\b", text, re.IGNORECASE)) == 2        # the original's two elements, no more
    assert len(re.findall(r"</script>", text, re.IGNORECASE)) == 2
    assert "<!--" not in text                                              # nothing opens a comment or double-escape
    assert htmllib.escape(HOSTILE, quote=True) in text                     # shown literally, as text
    md_js = re.search(r"window\.__MD__ = (.*?); window\.__MDNAME__", text, re.S).group(1)
    md = (run.path / out["folder"] / "M5_script_v01.md").read_text(encoding="utf-8")
    assert json.loads(md_js.replace("<\\/", "</").replace("<\\!--", "<!--").replace("<\\", "<")) == md
    assert HOSTILE in md


@pytest.mark.private_data
def test_times_in_minutes_and_a_changed_page_language(tmp_path, capsys):
    data = exampleedu.script()
    data["shots"][-1]["time"] = "1:02–1:10"
    assert script.words_per_second(data)[1] == 70.0
    data["shots"][-1]["time"] = "12–16.5 s"
    assert script.words_per_second(data)[1] == 16.5
    run = _run(tmp_path / "en", "en")                    # an English run: no request needed
    s = exampleedu.script()
    s["plugin"] = {}
    assert _check(run, capsys, s)[0] == 0 and script.checked_gap(run) is None
    config.save(run, {**config.load(run), "page_lang": "pl"})   # the pages moved to Polish since the check
    gap = script.checked_gap(run)
    assert gap is not None and "'en'" in gap and "page_lang" in gap
    s["plugin"] = {"lang_request": "English version"}
    assert _check(run, capsys, s)[0] == 0 and script.checked_gap(run) is None
