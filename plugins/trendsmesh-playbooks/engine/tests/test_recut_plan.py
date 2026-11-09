"""Edit-list rules for re-cuts (`tm recut points | check | music`), on the reference numbers.

The edit lists in fixtures/recut/ are handoff/refresh-ad_v03's reference lists, with the same timings and fields;
`header` adds the fields this build adds to the handoff's format. The ad_2 lists' notes (U_J1_v05, U_R1_coldopen_v03 and its
end1976 variant) are reworded, as they described the creator's real lines. R1_15s_inpaintE_L5_v01.json carries its
header (RC5, level 0: the method E take exists already), and U_R1_coldopen_v03_end1976.json is the reference cold open v03
with segment 2 ending at 19.76 s (its note says why). The teardowns and the ad_2 transcript are hand-written in the
teardown and transcribe tools' schemas; the transcript's words are made up, its timings are the reference's.
"""

import copy
import json
import math
from datetime import date
from pathlib import Path

import pytest

from tm import changes, config, flow, recut_plan, state
from tm.cli import main
from tm.runfolder import RunFolder

FIX = Path(__file__).parent / "fixtures" / "recut"
AD3_SRC = "../../../2026-11-02_ad3-dry-run/01_base/ad3_original.mp4"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def header(edit, **kw):
    """The reference edit list plus the header fields this build adds to the handoff's format."""
    sync = edit.get("audio_mode") == "sync"
    base = {"variant": "test", "change_id": "recut_shorter", "level": 0,
            "cause": "ad longer than its content", "music_source": "sync" if sync else "original_file"}
    return {**copy.deepcopy(edit), **base, **kw}


AD2 = _load("ad2_teardown.json")
AD3 = _load("ad3_teardown.json")
WORDS = _load("ad2_transcript.json")

J1_V04 = header(_load("U_J1_v04.json"), variant="J1", cause="dead air", jump="hard")
J1_V05 = header(_load("U_J1_v05.json"), variant="J1", cause="dead air", jump="hard")
COLD_OPEN = header(_load("U_R1_coldopen_v03.json"), variant="cold_open", change_id="recut_reorder",
                   cause="the strongest line sits late")
COLD_OPEN_FIXED = header(_load("U_R1_coldopen_v03_end1976.json"), variant="cold_open",
                         change_id="recut_reorder", cause="the strongest line sits late")
AD3_R1_15S = _load("R1_15s_inpaintE_L5_v01.json")  # RC5 "Ad 3 R1 E": its header is in the fixture
AD3_R1_BEAT_CUT = header(_load("R1_15s_L0_v01.json"), variant="R1_15s")
R3_SPEEDUP = header(_load("R3_speedup_L5_v02.json"), variant="R3", change_id="recut_speedup", level=5,
                    cause="visual monotony", music_source="elevenlabs_continuation")


def ad3_edit(video, *, level=0, music_source="elevenlabs_continuation", **kw):
    """An Ad 3 edit list with one music segment (a continuation take, no joint in the music)."""
    pieces = [{"src": AD3_SRC, "from": a, "to": b} if isinstance(a, (int, float)) else a for a, b in video]
    length = sum(p["to"] - p["from"] for p in pieces)
    return header({"out": "../../04_final/x_v01.mp4", "video": pieces,
                   "audio": [{"src": "../audio/take_v01.wav", "from": 0, "to": round(length + 0.2, 3)}],
                   "audio_xfade_ms": 40, "audio_tail_fade_ms": 300},
                  variant="x", level=level, music_source=music_source, **kw)


def edit_ending_at(to):
    """J1 v05 with its third segment ending at `to` (v04 ends it at 19.80, v05 at 19.76)."""
    e = copy.deepcopy(J1_V05)
    e["video"][2]["to"] = to
    return e


cut_4s_inside_shot_2 = ad3_edit([(0, 16.0), (20.0, 24.149)])
L4_EDIT = ad3_edit([(0, 12.08), ({"src": "../ai/v02/veo_R4_v03_0.mp4", "from": 0.05, "to": 8.0}, None),
                    (20.068, 24.149)], level=4, music_source="original_file")


def ok(edit, teardown=AD3, transcript=None, cfg=None, mode="hitl", approved=frozenset()):
    return recut_plan.check(edit, teardown, transcript, cfg, mode=mode, approved=set(approved))


# --- the plan's tests -----------------------------------------------------------------------

def test_rc15_j1_v04_flash_refused_v05_ok():
    assert recut_plan.check(J1_V04, AD2, WORDS, None, mode="hitl", approved=set()).status == "refused"
    assert recut_plan.check(J1_V05, AD2, WORDS, None, mode="hitl", approved=set()).status == "ok"


def test_flash_margin_uses_source_fps():  # ad_2: frame 593 = 19.798 s, so fps 29.95, not 30
    v = recut_plan.check(edit_ending_at(19.80), AD2, WORDS, None, mode="hitl", approved=set())
    assert v.status == "refused" and "19.76" in " ".join(v.problems)  # the latest legal end at 29.95 fps
    assert "frame 593" in " ".join(v.problems) and "19.73" not in " ".join(v.problems)  # 30 fps would say 19.73


def test_rc5_ad3_15s_reference_passes():
    v = recut_plan.check(AD3_R1_15S, AD3, None, None, mode="hitl", approved=set())
    assert v.status == "ok" and v.length_s == pytest.approx(14.5, abs=0.07)
    assert v.joints_s == [pytest.approx(11.146, abs=0.07)] and v.level == 0


