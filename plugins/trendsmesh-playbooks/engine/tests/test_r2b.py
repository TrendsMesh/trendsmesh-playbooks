import json
from datetime import date
from pathlib import Path

import pytest

from tm import config, r2, r2b, state
from tm.cli import main
from tm.meta_rows import normalise
from tm.runfolder import RunFolder

FIXTURE = Path(__file__).parent / "fixtures" / "ad3_same_file_uploads.json"
RAW = json.loads(FIXTURE.read_text(encoding="utf-8"))
UPLOADS = {k: normalise(v) for k, v in RAW.items()}
LENGTH = 24.149


def rows_with_plays(plays, *, p25=0.3, p50=0.6, p75=0.5, p95=0.6, p100=0.9):
    c = [plays]
    for r in (p25, p50, p75, p95, p100):
        c.append(round(c[-1] * r))
    keys = ("video_play_actions", "video_p25_watched_actions", "video_p50_watched_actions",
            "video_p75_watched_actions", "video_p95_watched_actions", "video_p100_watched_actions")
    return normalise([{"id": "x", "date_start": "2026-10-01", "date_stop": "2026-10-01",
                       **{k: str(v) for k, v in zip(keys, c)}}])


def test_rc2_ad3_is_structural_at_p75_p50():
    s = r2b.check(UPLOADS, length_s=LENGTH)
    assert s.structural and s.step == "p75/p50"
    assert s.segment_s == (12.07, 18.11)  # rounded to 0.01 s: 0.5 and 0.75 of 24.149
    assert len(s.uploads) == 4 and s.skipped == []
    assert all(0.491 <= round(u["ladder"]["p75/p50"], 3) <= 0.617 for u in s.uploads)
    assert all(u["weakest"] == "p75/p50" for u in s.uploads)
    assert {u["ad_id"]: u["plays"] for u in s.uploads}["9000000000011"] == 5971


def test_upload_under_1000_plays_is_skipped():
    s = r2b.check({**UPLOADS, "x": rows_with_plays(800)}, LENGTH)
    assert {"ad_id": "x", "plays": 800, "why": "fewer than 1,000 plays"} in s.skipped
    assert s.structural and len(s.uploads) == 4


def test_one_upload_is_never_structural():
    s = r2b.check({"a": UPLOADS["9000000000011"]}, LENGTH)
    assert not s.structural and s.step is None and s.segment_s is None


def test_a_skipped_upload_does_not_count_toward_two():
    s = r2b.check({"a": UPLOADS["9000000000011"], "x": rows_with_plays(800)}, LENGTH)
    assert not s.structural and len(s.uploads) == 1 and len(s.skipped) == 1


def test_different_weakest_steps_are_not_structural():
    other = rows_with_plays(5000, p50=0.3, p75=0.7)  # p50/p25 is weakest here
    s = r2b.check({"a": UPLOADS["9000000000011"], "b": other}, LENGTH)
    assert not s.structural and s.step is None
    assert {u["weakest"] for u in s.uploads} == {"p75/p50", "p50/p25"}


def test_ties_go_to_the_earlier_step():
    tie = rows_with_plays(5000, p50=0.5, p75=0.5, p95=0.9)
    s = r2b.check({"a": tie, "b": tie}, LENGTH)
    assert s.structural and s.step == "p50/p25"


def test_threshold_is_a_parameter():
    s = r2b.check({"a": UPLOADS["9000000000011"], "b": UPLOADS["9000000000012"]}, LENGTH, min_plays=5500)
    assert not s.structural and [k["ad_id"] for k in s.skipped] == ["b"]


def test_to_json_round_trip():
    s = r2b.check(UPLOADS, LENGTH)
    assert json.loads(json.dumps(s.to_json()))["segment_s"] == [12.07, 18.11]


def test_config_default_structural_recut_off():
    assert config.value(None, "diagnosis.structural_recut") is False


def test_diagnosis_without_structural_loads_from_a_02x_file():
    d = r2.Diagnosis.from_json({"stage": "hook", "refresh": True})
    assert d.structural is None and "structural" in d.to_json()


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy"
    ws.mkdir()
    return RunFolder.create(ws, "Ad 3", date(2026, 11, 6))


def _uploads_file(tmp_path, data=RAW):
    f = tmp_path / "uploads.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def test_structural_without_a_diagnosis_stops_with_exit_2(run, tmp_path, capsys):
    code = main(["structural", "--run", str(run.path), "--uploads", str(_uploads_file(tmp_path)),
                 "--length-s", "24.149"])
    assert code == 2
    assert "diagnosis" in capsys.readouterr().out.lower()
    assert not list((run.path / "04_final").glob("structural_v*.json"))


def test_rc3_structural_is_reported_not_a_stage(run, tmp_path, capsys):
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True))
    before = state.load(run).diagnosis
    args = ["structural", "--run", str(run.path), "--uploads", str(_uploads_file(tmp_path)),
            "--length-s", "24.149", "--json"]
    assert main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["structural"] is True and out["file"] == "04_final/structural_v01.json"
    diagnosis = state.load(run).diagnosis
    assert diagnosis["stage"] == "hook" and diagnosis["structural"]["structural"] is True
    assert diagnosis["refresh"] == before["refresh"] and diagnosis["target_stage"] == before["target_stage"]
    assert (run.path / "04_final" / "structural_v01.json").is_file()
    assert "structural_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")
    assert main(args) == 0  # again: a new version, the old one stays
    assert (run.path / "04_final" / "structural_v02.json").is_file()
    assert (run.path / "04_final" / "structural_v01.json").is_file()


def test_bad_uploads_file_is_an_error(run, tmp_path):
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True))
    f = tmp_path / "bad.json"
    f.write_text("[1, 2]", encoding="utf-8")
    assert main(["structural", "--run", str(run.path), "--uploads", str(f), "--length-s", "24"]) == 1
    assert main(["structural", "--run", str(run.path), "--uploads", str(_uploads_file(tmp_path)),
                 "--length-s", "0"]) == 1


def test_an_upload_without_play_data_has_its_own_reason():
    rows = normalise([{"id": "x", "date_start": "2026-10-01", "date_stop": "2026-10-01"}])
    s = r2b.check({"a": UPLOADS["9000000000011"], "x": rows}, LENGTH)
    assert s.skipped == [{"ad_id": "x", "plays": 0, "why": "no video play data"}]
    assert r2b.check({"y": rows_with_plays(800)}, LENGTH).skipped[0]["why"] == "fewer than 1,000 plays"


def test_a_done_run_refuses_structural_and_writes_nothing(run, tmp_path):
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True))
    s = state.load(run)
    s.status = "done"
    state.save(run, s)
    assert main(["structural", "--run", str(run.path), "--uploads", str(_uploads_file(tmp_path)),
                 "--length-s", "24.149"]) == 1
    assert not list((run.path / "04_final").glob("structural_v*.json"))
