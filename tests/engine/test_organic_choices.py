"""Issue #83: organic video's pages of choices (the intake A0, the style, voice and music D2) and the check-in pages'
frames and voiceover; the reply button after a page with decisions is shown (every playbook). Synthetic runs only, no
account data: a made-up channel and the public M5 pack fixture."""

import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tm import (config, manifest, mcp_saves, organic_config, organic_gates, organic_pack, organic_pages, organic_voiced,
                page, state)
from tm.cli import main
from tm.organic_pages import choices, gate, intake, taste
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import Stop

FIXTURES = Path(__file__).parent / "fixtures" / "organic"
SLUG = "5e0a1b2c-0000-4000-8000-000000000083"
PNG = b"\x89PNG\r\n\x1a\n fake image bytes"
MP3 = b"ID3 fake sound bytes"


@pytest.fixture(autouse=True)
def no_downloads(monkeypatch):
    monkeypatch.setattr(page, "fetch_image", lambda url, dest, timeout=30: False)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _later(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def _run(tmp_path, *, working="en") -> RunFolder:
    run = RunFolder.create(tmp_path / "ws", "zorbo", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "languages": {"working": working, "market": working}})
    return run


def _doc(did: str, **data) -> str:
    return json.dumps({"id": did, "data": {"updated_at": "2026-11-12T10:00:00.000Z", **data}, "version": 1},
                      ensure_ascii=False)


def _save_db(run, collection, *docs):
    summary = json.dumps({"count": len(docs), "nextCursor": None})
    text = "\n".join([summary, "<untrusted-document-83ab>", *docs, "</untrusted-document-83ab>"])
    return mcp_saves.save(run, "db_list", {"slug": SLUG, "collection": collection, "limit": 1000}, {"raw": text},
                          at=_later(1), server="claude-artifacts")


def _publish(run, name):
    page.record_published(run, name, SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    page.await_(run, name, "v1")


def _section(data, sid):
    return next(s for s in data["sections"] if s["id"] == sid)


def _default(data, sid):
    return [o["id"] for o in _section(data, sid)["options"] if o.get("default")]


# --- the intake page (A0) ------------------------------------------------------------------------------------

def test_intake_page_asks_every_question_with_its_default_and_never_a_paid_output(tmp_path, capsys):
    run = _run(tmp_path)
    code, out = _cli(capsys, "organic", "page", "intake", "--run", str(run.path), "--working", "en", "--market", "de")
    assert code == 0, out
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["sections"]]
    assert ids[:3] == ["channel", "platforms", "account"] and "level" in ids and "output" in ids
    assert _default(data, "output") == ["script"]                      # the free script, never the AI video
    assert _default(data, "platforms") == ["tiktok", "instagram", "youtube", "facebook"]
    assert _default(data, "level") == ["every_step"]
    assert _section(data, "languages")["text"]["value"] == "en, de"
    assert _section(data, "channel")["kind"] == "text"                 # a text field only where something is typed
    html = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert 'id="done"' in html and "Start a new video plan" in html
    assert '<span class="pill dark">Organic AI video</span>' in html and '<style id="tm-look">' in html   # #60
    assert out["reply_button"] == "Saved, read my choices" and "reply button" in out["message"]
    assert organic_pages.CAPABILITIES["intake"]["db"]["rules"][0]["path"] == "intake"


def test_a_week_runs_intake_asks_the_weeks_questions_with_scripts_by_default(tmp_path):
    run = _run(tmp_path)
    data = intake.page_json(run, week=True)
    ids = {s["id"] for s in data["sections"]}
    assert {"contents", "per_week", "days", "flexible_day", "run_day", "week_budget"} <= ids and "output" not in ids
    assert _default(data, "contents") == ["scripts"] and _default(data, "per_week") == ["5"]


