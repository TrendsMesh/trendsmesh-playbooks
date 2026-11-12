"""Organic AI video's check-in pages on the shared run page (issue #60): the images, the takes, the delivery page and
the style, voice and music as stages of the one page per run, built from made-up run files, and the answer saved
there read back by `tm page decision` and written as the organic pages' readers write it."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from tm import checkins, flow, i18n, manifest, organic_gates, organic_pack, organic_specs, page, run_page, state
from tm import stepchecks
from tm.cli import main
from tm.organic_pages import choices, gate as gate_page
from tm.playbooks import ORGANIC_VIDEO
from tm.run_page import organic_video, template, words
from tm.runfolder import RunFolder
from tm.stops import Stop

from test_run_page import _artifact_list, _publish, _read  # noqa: F401  (_artifact_list: the read's shape)

FIXTURES = Path(__file__).parent / "fixtures" / "organic"
PNG = b"\x89PNG\r\n\x1a\n made-up image bytes"


@pytest.fixture(autouse=True)
def no_downloads(monkeypatch):
    monkeypatch.setattr(page, "fetch_image", lambda url, dest, timeout=30: False)


def _new(tmp_path, level="every_step", lang=None):
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.level, s.outputs, s.budgets = level, ["organic_video"], {"ai_usd": 5.0}
    state.save(run, s)
    if lang:
        (run.path / "config.yaml").write_text(f"languages:\n  working: {lang}\n  market: {lang}\n", encoding="utf-8")
    return run


def _pack(run, n=1):
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    path = run.path / "03_wip" / f"pack_v{n:02d}.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="pack")
    return pack


def _record(run, stem, n, outputs):
    wip = run.path / "03_wip"
    (wip / f"{stem}_v{n:02d}.run.json").write_text(json.dumps(
        {"model": "m", "status": "done", "prediction_id": f"p{n}", "outputs": outputs}), encoding="utf-8")
    for name in outputs:
        (wip / name).write_bytes(PNG if name.endswith(".png") else b"made-up video bytes")


def _to(run, checkin):
    """Walk the flow (every step check passing) up to `checkin`'s ask."""
    real = stepchecks.run
    stepchecks.run = lambda name, folder: None
    try:
        for _ in range(80):
            nxt = flow.next(run)
            if nxt.action in ("ask", "auto", "work") and nxt.checkin and checkin in nxt.checkin.ids:
                return
            if nxt.action == "work" and nxt.checkin:                  # a check-in decided before `tm done`
                cat = checkins.load(playbook=ORGANIC_VIDEO)
                for cid in nxt.checkin.ids:
                    flow.decide(run, cid, cat.checkins[cid].choices[0], by="user", note=None)
                flow.complete(run, nxt.step)
            elif nxt.action == "work":
                flow.complete(run, nxt.step)
            elif nxt.action in ("ask", "auto"):
                cat = checkins.load(playbook=ORGANIC_VIDEO)
                for cid in nxt.checkin.ids:
                    flow.decide(run, cid, cat.checkins[cid].choices[0], by="user", note=None)
            else:
                raise AssertionError(nxt)
    finally:
        stepchecks.run = real
    raise AssertionError("never reached " + checkin)


