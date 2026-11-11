"""tm brief animatic (the port of the handoff's build_animatic.py) and tm brief evidence (CB8, CB11).

The LD dry run's `04_final/brief_pack_v01.json` (with `ld.py`'s plugin blocks) must rebuild the
reference `03_wip/animatic_gen/` v03 files exactly. The real render is `test_atlas.py`'s (opt-in, `-m video`);
here `atlas.render` is replaced. No test touches the network: `requests.get` is replaced wherever
a thumbnail would be fetched.
"""

import json
from pathlib import Path

import pytest
import requests
import yaml

import ld
import private
from tm import animatic, atlas, brief_page, manifest, page, state, trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder
from tm.stops import Stop
from tm.tools import _common as c

GEN = ld.LD / "03_wip" / "animatic_gen"
OUT = "03_wip/animatic"
V01 = "04_final/brief_pack_v01.json"
ALL = [(cid, fmt) for cid in ("C1", "C2", "C3") for fmt in ("9x16", "4x5")]
AGAIN = "The run continues from the same place."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return folder


def _write(run: RunFolder, rel: str, data) -> Path:
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def run(ws) -> RunFolder:
    """A creative brief run with the LD brief as 04_final/brief_pack_v01.json."""
    run = RunFolder.create(ws, ld.NAME, ld.CREATED, playbook=CREATIVE_BRIEF)
    _write(run, V01, ld.brief())
    return run


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _files(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()} \
        if folder.is_dir() else {}


def _set(run: RunFolder, **fields) -> None:
    s = state.load(run)
    for key, value in fields.items():
        setattr(s, key, value)
    state.save(run, s)


def _config(run: RunFolder, data: dict) -> None:
    (run.path / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


# --- the storyboard files ------------------------------------------------------------------------

@pytest.mark.private_data
def test_animatic_files_rebuild_ld_v03(run):
    items = animatic.build(run, run.path / V01, version="v03")
    out = run.path / OUT
    built = _files(out)
    expected = {f.name: private.alias(f.read_bytes().replace(b"\r", b"")) for f in GEN.iterdir() if f.is_file()}
    assert len(expected) == 11                   # the nine v03 files, engine.js and scenes.js
    assert built == expected
    assert [(i["concept"], i["format"]) for i in items] == ALL
    assert items[0]["html"] == f"{OUT}/C1_9x16_v03.html" and "mp4" not in items[0]
    assert not (out / "renders").exists()
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"   # no render, no new brief
    rows = [r for r in manifest.rows(run) if r["source"] == animatic.SOURCE]
    assert sorted(r["file"] for r in rows) == sorted(f"{OUT}/{n}" for n in expected if "_v03." in n)
    assert {r["parent"] for r in rows if r["file"].endswith(".js")} == {V01}
    assert {r["file"]: r["parent"] for r in rows}[f"{OUT}/C2_4x5_v03.html"] == f"{OUT}/C2_anim_v03.js"


def test_build_anim_is_the_originals():
    concept = {"id": "C9", "beats": [
        {"t0": 0, "t1": 2, "hear": ' "I wake up" ', "animatic": {"scene": "selfie_talk", "label": "hook"}},
        {"t0": 2, "t1": 5, "hear": "music only", "animatic": {"scene": "back_to_sleep", "params": {"a": 1},
                                                             "zoom": [1, 1.1], "texts": ["Night 1"]}}]}
    assert animatic.build_anim(concept) == {"id": "C9", "duration": 5, "beats": [
        {"t0": 0, "t1": 2, "label": "BEAT 1 · HOOK", "scene": "selfie_talk", "params": {}, "zoom": [1, 1.04],
         "texts": [], "vo": 'VO: "I wake up"'},
        {"t0": 2, "t1": 5, "label": "BEAT 2", "scene": "back_to_sleep", "params": {"a": 1}, "zoom": [1, 1.1],
         "texts": ["Night 1"], "vo": "music only"}]}
    assert animatic.build_anim({**concept, "length_s": 6})["duration"] == 6
    assert animatic.vo_text(None) == "" and animatic.vo_text('"x"') == 'VO: "x"'


@pytest.mark.private_data
@pytest.mark.parametrize("change", ["no animatic", "no scene", "empty scene"])
def test_missing_scene_refused(run, capsys, change):
    brief = ld.brief()
    beat = brief["concepts"][1]["beats"][2]
    if change == "no animatic":
        del beat["animatic"]
    elif change == "no scene":
        del beat["animatic"]["scene"]
    else:
        beat["animatic"]["scene"] = ""
    _write(run, "04_final/brief_pack_v02.json", brief)
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path))
    assert code == 2 and out["status"] == "stop", out
    assert "C2 beat 3" in out["message"] and "animatic.scene" in out["message"]
    assert "brief_pack_v02.json" in out["message"] and out["message"].endswith(AGAIN)
    assert not (run.path / OUT).exists() and manifest.rows(run) == rows     # nothing written, C1 included