def test_the_intakes_answers_on_the_page_are_written_as_the_configs_answers(tmp_path, capsys):
    run = _run(tmp_path)
    intake.build(run, working="pl", market="pl")
    _publish(run, "intake")
    _save_db(run, "intake",
             _doc("channel", section="channel", choice=None, text="Zorbo", note="", notes={}),
             _doc("output", section="output", choice="ai_video", text="", note="", notes={}),
             _doc("level", section="level", choice="big_calls", text="", note="", notes={}),
             _doc("bubble", section="bubble", choice=None, text="pet care tips for new owners", note="", notes={}),
             _doc("done", done=True))
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "intake")
    assert code == 0, out
    answers = json.loads((run.path / out["answers"]).read_text(encoding="utf-8"))
    assert answers == {"level": "big_calls", "outputs": ["proposals"], "languages": {"working": "pl", "market": "pl"},
                       "channels": ["Zorbo"], "output": "ai_video",
                       "generation": {"resolution": "768p", "upscale": "none"},
                       "budget": {"per_run_usd": 5.0}, "currency": "USD"}
    profile = json.loads((run.path / out["profile"]).read_text(encoding="utf-8"))["profile"]
    assert profile["bubble"] == "pet care tips for new owners" and profile["product_role"] == "not shown"
    assert "platforms" in profile["defaults_kept"] and out["done"] is True
    assert page.awaiting(run, "intake") is None                         # read: no longer waiting
    organic_config.write_from_intake(run, answers)                      # the same answers the agent writes from chat
    assert [p for p in organic_config.validate(run) if "channel" not in str(p)] == []   # no profile yet: A1's
    assert state.load(run).level == "big_calls"


def test_an_intake_answer_in_chat_counts_the_same(tmp_path):
    run = _run(tmp_path)
    intake.build(run)
    said = run.path / "03_wip" / "intake_chat_v01.txt"
    said.write_text("channel: Zorbo, Zorbo Kids\nlevel: hands_off\nbudget: 8\nplatforms: tiktok, youtube\n",
                    encoding="utf-8")
    got = intake.take(run, text=said)
    assert got["source"] == "chat" and got["intake"]["channels"] == ["Zorbo", "Zorbo Kids"]
    assert got["intake"]["level"] == "hands_off" and got["intake"]["budget"] == {"per_run_usd": 8.0}
    assert got["intake"]["output"] == "script"                           # untouched: the free default
    assert got["profile_answers"]["platforms"] == ["tiktok", "youtube"]


def test_an_answer_the_intake_did_not_offer_is_refused_and_nothing_is_written(tmp_path):
    run = _run(tmp_path)
    intake.build(run)
    said = run.path / "03_wip" / "intake_chat_v01.txt"
    said.write_text("channel: Zorbo\noutput: a_film_crew\n", encoding="utf-8")
    with pytest.raises(Stop, match="not an option the page offered"):
        intake.take(run, text=said)
    assert run.latest("03_wip", "intake_answers", "json") is None


# --- the style, voice and music page (D2) ---------------------------------------------------------------------

def _recipe(run, *, production="talking_character"):
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["production"] = production
    path = run.path / "03_wip" / "pack_v01.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="recipe")
    return pack


def _taste_options(run, *, trending=True, outside=None):
    voices = run.path / "02_research" / "voices" / "warm"
    voices.mkdir(parents=True)
    (voices / "preview_Ala_abc12345.mp3").write_bytes(MP3)
    (voices / "preview_Mine_def67890.mp3").write_bytes(MP3)
    music = run.path / "02_research" / "music"
    music.mkdir(parents=True)
    (music / "calm_piano.mp3").write_bytes(MP3)
    opts = {"voices": [{"voice_id": "abc12345XYZ", "name": "Ala", "why": "warm and close",
                        "preview": "02_research/voices/warm/preview_Ala_abc12345.mp3", "source": "library"},
                       {"voice_id": "def67890XYZ", "name": "My voice", "why": "the owner's own",
                        "preview": "02_research/voices/warm/preview_Mine_def67890.mp3", "source": "mine",
                        "recommended": True}],
            "music": {"trending": {"name": "Sunny loop", "link": "https://www.tiktok.com/music/x", "why": "rising"}
                      if trending else None,
                      "tracks": [{"file": outside or "02_research/music/calm_piano.mp3", "title": "Calm piano",
                                  "why": "under a calm voice", "licence": "Mixkit free", "recommended": True}]}}
    path = run.path / "03_wip" / "taste_options_v01.json"
    path.write_text(json.dumps(opts), encoding="utf-8")
    return opts