def test_rc5_beat_cut_version_is_refused_by_rule_4():
    v = recut_plan.check(AD3_R1_BEAT_CUT, AD3, None, None, mode="hitl", approved=set())
    assert v.status == "refused" and len(v.problems) == 1
    assert "beat-cut joints are audible; use the original file or a continuation (method E)" in v.problems[0]


def test_rc7_cut_inside_shot_2_refused_with_l4_offer():
    v = recut_plan.check(cut_4s_inside_shot_2, AD3, None, None, mode="hitl", approved=set())
    assert v.status == "refused" and "regenerate the shot (L4)" in v.problems[0]


def test_rc11_cold_open_reference_passes():
    # the reference v03 with segment 2 ending at 19.76 s (see the fixture's note)
    v = recut_plan.check(COLD_OPEN_FIXED, AD2, WORDS, None, mode="hitl", approved=set())
    assert v.status == "ok", v.problems
    assert v.length_s == pytest.approx(28.333, abs=0.04)  # the rendered v03: 28.333 s


def test_rc11_cold_open_v03_as_delivered_flashes_at_19_80():
    v = recut_plan.check(COLD_OPEN, AD2, WORDS, None, mode="hitl", approved=set())
    assert v.status == "refused" and len(v.problems) == 1
    assert "Segment 2 ends at 19.8 s" in v.problems[0] and "frame 593" in v.problems[0]
    assert "19.76" in v.problems[0]


def test_rc12_reorder_of_continuous_shots_refused():
    # Ad 3's cards in another order (promise, hook, CTA): each card sits inside one of two shots
    reorder = ad3_edit([(7.4, 13.5), (0, 7.4), (13.5, 24.149)], change_id="recut_reorder")
    v = ok(reorder)
    assert v.status == "refused"
    assert any("regenerate the shot (L4)" in p and "shot 1" in p for p in v.problems)


def test_whole_shot_swap_is_not_a_cut_inside_a_shot():
    # moving whole shots cuts nothing inside a shot (shot 1 ends 2 frames before frame 363)
    v = ok(ad3_edit([(12.13, 24.149), (0, 12.08)], change_id="recut_reorder"))
    assert v.status == "ok", v.problems
    early = ok(ad3_edit([(12.121, 24.149), (0, 12.08)], change_id="recut_reorder"))
    assert early.status == "refused" and "frame 362" in early.problems[0]  # 12.121 s < 363 / 29.948


def test_beat_cut_music_refused_unless_draft():
    beat_cut = copy.deepcopy(AD3_R1_BEAT_CUT)  # two segments of ad3_music_full.wav, 28 beats apart
    v = ok(beat_cut)
    assert v.status == "refused"
    assert "beat-cut joints are audible; use the original file or a continuation (method E)" in " ".join(v.problems)
    draft = ok({**beat_cut, "draft": True})
    assert not any("beat-cut" in p for p in draft.problems)
    one_take = ok(ad3_edit([(0, 11.146), (20.735, 24.149)]))
    assert one_take.status == "ok", one_take.problems


def test_rc16_hands_off_l4_without_ai_budget_waits():
    v = recut_plan.check(L4_EDIT, AD3, None, None, mode="auto", approved=set())
    assert v.status == "waiting" and "budget.ai_usd" in v.problems[0]


def test_rc17_existing_take_reused():
    assert recut_plan.reuse_take([{"file": "e.mp3", "length_s": 20.04}], 20.0)["file"] == "e.mp3"
    assert recut_plan.reuse_take([{"file": "e.mp3", "length_s": 20.10}], 20.0) is None


# --- rule 1: flash margin -------------------------------------------------------------------

def test_flash_margin_counts_source_frames_at_25_fps():
    td = {"fps": 25, "frame_count": 250, "has_speech": False, "overlays": [],
          "scenes": [{"start_s": 0.0, "end_s": 4.0, "start_frame": 0, "end_frame": 99},
                     {"start_s": 4.0, "end_s": 10.0, "start_frame": 100, "end_frame": 249}]}
    edit = ad3_edit([(0, 3.98), (5.0, 10.0)])
    v = ok(edit, td)
    assert v.status == "refused" and "3.96" in " ".join(v.problems)  # last frame must be <= 98
    assert ok(ad3_edit([(0, 3.96), (5.0, 10.0)]), td).status == "ok"


def test_a_segment_starting_one_frame_before_a_shot_change_is_refused():
    e = copy.deepcopy(J1_V05)
    e["video"][3]["from"] = 25.53  # frame 764: one frame of the next shot before frame 765
    v = ok(e, AD2, WORDS)
    assert v.status == "refused" and any("frame 764" in p for p in v.problems)


def test_continuing_the_same_shot_at_a_new_speed_is_not_a_cut():
    v = ok(R3_SPEEDUP, approved={"voice_credits"})
    assert v.status == "ok", v.problems
    assert v.length_s == pytest.approx(20.0, abs=0.04)  # recut_levels_test.md: R3 20.0 s
    assert v.joints_s == [pytest.approx(12.067, abs=0.034)]


# --- rule 2: no joint inside a continuous shot -----------------------------------------------

def test_a_dissolve_inside_a_shot_is_refused():
    e = ad3_edit([(0, 18.0), ({"src": AD3_SRC, "from": 21.733, "to": 24.149, "seam": "dissolve",
                                "seam_frames": 8}, None)], level=3)
    v = ok(e, approved={"ai_usd"})
    assert v.status == "refused" and "dissolve" in v.problems[0] and "regenerate the shot (L4)" in v.problems[0]


def test_a_sync_joint_inside_a_shot_needs_a_declared_jump():
    e = {k: v for k, v in J1_V05.items() if k != "jump"}
    v = ok(e, AD2, WORDS)
    assert v.status == "refused" and any("no jump is declared" in p for p in v.problems)


