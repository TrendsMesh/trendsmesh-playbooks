"""Issue #134: a decision given in chat is saved exactly or refused, never saved empty. The page builds list the
answers they take in chat (`chat_answers`), an item or option may be named the way the run names it (its pack name,
its file), a line that cannot be read stops, and a chat decision ends the page's wait and builds the run page again
(issue #131 item 6)."""

import json
from datetime import date

import pytest

from tm import flow, organic_gates, page, run_page, state
from tm.cli import main
from tm.flow import set_level
from tm.organic_pages import choices
from tm.runfolder import RunFolder
from tm.stops import Stop

ART_URL = "https://claude.ai/artifact/Ab3dEfGh1jKlMnOpQrStUv"

GATE = {"items": [
    {"id": "images-still-01", "label": "Image 1", "options": [
        {"id": "still_01_v01_0", "src": "03_wip/still_01_v01_0.png", "caption": "still_01_v01_0"},
        {"id": "still_01_v01_1", "src": "03_wip/still_01_v01_1.png", "caption": "still_01_v01_1"}]},
    {"id": "images-still-02", "label": "Image 2", "options": [
        {"id": "still_02_v01_0", "src": "03_wip/still_02_v01_0.png", "caption": "still_02_v01_0"}]}],
    "plugin": {"items": {
        "images-still-01": {"kind": "images", "name": "still_01", "stem": "still_01",
                            "files": {"still_01_v01_0": "03_wip/still_01_v01_0.png",
                                      "still_01_v01_1": "03_wip/still_01_v01_1.png"}},
        "images-still-02": {"kind": "images", "name": "still_02", "stem": "still_02",
                            "files": {"still_02_v01_0": "03_wip/still_02_v01_0.png"}}}}}

TASTE = {"sections": [
    {"id": "music", "kind": "one", "title": "Music", "options": [
        {"id": "track-mixkit-cat-walk-371", "label": "Cat Walk",
         "media": [{"src": "02_research/music/mixkit-cat-walk-371.mp3", "caption": "Cat Walk"}]},
        {"id": "track-mixkit-dreaming-big-31", "label": "Dreaming Big",
         "media": [{"src": "02_research/music/mixkit-dreaming-big-31.mp3", "caption": "Dreaming Big"}]}]},
    {"id": "voice", "kind": "one", "title": "Voice", "options": [
        {"id": "v1", "label": "Same", "media": []}, {"id": "v2", "label": "Same", "media": []}]}]}


# --- what the page takes in chat --------------------------------------------------------------------

def test_a_gate_page_lists_each_item_with_its_id_and_answers():
    lines = organic_gates.chat_answers(GATE)
    assert lines[0].startswith("Image 1 = images-still-01: accept / redo / drop; choice: still_01_v01_0 / ")
    assert lines[1] == "Image 2 = images-still-02: accept / redo / drop"


def test_a_choices_page_lists_each_section_with_its_options():
    lines = choices.chat_answers(TASTE)
    assert lines[0] == ("Music = music: track-mixkit-cat-walk-371 (Cat Walk) / track-mixkit-dreaming-big-31 "
                        "(Dreaming Big)")


# --- the check-in pages' chat lines ------------------------------------------------------------------

def test_an_item_is_named_by_its_pack_name():
    docs = dict(organic_gates.parse_chat("still_01: accept; choice: still_01_v01_1\n", GATE))
    assert docs == {"images-still-01": {"action": "accept", "choice": "still_01_v01_1"}}


def test_an_option_is_named_by_its_file_name_or_run_path():
    for said in ("still_01_v01_1.png", "03_wip/still_01_v01_1.png"):
        docs = dict(organic_gates.parse_chat(f"images-still-01: accept; choice: {said}", GATE))
        assert docs["images-still-01"]["choice"] == "still_01_v01_1"


def test_a_line_naming_no_item_stops_and_saves_nothing():
    with pytest.raises(Stop, match="images-still-01, images-still-02"):
        organic_gates.parse_chat("images-still-01: accept; choice: still_01_v01_0\nthe second one: drop\n", GATE)
    with pytest.raises(Stop, match="not an option of images-still-01"):
        organic_gates.parse_chat("images-still-01: accept; choice: still_09.png", GATE)