def test_taste_page_has_the_script_voices_with_players_and_music_with_no_track_first(tmp_path):
    run = _run(tmp_path)
    _recipe(run)
    _taste_options(run)
    got = taste.build(run)
    data = json.loads((run.path / got["data"]).read_text(encoding="utf-8"))
    assert [s["id"] for s in data["sections"]] == ["script", "voice", "music"]       # no style: nothing animated
    script = _section(data, "script")
    assert script["lines"][0]["at"] == "0–3 s" and script["lines"][0]["text"].startswith("Mało kto wie")
    music = _section(data, "music")["options"]
    assert music[0]["id"] == "none" and _default(data, "music") == ["trending"]       # the fitting trending sound
    assert _default(data, "voice") == ["def67890XYZ"]
    assert any(o.get("badge") for o in _section(data, "voice")["options"])           # the user's own voice
    names = [f["as"] for f in got["files"]]
    assert "media/preview_Ala_abc12345.mp3" in names and "media/calm_piano.mp3" in names   # carried on the page
    html = (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")
    assert "<audio" in html and 'lang="pl"' in html


def test_a_voices_mine_row_is_offered_as_it_is_and_marked_as_the_users_own(tmp_path):
    run = _run(tmp_path)
    _recipe(run)
    opts = _taste_options(run)
    mine = {"voice_id": "def67890XYZ", "name": "My clone", "gender": None, "age": None, "accent": None,
            "use_case": None, "category": "cloned", "description": None,
            "preview_file": "02_research/voices/warm/preview_Mine_def67890.mp3"}   # as `voices --mine --json` gives it
    opts["voices"] = [opts["voices"][0], mine]
    (run.path / "03_wip" / "taste_options_v02.json").write_text(json.dumps(opts), encoding="utf-8")
    voice = {o["id"]: o for o in _section(taste.page_json(run), "voice")["options"]}
    assert voice["def67890XYZ"]["badge"] and voice["def67890XYZ"]["media"][0]["src"].endswith("preview_Mine_def67890.mp3")
    assert not voice["abc12345XYZ"].get("badge")


def test_a_track_music_fetch_copied_into_the_run_is_found_by_its_name(tmp_path):
    run = _run(tmp_path)
    _recipe(run)
    opts = _taste_options(run, trending=False)
    opts["music"]["tracks"] = [{"file": "calm_piano.mp3", "title": "Calm piano", "author": "Some Artist",
                                "licence": "Mixkit Stock Music Free License", "recommended": True}]   # an index row
    (run.path / "03_wip" / "taste_options_v02.json").write_text(json.dumps(opts), encoding="utf-8")
    got = taste.build(run)
    data = json.loads((run.path / got["data"]).read_text(encoding="utf-8"))
    track = _section(data, "music")["options"][1]
    assert track["media"][0]["src"] == "02_research/music/calm_piano.mp3" and "Some Artist" in track["means"]
    assert "media/calm_piano.mp3" in [f["as"] for f in got["files"]]


def test_without_a_trending_sound_the_recommended_track_is_the_default(tmp_path):
    run = _run(tmp_path)
    _recipe(run)
    _taste_options(run, trending=False)
    data = taste.page_json(run)
    assert _default(data, "music") == ["track-calm_piano"]


def test_a_taste_option_outside_the_run_is_refused(tmp_path):
    run = _run(tmp_path)
    _recipe(run)
    away = tmp_path / "Music" / "song.mp3"
    away.parent.mkdir()
    away.write_bytes(MP3)
    _taste_options(run, outside=str(away))
    with pytest.raises(Stop, match="not a file of this run"):
        taste.build(run)


def test_the_taste_picks_go_into_the_packs_next_version(tmp_path, capsys):
    run = _run(tmp_path)
    _recipe(run)
    _taste_options(run)
    taste.build(run)
    _publish(run, "taste")
    _save_db(run, "taste",
             _doc("voice", section="voice", choice="abc12345XYZ", text="", note="", notes={}),
             _doc("music", section="music", choice="none", text="", note="quiet, please", notes={}),
             _doc("script", section="script", choice=None, text="", note="", notes={"2": "say it shorter"}))
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "taste")
    assert code == 0, out
    picks = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))
    assert picks["voice"] == {"voice_id": "abc12345XYZ", "name": "Ala", "source": "library"}
    assert picks["music"] == {"kind": "none"} and picks["line_notes"] == {"2": "say it shorter"}
    assert out["pack"] == "03_wip/pack_v02.json"
    pack = json.loads((run.path / out["pack"]).read_text(encoding="utf-8"))
    assert pack["taste"] == {"style": None, "voice": "Ala (abc12345XYZ)", "music": None, "by": "user", "why": None}
    assert "say it shorter" not in out["message"] and "2" in out["message"]          # notes are data


# --- the check-in pages: frames and the voiceover (points 3 and 4) -------------------------------------------

def _gate_run(tmp_path, *, production="animation", route="elevenlabs_narrator"):
    run = _run(tmp_path, working="pl")
    s = state.load(run)
    s.level, s.outputs = "every_step", ["organic_video"]
    state.save(run, s)
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["production"] = production
    pack["speech"]["route"] = route
    pack["host"] = {"kind": "none", "image": None}
    path = run.path / "03_wip" / "pack_v01.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="pack")
    return run, pack