def test_a_sync_joint_inside_a_shot_needs_a_speech_gap():
    e = copy.deepcopy(J1_V05)
    e["video"][0]["to"] = 8.3   # inside the word at 8.00-8.42 ("książkę.")
    v = ok(e, AD2, WORDS)
    assert v.status == "refused" and any("8.32 s is not in a speech gap" in p for p in v.problems)


def test_another_source_is_its_own_shot():
    v = ok(L4_EDIT, approved={"ai_usd"})
    assert v.status == "ok", v.problems


# --- rule 3: speech is cut in sync mode ------------------------------------------------------

def test_speech_needs_sync_mode():
    e = {k: v for k, v in J1_V05.items() if k != "audio_mode"}
    e["music_source"] = "original_file"
    v = ok(e, AD2, WORDS)
    assert v.status == "refused" and any('"sync"' in p for p in v.problems)


def test_an_audio_cut_inside_a_word_is_refused():
    e = copy.deepcopy(J1_V05)
    del e["video"][1]["audio_tail"]  # the picture cut at 11.51 is inside "sny." (11.18-11.60)
    v = ok(e, AD2, WORDS)
    assert v.status == "refused" and any("sny." in p for p in v.problems)


def test_speech_without_a_transcript_is_refused():
    v = ok(J1_V05, AD2, None)
    assert v.status == "refused" and any("transcript" in p for p in v.problems)


# --- rule 5: level --------------------------------------------------------------------------

def test_level_against_max_level_and_budgets():
    cfg4 = {"recut": {"max_level": 4}}
    assert ok(L4_EDIT, approved={"ai_usd"}).status == "ok"  # HITL, max_level unset: G3r asked
    assert ok(L4_EDIT, mode="auto", approved={"ai_usd"}).status == "waiting"  # Hands-off stops at L2
    assert ok(L4_EDIT, cfg=cfg4, mode="auto", approved={"ai_usd"}).status == "ok"
    v = ok(L4_EDIT, cfg={"recut": {"max_level": 2}}, approved={"ai_usd"})
    assert v.status == "refused" and "recut.max_level" in v.problems[0]
    waits = ok(L4_EDIT, cfg={"recut": {"max_level": 2}}, mode="auto", approved={"ai_usd"})
    assert waits.status == "waiting" and "recut.max_level" in waits.problems[0]


def test_l5_needs_the_voice_budget():
    v = ok(R3_SPEEDUP)
    assert v.status == "waiting" and "budget.voice_credits" in v.problems[0]
    assert v.level == 5


# --- the header -----------------------------------------------------------------------------

@pytest.mark.parametrize("change, words", [
    ({"variant": ""}, "variant"),
    ({"change_id": None}, "change_id"),
    ({"level": 6}, "level"),
    ({"level": True}, "level"),
    ({"cause": " "}, "cause"),
    ({"music_source": "beat_cut"}, "music_source"),
    ({"jump": "zoom"}, "jump"),
    ({"draft": "yes"}, "draft"),
])
def test_header_fields_are_checked(change, words):
    v = ok({**ad3_edit([(0, 11.146), (20.735, 24.149)]), **change})
    assert v.status == "refused" and any(words in p for p in v.problems)


@pytest.mark.parametrize("change_id", ["opening_text_card", "format_4x5", "a_shorter_cut", "Recut_Shorter"])
def test_change_id_must_be_a_middle_change(change_id):
    v = ok({**ad3_edit([(0, 11.146), (20.735, 24.149)]), "change_id": change_id})
    assert v.status == "refused"
    said = [p for p in v.problems if "change_id" in p]
    assert len(said) == 1, v.problems
    for allowed in ("recut_shorter", "recut_speedup", "recut_reorder", "recut_proof_insert", "recut_new_shot",
                    "recut_new_vo_line", "bumper_6s"):
        assert allowed in said[0]


@pytest.mark.parametrize("change_id", ["recut_shorter", "bumper_6s", "recut_new_vo_line"])
def test_every_middle_change_id_passes_the_header(change_id):
    v = ok({**ad3_edit([(0, 11.146), (20.735, 24.149)]), "change_id": change_id})
    assert not any("change_id" in p for p in v.problems), v.problems


def test_music_source_must_be_in_the_configured_chain():
    edit = ad3_edit([(0, 11.146), (20.735, 24.149)], music_source="generated")
    v = ok(edit, cfg={"recut": {"music_source": ["original_file", "elevenlabs_continuation"]}})
    assert v.status == "refused" and any("music_source" in p for p in v.problems)


def test_sync_music_source_goes_with_sync_mode():
    v = ok(ad3_edit([(0, 11.146), (20.735, 24.149)], music_source="sync"))
    assert v.status == "refused" and any("sync" in p for p in v.problems)


def test_src_with_spaces_and_polish_letters_is_one_source():
    e = copy.deepcopy(J1_V05)
    for seg in e["video"]:
        seg["src"] = "../../00_raw/reklama źródło 2.mp4" if seg is not e["video"][2] else \
            "../../00_raw/./reklama źródło 2.mp4"
    v = ok(e, {**AD2, "video": "00_raw/reklama źródło 2.mp4"}, WORDS)
    assert v.status == "ok", v.problems


def test_a_bad_segment_is_refused_not_a_crash():
    v = ok({**ad3_edit([(0, 11.146)]), "video": [{"src": AD3_SRC, "from": 5, "to": 2}]})
    assert v.status == "refused" and v.problems


# --- points ---------------------------------------------------------------------------------

