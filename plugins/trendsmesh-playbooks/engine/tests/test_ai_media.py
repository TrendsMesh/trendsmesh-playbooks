"""`tm ai-media` (issue #24): the facts behind Meta's AI disclosure, read from the run's own manifest before E2
creates the creatives. It lists, for each file an ad will use, the media in its ancestry that a generative AI
tool made or edited, and the files the run cannot trace (the original's, or a file with no manifest row). It
never decides the disclosure: that is the advertiser's call."""

import json
from datetime import date

from tm import ai_media, cli, manifest
from tm.runfolder import RunFolder


def _run(tmp_path):
    return RunFolder.create(tmp_path, "x", date(2026, 11, 5))


def _hook_run(tmp_path):
    """A hook refresh with a new voiceover line: the original, a cloned-voice line, the paste, the 4:5 crops."""
    run = _run(tmp_path)
    rec = lambda f, src, parent=None, model=None: manifest.record(run, f, f.split("/")[0], src, parent, None, None,
                                                                  model, None, None)
    rec("00_raw/original.mp4", "the user's brand folder")
    rec("03_wip/voice_clone_v01.json", "ElevenLabs instant voice clone", "03_wip/voice_sample_v01.wav")
    rec("03_wip/line_v01.mp3", "ElevenLabs text to speech", "voice-id-1", "eleven_multilingual_v2")
    rec("03_wip/music_take_v01.mp3", "ElevenLabs Music", None, "music_v1")
    rec("03_wip/voice_preview_v01.mp3", "ElevenLabs voice preview", "03_wip/shared_voices_v01.json")
    rec("03_wip/hook_v01.mp4", "ffmpeg (tm tool ffmpeg)", "00_raw/original.mp4, 03_wip/line_v01.mp3")
    rec("04_final/hook_9x16_v01.mp4", "tm tool deliver finish", "03_wip/hook_v01.mp4")
    rec("04_final/hook_4x5_v01.mp4", "tm tool reframe (ffmpeg)", "04_final/hook_9x16_v01.mp4")
    rec("04_final/original_4x5_v01.mp4", "tm tool reframe (ffmpeg)", "00_raw/original.mp4")
    return run


def test_variant_lists_the_cloned_voice_line_through_its_ancestry(tmp_path):
    run = _hook_run(tmp_path)
    out = ai_media.facts(run, ["04_final/hook_4x5_v01.mp4"])
    (entry,) = out["files"]
    assert entry["file"] == "04_final/hook_4x5_v01.mp4" and entry["recorded"] is True
    assert [(a["file"], a["kind"]) for a in entry["ai"]] == [("03_wip/line_v01.mp3", "voice")]
    assert entry["ai"][0]["source"] == "ElevenLabs text to speech"
    assert entry["untraced"] == ["00_raw/original.mp4"]


def test_original_crop_has_no_ai_from_the_run_but_the_original_is_untraced(tmp_path):
    run = _hook_run(tmp_path)
    (entry,) = ai_media.facts(run, ["04_final/original_4x5_v01.mp4"])["files"]
    assert entry["ai"] == [] and entry["untraced"] == ["00_raw/original.mp4"]


def test_ai_media_outside_the_ads_is_listed_apart_without_previews_or_metadata(tmp_path):
    run = _hook_run(tmp_path)
    out = ai_media.facts(run, ["04_final/hook_9x16_v01.mp4", "04_final/original_4x5_v01.mp4"])
    assert [a["file"] for a in out["elsewhere"]] == ["03_wip/music_take_v01.mp3"]
    assert out["elsewhere"][0]["kind"] == "music"


