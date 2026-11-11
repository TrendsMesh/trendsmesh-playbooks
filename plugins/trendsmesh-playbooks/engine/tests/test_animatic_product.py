"""The animatic's product shots (issue #12): `product_phone` and `morning_then_product` draw the brief's own product
(its name, what is on the screen, a picture of it from the run), and the dry run's book only as a fixture.

The scenes are drawn by node with a canvas that records what is written on it (no browser): the test skips without
node. A made-up brief, public.
"""

import base64
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tm import animatic, manifest
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder
from tm.stops import Stop

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg==")

# scenes.js, the ANIM and engine.js in one context, as the page loads them; a 2D context that records its texts
# and pictures; then the frame at a time, after the page's load (which decodes the pictures first).
DRAW = r"""
const fs = require('fs'), vm = require('vm');
const [scenes, anim, engine, at] = process.argv.slice(2);
const texts = [], pictures = [];
const ctx = new Proxy({}, {
  get(o, k) {
    if (k in o) return o[k];
    if (k === 'fillText') return (s) => texts.push(String(s));
    if (k === 'drawImage') return (img) => pictures.push(img.src);
    if (k === 'measureText') return (s) => ({ width: String(s).length * 20 });
    if (k === 'createRadialGradient') return () => ({ addColorStop() {} });
    return () => {};
  },
  set(o, k, v) { o[k] = v; return true; },
});
class Picture {
  set src(v) { this.s = v; this.naturalWidth = 40; this.naturalHeight = 20; }
  get src() { return this.s; }
  decode() { return Promise.resolve(); }
}
let onload = null;
const window = { addEventListener: (e, f) => { if (e === 'load') onload = f; } };
const document = { createElement: () => ({ style: {}, getContext: () => ctx }), body: { style: {}, appendChild() {} } };
const box = vm.createContext({ window, document, navigator: { webdriver: true }, Image: Picture });
vm.runInContext(fs.readFileSync(scenes, 'utf8'), box);
vm.runInContext(fs.readFileSync(anim, 'utf8'), box);
vm.runInContext(fs.readFileSync(engine, 'utf8'), box);
(async () => {
  await onload();
  texts.length = 0; pictures.length = 0;
  window.seek(Number(at));
  console.log(JSON.stringify({ texts, pictures }));
})();
"""

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node draws the scenes")


def _beat(t0, scene, params):
    return {"t0": t0, "t1": t0 + 2, "see": "x", "hear": "", "ost": "", "animatic": {"scene": scene, "params": params}}


def _concept(*beats) -> dict:
    return {"id": "C1", "beats": list(beats)}


def _draw(tmp_path: Path, anim_js: str, at: float) -> dict:
    (tmp_path / "anim.js").write_text(anim_js, encoding="utf-8")
    (tmp_path / "draw.js").write_text(DRAW, encoding="utf-8")
    got = subprocess.run(["node", str(tmp_path / "draw.js"), str(animatic.SCENES_JS), str(tmp_path / "anim.js"),
                          str(animatic.JS_DIR / "engine.js"), str(at)], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _anim_js(concept: dict) -> str:
    return "window.ANIM = " + json.dumps(animatic.build_anim(concept)) + ";\n"


@needs_node
def test_product_scenes_draw_the_briefs_product_not_the_book(tmp_path):
    concept = _concept(
        _beat(0, "product_phone", {"product": "Lumen lamp", "screen": ["Dims by itself", "Warm at night"],
                                   "highlight": 1}),
        _beat(2, "morning_then_product", {"product": "Lumen lamp", "screen": "Set the evening, then forget it."}),
        _beat(4, "product_phone", {"highlight": 2}),                  # the dry run's params alone: no book either
        _beat(6, "product_phone", {"fixture": "book", "highlight": 2}))
    js = _anim_js(concept)
    first = _draw(tmp_path, js, 1.0)["texts"]
    assert "Lumen lamp" in first and "Dims by itself" in first and "Warm at night" in first
    later = _draw(tmp_path, js, 3.5)["texts"]                        # past the morning notebook
    assert "Lumen lamp" in later and "Set the evening, then forget it." in " ".join(later)   # wrapped on the screen
    for at in (1.0, 3.5, 5.0):
        assert "LUCID" not in _draw(tmp_path, js, at)["texts"]
    assert "LUCID" in _draw(tmp_path, js, 7.0)["texts"]              # the fixture, asked for by name


def _run(tmp_path, monkeypatch, image) -> RunFolder:
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)
    (run.path / "01_base").mkdir(exist_ok=True)
    (run.path / "01_base" / "lumen.png").write_bytes(PNG)
    brief = {"concepts": [_concept(_beat(0, "product_phone", {"product": "Lumen lamp", "image": image}))]}
    (run.path / "04_final").mkdir(exist_ok=True)
    (run.path / "04_final" / "brief_pack_v01.json").write_text(json.dumps(brief), encoding="utf-8")
    return run


@needs_node
def test_a_product_picture_from_the_run_is_inlined_and_drawn(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "01_base/lumen.png")
    items = animatic.build(run, run.path / "04_final" / "brief_pack_v01.json", formats=["9x16"])
    js = (run.path / animatic.WIP / "C1_anim_v01.js").read_text(encoding="utf-8")
    uri = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")
    assert uri in js and "01_base/lumen.png" not in js and items[0]["html"].endswith("C1_9x16_v01.html")
    drawn = _draw(tmp_path, js, 1.0)
    assert drawn["pictures"] == [uri] and "Lumen lamp" in drawn["texts"]
    brief = json.loads((run.path / "04_final" / "brief_pack_v01.json").read_text(encoding="utf-8"))
    assert brief["concepts"][0]["beats"][0]["animatic"]["params"]["image"] == "01_base/lumen.png"   # the brief as read


@pytest.mark.parametrize("image", ["../lumen.png", "/tmp/lumen.png", "https://cdn.example.com/lumen.png",
                                   "01_base/none.png", "04_final/brief_pack_v01.json", 3])
def test_a_picture_that_is_not_an_image_of_the_run_stops(tmp_path, monkeypatch, image):
    run = _run(tmp_path, monkeypatch, image)
    rows = manifest.rows(run)
    with pytest.raises(Stop, match=r"names the image .*Nothing was written"):
        animatic.build(run, run.path / "04_final" / "brief_pack_v01.json", formats=["9x16"])
    assert not (run.path / animatic.WIP).exists() and manifest.rows(run) == rows