def test_points_ad2():
    p = recut_plan.points(AD2, WORDS)
    assert p["fps"] == pytest.approx(29.953)
    assert {"frame": 593, "s": 19.798} in p["shot_changes"] and {"frame": 765, "s": 25.54} in p["shot_changes"]
    assert 19.798 in p["card_switches"]
    assert [8.42, 9.8] in p["speech_gaps"] and [11.6, 11.74] in p["speech_gaps"]
    assert [25.52, 25.64] in p["speech_gaps"]  # the cold open's audio tail runs into this one
    assert [17.52, 17.62] not in p["speech_gaps"]  # 0.10 s is shorter than SPEECH_GAP_MIN_S
    assert all(b - a >= recut_plan.SPEECH_GAP_MIN_S - 1e-9 for a, b in p["speech_gaps"])


def test_points_fps_from_the_scene_frames_when_the_teardown_has_none():
    td = {k: v for k, v in AD2.items() if k != "fps"}
    assert recut_plan.points(td, None)["fps"] == pytest.approx(593 / 19.798, abs=1e-3)
    assert recut_plan.points(td, None)["speech_gaps"] == []


def test_points_ad3():
    p = recut_plan.points(AD3, None)
    assert p["shot_changes"] == [{"frame": 363, "s": 12.121}]
    assert p["card_switches"][:2] == [0.2, 6.411]


# --- the commands ---------------------------------------------------------------------------

@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy"
    ws.mkdir()
    return RunFolder.create(ws, "ad 2", date(2026, 11, 6))


def _files(run, edit, name="U_J1_v05.json", teardown=AD2, transcript=WORDS):
    recut = run.path / "03_wip" / "recut"
    recut.mkdir(parents=True, exist_ok=True)
    (recut / name).write_text(json.dumps(edit, ensure_ascii=False), encoding="utf-8")
    (run.path / "02_research" / "teardown_v01.json").write_text(json.dumps(teardown), encoding="utf-8")
    args = ["--teardown", str(run.path / "02_research" / "teardown_v01.json")]
    if transcript is not None:
        (run.path / "02_research" / "transcript_v01.json").write_text(json.dumps(transcript), encoding="utf-8")
        args += ["--transcript", str(run.path / "02_research" / "transcript_v01.json")]
    return recut / name, args


