from tm.cli import main


def test_version_prints_and_exits_zero(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "tm 0.13.1"


def test_unknown_command_exits_one():
    assert main(["no-such-command"]) == 1


def test_json_arguments_also_come_as_files(tmp_path):
    """Final review I8: on Windows, inline JSON loses its quotes on the way to `tm`, so every JSON
    argument the skill passes is a file."""
    import json
    from datetime import date

    from tm.runfolder import RunFolder

    run = RunFolder.create(tmp_path / "Moje reklamy", "ad", date(2026, 11, 5))
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"seconds": 8, "tekst": "Zacznij od dziś"}), encoding="utf-8")
    (run.path / "03_wip" / "a.txt").write_text("x", encoding="utf-8")
    assert main(["record", "--run", str(run.path), "--file", "03_wip/a.txt", "--stage", "03_wip",
                 "--source", "test", "--params", str(params)]) == 0
    assert "Zacznij od dziś" in (run.path / "manifest.md").read_text(encoding="utf-8")
    params.write_text("[1, 2]", encoding="utf-8")
    assert main(["record", "--run", str(run.path), "--file", "03_wip/a.txt", "--stage", "03_wip",
                 "--source", "test", "--params", str(params)]) == 1


def test_due_quiet_prints_only_what_is_due(tmp_path, monkeypatch, capsys):
    """Final review I7: the session-start hooks print `tm due --quiet` as it is, no second step."""
    from datetime import date

    from tm import state
    from tm.runfolder import RunFolder

    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    assert main(["due", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    run = RunFolder.create(tmp_path, "Łódź ad", date(2026, 11, 5))
    s = state.load(run)
    s.measurements_due = ["2026-11-01", "2026-11-03"]
    state.save(run, s)
    assert main(["due", "--quiet"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2 and all(run.path.name in line and "is due" in line for line in lines)
