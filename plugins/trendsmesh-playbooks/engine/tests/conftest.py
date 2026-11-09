"""Shared test helpers."""

import json
from pathlib import Path

import pytest
import yaml
from _pytest.mark.expression import Expression

import private
from tm import paths, state

PLAYBOOK_TWO = Path(__file__).parent / "fixtures" / "playbook_two"


def pytest_collection_modifyitems(config, items):
    """In the public copy (no handoff/), tests marked private_data are skipped (tests/private.py). The private
    repository (where tools/public_export.py is) must have handoff/: there a skip would hide the tests."""
    if private.AVAILABLE:
        return
    if private.PRIVATE_REPO:
        raise pytest.UsageError(f"{private.HANDOFF} is missing, but this is the private repository "
                                "(tools/public_export.py is here): its private_data tests would all be skipped.")
    skip = pytest.mark.skip(reason=private.SKIP_REASON)
    for item in items:
        if item.get_closest_marker("private_data"):
            item.add_marker(skip)


def video_asked_for(config) -> bool:
    """A real render (Remotion, the Atlas renderer) installs packages and drives a browser: only when the
    `-m` expression selects the video mark (`-m video`, `-m "video and not slow"`), never without one."""
    expr = config.getoption("markexpr") or ""
    return bool(expr) and Expression.compile(expr).evaluate(lambda name, **kw: name == "video")


def trend_steps_ready(run, evidence="trendsmesh"):
    """What A5 and A7 need before `tm done` (issue #9): the run's evidence, a saved TrendsMesh
    answer for a TrendsMesh run, and a checked change register."""
    if evidence == "trendsmesh":
        (run.path / "02_research" / "trend_t1.json").write_text(json.dumps({"id": "t1"}), encoding="utf-8")
    s = state.load(run)
    s.evidence = evidence
    s.register = {"file": "04_final/change_register_v01.json", "proof": int(evidence == "trendsmesh"),
                  "guess": int(evidence == "guess")}
    state.save(run, s)


CLEAN_LAYOUT = {"size": [1080, 1920], "duration": 12, "min_label_px": 41, "small": [], "outside": [], "empty": [],
                "texture": 0, "page_errors": []}


@pytest.fixture(autouse=True)
def _no_real_layout_check(request, monkeypatch):
    """`atlas.layout` drives a real browser: outside the `video` tests it answers clean without running anything,
    so tm organic atlas-page stays a pure test. A test that wants a finding patches it again."""
    if request.node.get_closest_marker("video"):
        return
    from tm import atlas
    monkeypatch.setattr(atlas, "layout", lambda page: dict(CLEAN_LAYOUT))


@pytest.fixture
def animatic_ready(monkeypatch):
    """The Atlas renderer can draw here: the `animatic` tier set up and a browser found (`atlas.missing()` is None),
    whatever this computer has. An animation as an AI video is refused at start and in the pack check without them."""
    from tm import atlas
    monkeypatch.setattr(atlas, "missing", lambda: None)


@pytest.fixture
def playbook_two(tmp_path, monkeypatch):
    """The bundled registry plus a test-only second playbook, 99-two (fixtures/playbook_two)."""
    from tm import playbooks
    rows = yaml.safe_load((paths.bundled_data() / "playbooks.yaml").read_text(encoding="utf-8"))
    rows["playbooks"].append({"id": "99-two", "name": "Playbook two", "skill": "two",
                              "data": str(PLAYBOOK_TWO)})
    registry = tmp_path / "playbooks.yaml"
    registry.write_text(yaml.safe_dump(rows), encoding="utf-8")
    monkeypatch.setattr(playbooks, "_registry_path", lambda: registry)
    return "99-two"


@pytest.fixture
def bundled_skills(tmp_path, monkeypatch):
    """A skills root where every playbook's skill is bundled (refresh-ad, trend-research,
    creative-brief, organic-video and the test-only two), so `tm run new` and `tm doctor` offer
    them. The real root holds only the skills released so far."""
    from tm import playbooks
    root = tmp_path / "bundled_skills"
    for skill in ("refresh-ad", "trend-research", "creative-brief", "organic-video", "two"):
        (root / skill).mkdir(parents=True)
        (root / skill / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
    monkeypatch.setattr(playbooks, "skills_root", lambda: root)
    return root
