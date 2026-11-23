"""Issue #153: every page of a run declares one set of capabilities (the union of what its pages need, the `profile`
scope and every db rule included), so a republish to the run's one link never drops the start card's scope or db rule.
Every command that builds a page returns it, and so does `tm page files`. `tm page await` and `tm brief await` take
the version `tm page published` recorded when `--version` is not given."""

import json
from datetime import date

import pytest

from test_research_report import _picks_file, _uroda
from tm import config, flow, organic_config, page, run_page, state
from tm.cli import main
from tm.flow import set_level
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop

URL = "https://claude.ai/artifact/Ab3dEfGh1jKlMnOpQrStUv"
PLAYBOOKS = [REFRESH_AD, CREATE_AD, TREND_RESEARCH, ORGANIC_VIDEO, CREATIVE_BRIEF]


@pytest.fixture(autouse=True)
def no_downloads(monkeypatch):
    monkeypatch.setattr(page, "fetch_image", lambda url, dest, timeout=30: False)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _run(tmp_path, playbook):
    r = RunFolder.create(tmp_path / "ws", "caps", date(2026, 11, 5), playbook=playbook)
    set_level(r, "every_step")
    if playbook == ORGANIC_VIDEO:
        config.save(r, {**organic_config.defaults(), "languages": {"working": "en", "market": "en"}})
    if playbook == CREATIVE_BRIEF:                     # the kind comes before the start card (issue #156)
        flow.decide(r, "brief_kind", "ad", by="user", note=None, said="an ad")
    return r


def _rules(caps) -> dict:
    return {r["path"]: (r["read"], r["write"]) for r in caps["db"]["rules"]}


@pytest.mark.parametrize("playbook", PLAYBOOKS)
def test_one_set_holds_every_page_of_the_run(playbook):
    caps = page.run_capabilities(playbook)
    assert caps["user"] == {"scopes": ["profile"]}                  # the start card's scope, on every page
    assert caps["downloads"] == {}
    rules = _rules(caps)
    assert rules["intake"] == ("owner", "owner")                    # the start card's answers
    if playbook == CREATIVE_BRIEF:                                  # the brief's page: everyone reads, each writes own
        assert rules["decisions"] == ("view", "owner") and rules["decisions/{self}"] == ("view", "interact")
    else:
        assert rules["decisions"] == ("owner", "owner")
    assert len(caps["db"]["rules"]) == len(rules)                   # one rule per path
    assert json.loads(json.dumps(caps)) == caps


def test_organic_video_declares_every_collection_its_pages_save():
    rules = _rules(page.run_capabilities(ORGANIC_VIDEO))
    assert {"intake", "decisions", "gate_images", "gate_video", "gate_edit", "week", "taste", "models"} <= set(rules)


def test_it_is_keyed_by_the_runs_playbook(tmp_path):
    run = _run(tmp_path, CREATE_AD)
    assert page.run_capabilities(run) == page.run_capabilities(CREATE_AD)
    assert "models" in _rules(page.run_capabilities(CREATE_AD))


@pytest.mark.parametrize("playbook", [REFRESH_AD, TREND_RESEARCH, CREATIVE_BRIEF])
def test_the_start_card_and_the_run_page_declare_the_same(tmp_path, capsys, playbook):
    run = _run(tmp_path, playbook)
    code, out = _cli(capsys, "page", "intake", "--run", str(run.path))
    assert code == 0, out
    assert out["capabilities"] == page.run_capabilities(run)
    assert "CAPABILITIES[" not in out["message"]                    # never a name in the plugin's source
    code, files = _cli(capsys, "page", "files", "--run", str(run.path), "--page", "intake")
    assert code == 0 and files["capabilities"] == out["capabilities"]
    page.record_published(run, "intake", None, "v1", URL)
    assert run_page.build(run)["capabilities"] == out["capabilities"]


def test_the_organic_pages_declare_the_runs_set(tmp_path, capsys):
    run = _run(tmp_path, ORGANIC_VIDEO)
    code, out = _cli(capsys, "organic", "page", "intake", "--run", str(run.path), "--working", "en", "--market", "en")
    assert code == 0, out
    assert out["capabilities"] == page.run_capabilities(ORGANIC_VIDEO)
    assert "CAPABILITIES[" not in out["message"]


def test_the_report_declares_the_runs_set(tmp_path, capsys):
    run, picks = _uroda(tmp_path)
    path = _picks_file(run, picks)
    assert main(["research", "report", "--run", str(run.path), "--picks", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["capabilities"] == page.run_capabilities(TREND_RESEARCH)


def test_tm_brief_capabilities_is_the_creative_briefs_set(capsys):
    code, out = _cli(capsys, "brief", "capabilities")
    assert code == 0 and out["capabilities"] == page.run_capabilities(CREATIVE_BRIEF)


# --- the wait takes the recorded version ---------------------------------------------------------------

def test_await_without_a_version_takes_the_recorded_publish(tmp_path, capsys):
    run = _run(tmp_path, REFRESH_AD)
    run_page.build(run)
    with pytest.raises(Stop, match="tm page published"):
        page.await_(run, run_page.PAGE, None)                       # nothing published yet: said plainly
    page.record_published(run, run_page.PAGE, None, "1700000001-abcd", URL)
    code, out = _cli(capsys, "page", "await", "--run", str(run.path), "--page", run_page.PAGE)
    assert code == 0, out
    assert out["awaiting"]["version"] == "1700000001-abcd"
    assert page.awaiting(run, run_page.PAGE)["version"] == "1700000001-abcd"


def test_await_without_a_version_refuses_a_build_not_published_yet(tmp_path, capsys):
    run = _run(tmp_path, REFRESH_AD)
    run_page.build(run)
    page.record_published(run, run_page.PAGE, None, "v1", URL)
    later = run_page.build(run)                                     # built, not published: people never saw it
    code, out = _cli(capsys, "page", "await", "--run", str(run.path), "--page", run_page.PAGE)
    assert code == 2 and later["folder"] in out["message"] and "tm page published" in out["message"]
    assert page.awaiting(run, run_page.PAGE) is None
    code, out = _cli(capsys, "page", "await", "--run", str(run.path), "--page", run_page.PAGE, "--version", "v1")
    assert code == 0 and out["awaiting"]["version"] == "v1"        # a version given is taken as given


def test_brief_await_without_a_version_takes_the_recorded_publish(tmp_path, capsys):
    run = _run(tmp_path, CREATIVE_BRIEF)
    (run.path / "04_final" / "brief_pack_v01").mkdir(parents=True)
    (run.path / "04_final" / "brief_pack_v01" / "index.html").write_text("<p>brief</p>", encoding="utf-8")
    code, out = _cli(capsys, "brief", "await", "--run", str(run.path), "--stage", "G4")
    assert code == 2 and "tm page published" in out["message"]
    page.record_published(run, "brief_pack", None, "v7", URL)
    code, out = _cli(capsys, "brief", "await", "--run", str(run.path), "--stage", "G4")
    assert code == 0, out
    assert out["awaiting"]["version"] == "v7" and out["awaiting"]["stage"] == "G4"
    assert state.load(run).pages["brief_pack"]["awaiting"]["version"] == "v7"
