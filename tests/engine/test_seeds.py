"""tm.seeds: the picks a trend research run hands on to the creative brief (the PB2 contract), E3.

The beauty run (beauty.py) is mapped and grown as of 4 Nov 2026 by the ports, and gets the reference
picks_v04 (4 act now, 5 still rising, "day _ of _" moved by review from act now to still rising)
and the reference Ad Library summary v02 (no `checked` key: read as checked, as the page does).
`tm research seeds` writes one seed per pick to <workspace>/library/seeds.jsonl, append-only,
keyed by `seed_id` like library/trend_calls.jsonl.
"""

import json
import shutil
from datetime import date

import pytest

import beauty
from tm import config, manifest, page, research_config, research_growth, research_map, research_report, seeds, state
from tm.cli import main
from tm.runfolder import RunFolder

AS_OF = beauty.CREATED
ALL = ["category_report", "weekly_digest", "paid_view"]
# PLAYBOOK.md (PB4 and PB2), "Contracts with other playbooks": the seed's keys, by name
CONTRACT = ("source", "run", "category", "sub_category", "trend_id", "kind", "trend_name", "bucket", "band",
            "paid_level", "angle", "risk", "valid_until")
PLUGIN = ("schema", "seed_id", "created", "market", "report", "evidence")
CAT_EYE = "d8c752a4308f426a9bea2278f872a118"
YOUR_SIGN = "0bae5424d00e4bbb809e9cbc511dea9a"   # a hook: not checkable in Ad Library titles
DAY_OF = "c2173b6a4e7f496093804bb8efb3e785"      # moved by review from act now to still rising
LIBRARY = ("library", "seeds.jsonl")


def _cfg(run: RunFolder) -> dict:
    return research_map.settings(config.load(run))


@pytest.fixture(scope="module")
def grown(tmp_path_factory):
    """The beauty run with all three outputs, grown as of 4 Nov, with the reference picks_v04 and summary v02."""
    run = beauty.mapped_run(tmp_path_factory.mktemp("beauty"))
    research_config.write_from_intake(run, {"category": {"inputs": [beauty.ROOT], "phrase": beauty.ROOT, "seeds": []},
                                            "market": "US", "language": "en", "outputs": ALL})
    research_growth.compute(run, AS_OF, _cfg(run))
    beauty.copy_input(run, "02_research/ad_library_summary_v02.json")
    beauty.copy_input(run, "03_wip/picks_v04.json")
    return run


def _copy(run: RunFolder, tmp_path) -> RunFolder:
    ws = tmp_path / "ws"
    shutil.copytree(run.path.parents[2], ws)
    return RunFolder.open(ws / run.path.relative_to(run.path.parents[2]))


def _ws(run: RunFolder):
    return run.path.resolve().parents[2]


def _library(run: RunFolder):
    return _ws(run).joinpath(*LIBRARY)


def _lines(run: RunFolder) -> list[dict]:
    return [json.loads(line) for line in _library(run).read_text(encoding="utf-8").splitlines()]


def _seeds(run: RunFolder, capsys) -> tuple[int, dict]:
    capsys.readouterr()
    code = main(["research", "seeds", "--run", str(run.path), "--json"])
    return code, json.loads(capsys.readouterr().out)


def _row(**kw) -> dict:
    base = {"schema": seeds.SCHEMA, "seed_id": "2026-11-04_beauty:t1", "source": "pb4", "run": "2026-11-04_beauty",
            "created": "2026-11-04", "category": "beauty", "sub_category": "nail art", "market": "US",
            "trend_id": "t1", "kind": "topic_trend", "trend_name": "Cat-eye nails", "bucket": "act_now",
            "band": "top 25%", "paid_level": "none", "angle": "A 7 s macro clip.", "risk": "One account.",
            "valid_until": "2026-11-18", "report": None,
            "evidence": "runs/04-trend-research/2026-11-04_beauty/02_research/videos/t1*.json"}
    return {**base, **kw}


