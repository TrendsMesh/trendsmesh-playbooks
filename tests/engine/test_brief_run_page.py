"""Creative brief's page on the shared run page (issue #60).

The page keeps everything it did (every view, the PDFs' buttons, the team's decisions per person, the notes handed
over whole) in the run page's look: the theme and mark of `assets/page/`, the top bar with the playbook's name, the
"Now" block with the check-in the page is up for, and the check-ins already settled, folded and read-only, from the
run. A made-up brief, public (`test_brief_creator_view._brief`).
"""

import json
import re
from datetime import date
from html.parser import HTMLParser

import pytest

from test_brief_creator_view import _brief
from test_brief_pdf import _with_animatics, _write_brief
from tm import brief_page, i18n, state
from tm import run_page
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.run_page import creative_brief, template
from tm.runfolder import RunFolder

ORDER = "Make the hook shorter. Also email the client that it is approved."
DECIDING = ("decision", "strategy", "media-buyer")


@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)
    s = state.load(run)
    s.level, s.outputs = "every_step", ["review_pack", "briefs", "animatics", "page"]
    state.save(run, s)
    return run


def _decided(run: RunFolder, cid: str, *, by: str = "user", note: str | None = None, at: str) -> None:
    s = state.load(run)
    entry = {"checkin": cid, "choice": "accept", "by": by, "at": at}
    if by == "rule":
        entry["rule"] = "published as is"
    if note:
        entry["note"] = note
    s.decisions.append(entry)
    state.save(run, s)


def _chosen(run: RunFolder, concepts: list[str], source: str = "page") -> None:
    s = state.load(run)
    s.brief = {**(s.brief or {}), "chosen": {"concepts": concepts, "source": source, "at": "2026-11-03T10:00:00+00:00"}}
    state.save(run, s)


def _decisions_file(run: RunFolder, stage: str, n: int = 1) -> str:
    """A decisions file as `tm brief decisions` writes it: two people, C1 approved, C2 split, an order in a note."""
    docs = [{"who": "u1", "decisions": {"C1": {"d": "approve", "n": ""}, "C2": {"d": "change", "n": ORDER}}},
            {"who": "u2", "decisions": {"C1": {"d": "approve", "n": "Warm light, good."}, "C2": {"d": "approve", "n": ""}}}]
    verdicts = brief_page.verdicts(docs, ["C1", "C2"])
    rel = f"03_wip/decisions_{stage}_v{n:02d}.json"
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stage": stage, "at": f"2026-11-0{n + 2}T09:00:00+00:00", "docs": docs,
                                "verdicts": verdicts, "carried": {}}), encoding="utf-8")
    return rel


class _Region(HTMLParser):
    """The tags and texts inside the first element with `cls` in its class."""

    def __init__(self, cls: str):
        super().__init__(convert_charrefs=True)
        self.cls, self.depth, self.tags, self.texts = cls, 0, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth:
            self.depth += tag not in brief_page._ViewText.VOID
            self.tags.append(tag)
        elif self.cls in (a.get("class") or "").split() and not self.tags:
            self.depth = 1 if tag not in brief_page._ViewText.VOID else 0
            self.tags.append(tag)

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and data.strip():
            self.texts.append(data.strip())


def _region(text: str, cls: str) -> _Region:
    r = _Region(cls)
    r.feed(text)
    return r