def _voiceover(run, name="vo_v01.mp3", data=MP3):
    (run.path / "03_wip" / name).write_bytes(data)
    manifest.record(run, f"03_wip/{name}", "03_wip", organic_voiced.TTS)


def _board(run, item="M5", panels=3):
    board = run.path / "03_wip" / item / "storyboard_v01"
    board.mkdir(parents=True)
    for n in range(1, panels + 1):
        (board / f"panel_{n:02d}.png").write_bytes(PNG)
    (board / "sheet.png").write_bytes(PNG)
    frames = [{"panel": 1, "from": 0, "to": 2.5, "line": "Mało kto wie…", "scene": "a kitchen", "overlay": "PEGI 12"},
              {"panel": 2, "from": 2.5, "to": 5, "line": "Młodsi nie mają…", "scene": "a phone"}]
    (run.path / "03_wip" / item / "frames_v01.json").write_text(json.dumps(frames, ensure_ascii=False), encoding="utf-8")


def test_the_storyboard_is_a_list_of_frames_with_a_note_on_each(tmp_path):
    run, _ = _gate_run(tmp_path)
    _board(run)
    _voiceover(run)
    data = organic_gates.gate_json(run, "images")
    board = next(it for it in data["items"] if it["id"].startswith("storyboard"))
    assert [f["id"] for f in board["frames"]] == ["panel_01", "panel_02", "panel_03"]
    first = board["frames"][0]
    assert first["time"] == "0–2.5 s" and first["line"] == "Mało kto wie…" and first["overlay"] == "PEGI 12"
    assert "line" not in board["frames"][2]                                        # a panel the file does not name
    got = gate.build(run, data, page="gate_images")
    html = (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")
    assert html.count('data-frame="panel_') == 3 and 'id="lightbox"' in html
    assert "media/panel_01.png" in html and "Klatka 1" in html


def test_a_page_without_frames_is_built_as_before(tmp_path):
    run, _ = _gate_run(tmp_path)
    data = {"lang": "en", "title": "T", "run": "runs/x/y", "gate": "images", "date": "2026-11-12", "lede": "",
            "items": [{"id": "voiceover", "label": "Voiceover", "options": [{"id": "a", "src": "a.png"}]}]}
    html = gate.render(data, lambda src: f"media/{src}")
    assert "lightbox" not in html and gate.FRAMES_CSS not in html


def test_frame_notes_are_read_per_frame_and_a_redo_names_only_those_frames(tmp_path, capsys):
    run, _ = _gate_run(tmp_path)
    _board(run)
    out = organic_gates.build(run, "gate_images")
    _publish(run, "gate_images")
    board = "storyboard-M5"
    _save_db(run, "gate_images",
             _doc(board, choice="storyboard_v01", action="redo", note="warmer colours", platforms=[], thumbnail=False,
                  item=board),
             _doc(f"{board}~panel_02", item=board, frame="panel_02", note="show the phone closer"),
             _doc(f"{board}~panel_03", item=board, frame="panel_03", note="  "))
    got = organic_gates.take_decisions(run, "gate_images")
    row = got["decisions"][board]
    assert row["frame_notes"] == {"panel_02": "show the phone closer"}
    assert row["note"] == "warmer colours\npanel_02: show the phone closer"
    assert out["items"] >= 1


def test_frame_notes_said_in_chat_count_the_same(tmp_path):
    run, _ = _gate_run(tmp_path)
    _board(run)
    organic_gates.build(run, "gate_images")
    said = run.path / "03_wip" / "chat_v01.txt"
    said.write_text("storyboard-M5: redo; frame 1: bigger title; note: keep the cat\n", encoding="utf-8")
    got = organic_gates.take_decisions(run, "gate_images", text=said)
    row = got["decisions"]["storyboard-M5"]
    assert row["frame_notes"] == {"panel_01": "bigger title"} and row["note"] == "keep the cat\npanel_01: bigger title"


def test_the_images_page_plays_the_voiceover_for_a_narrator_before_anything_paid(tmp_path):
    run, _ = _gate_run(tmp_path, production="ai_footage")
    s = state.load(run)
    (run.path / "03_wip" / "host_v01.run.json").write_text(json.dumps(
        {"model": "m", "status": "done", "prediction_id": "p1", "outputs": ["host_v01_0.png"]}), encoding="utf-8")
    (run.path / "03_wip" / "host_v01_0.png").write_bytes(PNG)
    state.save(run, s)
    _voiceover(run)
    data = organic_gates.gate_json(run, "images")
    vo = next(it for it in data["items"] if it["id"] == "voiceover")
    assert vo["question"] == organic_pages.gate_words("pl")["q_voiceover_images"]
    assert vo["options"][0]["src"] == "03_wip/vo_v01.mp3"


def test_a_talking_characters_images_page_has_no_voiceover_item(tmp_path):
    run, _ = _gate_run(tmp_path, production="talking_character", route="h3_native")
    (run.path / "03_wip" / "host_v01.run.json").write_text(json.dumps(
        {"model": "m", "status": "done", "prediction_id": "p1", "outputs": ["host_v01_0.png"]}), encoding="utf-8")
    (run.path / "03_wip" / "host_v01_0.png").write_bytes(PNG)
    _voiceover(run)
    data = organic_gates.gate_json(run, "images")
    assert all(it["id"] != "voiceover" for it in data["items"])


ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                            reason="ffmpeg is not installed")


