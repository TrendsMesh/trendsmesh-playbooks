"""Take QA's rubric, the rubric picks and the A–Z log (tm.organic_qa, `tm organic pick`): the transcript match on
ExampleEdu's two Polish takes, the pace a slow take is sped up to, a rule pick of a failing take refused, and every pick
in 03_wip/az_log.jsonl, read by the generation guard and the F1/F2 step checks."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import exampleedu
import pytest

from tm import manifest, organic_config, organic_pack, organic_qa, organic_specs, state, stepchecks
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "organic"
PNG = b"\x89PNG\r\n\x1a\n fake image bytes"
# ExampleEdu M5 PL's take (03_wip/M5_pl/take_v01.json), typed, its prompt made up: its first frame is the picked host image.
TAKE = {"model": "minimax/h3",
        "input": {"prompt": "Task: a phone-shot clip in which a dad chats to the lens at the kitchen table …",
                  "first_frame_image": "host_v01_0.png", "duration": 15, "resolution": "768P"}}
# The QA of M5 PL's take: its transcript (34 words heard from 0 to 13.74 s, 30 of the script's 33) and the manifest's
# cuts 6.75 / 11.04 s, −9.9 LUFS and peak +0.1 dBFS. At 2.47 words a second it is slow: sped up ×1.17 in the edit.
QA_PASS = {"take": "03_wip/take_v01_0.mp4", "transcript": "03_wip/qa/take_v01_0_transcript_v01.json",
           "match": 0.909, "words": 34, "speech_seconds": 13.74, "wps": 2.47, "tail_silence": 1.26,
           "cuts": [6.75, 11.04], "cut_offsets": [{"bracket": 7.0, "cut": 6.75, "offset": -0.25},
                                                  {"bracket": 11.0, "cut": 11.04, "offset": 0.04}],
           "lufs": -9.9, "peak": 0.1, "contact_sheet": "03_wip/qa/take_v01_0_contact_v01.png"}
# Round 46's voice-reference take: the transcript misses the script, and the loudness is out of the usable range.
QA_FAIL = {**QA_PASS, "match": 0.879, "lufs": -3.0}


def _words(which):
    return organic_qa.words_of(exampleedu.transcript(which))


@pytest.mark.private_data
def test_match_polish_take_word_for_word():
    script = exampleedu.take_script()
    assert [len(line.split()) for line in exampleedu.take_lines()] == [9, 8, 10, 6]     # the handoff's four host lines
    assert script == " ".join(exampleedu.take_lines()) and len(script.split()) == 33
    score = organic_qa.match(script, _words("take"))
    # Whisper hears a brand name and two numbers differently: 30 of the 33 words
    assert score == pytest.approx(30 / 33)
    assert score >= organic_config.DEFAULTS["qa"]["transcript_min"]


@pytest.mark.private_data
def test_match_garbled_voice_reference_below_threshold():
    """Round 46: H3 with a Polish voice sample of another text garbled the brand name, a number and one word."""
    score = organic_qa.match(exampleedu.take_script(), _words("voiceref"))
    assert score == pytest.approx(29 / 33)
    assert score < organic_config.DEFAULTS["qa"]["transcript_min"]


def test_match_keeps_polish_letters_and_drops_punctuation():
    assert organic_qa.match("Spróbuj dziś wieczór!", [" spróbuj", "dziś", "wieczór."]) == 1.0
    assert organic_qa.match("Spróbuj dziś wieczór!", ["Sprobuj", "dzis", "wieczor"]) == 0.0   # diacritics count
    assert organic_qa.match("a b c d", ["a", "x", "c", "d", "b"]) == 0.75   # in order: a c d
    with pytest.raises(ValueError, match="no words"):
        organic_qa.match(" … ", ["a"])


def test_slow_take_suggests_speed():
    cfg = organic_config.defaults()
    assert organic_qa.rubric_takes({**QA_PASS, "wps": 2.4}, cfg)["speed"] == 1.21   # 2.9 / 2.4, under 1.25
    assert organic_qa.rubric_takes({**QA_PASS, "wps": 2.0}, cfg)["speed"] == 1.25   # capped at qa.speed_max
    assert organic_qa.rubric_takes({**QA_PASS, "wps": 2.8}, cfg)["speed"] is None   # at qa.wps_min: not slow
    slow = organic_qa.rubric_takes({**QA_PASS, "wps": 2.4}, cfg)
    assert slow["fails"] == [] and any("1.21" in f for f in slow["findings"])


def test_rubric_fails_and_findings():
    cfg = organic_config.defaults()
    got = organic_qa.rubric_takes(QA_FAIL, cfg)
    assert len(got["fails"]) == 2
    assert "88%" in got["fails"][0] and "90%" in got["fails"][0]
    assert "-3.0 LUFS" in got["fails"][1] and "-30" in got["fails"][1] and "-5" in got["fails"][1]
    got = organic_qa.rubric_takes(QA_PASS, cfg)
    assert (got["fails"], got["speed"], len(got["findings"])) == ([], 1.17, 1)   # M5 PL passes; only its pace
    brisk = {**QA_PASS, "wps": 3.0}
    assert organic_qa.rubric_takes(brisk, cfg) == {"fails": [], "findings": [], "speed": None}
    # a cut more than qa.cut_flag_s (1 s) off its bracket, and a bracket with no cut, are findings, not fails
    late = {**brisk, "cut_offsets": [{"bracket": 3.0, "cut": 6.75, "offset": 3.75},
                                       {"bracket": 11.0, "cut": None, "offset": None}]}
    got = organic_qa.rubric_takes(late, cfg)
    assert got["fails"] == [] and len(got["findings"]) == 2
    assert "6.75" in got["findings"][0] and "3.75" in got["findings"][0] and "11" in got["findings"][1]
    # the run's own thresholds win over the defaults
    strict = {**cfg, "qa": {**cfg["qa"], "transcript_min": 0.95, "cut_flag_s": 0.2}}
    got = organic_qa.rubric_takes(brisk, strict)
    assert len(got["fails"]) == 1 and len(got["findings"]) == 1


# --- picks ------------------------------------------------------------------------------------------------

CHECKED_AT = "2026-11-07T08:00:00+00:00"   # the pack check, set back so picks made now come after it


def _record(run, stem, n, outputs, *, status="done"):
    """A replicate_run record 03_wip/<stem>_vNN.run.json and its output files."""
    wip = run.path / "03_wip"
    (wip / f"{stem}_v{n:02d}.run.json").write_text(json.dumps(
        {"model": "m", "status": status, "prediction_id": f"p{n}", "outputs": outputs}), encoding="utf-8")
    for name in outputs:
        (wip / name).write_bytes(PNG if name.endswith(".png") else b"not decoded here")


def _check(run, fixture="m5_pl_pack.json", n=1, change=None):
    """Write pack_vNN.json and record it as `tm organic pack check --stage pack` does after a pass; `change` edits
    the pack first."""
    pack = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    if change:
        change(pack)
    path = run.path / "03_wip" / f"pack_v{n:02d}.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="pack")


def _run(tmp_path, fixture):
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.level, s.budgets = "hands_off", {"ai_usd": 5.0}
    state.save(run, s)
    _check(run, fixture)
    s = state.load(run)
    s.checked["pack"]["at"] = CHECKED_AT
    state.save(run, s)
    return run


@pytest.fixture
def ov(tmp_path):
    """An organic-video production run at Hands-off with M5 PL's checked pack (host image, take), its host record
    (two images) and its take record (one take)."""
    run = _run(tmp_path, "m5_pl_pack.json")
    _record(run, "host", 1, ["host_v01_0.png", "host_v01_1.png"])
    _record(run, "take", 1, ["take_v01_0.mp4"])
    return run


def _qa(run, data, name="take_v01_0", n=1):
    path = run.path / "03_wip" / "qa" / f"{name}_qa_v{n:02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _decide_fails_qa(run, at):
    """The video check-in's fails_qa as `tm decide video fails_qa` records it (the walk is test_organic_flow's)."""
    s = state.load(run)
    s.decisions.append({"checkin": "video", "choice": "fails_qa", "by": "rule", "note": "QA fails", "at": at})
    state.save(run, s)


def _backdate(run, at):
    """Every pick in the A–Z log made at `at`."""
    log = run.path / organic_specs.AZ_LOG
    rows = [{**json.loads(line), "at": at} for line in log.read_text(encoding="utf-8").splitlines()]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _pick(capsys, run, stage, name, file, reason, *by):
    code = main(["organic", "pick", "--run", str(run.path), "--stage", stage, "--name", name, "--file", file,
                 "--reason", reason, *by, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _log(run):
    path = run.path / organic_specs.AZ_LOG
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def test_rule_pick_of_failing_take_refused(ov, capsys):
    _qa(ov, QA_FAIL)
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "the only take", "--by", "rule")
    assert (code, out["status"]) == (2, "stop")
    assert "decide `video fails_qa`" in out["message"] and "show the findings" in out["message"]
    assert "88%" in out["message"] and "-3.0 LUFS" in out["message"]
    assert _log(ov) == []   # nothing logged
    assert stepchecks.run("takes_checked", ov) is not None


def test_a_user_pick_of_a_failing_take_needs_fails_qa_after_its_qa(ov, capsys):
    """--by user is no way around the refusal: the user keeps a failing take only after `video fails_qa` was decided
    on its latest QA (the run was held for them)."""
    _qa(ov, QA_FAIL)
    _decide_fails_qa(ov, "2026-11-06T10:00:00+00:00")   # on an earlier QA
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "the user keeps it", "--by", "user")
    assert (code, out["status"]) == (2, "stop") and "video fails_qa" in out["message"] and _log(ov) == []
    _decide_fails_qa(ov, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "the user keeps it: speed it up",
                      "--by", "user")
    assert (code, out["status"]) == (0, "done")
    [row] = _log(ov)
    assert (row["by"], row["rubric"]["fails"] != []) == ("user", True)
    assert stepchecks.run("takes_checked", ov) is None


def test_a_take_pick_needs_its_qa(ov, capsys):
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "looks fine")
    assert (code, out["status"]) == (2, "stop")
    assert "tm tool take_qa" in out["message"] and _log(ov) == []


def test_a_pick_names_an_item_of_its_stage(ov, capsys):
    _qa(ov, QA_PASS)
    (ov.path / "03_wip" / "other.png").write_bytes(PNG)
    for stage, name, file in (("images", "take", "03_wip/host_v01_0.png"),        # take is a video item
                              ("takes", "host", "03_wip/take_v01_0.mp4"),         # host is an image item
                              ("images", "cover", "03_wip/host_v01_0.png"),       # not an item of the pack
                              ("images", "host", "03_wip/take_v01_0.mp4"),        # not an image
                              ("images", "host", "03_wip/other.png")):            # not made by host's records
        code, out = _pick(capsys, ov, stage, name, file, "why")
        assert (code, out["status"]) == (2, "stop"), (stage, name, file)
    assert "not a file it made" in out["message"] and "03_wip/host_v01_0.png" in out["message"]
    code, out = _pick(capsys, ov, "images", "host", "../outside.png", "why")
    assert (code, out["status"]) == (1, "error")
    code, out = _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "  ")
    assert (code, out["status"]) == (1, "error")
    assert _log(ov) == []


def test_az_log_lists_every_pick(ov, capsys):
    assert "host" in stepchecks.run("images_picked", ov)
    assert "take" in stepchecks.run("takes_checked", ov)
    code, out = _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png",
                      "both look real; _0 keeps the eyes level with the lens and a plain wall below for captions")
    assert (code, out["status"]) == (0, "done")
    assert stepchecks.run("images_picked", ov) is None
    # the guard reads the pick: the take's first frame is a picked image now
    assert organic_specs.check(ov, TAKE, ov.path / "03_wip" / "take.json") == []
    _qa(ov, QA_PASS)
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass: word for word, cuts on time")
    assert (code, out["status"]) == (0, "done")
    assert stepchecks.run("takes_checked", ov) is None
    image, take = _log(ov)
    assert list(image) == list(organic_specs.AZ_FIELDS) == list(take)
    assert (image["stage"], image["name"], image["file"], image["by"]) == ("images", "host", "03_wip/host_v01_0.png",
                                                                          "rule")
    assert image["rubric"] == {"against": list(organic_qa.IMAGE_RUBRIC)}
    assert (take["stage"], take["name"], take["file"]) == ("takes", "take", "03_wip/take_v01_0.mp4")
    assert take["rubric"]["qa"] == "03_wip/qa/take_v01_0_qa_v01.json"
    assert (take["rubric"]["match"], take["rubric"]["lufs"], take["rubric"]["fails"]) == (0.909, -9.9, [])
    assert "word for word" in take["reason"] and take["at"].startswith("20")
    rows = [r for r in manifest.rows(ov) if r["file"] in (image["file"], take["file"])]
    assert len(rows) == 2 and all("pick" in r["source"] for r in rows)


def test_a_pick_before_the_pack_is_checked_again_no_longer_counts(ov, capsys):
    _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "the sharper face")
    _qa(ov, QA_PASS)
    _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    _backdate(ov, "2026-11-07T09:00:00+00:00")   # after the check at 08:00
    assert stepchecks.run("images_picked", ov) is None and stepchecks.run("takes_checked", ov) is None
    _check(ov, n=2, change=_at_1080p)   # re-planned now at 1080p: every item changes
    for check in ("images_picked", "takes_checked"):
        assert "before the pack was checked again" in stepchecks.run(check, ov)


def _at_1080p(pack):
    pack["resolution"]["choice"] = "1080p"


def _redo_of(item):
    """A re-plan that only adds a priced redo line for `item` (PR C fix wave, part 3)."""
    def change(pack):
        line = next(x for x in pack["cost"]["lines"] if x["item"] == item)
        pack["cost"]["lines"].append({**line, "what": f"{line['what']}, redo", "redo": True})
        pack["cost"]["totals"]["ai_usd"] = round(pack["cost"]["totals"]["ai_usd"] + line["cost"], 2)
    return change


def _picks_made(ov, capsys):
    _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "the sharper face")
    _qa(ov, QA_PASS)
    _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    _backdate(ov, "2026-11-07T09:00:00+00:00")   # after the check at 08:00
    assert stepchecks.run("images_picked", ov) is None and stepchecks.run("takes_checked", ov) is None


def test_paying_for_a_redo_keeps_the_other_items_picks(ov, capsys):
    """The controller's ruling (part 3): a re-check whose only change is a redo line for host stales host's pick
    alone (the guard has no picked frame until host is made again and picked); the take's pick keeps counting."""
    _picks_made(ov, capsys)
    _check(ov, n=2, change=_redo_of("host"))
    assert "before the pack was checked again" in stepchecks.run("images_picked", ov)
    assert stepchecks.run("takes_checked", ov) is None
    assert organic_specs.picked(ov) == set()                   # host's own pick needs the redo's new image
    _record(ov, "host", 2, ["host_v02_0.png"])                 # the paid redo
    _pick(capsys, ov, "images", "host", "03_wip/host_v02_0.png", "the redo")
    assert stepchecks.run("images_picked", ov) is None and stepchecks.run("takes_checked", ov) is None
    # a later redo of the take keeps host's new pick
    _check(ov, n=3, change=lambda p: (_redo_of("host")(p), _redo_of("take")(p)))
    assert stepchecks.run("images_picked", ov) is None
    assert "before the pack was checked again" in stepchecks.run("takes_checked", ov)