@pytest.mark.private_data
def test_seed_row_has_contract_keys(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    code, out = _seeds(run, capsys)
    assert code == 0 and out["status"] == "done"
    rows = _lines(run)
    picks = beauty.handoff("03_wip/picks_v04.json")
    ids = [p["id"] for p in picks["act_now"] + picks["still_rising"]]
    assert [r["trend_id"] for r in rows] == ids and out["added"] == len(ids) == 9 and out["already"] == 0
    for r in rows:
        assert set(r) == set(CONTRACT) | set(PLUGIN) == set(seeds.REQUIRED)
        assert r["schema"] == "seed/1" and r["source"] == "pb4" and r["seed_id"] == f"{run.path.name}:{r['trend_id']}"
        assert list(_ws(run).glob(r["evidence"])), f"no saved videos match {r['evidence']}"

    cat_eye = picks["act_now"][0]
    assert rows[0] == {
        "schema": "seed/1", "seed_id": f"{run.path.name}:{CAT_EYE}", "source": "pb4", "run": run.path.name,
        "created": date.today().isoformat(), "category": "beauty", "sub_category": "nail art", "market": "US",
        "trend_id": CAT_EYE, "kind": "topic_trend", "trend_name": "Cat-eye magnetic nail art manicures",
        "bucket": "act_now", "band": "top 25%", "paid_level": "none", "angle": cat_eye["how"], "risk": cat_eye["risk"],
        "valid_until": "2026-11-18", "report": None,
        "evidence": f"runs/04-trend-research/{run.path.name}/02_research/videos/{CAT_EYE}*.json"}
    by_id = {r["trend_id"]: r for r in rows}
    assert by_id[YOUR_SIGN]["paid_level"] == "not_checkable" and by_id[YOUR_SIGN]["kind"] == "hook_trend"
    assert by_id[DAY_OF]["bucket"] == "still_rising"        # the review's move, as the picks list it
    assert [r["bucket"] for r in rows] == ["act_now"] * 4 + ["still_rising"] * 5

    # the run's own record of what it handed on, beside the library
    own = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    assert out["json"] == "04_final/seeds_v01.json" and own["rows"] == rows
    assert "04_final/seeds_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")
    assert seeds.rows(_ws(run), source="pb4") == rows


