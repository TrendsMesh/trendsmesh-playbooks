"""The Trend research page in the run's working language (issue #3): every fixed word of research_report.py's page
comes from the `report` area of data/i18n/en.yaml (and the month names from `common`); a language whose table lacks
any of them gets the English page and a warning in what `tm research report` says.

The made-up "Uroda, PL" run of test_research_report.py is in Polish (`language: pl`), so its working language is pl.
A pseudo-translation into pl (ROT13 of each English text, keeping placeholders and markup, behind "PL·") shows
whether any English text is left on the page: none of it can survive the translation.
"""

import codecs
import json
import re
import string
from html.parser import HTMLParser
from pathlib import Path

import pytest
import requests
import yaml

from test_research_report import _cfg, _fake_fetch, _picks_file, _read, _uroda, _write
from tm import i18n, page, research_growth, research_report
from tm.cli import main

AREAS = ("report", "common")
SOURCE = Path(research_report.__file__)
_PARTS = re.compile(r"(\{[^{}]*\}|<[^>]+>)")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("offline in tests")
    monkeypatch.setattr(page.requests, "get", no_network)


def _pseudo(text: str) -> str:
    """ROT13 of the words in swapped case ("Why" is "jUL", never the month "Jul"), the {placeholders} and <tags>
    kept, behind "PL·"."""
    return "PL·" + "".join(p if _PARTS.fullmatch(p) else codecs.encode(p, "rot13").swapcase()
                           for p in _PARTS.split(text))


def _translate(tmp_path, drop: tuple[str, ...] = ()) -> dict:
    strings = {k: _pseudo(v) for k, v in i18n.wanted("pl", AREAS).items() if k not in drop}   # Polish's forms too
    path = tmp_path / "i18n_pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)
    return strings


class _Text(HTMLParser):
    """What a reader sees: text outside <style> and <script>, and alt, title and aria-label."""

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("style", "script")
        self.parts += [v for k, v in attrs if k in ("alt", "title", "aria-label") and v]

    def handle_endtag(self, tag):
        self._skip -= tag in ("style", "script")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _seen(html_text: str) -> str:
    p = _Text()
    p.feed(html_text)
    return "\n".join(p.parts)


def _english_left(html_text: str) -> list[str]:
    """Each English text of the areas (its words between placeholders) still on the page."""
    seen = _seen(html_text)
    left = []
    for key, text in i18n.english().items():
        if key.split(".")[0] not in AREAS:
            continue
        for lit, _, _, _ in string.Formatter().parse(text):
            words = _PARTS.sub(" ", lit or "").strip(" .,:;()·→×%@'\"")
            whole = r"(?<![A-Za-z])" + re.escape(words) + r"(?![A-Za-z])"     # "Mar" is not in "Maseczki"
            if re.search(r"[A-Za-z]{3}", words) and re.search(whole, seen):
                left.append(f"{key}: {words!r}")
    return left


def _build(run, picks_path=None, **kw) -> str:
    folder = research_report.build(run, picks_path or run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run), **kw)
    return (folder / "index.html").read_text(encoding="utf-8")


# --- the table and the code -------------------------------------------------------------------------

def _keys_in_code() -> set[str]:
    found = re.findall(r"""["']((?:report|common)\.[a-z0-9_.]*[a-z0-9_])["']""", SOURCE.read_text(encoding="utf-8"))
    values = (research_report.BAND_KEY, research_report.CONFIDENCE_KEY, research_report.STATUS_KEY,
              research_report.KIND_KEY, research_report.WHY_KEY)
    return (set(found) - {"report.json"} | {k for keys in values for k in keys.values()}  # report.json: a file name
            | {research_report._V + "why_few_creators"})


def test_every_key_the_page_uses_is_in_the_table_and_every_report_key_is_used():
    counts = i18n.groups()
    en = {k.rpartition(".")[0] if k.rpartition(".")[0] in counts else k for k in i18n.english()}   # a count once
    used = _keys_in_code() | {f"common.month_{m}" for m in range(1, 13)}
    assert sorted(used - set(en)) == []
    assert sorted(k for k in en if k.startswith("report.") and k not in used) == []


def test_the_english_table_says_what_the_page_always_said():
    en = i18n.translator("en")
    assert {b: en(k) for b, k in research_report.LABEL_KEY.items()} == research_growth.LABEL
    assert research_report.VIEWS == {"report": "Category report", "digest": "Weekly digest", "paid": "Paid vs organic"}
    assert research_report.NO_ACT_NOW == "No trend reaches 'act now' this time."
    assert research_report.day("2026-11-18") == "18 Nov 2026"
    assert research_report.spread({"top_creator_share": 0.5}) == ("A few accounts", "top account 50% of views")


# --- a complete translation ---------------------------------------------------------------------------

