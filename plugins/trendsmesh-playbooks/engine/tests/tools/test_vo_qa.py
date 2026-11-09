"""vo_qa.compare (R9): onset steepness (dB per 5 ms) and spectral flatness against the original."""

import json
import subprocess

import pytest

pytestmark = pytest.mark.tools
pytest.importorskip("numpy")

from _media import ffmpeg  # noqa: E402
from tm.tools import vo_qa  # noqa: E402

# "Syllables": 220 Hz bursts of 0.12 s every 0.25 s, with a little noise floor.
SHARP = "0.6*sin(2*PI*220*t)*lt(mod(t,0.25),0.12)+0.002*(random(0)-0.5)"
# The same bursts with a 50 ms attack: what a smeared time stretch does to onsets.
SMEARED = "0.6*sin(2*PI*220*t)*min(1,mod(t,0.25)/0.05)*lt(mod(t,0.25),0.12)+0.002*(random(0)-0.5)"


def _wav(path, expr):
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}':s=44100:d=2", str(path)], check=True)
    return path


def test_vo_qa_identical_is_within_tolerance(tmp_path):
    a = _wav(tmp_path / "linia nowa.wav", SHARP)
    res = vo_qa.compare(a, a)
    assert res["within_tolerance"] is True
    assert res["onset_steepness_db_per_5ms"]["processed"] == res["onset_steepness_db_per_5ms"]["original"]
    assert res["onset_steepness_db_per_5ms"]["original"] > 10
    assert 0 < res["spectral_flatness"]["original"] < 1
    assert res["tolerance"] == 0.10


def test_vo_qa_smeared_onsets_fail(tmp_path):
    res = vo_qa.compare(_wav(tmp_path / "s.wav", SMEARED), _wav(tmp_path / "o.wav", SHARP))
    assert res["within_tolerance"] is False
    assert res["onset_steepness_db_per_5ms"]["rel_diff"] < -0.10


def test_vo_qa_noisy_line_fails_on_flatness(tmp_path):
    noisy = SHARP.replace("0.002*(random(0)-0.5)", "0.05*(random(0)-0.5)")
    res = vo_qa.compare(_wav(tmp_path / "n.wav", noisy), _wav(tmp_path / "o.wav", SHARP))
    assert res["within_tolerance"] is False
    assert res["spectral_flatness"]["rel_diff"] > 0.10


def test_cli_takes_tolerance_from_config_and_records(run, tmp_path):
    (run.path / "config.yaml").write_text("vo:\n  qa_tolerance: 0.5\n", encoding="utf-8")
    a = _wav(tmp_path / "a.wav", SHARP)
    assert vo_qa.main(["--run", str(run.path), str(a), str(a), "--json"]) == 0
    out = run.path / "03_wip" / "vo_qa_v01.json"
    assert json.loads(out.read_text(encoding="utf-8"))["tolerance"] == 0.5
    assert "03_wip/vo_qa_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")
