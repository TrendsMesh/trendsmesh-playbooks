"""tm brief handoff (E2): the chosen concepts' test plans handed on to PB1 (R4), and every brief_id
in the workspace's library/briefs.jsonl (the link PB1's R5 results row points back through).

The LD dry run's brief (with `ld.py`'s plugin blocks) is the oracle: its media rows are the reference run's.
"""

import importlib
import json
from datetime import date

import pytest

import ld
from tm import brief, brief_checks, library, manifest, page, state, stepchecks
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

pytestmark = pytest.mark.private_data

V01 = "04_final/brief_pack_v01.json"
ALL = ["review_pack", "briefs", "animatics", "page"]
KEYS = ["brief_id", "concept", "title", "hypothesis", "valid_until", "decision_metric", "baseline", "target",
        "minimum_events", "setup", "placements", "audience", "variants"]
TEST_FIELDS = ["decision_metric", "baseline", "target", "minimum_events", "setup", "placements", "audience",
               "variants"]
LABELS = {"Decision metric": "decision_metric", "Baseline": "baseline", "Target": "target",
          "Minimum before a decision": "minimum_events", "Setup": "setup", "Placements": "placements",
          "Audience": "audience"}
SLUG = "5b2c9e1a-0000-4000-8000-000000000001"
OLD_SLUG = "77aa0d3c-0000-4000-8000-000000000002"


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return folder


def _write(run: RunFolder, rel: str, data, *, checked: bool = True) -> None:
    """Write a file of the run; a brief is marked as passing its stage checks, as `tm brief check`
    marks it (the checks themselves are test_brief_checks.py's)."""
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if checked and rel.startswith("04_final/brief_pack_"):
        for stage in ("concepts", "production"):
            stepchecks.mark(run, brief_checks.key(stage), path)


def _set(run: RunFolder, **fields) -> None:
    s = state.load(run)
    for key, value in fields.items():
        setattr(s, key, value)
    state.save(run, s)


def _choose(run: RunFolder, *concepts: str) -> None:
    _set(run, brief={**(state.load(run).brief or {}), "chosen": {"concepts": list(concepts), "source": "chat"}})


def _new_run(ws, name="ld", outputs=ALL, data=None) -> RunFolder:
    run = RunFolder.create(ws, name, ld.CREATED, playbook=CREATIVE_BRIEF)
    _set(run, outputs=list(outputs))
    _write(run, V01, ld.brief() if data is None else data)
    return run


@pytest.fixture
def run(ws) -> RunFolder:
    """A full creative brief run with the LD brief as 04_final/brief_pack_v01.json, C1 and C3 chosen."""
    run = _new_run(ws)
    _choose(run, "C1", "C3")
    return run


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _library(ws) -> list[dict]:
    rows, damaged = library.read_jsonl(ws / "library" / "briefs.jsonl")
    assert damaged == []
    return rows


def _media(concept: dict) -> dict:
    return {LABELS[r["label"]]: r["text"] for r in concept["media"] if r["label"] in LABELS}


# --- the hand-off file -----------------------------------------------------------------------------

def test_handoff_maps_ld_media_labels(run, capsys):
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0, out
    assert out["file"] == "05_results/handoff_v01.json" and out["brief"] == V01
    rows = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))
    assert [list(r) for r in rows] == [KEYS, KEYS]
    by_id = {c["id"]: c for c in ld.brief()["concepts"]}
    for row, cid in zip(rows, ("C1", "C3")):
        c = by_id[cid]
        assert row == {"brief_id": c["brief_id"], "concept": cid, "title": c["title"], "hypothesis": c["hypothesis"],
                       "valid_until": "2026-11-18", **_media(c), "variants": c["hooks_to_test"]}
    c1 = rows[0]
    assert c1["brief_id"] == "PB2-LD-CA-20261104-C1"
    assert c1["decision_metric"].startswith("Cost per checkout started")
    assert c1["minimum_events"].startswith("30 checkouts per variant")
    assert c1["setup"].startswith("Meta A/B test")          # the row above is the brief's, in full
    assert c1["placements"].startswith("Facebook feed (4:5)")
    assert len(c1["variants"]) == 3 and "Landing page" not in json.dumps(rows)   # no PB1 field for it
    assert out["rows"] == rows

    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert (row["stage"], row["source"], row["parent"]) == ("05_results", "tm brief handoff", V01)
    assert "C1, C3" in out["message"] and "library/briefs.jsonl" in out["message"]


def test_media_labels_matched_as_the_production_check_matches_them(ws, capsys):
    data = ld.brief()
    media = data["concepts"][0]["media"]
    media[0]["label"] = "decision  METRIC"               # the production check takes it, so the hand-off does
    del media[1]                                         # no Baseline row: null, never another row's text
    run = _new_run(ws, data=data)
    _choose(run, "C1")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0, out
    row = out["rows"][0]
    assert row["decision_metric"].startswith("Cost per checkout started") and row["baseline"] is None


