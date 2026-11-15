"""A product scene without the product's name (follow-up to issue 12): `tm brief check` warns, it does not fail.

`product_phone` and `morning_then_product` draw the brief's product from `params.product`; without it the screen is a
plain placeholder (with `fixture: "book"`, the dry run's book). A made-up brief, public.
"""

import argparse
import json
from datetime import date

import pytest

from tm import brief, brief_checks
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder


def _beat(scene, params=None):
    return {"t0": 0, "t1": 2, "see": "x", "hear": "", "ost": "", "animatic": {"scene": scene, "params": params or {}}}


def _brief(*beats):
    return {"meta": {"product": {"name": "Lumen"}}, "concepts": [{"id": "C1", "beats": list(beats)}]}


def test_a_product_scene_without_its_product_is_a_warning():
    found = brief_checks.warnings(_brief(
        _beat("product_phone", {"product": "Lumen lamp", "screen": "Dims by itself"}),   # named: fine
        _beat("product_phone", {"highlight": 2}),
        _beat("finger_tap", {"note": "Tap"}),                                             # not a product scene
        _beat("morning_then_product", {"product": "  "}),
        _beat("morning_then_product", {"fixture": "book"})))
    assert [w.field for w in found] == ["concepts[0].beats[1].animatic.params.product",
                                        "concepts[0].beats[3].animatic.params.product",
                                        "concepts[0].beats[4].animatic.params.product"]
    assert "plain placeholder" in found[0].what and "C1's beat 2" in found[0].what
    assert "the dry run's book" in found[2].what
    assert all("Lumen" in w.todo and "params.product" in w.todo for w in found)


def test_a_brief_without_animatic_params_has_no_warning():
    beat = {"t0": 0, "t1": 2, "see": "x", "hear": "", "ost": ""}
    assert brief_checks.warnings({"concepts": [{"id": "C1", "beats": [beat, {**beat, "animatic": None}]}]}) == []
    assert brief_checks.warnings({"concepts": "not a list"}) == []


@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)


def test_brief_check_passes_and_says_the_warning(run, monkeypatch, capsys):
    path = run.path / "04_final" / f"{brief_checks.STEM}_v01.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(_brief(_beat("product_phone", {"highlight": 1}))), encoding="utf-8")
    monkeypatch.setattr(brief_checks, "check", lambda *a: [])            # the brief holds otherwise
    monkeypatch.setattr(brief_checks, "running_ads", lambda r: ([], 0))
    args = argparse.Namespace(file=str(path), stage="brief", json=True)
    assert brief._check_brief(args, run) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done"
    assert [w["field"] for w in out["warnings"]] == ["concepts[0].beats[0].animatic.params.product"]
    assert "plain placeholder" in out["message"]