def test_a_translated_page_is_in_the_working_language(tmp_path, monkeypatch):
    run, picks = _uroda(tmp_path)
    _translate(tmp_path)
    tr = i18n.translator("pl")
    _fake_fetch(monkeypatch)                                   # thumbnails, so their "views · date" shows
    text = _build(run, _picks_file(run, {**picks, "as_of": "2026-08-10"}))
    assert '<html lang="pl">' in text and 'lang="en"' not in text
    assert tr("report.h1", category="Uroda") in text and tr("report.view_digest") in text
    assert f"1 {tr('common.month_8')} 2026" in text                            # the months too
    assert _english_left(text) == []
    # report.json stays the original's data, in English
    report = _read(run.path / "04_final" / "report_v01" / "report.json")
    assert report["valid_until"] == "24 Aug 2026"
    assert report["paid"]["checks"][picks["act_now"][0]["id"]]["verdict"] == "A few advertisers"


def test_every_digest_and_paid_text_is_translated(tmp_path):
    """The rebuilt previous week, ended trends not checked and an unchecked Ad Library: the other branches."""
    run, picks = _uroda(tmp_path, act_now=False)
    _translate(tmp_path)
    prev = run.path / "02_research" / "snapshot_growth_2026-10-28_rebuilt_v01.json"
    _write(prev, {"params": {"as_of": "2026-10-28", "ref": "2026-10-26"}, "trends": {}, "rebuilt": True})
    digest = _read(run.path / "02_research" / "digest_v01.json")
    _write(run.path / "02_research" / "digest_v02.json", {**digest, "plugin": {"ended_checked": False}})
    _write(run.path / "02_research" / "ad_library_summary_v02.json", {"checked": False, "checks": []})
    text = _build(run, prev_snapshot=prev)
    assert '<html lang="pl">' in text and i18n.t("report.no_act_now", "pl") in text
    assert i18n.t("report.ended_rebuilt", "pl") in text
    assert _english_left(text) == []