def test_review_pack_only_handoff_has_null_test_fields(ws, capsys):
    pack = ld.brief()
    for c in pack["concepts"]:                           # a review pack stops at C1: no media part, no hooks
        for key in ("media", "hooks_to_test", "editor", "creator", "casting"):
            c.pop(key, None)
    run = _new_run(ws, outputs=["review_pack"], data=pack)
    _choose(run, "C2")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0, out
    (row,) = out["rows"]
    assert {k: row[k] for k in TEST_FIELDS} == dict.fromkeys(TEST_FIELDS)
    assert out["test_plan"] is False and "test fields null" in out["message"]
    assert row["brief_id"] == "PB2-LD-CA-20261104-C2" and row["hypothesis"] == pack["concepts"][1]["hypothesis"]

    other = _new_run(ws, name="ld-unchecked", outputs=["review_pack"])   # the media rows there, but never checked
    _choose(other, "C2")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(other.path))
    assert code == 0, out
    assert {k: out["rows"][0][k] for k in TEST_FIELDS} == dict.fromkeys(TEST_FIELDS)


def test_handoff_refused_without_a_choice_or_a_brief_id(ws, capsys):
    run = _new_run(ws)
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 2 and "tm brief choose" in out["message"] and out["message"].endswith("same place.")
    data = ld.brief()
    data["concepts"][0]["brief_id"] = ""
    _write(run, "04_final/brief_pack_v02.json", data)
    _choose(run, "C1", "C2")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 2 and "C1" in out["message"] and "brief_id" in out["message"], out
    _choose(run, "C7")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 2 and "C7" in out["message"], out
    assert not (run.path / "05_results" / "handoff_v01.json").exists()
    assert not (ws / "library" / "briefs.jsonl").exists()


# --- the briefs library ----------------------------------------------------------------------------

def test_briefs_library_written_once_per_brief_id(ws, run, capsys):
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0 and out["added"] == ["PB2-LD-CA-20261104-C1", "PB2-LD-CA-20261104-C3"], out
    rows = _library(ws)
    meta = ld.brief()["meta"]
    by_id = {c["id"]: c for c in ld.brief()["concepts"]}
    assert rows == [{"schema": "brief/1", "brief_id": by_id[cid]["brief_id"], "run": run.path.name, "concept": cid,
                     "title": by_id[cid]["title"], "hypothesis": by_id[cid]["hypothesis"],
                     "prepared": meta["prepared"], "valid_until": meta["valid_until"], "market": meta["market"],
                     "page": None, "handoff": "05_results/handoff_v01.json"} for cid in ("C1", "C3")]

    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))   # again: the same hand-off, nothing added
    assert code == 0 and out["file"] == "05_results/handoff_v01.json" and out["added"] == [], out
    assert not (run.path / "05_results" / "handoff_v02.json").exists()
    assert _library(ws) == rows

    data = ld.brief()
    data["concepts"][0]["title"] = "A new title"         # a later brief, one more concept chosen
    _write(run, "04_final/brief_pack_v02.json", data)
    _choose(run, "C1", "C2", "C3")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0 and out["file"] == "05_results/handoff_v02.json", out
    assert out["added"] == ["PB2-LD-CA-20261104-C2"] and out["there"] == ["PB2-LD-CA-20261104-C1",
                                                                           "PB2-LD-CA-20261104-C3"]
    after = _library(ws)
    assert after[:2] == rows                             # never rewritten: C1 keeps its first row
    assert [(r["brief_id"], r["handoff"]) for r in after[2:]] == [("PB2-LD-CA-20261104-C2",
                                                                    "05_results/handoff_v02.json")]
    assert json.loads((run.path / "05_results/handoff_v02.json").read_text(encoding="utf-8"))[0]["title"] == "A new title"


def test_damaged_briefs_library_stops_before_anything_is_written(ws, run, capsys):
    target = ws / "library" / "briefs.jsonl"
    target.parent.mkdir()
    target.write_text('{"schema": "brief/1", "brief_id": "X"}\nnot json\n', encoding="utf-8")
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 2 and out["status"] == "stop", out
    assert "library/briefs.jsonl" in out["message"] and "(not JSON rows): 2." in out["message"]
    assert out["message"].endswith("the run continues from the same place.")
    assert not (run.path / "05_results" / "handoff_v01.json").exists() and manifest.rows(run) == rows
    assert target.read_text(encoding="utf-8").count("\n") == 2
    assert brief.handoff_gap(run) is not None


