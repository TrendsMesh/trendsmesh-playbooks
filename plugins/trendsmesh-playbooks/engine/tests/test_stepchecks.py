"""Named checks a step requires (tm.stepchecks): the registry, resolving a check, and the record
of which file a check passed on."""

import hashlib
import importlib
import sys
import types
from datetime import date, datetime

import pytest

from tm import state, stepchecks, stops
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder


@pytest.fixture
def run(tmp_path):
    (tmp_path / "ws").mkdir()
    return RunFolder.create(tmp_path / "ws", "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


def _themes(run, version, text):
    path = run.path / "02_research" / "voice" / f"voice_themes_v{version:02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_every_name_points_to_a_tm_module_and_function():
    assert len(stepchecks.NAMES) == 50   # 12 for creative brief, 25 for organic video, 13 for create an ad
    for name, target in stepchecks.NAMES.items():
        module, _, function = target.partition(":")
        assert module.startswith("tm.") and function.isidentifier(), name
        assert function.endswith("_gap"), name


def test_run_calls_the_named_function(run, monkeypatch):
    seen = []
    fake = types.ModuleType("fake_step_checks")
    fake.gap = lambda r: seen.append(r.path) or "the voice themes are checked"
    monkeypatch.setitem(sys.modules, "fake_step_checks", fake)
    monkeypatch.setitem(stepchecks.NAMES, "voice_checked", "fake_step_checks:gap")
    assert stepchecks.run("voice_checked", run) == "the voice themes are checked"
    assert seen == [run.path]
    fake.gap = lambda r: None
    assert stepchecks.run("voice_checked", run) is None


@pytest.mark.parametrize("answer", ["", "  ", 0, False, ["a gap"]])
def test_a_check_answering_no_words_is_refused(run, monkeypatch, answer):
    fake = types.ModuleType("fake_step_checks")
    fake.gap = lambda r: answer
    monkeypatch.setitem(sys.modules, "fake_step_checks", fake)
    monkeypatch.setitem(stepchecks.NAMES, "voice_checked", "fake_step_checks:gap")
    with pytest.raises(ValueError, match="^The step check voice_checked answered ") as bug:
        stepchecks.run("voice_checked", run)
    assert not isinstance(bug.value, stops.Stop)   # a bug in the check (exit 1), not a gap (exit 2)


@pytest.mark.parametrize("target", ["tm.no_such_check_module:gap", "tm.stepchecks:no_such_gap"])
def test_a_check_not_built_yet_is_named(run, monkeypatch, target):
    monkeypatch.setitem(stepchecks.NAMES, "handed_off", target)
    with pytest.raises(ValueError, match="^handed_off is not built yet$"):
        stepchecks.run("handed_off", run)


def test_a_broken_import_inside_a_check_module_is_not_hidden(run, monkeypatch):
    broken = types.ModuleType("fake_broken_checks")
    monkeypatch.setitem(sys.modules, "fake_broken_checks", broken)
    real = importlib.import_module

    def import_module(name, *a):
        if name == "fake_broken_checks":
            raise ModuleNotFoundError("No module named 'yaml_typo'", name="yaml_typo")
        return real(name, *a)
    monkeypatch.setattr(stepchecks.importlib, "import_module", import_module)
    monkeypatch.setitem(stepchecks.NAMES, "handed_off", "fake_broken_checks:gap")
    with pytest.raises(ModuleNotFoundError, match="yaml_typo"):
        stepchecks.run("handed_off", run)


def test_an_unknown_name_is_refused(run):
    with pytest.raises(ValueError, match="persona_guessed"):
        stepchecks.run("persona_guessed", run)


def test_mark_records_file_sha256_and_time(run):
    path = _themes(run, 1, '{"themes": []}')
    stepchecks.mark(run, "voice", path)
    entry = state.load(run).checked["voice"]
    assert entry["file"] == "02_research/voice/voice_themes_v01.json"
    assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert datetime.fromisoformat(entry["at"]).tzinfo is not None
    stepchecks.mark(run, "voice", "02_research/voice/voice_themes_v01.json")   # relative to the run
    assert state.load(run).checked["voice"]["file"] == entry["file"]


def test_mark_refuses_a_file_outside_the_run_or_missing(run, tmp_path):
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inside the run folder"):
        stepchecks.mark(run, "voice", outside)
    with pytest.raises(ValueError, match="voice_themes_v09.json"):
        stepchecks.mark(run, "voice", run.path / "02_research" / "voice" / "voice_themes_v09.json")
    assert state.load(run).checked == {}


def test_fresh_refuses_a_file_changed_after_check(run):
    args = ("voice", "02_research/voice", "voice_themes", "json")
    changed = "the latest voice_themes changed after it was checked: run the check again"
    assert stepchecks.fresh(run, *args) == "02_research/voice/voice_themes_vNN.json is written and checked"
    v1 = _themes(run, 1, '{"themes": []}')
    assert stepchecks.fresh(run, *args) == "the latest voice_themes is checked"
    stepchecks.mark(run, "voice", v1)
    assert stepchecks.fresh(run, *args) is None
    v1.write_text('{"themes": ["edited"]}', encoding="utf-8")   # edited after the check
    assert stepchecks.fresh(run, *args) == changed
    stepchecks.mark(run, "voice", v1)
    assert stepchecks.fresh(run, *args) is None
    _themes(run, 2, '{"themes": ["new"]}')   # a newer version, not checked
    assert stepchecks.fresh(run, *args) == changed
    assert stepchecks.fresh(run, "other", "02_research/voice", "voice_themes", "json") == (
        "the latest voice_themes is checked")   # a key never marked


def test_fresh_names_a_latest_file_linked_from_outside_the_run(run, tmp_path):
    stepchecks.mark(run, "voice", _themes(run, 1, '{"themes": []}'))
    outside = tmp_path / "elsewhere.json"
    outside.write_text('{"themes": []}', encoding="utf-8")
    (run.path / "02_research" / "voice" / "voice_themes_v02.json").symlink_to(outside)
    assert stepchecks.fresh(run, "voice", "02_research/voice", "voice_themes", "json") == (
        "the latest voice_themes is a file inside the run folder")