@pytest.mark.private_data
@pytest.mark.parametrize("cid", ["../C2", "C 2", 2])
def test_concept_id_that_cannot_name_a_file_refused(run, capsys, cid):
    brief = ld.brief()
    brief["concepts"][1]["id"] = cid
    _write(run, "04_final/brief_pack_v02.json", brief)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path))
    assert code == 2 and repr(cid) in out["message"] and "Nothing was written" in out["message"]
    assert not (run.path / OUT).exists() and not (run.path / "C2_anim_v01.js").exists()


@pytest.mark.private_data
def test_existing_version_refused_next_free_by_default(run, capsys):
    animatic.build(run, run.path / V01, version="v03")
    before = _files(run.path / OUT)
    for given in ("v03", "v3"):                          # the same number, however it is written
        with pytest.raises(ValueError, match="v03 already exists"):
            animatic.build(run, run.path / V01, version=given)
    with pytest.raises(ValueError, match="like v01"):
        animatic.build(run, run.path / V01, version="03")
    with pytest.raises(ValueError, match="C7"):
        animatic.build(run, run.path / V01, concepts=["C1", "C7"])
    assert _files(run.path / OUT) == before

    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--concepts", "C2")
    assert code == 0, out
    assert [i["html"] for i in out["items"]] == [f"{OUT}/C2_9x16_v04.html", f"{OUT}/C2_4x5_v04.html"]
    assert out["version"] == "v04" and "C2_anim_v04.js" in out["message"]
    assert set(_files(run.path / OUT)) - set(before) == {"C2_anim_v04.js", "C2_9x16_v04.html", "C2_4x5_v04.html"}
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--concepts", "C1")
    assert out["version"] == "v05"                       # a version is never used twice, whatever concept


@pytest.mark.private_data
def test_formats_follow_audience_pick(run, capsys):
    def formats(*extra) -> list[str]:
        code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--concepts", "C1", *extra)
        assert code == 0, out
        return [i["format"] for i in out["items"]]

    assert formats() == ["9x16", "4x5"]                  # no pick, no setting: both (R6)
    _set(run, audience={"formats": ["4x5"]})             # what tm audience pick found in the placements
    assert formats() == ["4x5"]
    _config(run, {"animatic": {"formats": ["9x16"]}})    # the run's setting comes first
    assert formats() == ["9x16"]
    assert formats("--formats", "4x5", "9x16") == ["4x5", "9x16"]
    _config(run, {"animatic": {"formats": ["16x9"]}})
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path))
    assert code == 2 and out["status"] == "stop" and "animatic.formats" in out["message"]   # a file to fix


# --- the render ----------------------------------------------------------------------------------