def test_brief_that_has_not_passed_its_check_is_not_handed_off(ws, run, capsys):
    _write(run, "04_final/brief_pack_v02.json", ld.brief(), checked=False)   # written after E1's check
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 2 and "tm brief check --stage production" in out["message"], out
    assert "Nothing was written" in out["message"]
    assert not (run.path / "05_results").exists() or not list((run.path / "05_results").glob("handoff_*"))
    assert not (ws / "library" / "briefs.jsonl").exists()
    pack = _new_run(ws, name="ld-pack", outputs=["review_pack"])
    _write(pack, "04_final/brief_pack_v02.json", ld.brief(), checked=False)
    _choose(pack, "C2")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(pack.path))
    assert code == 2 and "tm brief check --stage concepts" in out["message"], out


def test_brief_id_of_another_run_is_named(ws, run, capsys):
    assert _cli(capsys, "brief", "handoff", "--run", str(run.path))[0] == 0
    again = _new_run(ws, name="ld-again")                # a later run reusing the same brief ids
    _choose(again, "C1")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(again.path))
    assert code == 0 and out["added"] == [] and out["there"] == ["PB2-LD-CA-20261104-C1"], out
    assert out["other_runs"] == {"PB2-LD-CA-20261104-C1": run.path.name}
    assert f"the run {run.path.name}'s" in out["message"] and "new brief_id" in out["message"]
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))     # its own run: nothing named
    assert code == 0 and out["other_runs"] == {}


def test_unpublished_page_is_null(ws, capsys):
    before = _new_run(ws, name="ld-before")              # an earlier run published its page
    (before.path / "04_final" / "brief_pack_v01").mkdir()
    page.record_published(before, "brief_pack", OLD_SLUG, "v4")
    run = _new_run(ws)
    _set(run, previous_run=before.path.relative_to(ws).as_posix())
    assert page.published(run, "brief_pack")["slug"] == OLD_SLUG   # the trap: page.published walks back
    _choose(run, "C1")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0, out
    assert [r["page"] for r in _library(ws)] == [None]   # never an earlier run's page

    (run.path / "04_final" / "brief_pack_v01").mkdir()   # this run's own page, published
    page.record_published(run, "brief_pack", SLUG, "v2", f"https://claude.ai/artifact/{SLUG}")
    _choose(run, "C1", "C2")
    code, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0, out
    assert [r["page"] for r in _library(ws)] == [None, {"slug": SLUG, "version": "v2"}]


def test_pb1_results_row_links_back_through_brief_id(ws, run, capsys):
    """PB1's R5 row takes the hand-off's brief_id as it is: library.add keeps extra keys."""
    _, out = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    plan = out["rows"][0]
    result = {"account": "act_1", "product": "LD", "market": "Canada", "diagnosis": "new concept",
              "trend": {"id": "c2173b6a4e7f496093804bb8efb3e785", "type": "hook_trend", "status_on_test_day": "rising"},
              "change": {"layer": "hook", "method": "new concept"}, "decision_metric": plan["decision_metric"],
              "result_vs_control": "-22%", "events": 31, "decision": "scale", "run": "pb1-run", "variant": "A",
              "brief_id": plan["brief_id"]}
    library.add(ws, result)
    (got,) = library.rows(ws)
    assert got["brief_id"] in {r["brief_id"] for r in _library(ws)}


# --- the step checks ---------------------------------------------------------------------------------

def test_handoff_gap(run, capsys):
    assert "tm brief handoff" in brief.handoff_gap(run)
    code, _ = _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert code == 0 and brief.handoff_gap(run) is None
    _write(run, "04_final/brief_pack_v02.json", ld.brief())     # a newer brief: hand it off again
    assert "brief_pack_v02.json" in brief.handoff_gap(run)
    _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert brief.handoff_gap(run) is None
    _choose(run, "C1")                                    # another choice: the file no longer says it
    assert "C1" in brief.handoff_gap(run)
    _cli(capsys, "brief", "handoff", "--run", str(run.path))
    assert brief.handoff_gap(run) is None
    target = run.path.parents[2] / "library" / "briefs.jsonl"   # the library lost a row (a failed append)
    target.write_text("", encoding="utf-8")
    assert "PB2-LD-CA-20261104-C1" in brief.handoff_gap(run) and "library/briefs.jsonl" in brief.handoff_gap(run)
    target.write_text("not json\n", encoding="utf-8")
    assert "damaged" in brief.handoff_gap(run)


def test_every_required_check_resolves(ws):
    run = ld.build(ws)
    _set(run, outputs=list(ALL))
    for name, target in stepchecks.NAMES.items():
        module, _, function = target.partition(":")
        fn = getattr(importlib.import_module(module), function, None)
        assert callable(fn), f"{name}: {target} is not built"
        gap = stepchecks.run(name, run)                  # None, or the gap in words
        assert gap is None or (isinstance(gap, str) and gap.strip()), (name, gap)
    assert stepchecks.run("handed_off", run) is not None  # nothing handed off in the LD run yet
