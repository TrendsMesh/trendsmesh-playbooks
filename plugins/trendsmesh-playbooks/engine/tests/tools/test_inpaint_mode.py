"""inpaint_mode: budget (OpenCV) when the new captions cover the old ones, otherwise pro."""

import json

import pytest

pytestmark = pytest.mark.tools
pytest.importorskip("cv2")

from _media import make_clip  # noqa: E402
from tm.tools import inpaint_mode  # noqa: E402



def _clips(tmp_path):
    black = "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill"
    mask = make_clip(tmp_path / "maska.mp4", vf=f"{black},drawbox=x=100:y=700:w=300:h=80:color=white:t=fill",
                     tone=False, seconds=1.0)
    covered = make_clip(tmp_path / "covered.mp4", vf="drawbox=x=90:y=690:w=320:h=100:color=white:t=fill",
                        tone=False, seconds=1.0)
    bare = make_clip(tmp_path / "bare.mp4", vf="drawbox=x=0:y=0:w=iw:h=ih:color=gray:t=fill",
                     tone=False, seconds=1.0)
    return mask, covered, bare


def test_budget_when_covered_pro_when_bare(tmp_path):
    mask, covered, bare = _clips(tmp_path)
    crop = (0, 600, 540, 900)
    assert inpaint_mode.decide(mask, covered, crop)["mode"] == "budget"
    res = inpaint_mode.decide(mask, bare, crop)
    assert res["mode"] == "pro" and res["frames_with_old_caption"] == 25


def test_cli_records_decision(tmp_path, run):
    mask, covered, _ = _clips(tmp_path)
    assert inpaint_mode.main(["--run", str(run.path), str(mask), str(covered),
                              "--crop", "0", "600", "540", "900"]) == 0
    out = run.path / "03_wip" / "inpaint_mode_v01.json"
    assert json.loads(out.read_text(encoding="utf-8"))["mode"] == "budget"


def test_pro_waits_for_an_approved_ai_budget(tmp_path, run, capsys):
    """Follow-up to issue 21: with no AI budget approved, the free tool is the mode that can run now; ProPainter is
    reported as wanted, so the agent shows both ways and asks. With money approved and left, pro."""
    from tm import state

    mask, _, bare = _clips(tmp_path)
    args = ["--run", str(run.path), str(mask), str(bare), "--crop", "0", "600", "540", "900", "--json"]
    assert inpaint_mode.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["mode"], out["measured"], out["pro_wanted"], out["ai_usd_left"]) == ("budget", "pro", True, 0)
    s = state.load(run)
    s.budgets["ai_usd"], s.spend["ai_usd"] = 0.5, 0.2
    state.save(run, s)
    assert inpaint_mode.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["mode"], out["measured"], out["pro_wanted"], out["ai_usd_left"]) == ("pro", "pro", False, 0.3)
    s.spend["ai_usd"] = 0.5
    state.save(run, s)
    assert inpaint_mode.main(args) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "budget"   # all spent: the free way again