def test_a_changed_model_or_item_still_stales_its_pick(ov, capsys):
    """A re-check that changes an item (its model, its seconds) stales that item's pick, and only that one."""
    _picks_made(ov, capsys)

    def longer_take(pack):
        next(i for st in pack["stages"] for i in st["items"] if i["name"] == "take")["seconds"] = 12

    _check(ov, n=2, change=longer_take)
    assert stepchecks.run("images_picked", ov) is None
    assert "before the pack was checked again" in stepchecks.run("takes_checked", ov)

    def other_image_model(pack):
        longer_take(pack)
        next(i for st in pack["stages"] for i in st["items"] if i["name"] == "host")["model"] = "openai/gpt-image-1"

    _check(ov, n=3, change=other_image_model)
    assert "before the pack was checked again" in stepchecks.run("images_picked", ov)


def test_a_recheck_that_changes_no_item_keeps_every_pick(ov, capsys):
    _picks_made(ov, capsys)
    _check(ov, n=2, change=lambda p: p["facts"].append({"claim": "x", "source": "y", "url": "https://e.org"}))
    assert stepchecks.run("images_picked", ov) is None and stepchecks.run("takes_checked", ov) is None


def test_a_redone_item_needs_a_pick_of_its_new_take(ov, capsys):
    _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "the sharper face")
    assert stepchecks.run("images_picked", ov) is None
    _record(ov, "host", 2, ["host_v02_0.png", "host_v02_1.png"])   # made again (a redo)
    gap = stepchecks.run("images_picked", ov)
    assert "not from the item's latest take" in gap and "03_wip/host_v02_0.png" in gap
    code, out = _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "still the best")
    assert (code, out["status"]) == (2, "stop") and "earlier take" in out["message"]
    code, out = _pick(capsys, ov, "images", "host", "03_wip/host_v02_1.png", "the new one with the calmer counter")
    assert (code, out["status"]) == (0, "done") and stepchecks.run("images_picked", ov) is None
    # a failed redo makes nothing: the latest take is still the last one that made files
    _record(ov, "host", 3, [], status="failed")
    assert stepchecks.run("images_picked", ov) is None