def test_the_report_command_says_nothing_of_language_when_the_table_is_complete(tmp_path, capsys):
    run, _ = _uroda(tmp_path)
    _translate(tmp_path)
    assert main(["research", "report", "--run", str(run.path), "--picks", "03_wip/picks_v01.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "language_warning" not in payload and "English" not in payload["message"]
    assert '<html lang="pl">' in (run.path / payload["folder"] / "index.html").read_text(encoding="utf-8")


# --- an incomplete one ----------------------------------------------------------------------------------

def test_an_incomplete_table_builds_in_english_and_says_so(tmp_path, capsys):
    run, _ = _uroda(tmp_path)
    _translate(tmp_path, drop=("report.footer",))
    assert main(["research", "report", "--run", str(run.path), "--picks", "03_wip/picks_v01.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    warning = payload["language_warning"]
    assert "built in English" in warning and "Polish" in warning and "tm i18n export --lang pl" in warning
    assert warning in payload["message"]
    text = (run.path / payload["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in text and "What is moving in Uroda" in text and "PL·" not in text


def test_no_table_at_all_builds_in_english_and_says_so(tmp_path, capsys):
    run, _ = _uroda(tmp_path)
    assert main(["research", "report", "--run", str(run.path), "--picks", "03_wip/picks_v01.json"]) == 0
    out = capsys.readouterr().out
    assert "The page is built in English" in out and "tm i18n export --lang pl" in out


def test_a_table_without_the_month_names_builds_in_english(tmp_path):
    run, _ = _uroda(tmp_path)
    _translate(tmp_path, drop=("common.month_11",))
    text = _build(run)
    assert '<html lang="en">' in text and "As of 4 Nov 2026" in text
    assert len(_english_left(text)) > 50                       # the check above finds English where there is some


# --- counts and stored values (issue #3, items 3 and 4) ------------------------------------------------

def _translate_forms(tmp_path) -> None:
    """The pseudo-translation with each form of a count marked by its category (ONE·, FEW·, MANY·)."""
    strings = {k: (k.rpartition(".")[2].upper() + "·" if k.rpartition(".")[0] in i18n.groups() else "") + _pseudo(v)
               for k, v in i18n.wanted("pl", AREAS).items()}
    path = tmp_path / "i18n_pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)


def test_the_counts_take_the_polish_form_of_their_number(tmp_path):
    run, _ = _uroda(tmp_path)
    _translate_forms(tmp_path)
    tr = i18n.translator("pl")
    text = _build(run)
    # 1 trend to act on (one), 3 topics (few), 0 hooks (many), 30 creators (many), 20 videos (many), 4 relevant (few)
    for key, n, values, form in (("report.lede", 1, {"n": "1"}, "ONE·"),
                                 ("report.meta_topics", 3, {"n": 3}, "FEW·"),
                                 ("report.meta_hooks", 0, {"n": 0}, "MANY·"),
                                 ("report.reach_videos", 20, {"videos": 20}, "MANY·"),
                                 ("report.mapped_split", 4, {"n": 4, "root": "Uroda"}, "FEW·")):
        shown = tr.plural(key, n, **values)
        assert shown.startswith(form), key
        assert shown in text or research_report.E(shown) in text, key
    assert "FEW·" in tr.plural("report.act_on", 3, n="trzy") and "MANY·" in tr.plural("report.act_on", 5, n="pięć")
    assert "MANY·" in tr.plural("report.act_on", 12, n="12") and "FEW·" in tr.plural("report.act_on", 22, n="22")


def test_stored_values_are_shown_in_the_page_language_and_stay_stored(tmp_path):
    run, _ = _uroda(tmp_path)
    _translate(tmp_path)
    tr = i18n.translator("pl")
    text = _build(run)
    for key in ("report.value.band_top_10", "report.value.confidence_medium", "report.value.status_confirmed",
                "report.value.kind_topic"):
        assert research_report.E(tr(key)) in text, key
    assert ">top 10%<" not in text and ">medium<" not in text and "status confirmed" not in text
    assert "k-topic" in text and "conf-medium" in text                     # the classes keep the stored value
    growth = _read(run.path / "02_research" / "growth_v01.json")
    assert growth["trends"][0]["relative"]["band"] == "top 10%" and growth["trends"][0]["confidence"] == "medium"


def test_a_stored_value_shows_translated_or_as_it_is():
    tr = i18n.translator("en")
    assert research_report.shown("top 25%", research_report.BAND_KEY, tr) == "top 25%"
    assert research_report.shown("Top 5%", research_report.BAND_KEY, tr) == "Top 5%"        # not a known value
    assert research_report.shown(None, research_report.STATUS_KEY, tr) is None
    assert research_report.why("only 1 creators in evidence", tr) == "only 1 creator in evidence"
    assert research_report.why("only 4 creators in evidence", tr) == "only 4 creators in evidence"
    assert research_report.why("12 twórców", tr) == "12 twórców"
    assert research_report.why("some limits: see the risk line", tr) == "some limits: see the risk line"


def test_the_english_value_words_are_the_stored_values():
    """English pages show what they always showed: each value's English is the value research_growth stores."""
    en = i18n.translator("en")
    for keys in (research_report.BAND_KEY, research_report.CONFIDENCE_KEY, research_report.STATUS_KEY,
                 research_report.KIND_KEY, research_report.WHY_KEY):
        assert {v: en(k) for v, k in keys.items()} == {v: v for v in keys}
    th = research_growth.Thresholds.from_config({})
    for g, status in (({"creators": 1}, None), ({"creators": 99, "top_creator_share": 0.99}, None),
                      ({"creators": 99, "top_creator_share": 0.0}, "confirmed"),
                      ({"creators": 99, "top_creator_share": 0.0}, None)):
        level, said = research_growth.confidence(g, status, th)
        assert level in research_report.CONFIDENCE_KEY
        assert said in research_report.WHY_KEY or research_report._FEW_CREATORS.fullmatch(said), said
    for below in (95, 80, 60, 10):                         # the share of the pool below the trend
        pool = [0] * below + [9] * (100 - below)
        assert research_growth.relative({"new_recent": 1}, {"median_new": 1}, pool)["band"] in research_report.BAND_KEY


def test_a_hooks_band_by_its_rising_place_counts_the_rising_hooks_in_polish(tmp_path):
    """Issue #58's band ("Top 10% of TrendsMesh's 101 rising hooks") on the plural forms and the stored band."""
    _translate_forms(tmp_path)
    tr = i18n.translator("pl")
    pg = research_report._Page(None, tmp_path, category="Uroda", market="PL", as_of=None, sample={},
                               trends_by_id={}, paid={}, paid_checked=False, tr=tr)
    for n, form in ((22, "FEW·"), (101, "MANY·"), (1, "ONE·")):
        hook = {"kind": "hook_trend", "relative": {"band": "top 10%", "rising_of": n, "velocity_index": 1}}
        said = pg.momentum(hook)[0]
        assert said.startswith(form) and str(n) in said and tr("report.value.band_top_10")[:4] in said, said
    no_band = pg.momentum({"kind": "hook_trend", "relative": {"band": None, "rising_of": 40}})[0]
    assert no_band == tr("report.band_not_rising")
    en = research_report._Page(None, tmp_path, category="Uroda", market="PL", as_of=None, sample={},
                               trends_by_id={}, paid={}, paid_checked=False)
    assert en.momentum({"kind": "hook_trend", "relative": {"band": "top 10%", "rising_of": 101}})[0] == \
        "Top 10% of TrendsMesh's 101 rising hooks"