def _fake_render(calls: list):
    def render(page_, out_mp4, *, fps=atlas.FPS, stills=atlas.STILLS):
        out_mp4 = Path(out_mp4)
        assert not out_mp4.exists() and Path(page_).is_file()
        calls.append((Path(page_), out_mp4, fps))
        out_mp4.write_bytes(b"mp4 " + out_mp4.name.encode())
        for s in stills:
            (out_mp4.parent / f"{out_mp4.stem}_still_{round(s * 100):03d}.png").write_bytes(b"png")
        return {"out": str(out_mp4), "duration": 25, "frames": 600, "render_s": 3, "page_errors": []}
    return render


@pytest.fixture
def renderer(monkeypatch):
    calls: list = []
    monkeypatch.setattr(atlas, "need", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(atlas, "render", _fake_render(calls))
    return calls


@pytest.mark.private_data
def test_render_writes_new_brief_version_with_paths(run, capsys, renderer):
    _write(run, V01, ld.dated(ld.brief()))               # the clips' as-of dates, for the page built below
    _config(run, {"animatic": {"fps": 12}})
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 0, out
    assert out["brief"] == "04_final/brief_pack_v02.json" and out["version"] == "v01"
    renders = run.path / brief_page.RENDERS
    mp4s = [f"{cid}_animatic_{fmt}_v01.mp4" for cid, fmt in ALL]
    stills = [f"{Path(m).stem}_still_{n}.png" for m in mp4s for n in ("006", "030", "055", "080", "095")]
    assert sorted(_files(renders)) == sorted(mp4s + stills)
    assert [(p.name, o.name, fps) for p, o, fps in renderer] == [
        (f"{cid}_{fmt}_v01.html", f"{cid}_animatic_{fmt}_v01.mp4", 12) for cid, fmt in ALL]
    assert {p.parent for p, _, _ in renderer} == {(run.path / OUT).resolve()}
    assert [i["mp4"] for i in out["items"]] == [f"{brief_page.RENDERS}/{m}" for m in mp4s]

    old, new = json.loads((run.path / V01).read_text(encoding="utf-8")), \
        json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))
    assert [cc["animatic"]["default"] for cc in old["concepts"]] == ["9x16", "4x5", "9x16"]
    for c_old, c_new in zip(old["concepts"], new["concepts"]):
        cid = c_new["id"]
        assert c_new.pop("animatic") == {"9x16": f"animatic/{cid}_animatic_9x16_v01.mp4",
                                         "4x5": f"animatic/{cid}_animatic_4x5_v01.mp4",
                                         "default": c_old.pop("animatic")["default"]}   # C2 keeps its 4x5
    assert new == old                                    # nothing else changed

    rows = manifest.rows(run)
    made = [r for r in rows if r["model"] == animatic.MODEL]
    assert sorted(r["file"] for r in made) == sorted(f"{brief_page.RENDERS}/{n}" for n in mp4s + stills)
    assert {r["cost"] for r in made} == {"0"}
    first = next(r for r in made if r["file"].endswith("C1_animatic_9x16_v01.mp4"))
    assert first["parent"] == f"{OUT}/C1_9x16_v01.html" and json.loads(first["params"])["fps"] == 12
    brief_row = next(r for r in rows if r["file"] == out["brief"])
    assert (brief_row["source"], brief_row["parent"]) == (animatic.SOURCE, V01)

    # the page finds them where the brief names them
    got = brief_page.build(run)
    assert got["brief"] == out["brief"] and got["media_copied"] == 6
    assert (run.path / got["folder"] / "animatic" / mp4s[0]).read_bytes() == b"mp4 " + mp4s[0].encode()