def test_a_newer_qa_needs_the_take_picked_again(ov, capsys):
    _qa(ov, QA_PASS)
    _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    assert stepchecks.run("takes_checked", ov) is None
    _qa(ov, QA_FAIL, n=2)
    gap = stepchecks.run("takes_checked", ov)
    assert "newer QA" in gap and "take_v01_0_qa_v02.json" in gap
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    assert (code, out["status"]) == (2, "stop")   # picked on the latest QA, which fails


def test_a_narrated_take_is_judged_on_cuts_and_loudness(tmp_path, capsys):
    """P3 of the pet store: the narrator is ElevenLabs (added in the edit), so the H3 take carries no spoken lines."""
    run = _run(tmp_path, "p3_sections_pack.json")
    _record(run, "take", 1, ["take_v01_0.mp4"])
    cfg = organic_config.defaults()
    silent = {**QA_PASS, "transcript": None, "match": None, "words": None, "speech_seconds": None, "wps": None,
              "tail_silence": None, "lufs": None, "peak": None}
    assert organic_qa.rubric_takes(silent, cfg, speech=False) == {"fails": [], "findings": [], "speed": None}
    assert organic_qa.rubric_takes({**silent, "match": 0.05, "wps": 1.0}, cfg, speech=False)["fails"] == []
    assert len(organic_qa.rubric_takes(silent, cfg)["fails"]) == 2   # with speech: no match, no sound
    loud = organic_qa.rubric_takes({**silent, "lufs": -3.0}, cfg, speech=False)
    assert len(loud["fails"]) == 1 and "-3.0 LUFS" in loud["fails"][0]
    _qa(run, {**silent, "match": 0.05})   # stray sound heard, no script
    code, out = _pick(capsys, run, "takes", "take", "03_wip/take_v01_0.mp4", "cuts on time, no artefacts")
    assert (code, out["status"]) == (0, "done")
    gap = stepchecks.run("takes_checked", run)   # the take passes; P3's animation insert (S2) waits for its own
    assert "take:" not in gap and gap.startswith("each animation is drawn from its accepted storyboard (S2: "), gap


