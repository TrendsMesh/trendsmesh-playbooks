"""The playbook registry (data/playbooks.yaml): a run's playbook is its run folder id."""

import pytest
import yaml

from tm import paths, playbooks


def test_get_accepts_id_or_skill():
    by_id, by_skill = playbooks.get("01-refresh-ad"), playbooks.get("refresh-ad")
    assert by_id == by_skill == playbooks.get(playbooks.REFRESH_AD)
    assert (by_id.id, by_id.name, by_id.skill) == ("01-refresh-ad", "Refresh an ad", "refresh-ad")
    assert by_id.data_dir == paths.bundled_data()
    assert [p.id for p in playbooks.all_playbooks()] == ["01-refresh-ad", "02-creative-brief",
                                                         "03-organic-ai-video", "04-trend-research",
                                                         "05-create-ad"]


def test_get_reads_a_patched_registry(playbook_two):
    two = playbooks.get("two")
    assert two.id == playbook_two == playbooks.get("99-two").id
    assert (two.data_dir / "steps.yaml").is_file()
    assert [p.id for p in playbooks.all_playbooks()] == ["01-refresh-ad", "02-creative-brief",
                                                         "03-organic-ai-video", "04-trend-research",
                                                         "05-create-ad", "99-two"]


def test_unknown_playbook_lists_known():
    with pytest.raises(ValueError) as no:
        playbooks.get("trend-research-2")
    assert "trend-research-2" in str(no.value)
    assert "01-refresh-ad (refresh-ad)" in str(no.value)


@pytest.mark.parametrize("rows,named", [
    ([{"id": "01-refresh-ad", "name": "Refresh an ad", "skill": "refresh-ad", "data": "."},
      {"id": "99-two", "name": "Two", "data": "two"}], "row 2"),
    (["01-refresh-ad"], "row 1"),
    ([{"id": "x", "name": "X", "skill": "x", "data": 3}], "row 1"),
    ({"id": "x"}, "must be a list"),
])
def test_malformed_registry_row_is_named(tmp_path, monkeypatch, rows, named):
    registry = tmp_path / "playbooks.yaml"
    registry.write_text(yaml.safe_dump({"playbooks": rows}), encoding="utf-8")
    monkeypatch.setattr(playbooks, "_registry_path", lambda: registry)
    with pytest.raises(ValueError, match=named) as no:
        playbooks.get("refresh-ad")
    assert "playbooks.yaml" in str(no.value)


# --- a playbook is offered once its skill is bundled ---------------------------------------

LATER = "Trend research comes in a later version of this plugin. Check that the plugin is up to date."


def test_skills_root_is_the_plugins_own():
    assert playbooks.skills_root() == paths.bundled_data().parent / "skills"
    assert playbooks.offered("refresh-ad").id == "01-refresh-ad"
    assert playbooks.offered("creative-brief").id == "02-creative-brief"   # its skill ships since 0.5.0
    assert playbooks.offered("organic-video").id == "03-organic-ai-video"  # its skill ships with PR B (Task 10)
    # trend research's skill arrives with PR D: until then it is not offered, and then it is
    bundled = (playbooks.skills_root() / "trend-research" / "SKILL.md").is_file()
    if bundled:
        assert playbooks.offered("trend-research").id == "04-trend-research"
    else:
        with pytest.raises(ValueError, match="later version"):
            playbooks.offered("trend-research")


def test_a_playbook_without_its_skill_is_refused(tmp_path, monkeypatch, capsys):
    import json

    from tm import cli
    root = tmp_path / "skills"
    (root / "refresh-ad").mkdir(parents=True)
    (root / "refresh-ad" / "SKILL.md").write_text("x", encoding="utf-8")
    (root / "trend-research").mkdir()  # a folder alone is not a bundled skill
    monkeypatch.setattr(playbooks, "skills_root", lambda: root)
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    with pytest.raises(ValueError) as no:
        playbooks.offered("04-trend-research")
    assert str(no.value) == LATER
    for argv in (["run", "new", "--playbook", "trend-research", "--name", "w1", "--json"],
                 ["doctor", "--playbook", "trend-research", "--outputs", "category_report", "--json"]):
        assert cli.main(argv) == 1
        assert json.loads(capsys.readouterr().out)["message"] == LATER
    assert not (tmp_path / "ws" / "runs").exists()
    assert cli.main(["run", "new", "--name", "w1", "--json"]) == 0  # refresh-ad is bundled


def test_the_test_playbook_is_offered_with_its_skill(tmp_path, monkeypatch, capsys, playbook_two):
    from tm import cli
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    with pytest.raises(ValueError, match="Playbook two comes in a later version"):
        playbooks.offered("99-two")  # the real root has no skills/two
    root = tmp_path / "skills"
    (root / "two").mkdir(parents=True)
    (root / "two" / "SKILL.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(playbooks, "skills_root", lambda: root)
    assert playbooks.offered("two").id == "99-two"
    assert cli.main(["run", "new", "--playbook", "two", "--name", "w1", "--json"]) == 0
    assert (tmp_path / "ws" / "runs" / "99-two").is_dir()