@pytest.mark.private_data
def test_rendered_gap(run, capsys, renderer):
    assert "chosen" in animatic.rendered_gap(run)
    _set(run, brief={"chosen": {"concepts": ["C1", "C3"], "source": "chat"}})
    assert "C1 9x16" in animatic.rendered_gap(run)       # the v01 brief's v03 paths are not rendered here
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C3")
    assert code == 0, out
    gap = animatic.rendered_gap(run)
    assert "C1 9x16" in gap and "C1 4x5" in gap and "C3" not in gap
    _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert animatic.rendered_gap(run) is None            # C2 is not chosen, so its old paths do not count

    _set(run, audience={"formats": ["9x16"]})            # one format chosen: the 4x5 renders are not needed
    (run.path / brief_page.RENDERS / "C3_animatic_4x5_v01.mp4").unlink()
    assert animatic.rendered_gap(run) is None
    (run.path / brief_page.RENDERS / "C3_animatic_9x16_v01.mp4").unlink()
    assert "C3 9x16" in animatic.rendered_gap(run)

    latest = run.latest("04_final", "brief_pack", "json")
    brief = json.loads(latest.read_text(encoding="utf-8"))
    del brief["concepts"][0]["animatic"]
    _write(run, "04_final/brief_pack_v09.json", brief)
    assert "C1 9x16" in animatic.rendered_gap(run)
    _write(run, "04_final/brief_pack_v10.json", "{not json")
    assert "readable" in animatic.rendered_gap(run)


@pytest.mark.private_data
def test_render_stops_before_writing_without_the_renderer(run, capsys, monkeypatch):
    def no_browser():
        raise c.ToolStop("Drawing animatics needs Google Chrome or Microsoft Edge. Nothing was rendered. " + AGAIN)
    monkeypatch.setattr(atlas, "need", no_browser)
    monkeypatch.setattr(atlas, "render", lambda *a, **k: pytest.fail("render ran"))
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 2 and out["status"] == "stop" and "Chrome" in out["message"]
    assert not (run.path / OUT).exists() and manifest.rows(run) == rows

    calls: list = []
    good = _fake_render(calls)

    def fails_on_the_third(page_, out_mp4, **kw):
        if len(calls) == 2:
            raise c.ToolError("The animatic renderer failed on C2_9x16_v01.html: boom")
        return good(page_, out_mp4, **kw)
    monkeypatch.setattr(atlas, "need", lambda: Path("/chrome"))
    monkeypatch.setattr(atlas, "render", fails_on_the_third)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 1 and "boom" in out["message"] and "v01" in out["message"]
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"   # no brief names half a set
    _set(run, brief={"chosen": {"concepts": ["C1"], "source": "chat"}})
    assert "C1 9x16" in animatic.rendered_gap(run)       # the two v01 MP4s left behind do not count

    monkeypatch.setattr(atlas, "render", good)           # the next try takes the next version, and holds
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 0 and out["version"] == "v02" and out["brief"] == "04_final/brief_pack_v02.json", out
    assert animatic.rendered_gap(run) is None


@pytest.mark.private_data
def test_stop_midway_says_what_was_rendered(run, capsys, monkeypatch):
    calls: list = []
    good = _fake_render(calls)

    def sandbox_on_the_third(page_, out_mp4, **kw):
        if len(calls) == 2:
            raise c.ToolStop("Chrome would not start on this computer. Nothing was rendered. Ask the user to "
                             "install Google Chrome, then render again. " + AGAIN)
        return good(page_, out_mp4, **kw)
    monkeypatch.setattr(atlas, "need", lambda: Path("/chrome"))
    monkeypatch.setattr(atlas, "render", sandbox_on_the_third)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 2 and out["status"] == "stop", out
    message = out["message"]
    assert "Nothing was rendered" not in message and "2 of 6 animatics were rendered" in message
    assert "animatic v01 is not complete and no brief names it" in message and "next version" in message
    assert "install Google Chrome" in message and message.endswith(AGAIN)
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"
    _set(run, brief={"chosen": {"concepts": ["C1"], "source": "chat"}})
    assert "C1 4x5" in animatic.rendered_gap(run)        # C1 9x16 v01 was drawn, but no brief names it

    monkeypatch.setattr(atlas, "render", good)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render")
    assert code == 0 and out["version"] == "v02", out
    assert animatic.rendered_gap(run) is None