def test_a_qa_that_is_not_an_object_is_refused(ov, capsys):
    (ov.path / "03_wip" / "qa").mkdir(parents=True)
    (ov.path / "03_wip" / "qa" / "take_v01_0_qa_v01.json").write_text("[1, 2]", encoding="utf-8")
    code, out = _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    assert (code, out["status"]) == (2, "stop") and "not a JSON object" in out["message"]


def test_a_take_without_qa_is_not_checked(ov, capsys):
    """takes_checked: each video item has a QA file of its picked take and a pick."""
    _qa(ov, QA_PASS)
    _pick(capsys, ov, "takes", "take", "03_wip/take_v01_0.mp4", "QA pass")
    (ov.path / "03_wip" / "qa" / "take_v01_0_qa_v01.json").unlink()
    gap = stepchecks.run("takes_checked", ov)
    assert "take_v01_0.mp4" in gap.replace("\\", "/") and "take_qa" in gap


def test_the_checks_need_a_checked_pack(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    for name in ("images_picked", "takes_checked"):
        assert "pack check" in stepchecks.run(name, run)


def test_steps_require_the_checks():
    from tm import flow

    steps = {s.id: s for s in flow.steps(ORGANIC_VIDEO)}
    assert steps["F1"].requires == ("images_picked",) and steps["F2"].requires == ("takes_checked",)
    assert stepchecks.NAMES["images_picked"] == "tm.organic_qa:images_gap"
    assert stepchecks.NAMES["takes_checked"] == "tm.organic_qa:takes_gap"


def test_a_damaged_log_is_mended_before_any_pick(ov, capsys):
    (ov.path / organic_specs.AZ_LOG).write_text('{"stage": "images", "name": "host"\n', encoding="utf-8")
    code, out = _pick(capsys, ov, "images", "host", "03_wip/host_v01_0.png", "the sharper face")
    assert (code, out["status"]) == (2, "stop") and "damaged lines (1)" in out["message"]
    assert "readable" in stepchecks.run("images_picked", ov)
    assert (ov.path / organic_specs.AZ_LOG).read_text(encoding="utf-8").count("\n") == 1   # nothing appended


# --- take_qa's parts that need no media ---------------------------------------------------------------------

# ffmpeg's ebur128 summary as the Windows builds print it (each line prefixed), with a silent true peak
EBUR128 = """[Parsed_ebur128_0 @ 000001d2c] t: 4.4  TARGET:-23 LUFS    M: -18.2 S: -18.3     I: -18.4 LUFS
[Parsed_ebur128_0 @ 000001d2c] Summary:

[Parsed_ebur128_0 @ 000001d2c]   Integrated loudness:
[Parsed_ebur128_0 @ 000001d2c]     I:         -9.9 LUFS
[Parsed_ebur128_0 @ 000001d2c]     Threshold: -20.1 LUFS

[Parsed_ebur128_0 @ 000001d2c]   Loudness range:
[Parsed_ebur128_0 @ 000001d2c]     LRA:         4.2 LU

[Parsed_ebur128_0 @ 000001d2c]   True peak:
[Parsed_ebur128_0 @ 000001d2c]     Peak:        0.1 dBFS
"""


def test_the_loudness_parser_reads_the_summary():
    from tm.tools import take_qa

    assert take_qa.parse_ebur128(EBUR128) == (-9.9, 0.1)
    plain = "\n".join(line.split("] ", 1)[-1] for line in EBUR128.splitlines())   # the prefix-free form
    assert take_qa.parse_ebur128(plain) == (-9.9, 0.1)
    assert take_qa.parse_ebur128(EBUR128.replace("0.1 dBFS", "-inf dBFS")) == (-9.9, None)
    assert take_qa.parse_ebur128("t: 4.4 I: -18.4 LUFS") == (None, None)   # no Summary: nothing measured


def test_an_ffmpeg_failure_is_never_no_sound(monkeypatch):
    import subprocess

    from tm.tools import _common, take_qa

    monkeypatch.setattr(_common, "probe", lambda path: {"has_audio": True})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"Invalid data"))
    with pytest.raises(subprocess.CalledProcessError):
        take_qa.loudness(Path("take.mp4"))
    monkeypatch.setattr(_common, "probe", lambda path: {"has_audio": False})
    assert take_qa.loudness(Path("take.mp4")) == (None, None)


@pytest.mark.private_data
def test_script_from_the_pack_is_the_lines_its_one_take_says(tmp_path):
    from tm.tools import _common, take_qa

    m5 = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    for line, text in zip(m5["script"]["lines"], exampleedu.take_lines(), strict=True):   # the handoff's lines, not the made-up
        line["text"] = text
    path = tmp_path / "pack_v01.json"
    path.write_text(json.dumps(m5, ensure_ascii=False), encoding="utf-8")
    assert take_qa.script_text(path) == exampleedu.take_script()   # the four host lines, as the take's prompt said them
    p3 = json.loads((FIXTURES / "p3_sections_pack.json").read_text(encoding="utf-8"))
    path.write_text(json.dumps(p3, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(_common.ToolError, match="elevenlabs_narrator.*Leave out --script"):
        take_qa.script_text(path)
    two = {**m5, "stages": [*m5["stages"], {"stage": "video", "items": [{"name": "b-roll", "model": "minimax/h3",
                                                                          "seconds": 6}]}]}
    path.write_text(json.dumps(two, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(_common.ToolError, match="2 video items"):
        take_qa.script_text(path)
