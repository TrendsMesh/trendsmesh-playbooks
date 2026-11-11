"""tm.run_page (issue #19): Refresh an ad's one page per run, built from the run state at every check-in, with the
choice clicked on the page read back and recorded."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import yaml

from tm import config, flow, i18n, manifest, mcp_saves, page, review, run_page, state
from tm.cli import main
from tm.flow import set_level
from tm.run_page import template, words
from tm.runfolder import RunFolder
from tm.stops import Stop

ART_URL = "https://claude.ai/artifact/Ab3dEfGh1jKlMnOpQrStUv"
SRC = Path(run_page.__file__).parent


@pytest.fixture
def run(tmp_path):
    r = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = ["creative_brief", "edited_video", "ai_video", "live_test"]
    state.save(r, s)
    set_level(r, "every_step")
    return r


def _ask(run, checkin="G1", n=1, **extra) -> Path:
    body = {"checkin": checkin, "title": f"Pytanie {checkin} {n}", "lede": "Koszt wzrósł o **42%**.",
            "question": "Którą reklamę odświeżamy?", "context": "Ranking z ostatnich 4 tygodni.",
            "options": [{"choice": "ad1", "label": "Reklama 1", "means": "najwięcej do odzyskania", "recommended": True},
                        {"choice": "ad2", "label": "Reklama 2"}], **extra}
    path = run.path / "03_wip" / f"my_ask_{checkin}_{n}.json"
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def _decide(run, checkin, choice, at: str | None = None):
    s = state.load(run)
    s.decisions.append({"checkin": checkin, "choice": choice, "by": "user",
                        "at": at or (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat(timespec="seconds")})
    state.save(run, s)


def _html(run, built) -> str:
    return (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")


def _section(html, cls) -> str:
    m = re.search(rf'<section class="{cls}".*?</section>', html, re.S)
    return m.group(0) if m else ""


# --- the page from the run state -------------------------------------------------------------------

def test_a_run_without_asks_builds_a_page_with_nothing_open(run):
    built = run_page.build(run)
    assert built["folder"] == "04_final/run_page_v01" and built["open"] == [] and built["settled"] == 0
    html = _html(run, built)
    assert "Nothing to decide right now." in html and "<input" not in html
    assert built["capabilities"] == run_page.CAPABILITIES
    assert built["artifact"]["file_path"].endswith("index.html")
    assert ".build.json" not in json.dumps(built["artifact"])            # the build record is never published
    assert (run.path / built["folder"] / run_page.BUILD_FILE).is_file()


def test_the_open_check_in_is_the_only_active_decision_and_settled_ones_are_read_only(run):
    run_page.build(run, _ask(run, "G1"))
    _decide(run, "G1", "ad1")
    built = run_page.build(run, _ask(run, "G1b", options=[{"choice": "accept", "label": "Kobiety 25–34"}]))
    assert built["open"] == ["G1b"] and built["settled"] == 1
    html = _html(run, built)
    now = _section(html, "panel now")
    assert 'data-checkin="G1b" data-ask="G1b_v01"' in now and 'type="radio"' in now
    settled = _section(html, "settled")
    assert "Already settled (1)" in settled and "Pick the ad: Reklama 1" in settled
    assert "<input" not in settled and "<textarea" not in settled and "<button class=\"savebtn" not in settled
    assert html.index('class="panel now"') < html.index('class="settled"')     # new on top, settled below
    assert '<span class="n">1</span>' in settled and "2 · Audience" in now
    assert json.loads((run.path / built["folder"] / ".build.json").read_text())["open"] == {"G1b": "G1b_v01"}


def test_settled_stages_are_newest_first_and_rule_decisions_are_shown(run):
    _decide(run, "G1", "ad1", at="2026-11-05T10:00:00+00:00")
    s = state.load(run)
    s.decisions.append({"checkin": "G1a", "choice": "refresh", "by": "rule", "rule": "the R2 table",
                        "note": "hook rate fell", "at": "2026-11-05T11:00:00+00:00"})
    state.save(run, s)
    html = _html(run, run_page.build(run))
    settled = _section(html, "settled")
    assert settled.index("Diagnosis: refresh") < settled.index("Pick the ad: ad1")
    assert "by rule" in settled and "the R2 table" in settled and "hook rate fell" in settled


def test_an_ad_picked_in_chat_is_named_by_the_ranking(run):
    (run.path / "01_base" / "winner_ranking_v01.json").write_text(json.dumps({"ranking": ["a1"], "candidates": [
        {"ad_id": "a1", "name": "Spring video", "verdict": "fading", "peak": {"cpr": 4.1}, "latest": {"cpr": 6.2},
         "cost_increase": 0.51, "value_to_recover": 820}]}), encoding="utf-8")
    _decide(run, "G1", "a1")
    html = _html(run, run_page.build(run))
    assert "Pick the ad: Spring video" in html and "Source: 01_base/winner_ranking_v01.json" in html
    assert 'title="Source: 01_base/winner_ranking_v01.json">51.0%</td>' in html


def test_a_new_ask_reopens_a_decided_check_in(run):
    run_page.build(run, _ask(run, "G1"))
    _decide(run, "G1", "ad1", at="2000-01-01T00:00:00+00:00")         # decided before this ask was saved
    built = run_page.build(run)
    assert built["open"] == ["G1"]


def test_local_page_says_answer_in_chat_and_has_no_inputs(run, capsys):
    assert main(["page", "build", "--run", str(run.path), "--ask", str(_ask(run)), "--local", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["local"] is True and "capabilities" not in out and out["index"] in out["message"]
    html = _html(run, out)
    assert "This copy of the page can&#x27;t save choices. Answer in chat." in html
    assert "<input" not in html and "data-ask=" not in html
    assert '"local": true' in html


def test_page_escapes_everything(run):
    built = run_page.build(run, _ask(run, title="<script>alert(1)</script>", lede="Koszt **+42%** & <b>x</b>"))
    html = _html(run, built)
    assert '<html lang="en">' in html and "language_warning" not in built
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Koszt <b>+42%</b> &amp; &lt;b&gt;x&lt;/b&gt;" in html


def test_the_look_is_trendsmesh(run):
    html = _html(run, run_page.build(run))
    for token in ("#fff4e6", "#fffbf6", "#16110d", "#5a5049", "#ff4f8b", "#d6246e", "#ffe14a", "#eadfd2", "#c9bcae"):
        assert token in html
    assert "Bricolage+Grotesque" in html and "font-stretch: 78%" in html
    assert '<span class="pill dark">Refresh an ad</span>' in html and "<svg" in html


# --- the run's working language (tm.i18n) ------------------------------------------------------------

def _pseudo(text: str) -> str:
    return "PL·" + "".join(p if p.startswith("{") else p.upper() for p in re.split(r"(\{[^}]*\})", text))


@pytest.fixture
def polish_run(run, tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    (run.path / config.FILE).write_text(yaml.safe_dump({"languages": {"working": "pl", "market": "pl"}}),
                                        encoding="utf-8")
    return run


def _translate(tmp_path, drop=()):
    strings = {k: _pseudo(v) for k, v in i18n.english().items() if k.startswith("run_page.") and k not in drop}
    path = tmp_path / "i18n_pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)


def test_a_polish_run_builds_its_page_in_polish(polish_run, tmp_path, capsys):
    _translate(tmp_path)
    assert main(["page", "build", "--run", str(polish_run.path), "--ask", str(_ask(polish_run)), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lang"] == "pl" and "language_warning" not in out
    html = _html(polish_run, out)
    assert '<html lang="pl">' in html and "PL·SAVE NOTES" in html and "Save notes" not in html
    assert "PL·SAVED AT {time}" in html                          # filled on the page itself
    assert run_page.from_page_note("ok", "pl") == "ok PL·(FROM THE PAGE)"


def test_an_untranslated_working_language_builds_in_english_and_says_so(polish_run, tmp_path, capsys):
    _translate(tmp_path, drop=("run_page.decision.save_notes",))
    got = i18n.page_lang("pl", "run_page")
    assert got.lang == "en" and got.missing == ("run_page.decision.save_notes",)
    assert main(["page", "build", "--run", str(polish_run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lang"] == "en" and out["language_warning"] == got.warning and got.warning in out["message"]
    html = _html(polish_run, out)
    assert '<html lang="en">' in html and "PL·" not in html


def test_the_ask_has_no_language_of_its_own(run):
    with pytest.raises(Stop, match="'lang' is not a field"):
        run_page.build(run, _ask(run, lang="pl"))


# --- the ask -----------------------------------------------------------------------------------------

def test_a_bad_ask_is_refused_with_every_problem_and_nothing_saved(run):
    path = run.path / "03_wip" / "bad.json"
    path.write_text(json.dumps({"checkin": "VB", "title": "", "question": "Q", "colour": "red", "media": [{"file": "../x.mp4"}],
                                "options": [{"choice": "maybe", "label": "M", "recommended": True},
                                            {"choice": "approve", "label": "A", "recommended": True}]}), encoding="utf-8")
    with pytest.raises(Stop) as err:
        run_page.build(run, path)
    said = str(err.value)
    for part in ("'colour' is not a field", "title is needed", "'maybe' is not a choice of VB", "only one option",
                 "../x.mp4"):
        assert part in said
    assert not (run.path / run_page.ASKS).exists() and page.latest_folder(run, run_page.PAGE) is None
    with pytest.raises(Stop, match="not a check-in"):
        run_page.build(run, _ask(run, "Z9"))


def test_an_ask_adds_its_points_media_and_tables(run):
    (run.path / "03_wip" / "take 1.mp3").write_bytes(b"ID3")
    (run.path / "03_wip" / "credits.csv").write_text("item,credits\nline,1200\n", encoding="utf-8")
    built = run_page.build(run, _ask(run, points=["Głos: **klon**"], media=[{"file": "03_wip/take 1.mp3", "caption": "Ujęcie 1"}],
                                     data=[{"file": "03_wip/credits.csv", "title": "Kredyty"}]))
    html = _html(run, built)
    assert "<b>klon</b>" in html and 'src="assets/media/01_take_1.mp3"' not in html
    assert 'src="assets/media/01_take 1.mp3"' in html and "Ujęcie 1" in html
    assert (run.path / built["folder"] / "assets" / "media" / "01_take 1.mp3").is_file()
    assert "assets/media/01_take 1.mp3" in built["artifact"]["files"]
    assert 'title="Source: 03_wip/credits.csv">1\u2009200</td>' in html


# --- datasets and sources -----------------------------------------------------------------------------

def test_the_diagnosis_shows_its_numbers_with_their_source(run):
    (run.path / "04_final" / "diagnosis_v01.json").write_text(json.dumps({
        "stage": "hook", "refresh": True, "evidence": {"hook_rate": [0.31, 0.22], "cpm": [8.1, 9.0]},
        "also_seen": ["auction"], "target_stage": "hook",
        "ladder": {"peak": {"p50/p25": 0.6, "p75/p50": 0.7, "p95/p75": 0.5},
                   "latest": {"p50/p25": 0.58, "p75/p50": 0.71, "p95/p75": 0.49}, "dropped": []}}), encoding="utf-8")
    html = _html(run, run_page.build(run, _ask(run, "G1a", options=[{"choice": "refresh", "label": "Tylko początek"}])))
    assert "Hook rate (25% watched)" in html and "31.0% → 22.0% (-29%)" in html
    assert "Source: 04_final/diagnosis_v01.json" in html and "The start (hook)" in html
    assert 'class="tile sticker"' in html
    data = json.loads(re.search(r'<script type="application/json" id="tm-page">(.*?)</script>', html, re.S).group(1))
    assert all(d["source"] for d in data["datasets"].values())
    assert any(r.get("best") == 0.31 for d in data["datasets"].values() for r in d["rows"])


def test_money_and_test_plan_stages_read_run_json(run):
    s = state.load(run)
    s.budgets, s.spend, s.planned = {"voice_credits": 5000.0}, {"voice_credits": 1200.0}, {"voice_credits": 3000.0}
    s.test_plan = {"budget_total": 700.0, "per_day": 100.0, "days": 7, "min_events_per_variant": 50,
                   "thresholds": {"win": 0.1, "nested": {"x": 1}}, "calculation": "50 events at 14 per event"}
    state.save(run, s)
    vb = _html(run, run_page.build(run, _ask(run, "VB", options=[{"choice": "approve", "label": "Tak"}])))
    assert "Budgets in this run" in vb and "Voice credits" in vb and 'title="Source: run.json">1\u2009200</td>' in vb
    _decide(run, "VB", "approve")
    g10 = _html(run, run_page.build(run, _ask(run, "G10", options=[{"choice": "approve", "label": "Tak"}])))
    now = _section(g10, "panel now")
    assert "Test budget" in now and "Win and lose rules" in now and "50 events at 14 per event" in now
    assert "nested" not in now


def test_trend_cards_show_the_trendsmesh_fields(run):
    from tm import trends
    card = {"id": "t1", "kind": "hook_trend", "name": "what if i told you _", "formula": "a reveal opener",
            "status": "confirmed", "confidence": "high", "momentum": "rising", "creators": 31, "since": "2026-10-20",
            "languages": ["en", "pl"], "flags": ["one_video_leads"],
            "proof": [{"source": "TrendsMesh", "stands": "supports", "says": "31 creators in 14 days",
                       "links": ["https://www.tiktok.com/@a/video/1", "https://www.tiktok.com/@b/video/2"]}]}
    trends.save_answer(run, "get_trend", {"trend_id": "t1"}, card)
    trends.save_answer(run, "get_trend_videos", {"trend_id": "t1"}, {"videos": [
        {"asset_id": "v1", "hook_text": "what if i told you", "hook_source": "speech", "appears_at_s": 0, "views": 1200,
         "url": "https://www.tiktok.com/@a/video/1"},
        {"asset_id": "v2", "hook_text": "WHAT IF", "hook_source": "on_screen", "views": 90, "url": "javascript:x"}]})
    html = _html(run, run_page.build(run, _ask(run, "G2", options=[{"choice": "hook", "label": "Nowy początek"}])))
    assert "what if i told you _" in html and "Status: confirmed" in html and "Confidence: high" in html
    assert "Distinct creators" in html and "en, pl" in html and 'class="pill warn"' in html
    assert "What confirms it" in html and "31 creators in 14 days" in html
    assert "out of 2 videos read" in html and "On-screen text" in html
    assert 'href="https://www.tiktok.com/@a/video/1"' in html and "javascript:x" not in html.split("tm-page")[0]


def test_every_fixed_string_the_page_uses_is_in_the_table():
    keys = set()
    for f in SRC.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        keys |= set(re.findall(r'\bt\("([a-z0-9_.]+)"', text))
        keys |= {f"decision.{k}" for k in ("saving", "saved_at", "save_error", "cannot_save", "ready")}
    missing = [k for k in sorted(keys) if not k.endswith(".") and not words.has(k)]
    assert not missing, missing
    assert words.t("data.source", file="x.csv") == "Source: x.csv"
    assert words.label("col", "never_seen_field") == "Never seen field"


# --- the choice saved on the page ---------------------------------------------------------------------

def _artifact_list(*docs: dict) -> str:
    lines = [f'{len(docs)} document{"" if len(docs) == 1 else "s"} from collection "decisions":', "=== BEGIN ===",
             *(json.dumps({"id": d["id"], "data": d["data"], "version": 1, "updatedAt": "2026-11-11T19:37:51Z"})
               for d in docs), "=== END ==="]
    return "\n".join(lines)


def _publish(run):
    page.record_published(run, run_page.PAGE, page.artifact_id(ART_URL), "1700000001-abcd", ART_URL)


def _read(run, *docs, at="2999-01-01T00:00:00+00:00", **extra):
    whole = {"action": "list", "url": ART_URL, "collection": "decisions", "query": {"limit": 1000}, **extra}
    return mcp_saves.save(run, "ArtifactData", whole, {"raw": _artifact_list(*docs)}, at=at)


def _doc(checkin="G1", ask="G1_v01", choice="ad1", note='Bierzemy "jedynkę" { i już'):
    return {"id": checkin, "data": {"checkin": checkin, "ask": ask, "choice": choice, "label": "x", "note": note,
                                    "saved_at": "2026-11-11T14:23:00Z"}}


def test_the_choice_saved_on_the_page_is_read_and_recorded_from_the_page(run, capsys):
    for step in ("A0", "A0b"):                                  # the run is at G1's step
        flow.complete(run, step)
    run_page.build(run, _ask(run))
    _publish(run)
    _read(run, _doc(), _doc("G1a", "G1a_v09", "refresh"))     # another check-in's document is never this one's
    got = run_page.decision(run, "G1")
    assert (got["choice"], got["label"], got["note"]) == ("ad1", "Reklama 1", 'Bierzemy "jedynkę" { i już')
    assert main(["page", "decision", "G1", "--run", str(run.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["recorded_note"] == 'Bierzemy "jedynkę" { i już (from the page)'
    last = state.load(run).decisions[-1]
    assert (last["checkin"], last["choice"], last["by"], last["note"]) == ("G1", "ad1", "user", out["recorded_note"])
    with pytest.raises(Stop, match="already recorded"):
        run_page.decision(run, "G1")
    built = run_page.build(run)
    assert built["open"] == [] and "Pick the ad: Reklama 1" in _html(run, built)


def test_a_choice_made_on_an_earlier_version_of_the_question_is_refused(run):
    run_page.build(run, _ask(run))
    run_page.build(run, _ask(run, n=2))                        # the question asked again: G1_v02
    _publish(run)
    _read(run, _doc(ask="G1_v01"))
    with pytest.raises(Stop, match="earlier version of its question"):
        run_page.decision(run, "G1")


def test_a_read_from_before_the_latest_publish_is_refused(run):
    run_page.build(run, _ask(run))
    _publish(run)
    _read(run, _doc(), at="2000-01-01T00:00:00+00:00")
    with pytest.raises(Stop, match="before this page was published"):
        run_page.decision(run, "G1")


def test_the_page_must_be_published_with_the_question_on_it(run):
    run_page.build(run)                                         # published without the question
    _publish(run)
    run_page.build(run, _ask(run))
    _read(run, _doc())
    with pytest.raises(Stop, match="published before it"):
        run_page.decision(run, "G1")


def test_no_choice_a_filtered_read_and_an_unoffered_choice_are_refused(run):
    run_page.build(run, _ask(run))
    with pytest.raises(Stop, match="publish is not recorded"):
        run_page.decision(run, "G1")
    _publish(run)
    with pytest.raises(Stop, match="ArtifactData list"):
        run_page.decision(run, "G1")
    _read(run, _doc(choice="ad7"))
    with pytest.raises(Stop, match="not one the question offers"):
        run_page.decision(run, "G1")
    _read(run, at="2999-01-02T00:00:00+00:00")
    with pytest.raises(Stop, match="No choice for G1"):
        run_page.decision(run, "G1")
    _read(run, _doc(), at="2999-01-03T00:00:00+00:00", where=[["choice", "==", "ad1"]])
    with pytest.raises(Stop, match="where"):
        run_page.decision(run, "G1")
    assert main(["page", "decision", "G1", "--run", str(run.path)]) == 2


def test_the_page_script_saves_only_the_open_question_on_click():
    s = template.SCRIPT
    assert "db.doc('decisions/' + checkin)" in s and "v.ask === ask" in s
    assert "addEventListener('change'" in s and "save({note: note.value})" in s
    assert "cannot_save" in s and "isOwner" in s


# --- shared page rules -------------------------------------------------------------------------------

def test_a_reference_the_shell_rewrote_is_refused(run, tmp_path):
    assert page.mangled_blob_refs('src="/_blob/ab12" url(/_blob/x-1) see /_blob/ok') == []
    assert page.mangled_blob_refs('"C:/Program Files/Git/_blob/ab12"') == ["Files/Git/_blob/ab12"]
    assert page.mangled_blob_refs(r'"C:\Git\_blob\ab12"') != []
    folder = page.new_folder(run, "report")
    (folder / "index.html").write_text('<img src="C:/Program Files/Git/_blob/ab12">', encoding="utf-8")
    with pytest.raises(ValueError, match="MSYS_NO_PATHCONV=1"):
        page.files(folder)


def test_review_build_now_builds_the_run_page_locally(run, capsys):
    manifest.record(run, "03_wip/edit_v02.mp4", "wip", "ffmpeg", "01_base/orig.mp4", None, None, None, None,
                    "after (before: 01_base/orig.mp4)")
    (run.path / "03_wip" / "edit_v02.mp4").write_bytes(b"v")
    (run.path / "01_base" / "orig.mp4").write_bytes(b"v")
    _decide(run, "G5", "approve")
    assert main(["review", "build", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert Path(out["path"]).as_posix().endswith("run_page_v01/index.html") and "tm page build" in out["message"]
    html = Path(out["path"]).read_text(encoding="utf-8")
    assert "Before: 01_base/orig.mp4" in html and 'class="play"' in html and "<input class=\"seek\"" in html
    assert review.pairs(run) == [("01_base/orig.mp4", "03_wip/edit_v02.mp4")]