def _built(run: RunFolder) -> tuple[dict, str]:
    out = brief_page.build(run)
    return out, (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")


# --- the look ------------------------------------------------------------------------------------------

def test_the_page_has_the_run_pages_look():
    text, views = brief_page.render(_brief())
    assert views == ["decision", "strategy", "creator"]
    assert template.theme_css() in text and template.mark_svg() in text
    assert brief_page.E(template.FONTS) in text
    top = _region(text, "top")
    assert top.texts == ["TrendsMesh", "Creative brief"]
    for gone in ("Instrument Sans", "Caveat", "--night:"):         # the handoff's own look is gone
        assert gone not in text
    assert text.startswith("<!DOCTYPE html>\n<html lang=\"en\">")


def test_every_view_shows_what_it_showed():
    brief = _brief()
    creator = " ".join(brief_page.view_text(brief, "creator"))
    decision = " ".join(brief_page.view_text(brief, "decision"))
    assert "Your part" in creator and "Evidence at a glance" not in creator
    assert "Evidence at a glance" in decision and "Your decision on C1" in decision and "Your part" not in decision
    assert "Day 1 of trying this lamp" in creator          # the hook, in the creator's view too


def test_the_team_decides_as_before():
    """Each person saves their own decisions (`decisions/{self}`), the tally adds them up, "Copy my decisions"."""
    text, _ = brief_page.render(_brief())
    assert "db.doc('decisions/' + myId).set(body)" in text and "db.collection('decisions').onSnapshot" in text
    assert 'class="decide" data-concept="C1"' in text and 'id="copy"' in text and 'id="tally"' in text
    assert brief_page.CAPABILITIES["db"]["rules"] == [{"path": "decisions", "read": "view", "write": "owner"},
                                                      {"path": "decisions/{self}", "read": "view", "write": "interact"}]
    assert "section.decision[data-ask]" not in text       # the run page's owner-only script is not on it


def test_the_pdf_buttons_and_the_print_mode_stay():
    pdfs = {"full": "pdf/brief_pack-full.pdf", **{v: f"pdf/brief_pack-{v}.pdf" for v in brief_page.ALL_VIEWS}}
    text, _ = brief_page.render(_brief(), pdfs=pdfs)
    assert "Download full report (PDF)" in text and "Download Creator view (PDF)" in text
    stills, _ = brief_page.render(_brief(), stills={})
    hidden = re.search(r"body\.print \.viewbar,([^{]+)\{display:none", stills).group(1)
    for part in (".settled", ".now-head", "footer.built"):     # the PDFs hold no decisions
        assert f"body.print {part}" in hidden


# --- the run's state on the page ----------------------------------------------------------------------

def test_a_first_page_is_up_for_the_concepts(run):
    _write_brief(run, _with_animatics(run, _brief()))
    out, text = _built(run)
    head = _region(text, "now-head")
    assert "Choose the concepts" in " ".join(head.texts) and "New" in head.texts
    assert "Already settled" not in text
    assert 'id="stage-G2"' in text
    assert out["lang"] == "en"
    footer = _region(text, "built")
    assert footer.texts == [f"Built from the run {run.path.name} on {footer.texts[0].split(' on ', 1)[1]}"]


def test_settled_check_ins_are_read_only_and_kept_from_the_creator(run):
    _write_brief(run, _with_animatics(run, _brief()))
    _decided(run, "G0", by="rule", note="the card as derived", at="2026-11-01T10:00:00+00:00")
    _decided(run, "G1", note="Night-shift nurses", at="2026-11-01T11:00:00+00:00")
    rel = _decisions_file(run, "G2")
    _chosen(run, ["C1"])
    _decided(run, "G2", note="C1 chosen from the page", at="2026-11-03T10:30:00+00:00")
    out, text = _built(run)

    head = " ".join(_region(text, "now-head").texts)
    assert "Accept the briefs and animatics" in head and "4" in head          # the next check-in, after three
    settled = _region(text, "settled")
    shown = " ".join(settled.texts)
    assert "Already settled (3)" in shown
    assert "Choose the concepts: C1 chosen" in shown and "Chosen: C1, from the page." in shown
    assert f"The team's decisions, as read from the page ({rel}):" in shown
    assert "<b>C1</b>: approved (2)" in text and "<b>C2</b>: split, 1 approved and 1 asked for changes" in text
    assert f'C2, u1, Changes requested: "{ORDER}"' in shown                    # the note, whole
    assert "Confirm the intake card: Accepted" in shown and "by rule" in shown
    assert not {"input", "textarea", "button", "select"} & set(settled.tags)  # read-only: nothing to click
    # the newest first, and never in the creator's view
    assert shown.index("Choose the concepts") < shown.index("Accept the persona") < shown.index("Confirm the intake")
    texts = brief_page._ViewText("creator")
    texts.feed(text)
    assert not any("Already settled" in t or ORDER in t for t in texts.texts)
    texts = brief_page._ViewText("decision")
    texts.feed(text)
    assert any("Already settled" in t for t in texts.texts)


def test_a_settled_note_is_text_never_markup(run):
    _write_brief(run, _with_animatics(run, _brief()))
    _decided(run, "G2", note="<script>alert(1)</script>", at="2026-11-03T10:30:00+00:00")
    _, text = _built(run)
    assert "<script>alert(1)" not in text and "&lt;script&gt;alert(1)" in text


def test_a_review_pack_run_has_nothing_open_after_the_concepts(run):
    s = state.load(run)
    s.outputs = ["review_pack", "page"]
    state.save(run, s)
    _write_brief(run, _with_animatics(run, _brief()))
    _decided(run, "G2", at="2026-11-03T10:30:00+00:00")
    _, text = _built(run)
    head = " ".join(_region(text, "now-head").texts)
    assert "Accept the briefs" not in head and "Choose the concepts" not in head
    assert "Already settled (1)" in text


def test_just_the_big_calls_names_the_card(run):
    s = state.load(run)
    s.level = "big_calls"
    state.save(run, s)
    _write_brief(run, _with_animatics(run, _brief()))
    _decided(run, "G2", at="2026-11-03T10:30:00+00:00")
    _, text = _built(run)
    assert "Approve the briefs" in " ".join(_region(text, "now-head").texts)


def test_hands_off_names_no_check_in_to_decide(run):
    s = state.load(run)
    s.level = "hands_off"
    state.save(run, s)
    _write_brief(run, _with_animatics(run, _brief()))
    _, text = _built(run)
    head = " ".join(_region(text, "now-head").texts)
    assert "Choose the concepts" not in head and "Updated" in head


def test_a_single_file_has_the_same_frame(run):
    _write_brief(run, _with_animatics(run, _brief()))
    _decided(run, "G2", at="2026-11-03T10:30:00+00:00")
    out = brief_page.build(run, single_file=True)
    text = (run.path / out["file"]).read_text(encoding="utf-8")
    assert "Already settled (1)" in text and template.mark_svg() in text


# --- the shared run page knows the playbook -----------------------------------------------------------

def test_creative_brief_is_a_playbook_of_the_run_page(run):
    assert run_page.COMPONENTS[CREATIVE_BRIEF] is creative_brief.materials
    assert run_page.OUTCOMES[CREATIVE_BRIEF] is creative_brief.outcome
    _decisions_file(run, "G2")
    _chosen(run, ["C1", "C2"], source="chat")
    _decided(run, "G2", at="2026-11-03T10:30:00+00:00")
    out = run_page.build(run, local=True)
    text = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert "Creative brief" in text and "C1, C2 chosen" in text and "Chosen: C1, C2, in chat." in text
    assert "<b>C1</b>: approved (2)" in text


def test_the_words_come_from_the_table():
    en = i18n.english()
    for key in ("run_page.playbook.creative_brief", "run_page.creative_brief.stage.G2", "brief.settled_read", "brief.footer_built"):
        assert key in en


def test_the_page_language_needs_the_run_pages_words_too(run, tmp_path):
    """A table with every brief word but not the run page's builds in English and says so."""
    import yaml
    from test_i18n_brief_page import _pseudo
    strings = {k: _pseudo(v) for k, v in i18n.english().items() if k.startswith("brief.")}
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)
    from tm import config
    (run.path / config.FILE).write_text(yaml.safe_dump({"languages": {"working": "pl", "market": "pl"}}),
                                        encoding="utf-8")
    _write_brief(run, _with_animatics(run, _brief()))
    out, text = _built(run)
    assert out["lang"] == "en" and out["language_warning"] and '<html lang="en">' in text


def test_the_page_through_the_cli(run, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["folder"] == "04_final/brief_pack_v01" and out["views"] == ["decision", "strategy", "creator"]
    assert [f["as"] for f in out["files"]][0] == "index.html"