def _ask(run, checkin, n=1, **extra):
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    body = {"checkin": checkin, "title": f"{checkin}: made-up title", "question": "Shall we go on?",
            "options": [{"choice": c, "label": c.capitalize()} for c in cat.checkins[checkin].choices], **extra}
    path = run.path / "03_wip" / f"my_ask_{checkin}_{n}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _html(run, built) -> str:
    return (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")


def _built(run, built) -> dict:
    return json.loads((run.path / built["folder"] / run_page.BUILD_FILE).read_text(encoding="utf-8"))


def _paths(html) -> set[str]:
    return {json.loads(p.replace("&quot;", '"'))[0] for p in re.findall(r'data-detail="([^"]+)"', html)}


def _doc(checkin, ask, choice, note="", **detail_):
    return {"id": checkin, "data": {"checkin": checkin, "ask": ask, "choice": choice, "label": "x", "note": note,
                                    "detail": detail_, "saved_at": "2026-11-11T14:23:00Z"}}


@pytest.fixture
def images(tmp_path):
    """A production run at Check every step at its images check-in: the checked pack, two host images made."""
    run = _new(tmp_path)
    _pack(run)
    _record(run, "host", 1, ["host_v01_0.png", "host_v01_1.png"])
    _to(run, "images")
    return run


# --- the stage -------------------------------------------------------------------------------------

def test_the_images_check_in_is_a_stage_of_the_run_page_in_its_look(images):
    built = run_page.build(images, _ask(images, "images"))
    html = _html(images, built)
    assert built["open"] == ["images"] and built["capabilities"] == run_page.CAPABILITIES
    assert "theme" not in built and 'class="top"' in html and "Organic AI video" in html     # the top bar and its pill
    assert "--accent:#B7791F" not in html and "Source+Sans" not in html                     # never the old look
    now = html.split('<section class="decision"')[0]
    assert "Images: host" in now or "Obrazy: host" in now                                    # the pack's words
    assert now.count('name="ovc-images-host"') == 2 and now.count("ova-images-host") == 3   # 2 options, 3 actions
    assert _paths(html) == {"choices", "actions", "notes"}
    offer = _built(images, built)["offer"]["images"]
    assert offer["actions"] == {"type": "each", "keys": ["images-host"], "values": ["accept", "redo", "drop"]}
    assert set(offer["choices"]["values"]) == {"host_v01_0", "host_v01_1"}
    shown = re.findall(r'src="(assets/media/[^"]+)"', html)
    assert len(shown) == 2 and all((images.path / built["folder"] / s).is_file() for s in shown)


def test_the_build_keeps_the_stage_data_as_a_build_of_the_page_it_replaces(images):
    built = run_page.build(images, _ask(images, "images"))
    rows = [r for r in manifest.rows(images) if r["source"] == "tm organic page gate_images"]
    assert [r["file"] for r in rows] == [built["folder"]]
    assert rows[0]["parent"].startswith("03_wip/gates/gate_images_v")
    decided = organic_gates.decided_page(images, "gate_images", folder=built["folder"])
    assert [it["id"] for it in decided["data"]["items"]] == ["images-host"]


def test_a_local_page_shows_the_items_without_inputs(images):
    html = _html(images, run_page.build(images, _ask(images, "images"), local=True))
    assert "host_v01_0" in html and "data-detail=\"" not in html and "ov-rest\"" not in html


def test_every_organic_page_word_is_in_both_tables():
    en, pl = i18n.table("en"), i18n.table("pl")
    src = Path(organic_video.__file__).read_text(encoding="utf-8")
    literal = {"organic." + k for k in re.findall(r'_w\((?:ctx|lang), "([a-z_.]+)"', src) if not k.endswith(".")}
    assert literal <= organic_video.keys()                   # every word it reads is listed
    for key in organic_video.keys():
        assert key in en and key in pl, key
    for key in words.TEMPLATE:
        assert any(k.startswith(f"run_page.{key}") for k in pl), key
    assert "run_page.playbook.organic_video" in pl


def test_a_polish_run_builds_a_polish_page_from_the_plugins_own_words(tmp_path):
    run = _new(tmp_path, lang="pl")
    _pack(run)
    _record(run, "host", 1, ["host_v01_0.png"])
    _to(run, "images")
    built = run_page.build(run, _ask(run, "images"))
    html = _html(run, built)
    assert built["lang"] == "pl" and "language_warning" not in built
    assert 'lang="pl"' in html and "Organiczne wideo AI" in html and "Akceptuj" in html and "Obrazy" in html
    assert "Twoja uwaga (opcjonalnie)" in html and "Uwaga dla Claude" in html          # the template's, the item's
    assert "Your note (optional)" not in html and "Note for Claude" not in html and "Accept the rest" not in html


def test_the_page_language_needs_only_the_templates_words_and_the_organic_area(tmp_path, monkeypatch):
    run = _new(tmp_path, lang="pl")
    real = i18n.missing
    monkeypatch.setattr(i18n, "missing", lambda lang, areas=(): real(lang, areas) + (
        ["run_page.stage.someone_elses"] if "run_page" in areas else []))
    assert words.page_lang(run).lang == "pl"                 # another playbook's stage words are not this page's
    monkeypatch.setattr(i18n, "missing", lambda lang, areas=(): real(lang, areas) + (
        ["run_page.decision.saving"] if "run_page" in areas else []))
    got = words.page_lang(run)
    assert got.lang == "en" and got.warning and "run_page.decision.saving" in got.missing


# --- the answer, recorded ----------------------------------------------------------------------------

def _answered(run, checkin, ask, choice, **detail_):
    _publish(run)
    _read(run, _doc(checkin, ask, choice, **detail_))


def test_an_answer_on_the_images_stage_is_written_as_the_images_page_writes_it(images, capsys):
    run_page.build(images, _ask(images, "images"))
    _answered(images, "images", "images_v01", "accept", actions={"images-host": "accept"},
              choices={"images-host": "host_v01_1"}, notes={"images-host": "the second one, warmer light"})
    assert main(["page", "decision", "images", "--run", str(images.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["recorded_note"].splitlines()[0] == "Images: host: Accept (host_v01_1)" or \
        "Accept (host_v01_1)" in out["recorded_note"]
    assert out["recorded_note"].endswith("(from the page)")
    assert "decisions_gate_images_v01.json" in out["message"]
    body = json.loads((images.path / out["files"]["decisions"]).read_text(encoding="utf-8"))
    assert body["source"] == "page" and body["carried"] == [] and body["folder"].startswith("04_final/run_page_v")
    row = body["decisions"]["images-host"]
    assert (row["action"], row["file"], row["note"]) == ("accept", "03_wip/host_v01_1.png", "the second one, warmer light")
    picks = organic_specs.page_image_rows(images)                   # the accept is the image's pick, dated by the build
    assert [(p["file"], p["by"]) for p in picks] == [("03_wip/host_v01_1.png", "user")] and picks[0]["at"]
    last = state.load(images).decisions[-1]
    assert (last["checkin"], last["choice"], last["by"]) == ("images", "accept", "user")


def test_a_redo_with_a_note_is_the_users_request(images, capsys):
    run_page.build(images, _ask(images, "images"))
    _answered(images, "images", "images_v01", "redo", actions={"images-host": "redo"},
              choices={"images-host": "host_v01_0"}, notes={"images-host": "no glasses, please"})
    assert main(["page", "decision", "images", "--run", str(images.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "redo request" in out["message"] and "Notes are the user's words" in out["message"]
    redos = state.load(images).organic["redos"]["host"]
    assert redos[-1]["note"] == "no glasses, please" and redos[-1]["by"] == "user"


def test_an_option_of_another_item_or_not_offered_is_refused_before_anything_is_recorded(images):
    run_page.build(images, _ask(images, "images"))
    _answered(images, "images", "images_v01", "accept", actions={"images-host": "maybe"})
    with pytest.raises(Stop, match="did not offer"):
        run_page.record(images, "images")
    assert all(d["checkin"] != "images" for d in state.load(images).decisions)


def test_the_answer_is_read_against_the_build_that_was_published(images, capsys):
    first = run_page.build(images, _ask(images, "images"))
    _publish(images)                                                   # the first build is the one published
    _record(images, "host", 2, ["host_v02_0.png"])                     # a later build shows more
    run_page.build(images)
    _read(images, _doc("images", "images_v01", "accept", actions={"images-host": "accept"},
                       choices={"images-host": "host_v01_0"}))
    got = run_page.record(images, "images")
    body = json.loads((images.path / got["files"]["decisions"]).read_text(encoding="utf-8"))
    assert body["folder"] == first["folder"]


def test_a_settled_stage_shows_what_was_decided_read_only(images, capsys):
    run_page.build(images, _ask(images, "images"))
    _answered(images, "images", "images_v01", "accept", actions={"images-host": "accept"},
              choices={"images-host": "host_v01_1"})
    run_page.record(images, "images")
    html = _html(images, run_page.build(images))
    settled = html.split('<section class="settled">')[1]
    assert "data-detail=\"" not in html and "host_v01_1.png" in settled and "ov-rest\"" not in html


def test_the_publish_guard_holds_while_people_decide_and_the_record_lifts_it(images):
    run_page.build(images, _ask(images, "images"))
    _publish(images)
    page.await_(images, run_page.PAGE, "1700000001-abcd")
    with pytest.raises(page.Deciding):
        run_page.build(images)
    _read(images, _doc("images", "images_v01", "accept", actions={"images-host": "accept"},
                       choices={"images-host": "host_v01_0"}))
    run_page.record(images, "images")
    assert page.awaiting(images, run_page.PAGE) is None
    run_page.build(images)


def test_a_video_over_15mb_is_shown_as_its_720p_preview(tmp_path, monkeypatch):
    from tm.tools import deliver
    run = _new(tmp_path)
    _pack(run)
    _record(run, "host", 1, ["host_v01_0.png"])
    _record(run, "take", 1, ["take_v01_0.mp4"])
    with open(run.path / "03_wip" / "take_v01_0.mp4", "wb") as fh:
        fh.truncate(gate_page.VIDEO_MAX_BYTES + 1)
    made = []

    def preview(r, path):
        out = deliver.preview_of(r, path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"a small preview")
        made.append(out.name)
        return out
    monkeypatch.setattr(deliver, "make_preview", preview)
    _to(run, "video")
    built = run_page.build(run, _ask(run, "video"))
    assert made == ["take_v01_0_720p.mp4"]
    html = _html(run, built)
    assert "take_v01_0_720p.mp4" in html and not any("take_v01_0.mp4" in s for s in re.findall(r'src="([^"]+)"', html))
    _answered(run, "video", "video_v01", "accept", actions={"takes-take": "accept"}, choices={"takes-take": "take_v01_0"})
    run_page.record(run, "video")
    settled = _html(run, run_page.build(run)).split('<section class="settled">')[1]
    shown = re.findall(r'src="([^"]+)"', settled)
    assert any(s.endswith("take_v01_0_720p.mp4") for s in shown) and not any(s.endswith("take_v01_0.mp4") for s in shown)


# --- the delivery page: the posting kit, the platform ticks --------------------------------------------

def _delivered(run):
    for rel in ("04_final/M5_final_v01.mp4", "04_final/M5_final_v01_upload.mp4", "04_final/kits/cover_M5_v01.jpg"):
        (run.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (run.path / rel).write_bytes(b"made-up " + rel.encode("utf-8"))
    kit = {"id": "M5", "version": "v1", "date": "2026-11-07", "channel": "made-up channel",
           "video": "04_final/M5_final_v01.mp4", "platforms": {
        "tiktok": {"caption": "A made-up caption line", "hashtags": ["#madeup"], "cover": "frame 2",
                   "ai_label": "on", "sound": "original"},
        "youtube": {"title": "A made-up title", "description": "A made-up description", "hashtags": ["#madeup"],
                    "tags": ["made", "up"], "cover": "frame 2", "ai_label": "on"}},
        "search_phrase": "made up phrase"}
    (run.path / "04_final" / "kits" / "M5_kit_v01.json").write_text(json.dumps(kit), encoding="utf-8")


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    run = _new(tmp_path)
    _pack(run)
    _record(run, "host", 1, ["host_v01_0.png"])
    _delivered(run)
    monkeypatch.setattr(organic_gates.organic_final, "idea_id", lambda r: "M5")
    _to(run, "final_edit")
    return run


def test_the_delivery_stage_has_one_text_per_platform_to_copy_and_the_ticks(delivery):
    built = run_page.build(delivery, _ask(delivery, "final_edit"))
    html = _html(delivery, built)
    assert html.count('class="ov-copy"') >= 3 and "A made-up caption line" in html and "made up phrase" in html
    assert html.count('class="ov-pf"') == 4 and "Make a YouTube thumbnail" in html
    assert "You post the video yourself" in html
    offer = _built(delivery, built)["offer"]["final_edit"]
    assert offer["platforms"]["values"] == [True, False] and "final~tiktok" in offer["platforms"]["keys"]
    assert any(r["source"] == "tm organic page delivery" for r in manifest.rows(delivery))
    assert organic_gates.delivery_gap(delivery) is None              # the step check reads the run page's build


def test_an_unticked_platform_is_a_new_kit_version(delivery, capsys):
    run_page.build(delivery, _ask(delivery, "final_edit"))
    _answered(delivery, "final_edit", "final_edit_v01", "accept", actions={"final": "accept"},
              choices={"final": "v01"}, platforms={"final~tiktok": True, "final~instagram": False,
                                                    "final~youtube": True, "final~facebook": False},
              thumbnail={"final": True})
    assert main(["page", "decision", "final_edit", "--run", str(delivery.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["files"]["kit"] == "04_final/kits/M5_kit_v02.json" and "tm kit check" in out["message"]
    kit = json.loads((delivery.path / out["files"]["kit"]).read_text(encoding="utf-8"))
    assert list(kit["platforms"]) == ["tiktok", "youtube"] and kit["plugin"]["youtube_thumbnail"] is True


def test_every_platform_unticked_is_asked_never_dropped(delivery):
    run_page.build(delivery, _ask(delivery, "final_edit"))
    _answered(delivery, "final_edit", "final_edit_v01", "accept", actions={"final": "accept"},
              platforms={f"final~{p}": False for p in ("tiktok", "instagram", "youtube", "facebook")})
    with pytest.raises(Stop, match="unticks every platform"):
        run_page.record(delivery, "final_edit")
    assert all(d["checkin"] != "final_edit" for d in state.load(delivery).decisions)


# --- the style, voice and music -------------------------------------------------------------------------

def _taste_options(run):
    for rel in ("02_research/voices/v1.mp3", "02_research/voices/v2.mp3", "02_research/music/track_a.mp3"):
        (run.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (run.path / rel).write_bytes(b"made-up sound")
    opts = {"styles": [], "voices": [
        {"voice_id": "v1", "name": "Made-up voice one", "why": "calm", "preview": "02_research/voices/v1.mp3",
         "recommended": True},
        {"voice_id": "v2", "name": "Made-up voice two", "why": "bright", "preview": "02_research/voices/v2.mp3"}],
        "music": {"trending": None, "tracks": [{"file": "02_research/music/track_a.mp3", "title": "Made-up track",
                                                 "licence": "free", "recommended": True}]}}
    (run.path / "03_wip" / "taste_options_v01.json").write_text(json.dumps(opts), encoding="utf-8")


@pytest.fixture
def tasting(tmp_path, monkeypatch):
    run = _new(tmp_path)
    pack = _pack(run)
    organic_pack.record(run, run.path / "03_wip" / "pack_v01.json", pack, stage="recipe")
    _taste_options(run)
    _to(run, "taste")
    return run


def test_the_taste_stage_offers_each_voice_and_track_to_hear(tasting):
    built = run_page.build(tasting, _ask(tasting, "taste"))
    html = _html(tasting, built)
    assert "Made-up voice one" in html and html.count("<audio") >= 3
    assert {"picks", "notes"} <= _paths(html)
    offer = _built(tasting, built)["offer"]["taste"]
    assert set(offer["picks"]["keys"]) >= {"voice", "music"}
    assert any(r["source"] == "tm organic page taste" for r in manifest.rows(tasting))


def test_taste_picked_on_the_page_is_the_taste_file_and_the_next_pack(tasting, capsys):
    built = run_page.build(tasting, _ask(tasting, "taste"))
    offer = _built(tasting, built)["offer"]["taste"]
    voice2 = next(v for v in offer["picks"]["values"] if v.startswith("v2"))
    _answered(tasting, "taste", "taste_v01", "accept", picks={"voice": voice2, "music": "none"},
              notes={"voice": "a little slower"})
    assert main(["page", "decision", "taste", "--run", str(tasting.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    picks = json.loads((tasting.path / out["files"]["taste"]).read_text(encoding="utf-8"))
    assert picks["voice"]["voice_id"] == "v2" and picks["music"] == {"kind": "none"}
    assert picks["notes"] == {"voice": "a little slower"} and out["files"]["pack"] == "03_wip/pack_v02.json"
    assert "Made-up voice two" in out["recorded_note"]


# --- the shared core is unchanged for the other playbooks ----------------------------------------------

def test_a_playbooks_own_block_cannot_replace_the_templates():
    with pytest.raises(ValueError):
        template.register_block("cards", lambda b, ds, lang, live: "")
    template.register_block("ov_items", organic_video._items)      # registering its own again is harmless