def test_blank_lines_and_comments_are_skipped():
    docs = organic_gates.parse_chat("# the user's words\n\nimages-still-02: drop\n", GATE)
    assert docs == [("images-still-02", {"action": "drop"})]


def test_a_name_that_fits_two_items_stops_and_lists_them():
    data = json.loads(json.dumps(GATE))
    data["plugin"]["items"]["images-still-02"]["name"] = "still_01"
    with pytest.raises(Stop, match="images-still-01, images-still-02"):
        organic_gates.parse_chat("still_01: accept", data)


# --- the choices pages' chat lines -------------------------------------------------------------------

def test_a_track_is_named_by_its_run_path_file_name_or_label():
    for said in ("02_research/music/mixkit-cat-walk-371.mp3", "mixkit-cat-walk-371.mp3", "Cat Walk"):
        docs = dict(choices.parse_chat(f"music: {said}", TASTE))
        got, _, bad = choices.answers(TASTE, list(docs.items()))
        assert bad == [] and got["music"]["choice"] == "track-mixkit-cat-walk-371"


def test_a_section_is_named_by_its_title():
    docs = choices.parse_chat("Music: Cat Walk", TASTE)
    assert docs[0][0] == "music"


def test_a_label_of_two_options_stops_and_lists_them():
    with pytest.raises(Stop, match="v1, v2"):
        choices.parse_chat("voice: Same", TASTE)


# --- the run page: the lines, and a chat decision -----------------------------------------------------

@pytest.fixture
def run(tmp_path):
    r = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = ["creative_brief", "edited_video", "ai_video", "live_test"]
    state.save(r, s)
    set_level(r, "every_step")
    for step in ("A0", "A0b"):
        flow.complete(r, step)
    return r


def _ask(run, checkin="G1"):
    body = {"checkin": checkin, "title": "Which ad", "question": "Which ad do we refresh?",
            "options": [{"choice": "ad1", "label": "Ad 1", "recommended": True}, {"choice": "ad2", "label": "Ad 2"}]}
    path = run.path / "03_wip" / f"my_ask_{checkin}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_the_run_page_build_lists_the_open_check_in_answers(run, capsys):
    assert main(["page", "build", "--run", str(run.path), "--ask", str(_ask(run)), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["chat_answers"] == ['Pick the ad = G1: ad1 (Ad 1) / ad2 (Ad 2) '
                                   '(tm decide G1 <choice> --said "<their words>")']


def test_a_decision_in_chat_ends_the_wait_and_builds_the_page_again(run, capsys):
    built = run_page.build(run, _ask(run))
    page.record_published(run, run_page.PAGE, page.artifact_id(ART_URL), "v1", ART_URL)
    page.await_(run, run_page.PAGE, "v1")
    capsys.readouterr()
    assert main(["decide", "G1", "ad2", "--said", "the second one", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert page.awaiting(run, run_page.PAGE) is None
    again = out["run_page"]
    assert again["folder"] != built["folder"] and again["open"] == []
    assert "republish it to the same link" in out["message"]
    assert main(["page", "build", "--run", str(run.path), "--json"]) == 0      # no `tm page await --clear` needed


def test_a_decision_not_on_the_page_leaves_it_alone(run, capsys):
    run_page.build(run, _ask(run))
    page.record_published(run, run_page.PAGE, page.artifact_id(ART_URL), "v1", ART_URL)
    page.await_(run, run_page.PAGE, "v1")
    assert run_page.after_decision(run, "G1b", "user") is None
    assert page.awaiting(run, run_page.PAGE) is not None


def test_a_chat_reader_ends_the_run_page_wait(run):
    run_page.build(run, _ask(run))
    page.record_published(run, run_page.PAGE, page.artifact_id(ART_URL), "v1", ART_URL)
    page.await_(run, run_page.PAGE, "v1")
    assert "republish" in page.end_wait_for_chat(run, "models")
    assert page.awaiting(run, run_page.PAGE) is None
