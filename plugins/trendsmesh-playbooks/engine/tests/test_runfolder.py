import json
from datetime import date

import pytest

from tm import state
from tm.cli import main
from tm.runfolder import ReadOnlyError, RunFolder

STAGES = ["00_raw", "01_base", "02_research", "03_wip", "04_final", "05_results", "showcase"]


def test_create_makes_all_stage_folders_and_manifest(tmp_path):
    run = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    assert run.path == tmp_path / "runs" / "01-refresh-ad" / "2026-11-05_Ad-3"
    for s in STAGES:
        assert (run.path / s).is_dir()
    assert (run.path / "manifest.md").is_file()
    assert (run.path / "run.json").is_file()


def test_next_version_counts_up(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    first = run.next_version("03_wip", "edit_A", "mp4")
    assert first == run.path / "03_wip" / "edit_A_v01.mp4"
    first.write_bytes(b"1")
    assert run.next_version("03_wip", "edit_A", "mp4").name == "edit_A_v02.mp4"
    assert run.next_version("wip", "edit_A", "mp4").name == "edit_A_v02.mp4"


def test_base_files_are_read_only(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    run.assert_writable(run.path / "01_base" / "new.mp4")  # does not exist yet: fine
    for stage in ("00_raw", "01_base"):
        f = run.path / stage / "a.mp4"
        f.write_bytes(b"x")
        with pytest.raises(ReadOnlyError):
            run.assert_writable(f)
    wip = run.path / "03_wip" / "a.mp4"
    wip.write_bytes(b"x")
    run.assert_writable(wip)


def test_path_with_spaces_and_polish_letters(tmp_path):
    ws = tmp_path / "Moje reklamy Łódź"
    ws.mkdir()
    run = RunFolder.create(ws, "Żółta reklama 1", date(2026, 11, 5))
    assert run.path.name == "2026-11-05_Żółta-reklama-1"
    assert RunFolder.open(run.path).path == run.path
    out = run.next_version("wip", "clip", "mp4")
    out.write_bytes(b"x")
    assert out.exists()


def test_state_round_trip(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    s = state.load(run)
    assert s.status == "active" and s.level is None and s.playbook == "01-refresh-ad"
    assert s.created == "2026-11-05" and s.run_id == run.path.name
    s.level = "big_calls"
    s.spend = {"ai_usd": 1.5}
    s.decisions.append({"id": "d1"})
    state.save(run, s)
    assert state.load(run) == s
    assert not list(run.path.glob("run.json.*"))


def test_cli_run_new_and_record(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    assert main(["run", "new", "--name", "Ad 3", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    run_path = out["path"]
    assert main(["record", "--run", run_path, "--file", "03_wip/a.mp4", "--stage", "wip",
                 "--source", "ffmpeg", "--json"]) == 0
    assert "a.mp4" in (RunFolder.open(run_path).path / "manifest.md").read_text(encoding="utf-8")


def test_next_version_uses_highest_not_first_gap(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    for v in ("v01", "v03"):
        (run.path / "03_wip" / f"e_{v}.mp4").write_bytes(b"x")
    assert run.next_version("wip", "e", "mp4").name == "e_v04.mp4"


def test_cli_params_must_be_object(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    main(["run", "new", "--name", "p", "--json"])
    path = json.loads(capsys.readouterr().out)["path"]
    assert main(["record", "--run", path, "--file", "03_wip/a.mp4", "--stage", "wip",
                 "--source", "x", "--params", "[1]", "--json"]) == 1


def test_latest_picks_highest_version_or_plain_name(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    assert run.latest("02_research", "growth", "json") is None
    (run.path / "02_research" / "growth.json").write_text("{}", encoding="utf-8")
    assert run.latest("research", "growth", "json") == run.path / "02_research" / "growth.json"
    for v in ("v01", "v03"):
        (run.path / "02_research" / f"growth_{v}.json").write_text("{}", encoding="utf-8")
    (run.path / "02_research" / "growth_v09.md").write_text("", encoding="utf-8")
    (run.path / "02_research" / "growth_rebuilt_v12.json").write_text("{}", encoding="utf-8")
    assert run.latest("02_research", "growth", ".json") == run.path / "02_research" / "growth_v03.json"
    for v in ("v09", "v10"):
        (run.path / "02_research" / f"growth_{v}.json").write_text("{}", encoding="utf-8")
    (run.path / "02_research" / "growth_v20.json").mkdir()          # a folder is not a version
    assert run.latest("02_research", "growth", "json") == run.path / "02_research" / "growth_v10.json"
    assert run.latest("02_research", "map", "json") is None
    for name in ("map_v3.json", "map_v03.json"):                      # same number: the padded name
        (run.path / "02_research" / name).write_text("{}", encoding="utf-8")
    assert run.latest("02_research", "map", "json") == run.path / "02_research" / "map_v03.json"


def test_unique_path_never_overwrites(tmp_path):
    run = RunFolder.create(tmp_path, "x", date(2026, 11, 5))
    folder = run.path / "02_research" / "search"
    folder.mkdir()
    assert run.unique_path(folder / "s.json") == folder / "s.json"
    assert run.unique_path("02_research/search/s.json") == folder / "s.json"   # relative to the run
    (folder / "s.json").write_text("{}", encoding="utf-8")
    assert run.unique_path(folder / "s.json") == folder / "s_v02.json"
    (folder / "s_v02.json").write_text("{}", encoding="utf-8")
    assert run.unique_path(folder / "s.json") == folder / "s_v03.json"
    assert run.unique_path(folder / "s_v02.json") == folder / "s_v03.json"
    (folder / "s_v03.json").mkdir()                                            # a folder is taken too
    assert run.unique_path(folder / "s.json") == folder / "s_v04.json"


def test_create_for_another_playbook(tmp_path, playbook_two):
    run = RunFolder.create(tmp_path, "w 1", date(2026, 11, 7), playbook="two")
    assert run.path == tmp_path / "runs" / "99-two" / "2026-11-07_w-1"
    assert state.load(run).playbook == "99-two"
    assert (run.path / "manifest.md").read_text(encoding="utf-8").startswith("# Manifest: 99-two ")
    with pytest.raises(ValueError, match="01-refresh-ad"):
        RunFolder.create(tmp_path, "w 2", date(2026, 11, 7), playbook="nope")
    assert not (tmp_path / "runs" / "nope").exists()


def test_run_new_with_playbook_and_after(tmp_path, monkeypatch, capsys, playbook_two, bundled_skills):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    assert main(["run", "new", "--playbook", "two", "--name", "w1", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert state.load(RunFolder.open(first["path"])).previous_run is None
    assert main(["run", "new", "--playbook", "99-two", "--name", "w2", "--after", first["path"],
                 "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    s = state.load(RunFolder.open(second["path"]))
    assert s.playbook == "99-two" and s.previous_run == f"runs/99-two/{first['run_id']}"
    assert s.pages == {} and s.schedule is None
    # refresh-ad (the default) after a 99-two run: refused, and no folder made
    assert main(["run", "new", "--name", "w3", "--after", first["path"], "--json"]) == 1
    assert "Playbook two" in json.loads(capsys.readouterr().out)["message"]
    assert not (ws / "runs" / "01-refresh-ad").exists()
    # a run in another workspace, an unknown playbook, a folder that is not a run
    other = tmp_path / "other"
    other.mkdir()
    elsewhere = RunFolder.create(other, "w0", date(2026, 11, 7), playbook="99-two")
    for argv in (["--playbook", "two", "--name", "w4", "--after", str(elsewhere.path)],
                 ["--playbook", "nope", "--name", "w5"],
                 ["--playbook", "two", "--name", "w6", "--after", str(tmp_path)]):
        assert main(["run", "new", *argv, "--json"]) == 1
        capsys.readouterr()
    assert sorted(p.name for p in (ws / "runs" / "99-two").iterdir()) == sorted(
        [first["run_id"], second["run_id"]])


def test_run_new_after_reads_a_relative_path_from_the_workspace(tmp_path, monkeypatch, capsys,
                                                               playbook_two, bundled_skills):
    ws, elsewhere = tmp_path / "ws", tmp_path / "elsewhere"
    ws.mkdir()
    elsewhere.mkdir()
    first = RunFolder.create(ws, "w1", date(2026, 11, 7), playbook="99-two")
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.chdir(elsewhere)
    rel = f"runs/99-two/{first.path.name}"
    assert main(["run", "new", "--playbook", "two", "--name", "w2", "--after", rel, "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert state.load(RunFolder.open(second["path"])).previous_run == rel


def test_a_taken_name_suggests_a_free_one(tmp_path):
    """Issue #7: a run name already taken that day is refused with a free name to use instead, never
    by a bare refusal that leaves the agent to invent one."""
    first = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    assert RunFolder.free_name(tmp_path, "Ad 3", date(2026, 11, 5)) == "Ad-3-2"
    assert RunFolder.free_name(tmp_path, "Ad 3", date(2026, 11, 6)) == "Ad-3"     # another day: free
    assert RunFolder.free_name(tmp_path, "Ad 3", date(2026, 11, 5), playbook="trend-research") == "Ad-3"
    with pytest.raises(FileExistsError) as taken:
        RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    assert taken.value.path == first.path and taken.value.suggested == "Ad-3-2"
    RunFolder.create(tmp_path, "Ad-3-2", date(2026, 11, 5))
    assert RunFolder.free_name(tmp_path, "Ad 3", date(2026, 11, 5)) == "Ad-3-3"


def test_cli_run_new_with_a_taken_name_names_the_run_and_a_free_name(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    assert main(["run", "new", "--name", "Ad 3", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)["path"]
    s = state.load(RunFolder.open(first))
    s.step = "A2"
    state.save(RunFolder.open(first), s)
    assert main(["run", "new", "--name", "Ad 3", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error" and out["existing"] == first and out["suggested_name"] == "Ad-3-2"
    assert out["existing_status"] == s.status and out["existing_step"] == "A2"
    assert f"tm next --run {first}" in out["message"] and "--name Ad-3-2" in out["message"]
    assert "Pick another name" not in out["message"]
    assert len(list((tmp_path / "runs" / "01-refresh-ad").iterdir())) == 1      # nothing made