@pytest.mark.private_data
def test_one_format_render_takes_the_drawn_default_and_the_phone_plays_it(run, capsys, renderer):
    _write(run, V01, ld.dated(ld.brief()))               # the clips' as-of dates, for the page built below
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--formats", "9x16")
    assert code == 0, out
    new = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))
    assert [cc["animatic"] for cc in new["concepts"]] == [
        {"9x16": f"animatic/{cid}_animatic_9x16_v01.mp4", "default": "9x16"} for cid in ("C1", "C2", "C3")]

    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--formats", "4x5")
    assert code == 0, out
    new = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))
    assert {cc["animatic"]["default"] for cc in new["concepts"]} == {"4x5"}   # 9x16 was not drawn this time
    got = brief_page.build(run)
    html = (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")
    phones = html.split('<div class="phones">', 1)[1].split("</div></div></div>", 1)[0]
    assert phones.count('<video src="animatic/') == 3 and 'src=""' not in phones   # the strip plays the 4x5s
    assert "C1_animatic_4x5_v02.mp4" in phones


@pytest.mark.private_data
def test_render_of_some_concepts_names_the_others_not_rendered(run, capsys, renderer):
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C2")
    assert code == 0, out
    assert "not rendered in this run: C1 9x16, C1 4x5, C3 9x16, C3 4x5" in out["message"]
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1", "C3")
    assert code == 0 and "not rendered" not in out["message"], out


# --- evidence thumbnails (CB8) ---------------------------------------------------------------------

def _clips(brief: dict) -> list[dict]:
    return [x for cc in brief["concepts"] for x in cc["copy_from_hook"]["evidence"]]


def _thumb_urls(run: RunFolder, brief: dict) -> dict[str, str]:
    """clip url -> its saved video's thumbnail_url."""
    out = {}
    for cc in brief["concepts"]:
        videos = {v["url"]: v for v in trends.load_videos(run, cc["plugin"]["trend"]["trend_id"])}
        out |= {x["url"]: videos[x["url"]]["thumbnail_url"] for x in cc["copy_from_hook"]["evidence"]}
    return out


def _kept(run: RunFolder, brief: dict) -> dict[str, str]:
    """clip url -> the evidence file its thumbnail is kept as: its saved video's asset_id (issue #11)."""
    out = {}
    for cc in brief["concepts"]:
        trend = (cc["plugin"].get("trend") or {}).get("trend_id")
        videos = {v["url"]: v for v in trends.load_videos(run, trend)} if trend else {}
        out |= {x["url"]: f"{brief_page.EVIDENCE}/{page.asset_name(videos[x['url']]['asset_id'])}.jpg"
                for x in cc["copy_from_hook"]["evidence"] if x["url"] in videos}
    return out


class _Image:
    headers = {"Content-Type": "image/jpeg"}

    def __init__(self, body: bytes):
        self.body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        yield self.body

    def close(self):
        pass


@pytest.fixture
def web(monkeypatch):
    """requests.get replaced: offline unless `answers` holds the URL."""
    calls, answers = [], {}

    def get(url, **kw):
        calls.append(url)
        if url not in answers:
            raise requests.ConnectionError("offline")
        return _Image(answers[url])
    monkeypatch.setattr(requests, "get", get)
    return calls, answers


def _placeholder_animatics(run: RunFolder, brief: dict) -> None:
    for cc in brief["concepts"]:
        for fmt in ("9x16", "4x5"):
            _write(run, f"{brief_page.RENDERS}/{Path(cc['animatic'][fmt]).name}", b"mp4")


@pytest.mark.private_data
def test_evidence_thumbnails_fetched_or_listed(run, capsys, web):
    calls, answers = web
    ld.save_trends(run)
    brief = ld.brief()
    thumbs = _thumb_urls(run, brief)
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    assert out["fetched"] == [] and len(out["missing"]) == 9 and out["brief"] == "04_final/brief_pack_v02.json"
    assert {m["url"] for m in out["missing"]} == set(thumbs) and {m["why"] for m in out["missing"]} == {"not fetched"}
    assert sorted(calls) == sorted(thumbs.values())
    assert not (run.path / brief_page.EVIDENCE).exists()
    assert not [r for r in manifest.rows(run)[len(rows):] if r["file"].startswith(brief_page.EVIDENCE)]
    assert "9 thumbnails missing" in out["message"] and "clip links" in out["message"]
    _placeholder_animatics(run, brief)
    got = brief_page.build(run)                          # the page still builds, the thumbnails listed
    assert sorted(got["media_missing"]) == sorted(x["thumb"] for x in _clips(brief))

    c1 = brief["concepts"][0]["copy_from_hook"]["evidence"]
    for x in c1:                                         # C1's three answer now
        answers[thumbs[x["url"]]] = b"\xff\xd8 " + x["url"].encode()
    brief["concepts"][2]["plugin"]["trend"] = None       # C3 without its trend, C2 with a clip not saved
    brief["concepts"][1]["copy_from_hook"]["evidence"][0]["url"] = "https://www.tiktok.com/@gone/video/1"
    _write(run, "04_final/brief_pack_v03.json", brief)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    names = _kept(run, brief)
    assert out["fetched"] == [names[x["url"]] for x in c1]
    for x in c1:
        assert (run.path / names[x["url"]]).read_bytes() == b"\xff\xd8 " + x["url"].encode()
    written = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))   # the paths written back
    assert [x["thumb"] for x in written["concepts"][0]["copy_from_hook"]["evidence"]] == [
        names[x["url"]].removeprefix("02_research/") for x in c1]
    why = {m["url"]: m["why"] for m in out["missing"]}
    assert why["https://www.tiktok.com/@gone/video/1"] == "not in the saved video pages"
    assert {why[x["url"]] for x in brief["concepts"][2]["copy_from_hook"]["evidence"]} == {"no trend"}
    fetched_rows = [r for r in manifest.rows(run) if r["file"].startswith(brief_page.EVIDENCE)]
    assert sorted(r["file"] for r in fetched_rows) == sorted(out["fetched"])
    assert {r["source"] for r in fetched_rows} == {"tm brief evidence"}
    assert {json.loads(r["params"])["url"] for r in fetched_rows} == {thumbs[x["url"]] for x in c1}
    with pytest.raises(Stop, match="C2 https://www.tiktok.com/@gone/video/1"):   # a clip with no saved page, no date
        brief_page.build(run)
    kept = json.loads(run.latest("04_final", "brief_pack", "json").read_text(encoding="utf-8"))
    kept["concepts"][1]["copy_from_hook"]["evidence"].pop(0)
    _write(run, run.next_version("04_final", "brief_pack", "json").relative_to(run.path).as_posix(), kept)
    got = brief_page.build(run)
    assert got["media_copied"] == 6 + 3

    count = len(calls)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))   # kept in the run: never fetched again
    assert out["fetched"] == [names[x["url"]] for x in c1]
    assert [u for u in calls[count:] if u in answers] == []
    assert len([r for r in manifest.rows(run) if r["file"].startswith(brief_page.EVIDENCE)]) == 3