def test_cli_check_records_an_ok_edit_list(run, capsys):
    path, args = _files(run, J1_V05)
    assert main(["recut", "check", "--run", str(run.path), str(path), *args, "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    rec = json.loads((run.path / "run.json").read_text(encoding="utf-8"))["recut"]["checked"]
    assert len(rec) == 1
    assert set(rec[0]) == {"edit", "variant", "change_id", "level", "joints_s", "length_s", "audio_mode",
                           "music_source", "status"}
    assert rec[0]["edit"] == "03_wip/recut/U_J1_v05.json" and rec[0]["status"] == "ok"
    assert rec[0]["audio_mode"] == "sync" and rec[0]["music_source"] == "sync" and rec[0]["level"] == 0
    assert rec[0]["length_s"] == pytest.approx(19.3, abs=0.04)  # manifest.md: J1 v05 19.30 s


def test_cli_check_refused_stops_with_exit_2_and_is_recorded(run, capsys):
    path, args = _files(run, J1_V04, "U_J1_v04.json")
    assert main(["recut", "check", "--run", str(run.path), str(path), *args]) == 2
    text = capsys.readouterr().out
    assert "19.76" in text and "nothing was rendered" in text and "continues from the same place" in text
    rec = state.load(run).recut["checked"]
    assert rec[-1]["status"] == "refused" and rec[-1]["edit"] == "03_wip/recut/U_J1_v04.json"


def test_cli_check_reads_mode_and_budgets_from_the_run(run, capsys):
    path, args = _files(run, L4_EDIT, "R4_v01.json", AD3, None)
    flow.set_level(run, "hands_off")
    assert main(["recut", "check", "--run", str(run.path), str(path), *args, "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "waiting" and "budget.ai_usd" in out["problems"][0]
    assert state.load(run).recut["checked"][-1]["status"] == "waiting"


def test_change_id_must_fit_the_material():
    edit = {**ad3_edit([(0, 11.146), (20.735, 24.149)]), "change_id": "recut_speedup"}
    v = recut_plan.check(edit, AD3, None, None, mode="hitl", approved=set(), material="talking_head")
    said = [p for p in v.problems if "change_id" in p]
    assert v.status == "refused" and len(said) == 1, v.problems
    assert "talking head" in said[0]
    assert "recut_shorter, recut_reorder, recut_proof_insert" in said[0] and "recut_speedup," not in said[0]
    for material in ("text_cards", None):                      # speed-up is a text-card change
        v = recut_plan.check(edit, AD3, None, None, mode="hitl", approved=set(), material=material)
        assert not any("change_id" in p for p in v.problems), (material, v.problems)


def test_cli_check_reads_the_material_from_the_run(run, capsys):
    path, args = _files(run, J1_V05)                          # recut_shorter: fits a talking head
    changes.record_material(run, "talking_head")
    assert main(["recut", "check", "--run", str(run.path), str(path), *args, "--json"]) == 0
    capsys.readouterr()
    path, args = _files(run, {**J1_V05, "change_id": "bumper_6s"}, "U_J1_bumper.json")
    assert main(["recut", "check", "--run", str(run.path), str(path), *args, "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert any("change_id" in p and "talking head" in p for p in out["problems"])


def test_run_context(run):
    assert recut_plan.run_context(run) == ("hitl", set())
    s = state.load(run)
    s.level, s.budgets = "hands_off", {"ai_usd": 4.0, "voice_credits": 0.0}
    state.save(run, s)
    assert recut_plan.run_context(run) == ("auto", {"ai_usd"})


def test_run_context_a_declined_recut_budget_borrows_no_other_budget(run):
    """RB reject, then ai_usd approved for the AI video (G6): the re-cut gets none of it (PR C review)."""
    flow.set_level(run, "every_step")
    s = state.load(run)
    s.decisions = [{"checkin": "RB", "choice": "reject", "by": "user"},
                   {"checkin": "G6", "choice": "approve", "by": "user"}]
    s.budgets = {"ai_usd": 15.0}
    state.save(run, s)
    assert recut_plan.run_context(run) == ("hitl", set())
    path, args = _files(run, L4_EDIT, "R4_v01.json", AD3, None)
    assert main(["recut", "check", "--run", str(run.path), str(path), *args]) == 2
    assert state.load(run).recut["checked"][-1]["status"] == "waiting"  # no budget for L4
    s = state.load(run)
    s.decisions.append({"checkin": "RB", "choice": "approve", "by": "user"})  # changed with --change
    state.save(run, s)
    assert recut_plan.run_context(run) == ("hitl", {"ai_usd"})


def test_run_context_mode_follows_the_level_not_a_stale_config(run):
    import yaml
    (run.path / "config.yaml").write_text(yaml.safe_dump({"mode": "auto"}), encoding="utf-8")
    assert recut_plan.run_context(run)[0] == "auto"  # no level yet: the config's mode
    flow.set_level(run, "hands_off")
    assert recut_plan.run_context(run)[0] == "auto"
    flow.set_level(run, "every_step")  # moved off Hands-off after intake; config.yaml still says auto
    assert recut_plan.run_context(run)[0] == "hitl"
    path, args = _files(run, L4_EDIT, "R4_v01.json", AD3, None)
    assert main(["recut", "check", "--run", str(run.path), str(path), *args]) == 2
    assert state.load(run).recut["checked"][-1]["status"] == "waiting"  # ai_usd, not max_level
    v = ok(L4_EDIT, mode=recut_plan.run_context(run)[0])
    assert not any("recut.max_level" in p for p in v.problems)


def test_a_02x_run_json_without_recut_loads_and_records(run, capsys):
    data = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
    data.pop("recut")
    (run.path / "run.json").write_text(json.dumps(data), encoding="utf-8")
    assert state.load(run).recut is None
    path, args = _files(run, J1_V05)
    assert main(["recut", "check", "--run", str(run.path), str(path), *args]) == 0
    assert [c["status"] for c in state.load(run).recut["checked"]] == ["ok"]


def test_cli_points_prints_one_object(run, capsys):
    _, args = _files(run, J1_V05)
    assert main(["recut", "points", "--run", str(run.path), *args, "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and {"frame": 593, "s": 19.798} in out["shot_changes"]


def test_cli_check_bad_input_is_an_error(run, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1]", encoding="utf-8")
    _, args = _files(run, J1_V05)
    assert main(["recut", "check", "--run", str(run.path), str(bad), *args]) == 1
    assert state.load(run).recut is None


def _take(run, name, length, **extra):
    audio = run.path / "03_wip" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    (audio / name).write_bytes(b"RIFF")
    rec = {"kind": "music_take", "file": name, "length_s": length, "model": "music_v2_5",
           "plan": {"sections": []}, "credits_used": 220, **extra}
    (audio / f"{name}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_cli_music_reuses_a_take_that_fits(run, capsys):
    _take(run, "R3_music_E_v01.wav", 20.04)
    _take(run, "R1_music_E_v01.wav", 14.6)
    (run.path / "03_wip" / "audio" / "beats_v01.json").write_text('{"beats": []}', encoding="utf-8")
    assert main(["recut", "music", "--run", str(run.path), "--target-s", "20.0", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "reuse" and out["take"]["file"] == "03_wip/audio/R3_music_E_v01.wav"
    assert len(out["takes"]) == 2


def test_cli_music_says_generate_when_nothing_fits(run, capsys):
    _take(run, "R1_music_E_v01.wav", 14.6)
    assert main(["recut", "music", "--run", str(run.path), "--target-s", "20.0"]) == 0
    text = capsys.readouterr().out
    assert "generate" in text.lower() and "220" in text


# --- config ---------------------------------------------------------------------------------

def test_config_recut_defaults():
    assert config.value(None, "recut.max_level") is None
    assert config.value(None, "recut.music_source") == ["original_file", "elevenlabs_continuation",
                                                        "licensed_track", "generated"]
    assert config.value(None, "recut.qa") == {"music_joint_db": 3, "beat_interval": 0.15, "tempo_drift": 0.04,
                                              "tail_db": -6, "caption_flash_s": 0.2}


def test_config_recut_values_are_validated(run):
    import yaml
    cfg = {"recut": {"max_level": 6, "music_source": ["original_file", "beat_cut"],
                     "qa": {"tail_db": 6, "beat_interval": 1.5}}}
    (run.path / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    fields = {p.field for p in config.validate(run)}
    assert {"recut.max_level", "recut.music_source", "recut.qa.tail_db", "recut.qa.beat_interval"} <= fields
    (run.path / "config.yaml").write_text(yaml.safe_dump({"recut": {"max_level": 3}}), encoding="utf-8")
    assert not {f for f in (p.field for p in config.validate(run)) if f.startswith("recut")}


# --- fix round 1 ----------------------------------------------------------------------------

def _three_shots(fps, c1, c2, n, video=None):
    td = {"fps": fps, "frame_count": n, "has_speech": False, "overlays": [],
          "scenes": [{"start_s": 0.0, "start_frame": 0, "end_frame": c1 - 1},
                     {"start_s": round(c1 / fps, 3), "start_frame": c1, "end_frame": c2 - 1},
                     {"start_s": round(c2 / fps, 3), "start_frame": c2, "end_frame": n - 1}]}
    if video:
        td["video"] = video
    return td


@pytest.mark.parametrize("fps, c1, c2, n", [(25, 100, 200, 300), (29.952, 300, 600, 900)])
@pytest.mark.parametrize("offset, status", [(-1, "refused"), (-2, "refused"), (-3, "refused"),
                                            (-4, "refused"), (-7, "refused"), (0, "ok"), (-8, "ok")])
def test_start_margin_mirrors_the_end(fps, c1, c2, n, offset, status):
    td = _three_shots(fps, c1, c2, n)
    start = (c2 + offset + 0.5) / fps  # the middle of source frame c2 + offset
    end = (n - 0.5) / fps
    v = ok(ad3_edit([(start, end)]), td)
    assert v.status == status, v.problems
    if status == "refused":
        earliest = math.ceil(c2 / fps * 100 - 1e-6) / 100
        same_shot = math.floor((c2 - 8) / fps * 100 + 1e-6) / 100  # a piece of the previous shot >= 8 frames
        text = " ".join(v.problems)
        assert f"frame {c2 + offset}" in text and f"{earliest:.2f} s" in text and f"{same_shot:.2f} s" in text


@pytest.mark.parametrize("speed", [1.0, 1.5])
def test_a_dissolve_on_the_next_frame_is_still_inside_the_shot(speed):
    second = {"src": AD3_SRC, "from": 16.0, "to": 18.0, "seam": "dissolve", "seam_frames": 8, "speed": speed}
    v = ok(ad3_edit([(14.0, 16.0), (second, None)], level=3), approved={"ai_usd"})
    assert v.status == "refused" and "dissolves inside one continuous shot" in v.problems[0]


def test_the_teardowns_file_is_matched_not_counted():
    td = _three_shots(25, 100, 200, 300, video="00_raw/o.mp4")
    edit = ad3_edit([({"src": "veo.mp4", "from": 0, "to": 2}, None), ({"src": "veo.mp4", "from": 2, "to": 4}, None),
                     ({"src": "../../00_raw/o.mp4", "from": 0, "to": 4.0}, None),
                     ({"src": "../../00_raw/o.mp4", "from": 8.0, "to": 10.0}, None)], level=4)
    v = ok(edit, td, approved={"ai_usd"})
    assert v.status == "refused" and len(v.problems) == 1
    assert v.problems[0].startswith("Segment 3 ends at 4 s, on source frame 99")


def test_without_video_the_most_used_file_is_the_teardowns():
    td = _three_shots(25, 100, 200, 300)  # hand-made: no "video"
    edit = ad3_edit([(0, 4.0), (8.0, 10.0), ({"src": "veo.mp4", "from": 0, "to": 3.98}, None)], level=4)
    v = ok(edit, td, approved={"ai_usd"})
    assert v.status == "refused" and v.problems[0].startswith("Segment 1 ends at 4 s, on source frame 99")


def test_a_teardown_of_another_file_is_refused():
    v = ok(J1_V05, {**AD2, "video": "00_raw/ad_3.mp4"}, WORDS)
    assert v.status == "refused" and "00_raw/ad_3.mp4" in v.problems[0]


def test_check_resolves_srcs_against_the_edit_folder_and_video_against_the_run(tmp_path):
    run_dir, edit_dir = tmp_path / "run", tmp_path / "run" / "03_wip" / "recut"
    td = _three_shots(25, 100, 200, 300, video="00_raw/o.mp4")
    edit = ad3_edit([({"src": "../../00_raw/o.mp4", "from": 0, "to": 4.0}, None),
                     ({"src": "../../../run/00_raw/o.mp4", "from": 8.0, "to": 10.0}, None),
                     ({"src": "../ai/veo.mp4", "from": 0, "to": 2}, None),
                     ({"src": "../ai/veo.mp4", "from": 2.5, "to": 4}, None)], level=4)
    v = recut_plan.check(edit, td, None, None, mode="hitl", approved={"ai_usd"}, base=run_dir, edit_dir=edit_dir)
    texts = " ".join(v.problems)
    assert "Segment 1 ends at 4 s, on source frame 99" in texts  # the original, written two ways
    assert "veo.mp4 (another file" in texts  # the Veo clip's own jump, not blamed for the original


def test_cli_check_matches_the_teardowns_video(run, capsys):
    td = _three_shots(25, 100, 200, 300, video="00_raw/o.mp4")
    edit = ad3_edit([({"src": "../ai/veo.mp4", "from": 0, "to": 2}, None),
                     ({"src": "../ai/veo.mp4", "from": 2, "to": 4}, None),
                     ({"src": "../../00_raw/o.mp4", "from": 0, "to": 4.0}, None)], level=4)
    path, args = _files(run, edit, "R4_v02.json", td, None)
    s = state.load(run)
    s.budgets = {"ai_usd": 4.0}
    state.save(run, s)
    assert main(["recut", "check", "--run", str(run.path), str(path), *args, "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert len(out["problems"]) == 1 and out["problems"][0].startswith("Segment 3 ends at 4 s, on source frame 99")


def test_speech_comes_from_the_transcript_too():
    v = ok({**J1_V05, "audio_mode": None, "music_source": "original_file"}, {**AD2, "has_speech": False}, WORDS)
    assert v.status == "refused" and any('"audio_mode" must be "sync"' in p for p in v.problems)


def test_a_segment_starting_after_the_latest_end_is_told_to_move():
    td = _three_shots(25, 100, 200, 300)
    v = ok(ad3_edit([(0, 3.0), (3.98, 4.06)]), td)  # frames 99-101: starts after 3.96, the latest end
    text = " ".join(v.problems)
    assert "Drop segment 2, or start it in the next shot" in text
    assert "end it at 3.96 s or earlier" not in text


# --- PR B fix wave --------------------------------------------------------------------------

@pytest.mark.parametrize("a, b, speed, frames", [(0, 11.146, 1, 334), (5.0, 7.777, 1, 83), (3.3, 6.71, 1.5, 68)])
def test_one_timeline_counts_the_frames_check_and_render_use(a, b, speed, frames):
    edit = ad3_edit([({"src": AD3_SRC, "from": a, "to": b, "speed": speed}, None),
                     ({"src": "../ai/veo.mp4", "from": 0, "to": 1.0}, None)], level=4)
    tl = recut_plan.timeline(edit)
    assert tl.fps == 30 and tl.frames == [frames, 30]
    assert tl.lens_s == [frames / 30, 1.0] and tl.starts_s == [0.0, frames / 30]
    v = ok(edit, approved={"ai_usd"})
    assert v.joints_s == tl.joints_s == [round(frames / 30, 3)]
    assert v.length_s == tl.length_s == round(frames / 30 + 1.0, 3)


def test_sync_mode_refuses_a_dissolve():
    e = copy.deepcopy(J1_V05)
    e["video"][1].update({"seam": "dissolve", "seam_frames": 6})
    v = ok(e, AD2, WORDS)
    assert v.status == "refused"
    assert any("a dissolve can't be used with speech: cut instead" in p for p in v.problems), v.problems


@pytest.mark.parametrize("fps, c1, c2, n", [(25, 100, 200, 300), (29.952, 300, 600, 900)])
@pytest.mark.parametrize("piece", range(2, 9))
def test_a_sliver_of_the_next_shot_at_a_segments_end_is_refused(fps, c1, c2, n, piece):
    td = _three_shots(fps, c1, c2, n)
    end = (c1 + piece - 0.5) / fps  # the last frame is c1 + piece - 1: `piece` frames of shot 2
    v = ok(ad3_edit([(0.0, end), ((c2 + 0.5) / fps, (n - 0.5) / fps)]), td)
    if piece >= recut_plan.MIN_PIECE_FRAMES:
        assert v.status == "ok", v.problems
        return
    assert v.status == "refused", f"{piece} frames of shot 2 passed"
    text = " ".join(v.problems)
    assert f"frame {c1 + piece - 1}" in text
    if piece > 3:  # 1-3 frames are rule 1's flash; 4-7 a sliver, with the second to end at
        longer = math.ceil((c1 + 8) / fps * 100 - 1e-6) / 100
        latest = math.floor((c1 - 1) / fps * 100 + 1e-6) / 100
        assert "at least 8 frames" in text and f"{longer:.2f} s or later" in text
        assert f"{latest:.2f} s or earlier" in text and len(v.problems) == 1


def test_the_reviewers_probe_slivers_are_refused():
    td = {"fps": 30.0, "video": "a.mp4", "frame_count": 900,
          "scenes": [{"start_frame": 0, "start_s": 0.0}, {"start_frame": 300, "start_s": 10.0},
                     {"start_frame": 600, "start_s": 20.0}]}
    for to in (10.1334, 10.1667, 10.2):  # 5 to 6 frames of shot 2, then shot 3
        e = ad3_edit([({"src": "a.mp4", "from": 0.0, "to": to}, None), ({"src": "a.mp4", "from": 20.5, "to": 22.0}, None)])
        assert ok(e, td).status == "refused", to
    early = ad3_edit([({"src": "a.mp4", "from": 0.0, "to": 5.0}, None),
                      ({"src": "a.mp4", "from": 596 / 30, "to": 22.0}, None)])
    v = ok(early, td)
    assert v.status == "refused" and "4 frames" in " ".join(v.problems)


def test_an_nfd_name_on_disk_matches_an_nfc_src(tmp_path):
    import unicodedata
    name = "reklama źródło ż.mp4"
    nfd, nfc = unicodedata.normalize("NFD", name), unicodedata.normalize("NFC", name)
    assert nfd != nfc
    run_dir = tmp_path / "run"
    (run_dir / "00_raw").mkdir(parents=True)
    (run_dir / "00_raw" / nfd).write_bytes(b"x")  # as macOS hands the name to the teardown
    edit_dir = run_dir / "03_wip" / "recut"
    edit_dir.mkdir(parents=True)
    td = _three_shots(25, 100, 200, 300, video="00_raw/" + nfd)
    edit = ad3_edit([({"src": "../../00_raw/" + nfc, "from": 0, "to": 3.96}, None),
                     ({"src": "../../00_raw/" + nfc, "from": 4.0, "to": 7.96}, None)])
    v = recut_plan.check(edit, td, None, None, mode="hitl", approved=set(), base=run_dir, edit_dir=edit_dir)
    assert v.status == "ok", v.problems
    bare = recut_plan.check(edit, {**td, "video": nfd}, None, None, mode="hitl", approved=set())
    assert bare.status == "ok", bare.problems


def test_messages_name_a_file_by_its_last_part_never_a_resolved_path(tmp_path):
    edit_dir = tmp_path / "run" / "03_wip" / "recut"
    td = _three_shots(25, 100, 200, 300, video="o.mp4")  # a bare name: the file lives outside the run
    edit = ad3_edit([({"src": "..\\a\\o.mp4", "from": 0, "to": 3.96}, None),
                     ({"src": "../b/o.mp4", "from": 4.0, "to": 7.96}, None)])
    v = recut_plan.check(edit, td, None, None, mode="hitl", approved=set(), base=tmp_path / "run",
                         edit_dir=edit_dir)
    assert v.status == "refused" and "Several different files" in v.problems[0]
    assert str(tmp_path) not in v.problems[0] and "/a/" not in v.problems[0] and "\\" not in v.problems[0]
    assert "o.mp4" in v.problems[0] and "segments 1 and 2" in v.problems[0]


@pytest.mark.parametrize("layers, words", [
    ("vo.wav", "a list"),
    ([{"at": 1.0}], '"src"'),
    ([{"src": "vo.wav"}], '"at"'),
    ([{"src": "vo.wav", "at": -0.5}], '"at"'),
    ([{"src": "vo.wav", "at": 20.0}], "below the output's"),
    ([{"src": "vo.wav", "at": True}], '"at"'),
    ([{"src": "vo.wav", "at": 1.0, "gain_db": "loud"}], '"gain_db"'),
])
def test_extra_audio_layers_are_checked(layers, words):
    v = ok({**ad3_edit([(0, 11.146), (20.735, 24.149)]), "extra_audio": layers})
    assert v.status == "refused" and any("extra_audio" in p and words in p for p in v.problems), v.problems


def test_good_extra_audio_passes_and_is_what_the_renderer_mixes():
    edit = {**ad3_edit([(0, 11.146), (20.735, 24.149)]),
            "extra_audio": [{"src": "../audio/vo.wav", "at": 3}, {"src": "x.wav", "at": 0, "gain_db": -6}]}
    assert ok(edit).status == "ok"
    layers, problems = recut_plan.extra_audio(edit, recut_plan.timeline(edit).length_s)
    assert problems == [] and layers == [{"src": "../audio/vo.wav", "at": 3.0, "gain_db": 0.0},
                                         {"src": "x.wav", "at": 0.0, "gain_db": -6.0}]


def test_cli_music_names_a_pending_paid_take_to_resume(run, capsys):
    _take(run, "R1_music_E_v01.wav", 14.6)
    audio = run.path / "03_wip" / "audio"
    (audio / "music_take_v02.mp3.json").write_text(json.dumps(
        {"kind": "music_pending", "file": "music_take_v02.mp3", "history_item_id": "h9", "model": "music_v2_5",
         "plan": {"sections": []}, "credits_used": 5000}), encoding="utf-8")
    assert main(["recut", "music", "--run", str(run.path), "--target-s", "20.0", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "resume" and out["credits"] == 0
    assert out["pending"] == [{"record": "03_wip/audio/music_take_v02.mp3.json", "file": "music_take_v02.mp3",
                               "credits_used": 5000}]
    assert main(["recut", "music", "--run", str(run.path), "--target-s", "20.0"]) == 0
    text = capsys.readouterr().out
    assert "--resume 03_wip/audio/music_take_v02.mp3.json" in text and "generate" not in text.lower()


# --- PR B fix wave, round 2 -----------------------------------------------------------------

_TALK = {"fps": 30.0, "video": "a.mp4", "frame_count": 900, "has_speech": True,
         "scenes": [{"start_frame": 0, "start_s": 0.0}, {"start_frame": 300, "start_s": 10.0},
                    {"start_frame": 600, "start_s": 20.0}]}
_TALK_WORDS = {"segments": [{"words": [{"word": "x", "start": 28.0, "end": 29.0}]}]}


def _talk(segs):
    """A sync, talking-head edit list with a declared jump; every audio cut sits before the only word."""
    e = {"variant": "v", "change_id": "recut_shorter", "cause": "c", "level": 0, "music_source": "sync", "jump": "hard",
         "audio_mode": "sync", "audio": [], "video": [{"src": "a.mp4", "from": a, "to": b} for a, b in segs]}
    return recut_plan.check(e, _TALK, _TALK_WORDS, None, mode="hitl", approved=set())


def _mid(frame):
    return (frame + 0.5) / 30


def test_a_reorder_through_two_same_shot_slivers_is_refused():
    # shot 2 plays first, then shot 1, then shot 2 again through 5 + 5 frames the neighbour rule lets pass
    v = _talk([(_mid(315), _mid(360)), (1.0, 3.0), (5.0, 305 / 30 - 0.01), (_mid(595), 21.0)])
    assert v.status == "refused" and any("play shot 2" in p and "in pieces" in p for p in v.problems), v.problems
    longer = _talk([(_mid(315), _mid(360)), (1.0, 3.0), (5.0, 310 / 30 - 0.01), (_mid(590), 21.0)])
    assert longer.status == "refused" and any("in pieces" in p for p in longer.problems)


def test_a_sliver_of_another_shot_next_to_a_jump_cut_is_refused():
    # a jump cut inside shot 1, segment 2 ends 5 frames into shot 2, segment 3 starts at shot 3's change
    v = _talk([(1.0, 3.0), (5.0, 305 / 30 - 0.01), (_mid(600), 21.0)])
    assert v.status == "refused" and any("shows only 5 frames" in p for p in v.problems), v.problems


def test_the_same_shot_on_both_sides_of_a_jump_is_not_a_sliver():
    # the J1 v05 shape: a jump inside shot 1, then 5 more frames of shot 1 before its change
    v = _talk([(1.0, 4.0), (_mid(295), 12.0)])
    assert v.status == "ok", v.problems