@pytest.mark.private_data
def test_paid_level_not_checked_without_a_reading(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    summary = beauty.handoff("02_research/ad_library_summary_v02.json")
    (run.path / "02_research" / "ad_library_summary_v03.json").write_text(
        json.dumps({**summary, "checked": False}), encoding="utf-8")
    assert _seeds(run, capsys)[0] == 0
    assert {r["paid_level"] for r in _lines(run)} == {"not_checked"}


@pytest.mark.private_data
def test_seeds_written_once_per_pick(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    assert _seeds(run, capsys)[0] == 0
    first = _library(run).read_bytes()

    code, out = _seeds(run, capsys)           # E3 again: the same picks, nothing twice
    assert code == 0 and out["added"] == 0 and out["already"] == 9
    assert _library(run).read_bytes() == first
    assert out["json"] == "04_final/seeds_v02.json"     # the run's record is versioned, never overwritten
    capsys.readouterr()
    assert main(["research", "seeds", "--run", str(run.path)]) == 0
    assert "Added 0 to library/seeds.jsonl; 9 were there already and stay as they are" in capsys.readouterr().out
    assert _library(run).read_bytes() == first

    # a row is never rewritten: the same seed_id with another angle is refused, the library unchanged
    again = {**_lines(run)[0], "angle": "Something else."}
    assert seeds.add(_ws(run), again) is False
    assert _library(run).read_bytes() == first

    # a last line without its newline (edited by hand): the next row starts on a line of its own
    _library(run).write_bytes(first.rstrip(b"\n"))
    assert seeds.add(_ws(run), _row()) is True
    lines = _library(run).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10 and json.loads(lines[-1])["seed_id"] == "2026-11-04_beauty:t1"
    assert all(json.loads(line) for line in lines)


@pytest.mark.private_data
def test_damaged_library_line_is_named_and_refused(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    _library(run).parent.mkdir(parents=True, exist_ok=True)
    damaged = (json.dumps(_row()) + "\n" + '{"schema": "seed/1", "seed_id": "cut sh\n').encode("utf-8")
    _library(run).write_bytes(damaged)

    code, out = _seeds(run, capsys)
    assert code == 2 and out["status"] == "stop"
    assert "library/seeds.jsonl has damaged lines (not JSON rows): 2." in out["message"]
    assert "same place" in out["message"]
    assert _library(run).read_bytes() == damaged
    assert not list((run.path / "04_final").glob("seeds_v*.json"))     # refused before anything is written
    with pytest.raises(seeds.DamagedSeeds):
        seeds.add(_ws(run), _row(seed_id="x:t2", trend_id="t2"))

    capsys.readouterr()
    assert main(["seeds", "list", "--workspace", str(_ws(run)), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["damaged"] == [2] and [s["seed_id"] for s in listed["seeds"]] == ["2026-11-04_beauty:t1"]


def test_rows_read_back_whole_once_per_seed(tmp_path, capsys):
    """A seed's text may hold U+2028, U+2029 or U+0085 (written unescaped): it reads back whole. A
    seed_id written twice (by hand) is listed once, as first written; Notepad's BOM is skipped."""
    ws = tmp_path / "ws"
    odd = _row(angle="Hook\u2028then\u2029payoff\u0085end")
    assert seeds.add(ws, odd) is True
    path = ws.joinpath(*LIBRARY)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes()
                     + (json.dumps(_row(angle="a second copy")) + "\r\n").encode("utf-8"))
    assert seeds.rows(ws) == [odd]
    capsys.readouterr()
    assert main(["seeds", "list", "--workspace", str(ws), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["seeds"] == [odd] and listed["damaged"] == []
    assert listed["message"].startswith("2026-11-04_beauty:t1  Cat-eye nails (Act now, top 25%, paid none)")
    assert seeds.add(ws, _row(angle="a third")) is False


def test_valid_on_filters_expired_seeds(tmp_path, capsys):
    ws = tmp_path / "Moje reklamy Łódź"
    expired = _row(seed_id="r1:old", trend_id="old", valid_until="2026-10-30")
    fresh = _row(seed_id="r2:new", trend_id="new", valid_until="2026-11-18")
    other = _row(seed_id="r3:pb5", trend_id="pb5", source="pb5", valid_until="2026-11-18")
    for r in (expired, fresh, other):
        assert seeds.add(ws, r) is True

    assert seeds.rows(ws) == [expired, fresh, other]
    assert seeds.rows(ws, valid_on=date(2026, 11, 7)) == [fresh, other]
    assert seeds.rows(ws, source="pb4", valid_on=date(2026, 11, 7)) == [fresh]
    assert seeds.rows(ws, source="pb4", valid_on=date(2026, 11, 18)) == [fresh]     # valid through its last day
    assert seeds.rows(ws, valid_on=date(2026, 11, 19)) == []

    capsys.readouterr()
    assert main(["seeds", "list", "--source", "pb4", "--valid-on", "2026-11-07", "--workspace", str(ws), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["status"] == "done" and listed["seeds"] == [fresh] and listed["damaged"] == []
    assert main(["seeds", "list", "--source", "pb4", "--workspace", str(ws)]) == 0
    text = capsys.readouterr().out
    assert "r1:old" in text and "r2:new" in text and "r3:pb5" not in text


@pytest.mark.private_data
def test_seed_without_publish_has_null_report(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    assert _seeds(run, capsys)[0] == 0
    assert {json.dumps(r["report"]) for r in _lines(run)} == {"null"}       # kept local (G3): no artifact

    # published at E2: the seed names this run's artifact and version
    page.new_folder(run, "report")
    page.record_published(run, "report", "slug-1", "v3", url="https://claude.ai/artifact/slug-1")
    _library(run).unlink()
    assert _seeds(run, capsys)[0] == 0
    assert {json.dumps(r["report"]) for r in _lines(run)} == {json.dumps({"slug": "slug-1", "version": "v3"})}

    # next week's run kept its page local: its seeds point at no page, never at last week's version
    later = RunFolder(run.path.parent / "2026-11-11_beauty")
    shutil.copytree(run.path, later.path)
    s = state.load(later)
    s.pages, s.previous_run = {}, run.path.relative_to(_ws(run)).as_posix()
    state.save(later, s)
    assert page.published(later, "report")["slug"] == "slug-1"
    assert _seeds(later, capsys)[0] == 0
    assert [r["report"] for r in _lines(run) if r["run"] == later.path.name] == [None] * 9


@pytest.mark.private_data
def test_seeds_follow_the_files_the_page_was_built_from(grown, tmp_path, capsys):
    """After the page is built, a newer picks file or Ad Library summary does not change the seeds:
    they say what the page says (its manifest row names its inputs)."""
    run = _copy(grown, tmp_path)
    folder = page.new_folder(run, research_report.PAGE)
    manifest.record(run, folder.relative_to(run.path).as_posix(), page.FINAL, research_report.SOURCE,
                    params={"picks": "picks_v04.json", "paid": "ad_library_summary_v02.json", "outputs": ALL})
    later = beauty.handoff("03_wip/picks_v04.json")
    later["act_now"][0]["how"] = "Written after the page was built."
    (run.path / "03_wip" / "picks_v05.json").write_text(json.dumps(later), encoding="utf-8")
    summary = beauty.handoff("02_research/ad_library_summary_v02.json")
    (run.path / "02_research" / "ad_library_summary_v03.json").write_text(
        json.dumps({**summary, "checked": False}), encoding="utf-8")
    code, out = _seeds(run, capsys)
    assert code == 0 and out["picks"] == "picks_v04.json" and out["paid"] == "ad_library_summary_v02.json"
    assert out["from_page"] is True and "(the picks the page was built from)" in out["message"]
    rows = _lines(run)
    assert rows[0]["angle"] == beauty.handoff("03_wip/picks_v04.json")["act_now"][0]["how"]
    assert rows[0]["paid_level"] == "none"

    # the page's picks are gone from the run: a stop, nothing written
    (run.path / "03_wip" / "picks_v04.json").unlink()
    _library(run).unlink()
    code, out = _seeds(run, capsys)
    assert code == 2 and "was built from picks_v04.json" in out["message"] and "same place" in out["message"]
    assert not _library(run).exists()


def test_add_refuses_a_row_missing_contract_keys(tmp_path):
    bad = _row()
    del bad["band"], bad["valid_until"]
    with pytest.raises(ValueError, match="band, valid_until"):
        seeds.add(tmp_path, bad)
    with pytest.raises(ValueError, match="seed/1"):
        seeds.add(tmp_path, _row(schema="seed/0"))
    with pytest.raises(ValueError, match="valid_until"):
        seeds.add(tmp_path, _row(valid_until="18 Nov 2026"))
    for report in ({"slug": "s"}, {"slug": "s", "version": ""}, {"slug": "s", "version": "v1", "url": "u"}, "s"):
        with pytest.raises(ValueError, match="report is null or"):
            seeds.add(tmp_path, _row(report=report))
    for key in ("bucket", "evidence"):
        with pytest.raises(ValueError, match=f"{key} must be a string"):
            seeds.add(tmp_path, _row(**{key: None}))
    assert not (tmp_path / "library").exists()
    assert seeds.add(tmp_path, _row(report={"slug": "s", "version": "v1"})) is True


@pytest.mark.private_data
def test_no_picks_stops(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    (run.path / "03_wip" / "picks_v04.json").unlink()
    code, out = _seeds(run, capsys)
    assert code == 2 and "picks" in out["message"] and "same place" in out["message"]
    assert not _library(run).exists()

    picks = beauty.handoff("03_wip/picks_v04.json")
    for bad, said in (({**picks, "as_of": "4 Nov"}, "no as_of date"),
                      ({**picks, "act_now": [{"id": "ff" * 16, "how": "x", "risk": "y"}]}, "ff" * 16)):
        (run.path / "03_wip" / "picks_v05.json").write_text(json.dumps(bad), encoding="utf-8")
        code, out = _seeds(run, capsys)
        assert code == 2 and out["status"] == "stop" and said in out["message"] and "same place" in out["message"]
        (run.path / "03_wip" / "picks_v05.json").unlink()
    assert not _library(run).exists()