@pytest.mark.private_data
def test_evidence_thumbnail_names_are_asset_names(run, capsys, web):
    calls, answers = web
    ld.save_trends(run)
    brief = ld.brief()
    clip = brief["concepts"][0]["copy_from_hook"]["evidence"][0]
    for x in brief["concepts"][0]["copy_from_hook"]["evidence"]:
        x["thumb"] = "evidence/../"                      # the thumb's own name is never read: the video's id is
    _write(run, "04_final/brief_pack_v02.json", brief)
    answers[_thumb_urls(run, brief)[clip["url"]]] = b"\xff\xd8"
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    name = "tiktok_7682471028282477854.jpg"               # the asset id tiktok:<video>, as a file name
    assert out["fetched"] == [f"{brief_page.EVIDENCE}/{name}"]
    assert {m["why"] for m in out["missing"] if m["concept"] == "C1"} == {"not fetched"}
    assert _files(run.path / brief_page.EVIDENCE) == {name: b"\xff\xd8"}
    written = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))["concepts"][0]["copy_from_hook"]
    assert written["evidence"][0]["thumb"] == f"evidence/{name}"


def _save_dated(run: RunFolder, trend_id: str, at1: str, at2: str) -> None:
    """The LD video page of a trend saved in two pages, on the dates given."""
    videos = json.loads((ld.TRENDS / f"videos_{trend_id}.json").read_text(encoding="utf-8"))["videos"]
    half = len(videos) // 2
    trends.save_answer(run, "get_trend_videos", {"trend_id": trend_id},
                       {"data": videos[:half], "page": 1, "has_more": True}, at=at1)
    trends.save_answer(run, "get_trend_videos", {"trend_id": trend_id, "page": 2},
                       {"data": videos[half:], "page": 2, "has_more": False}, at=at2)