def test_replicate_inpainting_and_generated_shots_count_as_picture(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "00_raw/original.mp4", "00_raw", "brand folder", None, None, None, None, None, None)
    manifest.record(run, "03_wip/clean_v01.mp4", "03_wip", "Replicate", "00_raw/original.mp4", None, None,
                    "jd7h/propainter", "$0.40", None)
    manifest.record(run, "03_wip/shot_v01.mp4", "03_wip", "Replicate", None, "a hand", None,
                    "google/veo-3.1-fast", "$1.20", None)
    manifest.record(run, "04_final/recut_v01.mp4", "04_final", "tm tool recut (ffmpeg)",
                    "03_wip/clean_v01.mp4,03_wip/shot_v01.mp4", None, None, None, None, None)
    (entry,) = ai_media.facts(run, ["04_final/recut_v01.mp4"])["files"]
    assert {(a["file"], a["kind"], a["model"]) for a in entry["ai"]} == {
        ("03_wip/clean_v01.mp4", "picture", "jd7h/propainter"),
        ("03_wip/shot_v01.mp4", "picture", "google/veo-3.1-fast")}


def test_an_agent_recorded_ai_file_counts_by_its_model(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/frame_v01.png", "03_wip", "ads made by hand", None, None, None,
                    "black-forest-labs/flux-1.1-pro", None, None)
    manifest.record(run, "04_final/ai_video_v01.mp4", "04_final", "Remotion render", "03_wip/frame_v01.png",
                    None, None, None, None, None)
    (entry,) = ai_media.facts(run, ["04_final/ai_video_v01.mp4"])["files"]
    assert [a["file"] for a in entry["ai"]] == ["03_wip/frame_v01.png"]


def test_a_file_without_a_manifest_row_is_unrecorded_and_untraced(tmp_path):
    run = _hook_run(tmp_path)
    (entry,) = ai_media.facts(run, ["04_final/thumbnail_v01.jpg"])["files"]
    assert entry["recorded"] is False and entry["ai"] == []
    assert entry["untraced"] == ["04_final/thumbnail_v01.jpg"]


def test_a_parent_named_by_its_file_name_only_is_followed(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/line_v01.mp3", "03_wip", "ElevenLabs text to speech", "voice-1", None, None,
                    None, None, None)
    manifest.record(run, "04_final/v_v01.mp4", "04_final", "ffmpeg", "line_v01.mp3", None, None, None, None, None)
    (entry,) = ai_media.facts(run, ["04_final/v_v01.mp4"])["files"]
    assert [a["file"] for a in entry["ai"]] == ["03_wip/line_v01.mp3"]


def test_a_parent_loop_ends(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/a.mp4", "03_wip", "ffmpeg", "03_wip/b.mp4", None, None, None, None, None)
    manifest.record(run, "03_wip/b.mp4", "03_wip", "Replicate", "03_wip/a.mp4", None, None, "veo", None, None)
    (entry,) = ai_media.facts(run, ["03_wip/a.mp4"])["files"]
    assert [a["file"] for a in entry["ai"]] == ["03_wip/b.mp4"]


def test_cli_prints_the_facts_and_leaves_the_decision_to_the_user(tmp_path, capsys):
    run = _hook_run(tmp_path)
    code = cli.main(["ai-media", "--run", str(run.path), "--file", "04_final/hook_9x16_v01.mp4",
                     "--file", str(run.path / "04_final" / "original_4x5_v01.mp4"), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "done"
    assert [f["file"] for f in out["files"]] == ["04_final/hook_9x16_v01.mp4", "04_final/original_4x5_v01.mp4"]
    assert "advertiser" in out["message"] and "line_v01.mp3" in out["message"]


def test_cli_refuses_a_path_outside_the_run(tmp_path, capsys):
    run = _hook_run(tmp_path)
    code = cli.main(["ai-media", "--run", str(run.path), "--file", "../elsewhere.mp4", "--json"])
    assert code == 1 and json.loads(capsys.readouterr().out)["status"] == "error"


def test_tm_loads_the_command_by_itself():
    """`tm` itself registers `ai-media` (cli._load_commands), not only a test that imports the module."""
    import subprocess
    import sys
    code = ("import sys\nfrom tm import cli\nsys.exit(0 if 'ai-media' in "
            "cli.build_parser()._subparsers._group_actions[0].choices else 3)")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