def _lavfi(out: Path, *args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, str(out)], check=True)


@ffmpeg
def test_the_video_page_plays_each_take_with_the_voiceover_laid_under_it(tmp_path):
    run, pack = _gate_run(tmp_path, production="ai_footage")
    wip = run.path / "03_wip"
    _lavfi(wip / "take_v01_0.mp4", "-f", "lavfi", "-i", "testsrc=size=180x320:rate=10:duration=3",
           "-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p")
    (wip / "take_v01.run.json").write_text(json.dumps(
        {"model": "minimax/h3", "status": "done", "prediction_id": "p1", "outputs": ["take_v01_0.mp4"]}),
        encoding="utf-8")
    _lavfi(wip / "vo_v01.mp3", "-f", "lavfi", "-i", "sine=frequency=800:duration=5")
    manifest.record(run, "03_wip/vo_v01.mp3", "03_wip", organic_voiced.TTS)
    data = organic_gates.gate_json(run, "video")
    take = next(it for it in data["items"] if it["id"].startswith("takes-"))
    option = take["options"][0]
    assert option["src"] == "showcase/take_v01_0__vo_v01_vo.mp4" and (run.path / option["src"]).is_file()
    assert take["question"].startswith(organic_pages.gate_words("pl")["q_takes_voiceover"].split("{")[0])
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of",
                            "json", str(run.path / option["src"])], capture_output=True, check=True)
    assert json.loads(probe.stdout)["streams"]
    again = organic_gates.gate_json(run, "video")                                 # the same files: reused
    assert next(it for it in again["items"] if it["id"].startswith("takes-"))["options"][0]["src"] == option["src"]


def test_a_take_starts_the_voiceover_at_its_sections_time():
    pack = {"production": "sections", "sections": [{"id": "S1", "type": "ai_footage", "from": 0, "to": 6},
                                                   {"id": "S2", "type": "animation", "from": 6, "to": 9},
                                                   {"id": "S3", "type": "ai_footage", "from": 9, "to": 14}],
            "stages": [{"stage": "video", "items": [{"name": "a", "model": "m", "seconds": 6},
                                                    {"name": "b", "model": "m", "seconds": 5, "section": "S3"}]}]}
    assert organic_voiced.offsets(pack) == {"a": 0.0, "b": 9.0, "S2": 6.0}


# --- the reply button (point 5, every playbook) --------------------------------------------------------------

def test_waiting_on_a_page_ends_the_turn_with_the_reply_button_in_the_runs_language(tmp_path, capsys):
    run = _run(tmp_path, working="pl")
    intake.build(run, working="pl")
    page.record_published(run, "intake", SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    code, out = _cli(capsys, "page", "await", "--run", str(run.path), "--page", "intake", "--version", "v1")
    assert code == 0, out
    assert out["reply_button"] == "Zapisane, odczytaj moje wybory" and "reply button" in out["message"]
    assert page.reply_button(_run(tmp_path / "en")) == "Saved, read my choices"


def test_the_choices_check_their_data():
    assert choices.problems({"page": "intake", "title": "t", "run": "r", "date": "d",
                             "sections": [{"id": "done", "kind": "one", "options": []}]})
    ok = {"page": "intake", "title": "t", "run": "r", "date": "d",
          "sections": [{"id": "a", "kind": "one", "options": [{"id": "x", "label": "X", "default": True},
                                                              {"id": "y", "label": "Y", "disabled": "no start frame"}]}]}
    assert choices.problems(ok) == []
    found, done, bad = choices.answers(ok, [("a", {"section": "a", "choice": "y"})])
    assert bad and "cannot be chosen" in bad[0]