@pytest.mark.private_data
def test_evidence_as_of_is_the_saved_page_date(run, capsys, web):
    brief = ld.brief()
    pages: dict[str, int] = {}                           # clip url -> the page that holds it (1 or 2)
    for cc in brief["concepts"]:
        tid = cc["plugin"]["trend"]["trend_id"]
        _save_dated(run, tid, "2026-11-02T09:00:00+00:00", "2026-11-03T23:30:00+00:00")
        first = trends.answer_of(trends.video_files(run, tid)[0])["data"]
        pages |= {x["url"]: 1 if x["url"] in {v["url"] for v in first} else 2 for x in cc["copy_from_hook"]["evidence"]}
    assert set(pages.values()) == {1, 2}                 # the clips sit on both pages
    c1 = brief["concepts"][0]
    tid = c1["plugin"]["trend"]["trend_id"]
    again = json.loads((ld.TRENDS / f"videos_{tid}.json").read_text(encoding="utf-8"))["videos"]
    trends.save_answer(run, "get_trend_videos", {"trend_id": tid},  # page 1 of C1's trend read again later
                       {"data": again[:len(again) // 2], "page": 1, "has_more": True}, at="2026-11-04T08:00:00+00:00")
    expected = {url: ("2026-11-02", "2026-11-03")[p - 1] for url, p in pages.items()}
    expected |= {x["url"]: "2026-11-04" for x in c1["copy_from_hook"]["evidence"] if pages[x["url"]] == 1}

    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    assert out["brief"] == "04_final/brief_pack_v02.json" and out["as_of"] == expected
    new = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))
    assert {x["url"]: x["plugin"]["as_of"] for x in _clips(new)} == expected
    for x in _clips(new):
        del x["plugin"]
    assert new == ld.brief()                             # only the as-of dates were added
    assert json.loads((run.path / V01).read_text(encoding="utf-8")) == ld.brief()   # never overwritten
    row = next(r for r in manifest.rows(run) if r["file"] == out["brief"])
    assert (row["source"], row["parent"]) == ("tm brief evidence", V01)

    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0 and out["brief"] is None            # the dates hold: no new version
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v02.json"


@pytest.mark.private_data
def test_evidence_as_of_is_the_latest_page_that_holds_the_clip(run, capsys, web):
    brief = ld.brief()
    c1 = brief["concepts"][0]
    tid = c1["plugin"]["trend"]["trend_id"]
    videos = json.loads((ld.TRENDS / f"videos_{tid}.json").read_text(encoding="utf-8"))["videos"]
    clip = c1["copy_from_hook"]["evidence"][0]["url"]
    first = [v for v in videos if v["url"] == clip]
    rest = [v for v in videos if v["url"] != clip]
    trends.save_answer(run, "get_trend_videos", {"trend_id": tid},
                       {"data": first + rest[:3], "page": 1, "has_more": True}, at="2026-11-02T09:00:00+00:00")
    trends.save_answer(run, "get_trend_videos", {"trend_id": tid, "page": 2},     # read before page 1 again
                       {"data": first + rest[3:], "page": 2, "has_more": False}, at="2026-11-03T09:00:00+00:00")
    trends.save_answer(run, "get_trend_videos", {"trend_id": tid},
                       {"data": first + rest[:3], "page": 1, "has_more": True}, at="2026-11-04T09:00:00+00:00")
    assert [f.name for f in trends.video_files(run, tid)][-1].endswith("_p02.json")   # page 2 is read last
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    assert out["as_of"][clip] == "2026-11-04"


@pytest.mark.private_data
def test_evidence_clips_with_one_thumb_name_each_keep_their_own(run, capsys, web):
    """Every TrendsMesh thumbnail URL ends in /thumb.jpg (issue #11): one file name, each clip its own file."""
    calls, answers = web
    ld.save_trends(run)
    brief = ld.brief()
    thumbs = _thumb_urls(run, brief)
    one, two = brief["concepts"][0]["copy_from_hook"]["evidence"][:2]
    one["thumb"] = two["thumb"] = "https://cdn.example.com/thumb.jpg"
    answers[thumbs[one["url"]]] = b"\xff\xd8 one"
    answers[thumbs[two["url"]]] = b"\xff\xd8 two"
    _write(run, "04_final/brief_pack_v02.json", brief)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    kept = _kept(run, brief)
    assert {kept[one["url"]], kept[two["url"]]} <= set(out["fetched"]) and kept[one["url"]] != kept[two["url"]]
    assert (run.path / kept[one["url"]]).read_bytes() == b"\xff\xd8 one"
    assert (run.path / kept[two["url"]]).read_bytes() == b"\xff\xd8 two"

    later = ld.brief()                                   # a later version swaps the two clips' places
    first = later["concepts"][0]["copy_from_hook"]["evidence"]
    first[0]["url"], first[1]["url"] = first[1]["url"], first[0]["url"]
    _write(run, "04_final/brief_pack_v09.json", later)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    written = json.loads((run.path / out["brief"]).read_text(encoding="utf-8"))["concepts"][0]["copy_from_hook"]
    assert [x["thumb"] for x in written["evidence"][:2]] == [kept[two["url"]].removeprefix("02_research/"),
                                                              kept[one["url"]].removeprefix("02_research/")]
    assert (run.path / kept[one["url"]]).read_bytes() == b"\xff\xd8 one"   # never the other clip's image


@pytest.mark.private_data
@pytest.mark.parametrize("change", ["plugin", "trend", "copy_from_hook", "evidence", "clip plugin"])
def test_evidence_brief_not_in_its_shape_stops(run, capsys, web, change):
    calls, _ = web
    ld.save_trends(run)
    brief = ld.brief()
    c1 = brief["concepts"][0]
    if change == "plugin":
        c1["plugin"] = ["trend"]
    elif change == "trend":
        c1["plugin"]["trend"] = "c2173b6a"
    elif change == "copy_from_hook":
        c1["copy_from_hook"] = "a hook"
    elif change == "evidence":
        c1["copy_from_hook"]["evidence"] = 3
    else:
        c1["copy_from_hook"]["evidence"][0]["plugin"] = "2026-11-03"
    _write(run, "04_final/brief_pack_v02.json", brief)
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 2 and out["status"] == "stop", out
    assert "brief_pack_v02.json is not in its shape" in out["message"] and "Nothing was fetched" in out["message"]
    assert calls == [] and manifest.rows(run) == rows
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v02.json"
