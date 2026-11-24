"""The channel's text set picked on the images check-in of its first video (issue #165, item 1): the three sets drawn
on the user's words are one item of the page, one click picks one, and recording it approves that style and saves it
for the channel, so the second video uses it without asking."""

from __future__ import annotations

import json

import pytest

from test_organic_edit import remotion  # noqa: F401  (tm render without Node)
from test_organic_gates import _cli, _decide, _m5, _ready, no_downloads  # noqa: F401
from tm import organic_edit, organic_gates, page, state, text_sets, trend_spool
from tm.stops import Stop

LOOKS = ("outline", "native", "pop")


def _draw(run, capsys, *looks):
    """Each set drawn on the host image, as the agent draws the three the first time: {look: (style, still)}."""
    out = {}
    for look in looks:
        code, got = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                         "03_wip/host_v01_0.png", "--caption", "Sprawdzam, co rośnie", "--overlay", "Jak szukam",
                         "--look", look)
        assert code == 0, got
        out[look] = (got["style"], got["still"])
    return out


@pytest.fixture
def first(tmp_path, remotion, capsys):  # noqa: F811
    run = _m5(tmp_path, picked=False, final=False)
    assert text_sets.for_run(run) is None
    return run, _draw(run, capsys, *LOOKS)


def _data(run, capsys):
    code, out = _cli(capsys, "organic", "page", "gate", "--gate", "images", "--run", str(run.path))
    assert code == 0, out
    return json.loads((run.path / out["data"]).read_text(encoding="utf-8"))


# --- text_sets.take_pick -----------------------------------------------------------------------------

@pytest.mark.private_data
def test_a_pick_that_is_not_the_latest_style_is_made_the_latest_approved_and_saved(first):
    run, drawn = first
    style = drawn["outline"][0]
    got = text_sets.take_pick(run, style, note="ten pierwszy")
    assert got["style"] == "03_wip/text_style_v04.json" and got["picked_from"] == style and got["look"] == "outline"
    assert (run.path / got["style"]).read_bytes() == (run.path / style).read_bytes()
    assert organic_edit.approved_style(run)[0] == got["style"]
    assert state.load(run).checked["text_style"]["look"] == drawn["outline"][1]   # the still the user saw
    saved = text_sets.for_run(run)
    assert saved["look"] == "outline" and saved["note"] == "ten pierwszy" and got["saved"] == saved["file"]
    assert got["owner"] == ["channel", "exampleedu"]


def _brand_inventory(run):
    """What `tm tool site brand` left in the run: the brand's font and its logo, listed in 02_research/brand_v01.json."""
    folder = run.path / "02_research" / "brand"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Brand-Bold.ttf").write_bytes(b"\x00\x01\x00\x00 a font")
    (folder / "logo.png").write_bytes(b"\x89PNG logo")
    (run.path / "02_research" / "brand_v01.json").write_text(json.dumps(
        {"fonts": [{"family": "Brand Sans", "files": [{"file": "02_research/brand/Brand-Bold.ttf"}]}],
         "logos": [{"png": "02_research/brand/logo.png", "names_brand": True}]}), encoding="utf-8")


@pytest.mark.private_data
def test_a_pick_is_saved_with_the_brands_font_and_logo_when_the_run_has_them(first):
    """#176 line 74: the save adds them itself; nothing depends on Claude saving the set again."""
    run, drawn = first
    _brand_inventory(run)
    got = text_sets.take_pick(run, drawn["pop"][0], note="pop")
    saved = text_sets.for_run(run)
    assert saved["font"]["family"] == "Brand Sans" and saved["font"]["file"].endswith("/text/brand-bold_v01.ttf")
    assert saved["logo"].endswith("/text/logo_v01.png")
    assert got["brand_files"] == {"font": "02_research/brand_v01.json", "logo": "02_research/brand_v01.json"}
    said = organic_gates.text_set_said({"text_set": got})
    assert "with the brand's font Brand Sans and logo" in said


@pytest.mark.private_data
def test_a_pick_without_the_brands_files_saves_the_set_as_drawn(first):
    run, drawn = first
    got = text_sets.take_pick(run, drawn["pop"][0], note="pop")
    saved = text_sets.for_run(run)
    assert saved["font"] is None and saved["logo"] is None and got["brand_files"] == {}
    assert "brand's font" not in organic_gates.text_set_said({"text_set": got})


@pytest.mark.private_data
def test_a_pick_of_the_latest_style_copies_nothing(first):
    run, drawn = first
    got = text_sets.take_pick(run, drawn["pop"][0], note="pop")
    assert got["style"] == drawn["pop"][0] == "03_wip/text_style_v03.json"
    assert run.latest("03_wip", "text_style", "json").name == "text_style_v03.json"
    assert text_sets.for_run(run)["look"] == "pop"


@pytest.mark.private_data
def test_a_run_naming_no_channel_is_approved_and_not_saved(first, monkeypatch):
    run, drawn = first
    monkeypatch.setattr(text_sets, "owners", lambda run: [])
    got = text_sets.take_pick(run, drawn["native"][0], note="native")
    assert got["saved"] is None and got["owner"] is None and organic_edit.approved_style(run) is not None


@pytest.mark.private_data
def test_a_style_changed_since_it_was_drawn_is_refused(first):
    run, drawn = first
    style = drawn["native"][0]
    sha = organic_edit._sha(run.path / style)
    (run.path / style).write_text("{}", encoding="utf-8")
    with pytest.raises(Stop, match="changed since"):
        text_sets.check_pick(run, style, sha)


# --- the images check-in ------------------------------------------------------------------------------

@pytest.mark.private_data
def test_the_first_videos_images_page_has_the_text_set_item(first, capsys):
    run, drawn = first
    data = _data(run, capsys)
    item = data["items"][-1]
    assert item["id"] == "text-set" and [o["id"] for o in item["options"]] == list(LOOKS)
    assert [o["src"] for o in item["options"]] == [drawn[x][1] for x in LOOKS]
    assert [o.get("pick", False) for o in item["options"]] == [True, False, False]   # the suggested: drawn first
    assert item["label"] == "Zestaw napisów"                                       # the run's page language
    entry = data["plugin"]["items"]["text-set"]
    assert entry["kind"] == "text_set" and entry["files"]["pop"] == drawn["pop"][1]
    assert entry["styles"]["native"]["file"] == drawn["native"][0]
    host = next(it for it in data["items"] if it["id"] == "images-host")
    assert not any(r["src"].startswith("03_wip/text_look") for r in host["refs"])   # shown once, as the item
    assert any(line.startswith("Zestaw napisów = text-set: accept") and "native" in line
               for line in organic_gates.chat_answers(data))


@pytest.mark.private_data
def test_with_a_saved_set_or_fewer_than_three_drawn_there_is_no_text_set_item(tmp_path, remotion, capsys):  # noqa: F811
    run = _m5(tmp_path, picked=False, final=False)
    _draw(run, capsys, "outline", "native")
    data = _data(run, capsys)
    assert [it["id"] for it in data["items"]] == ["images-host"]
    assert sum(r["src"].startswith("03_wip/text_look") for r in data["items"][0]["refs"]) == 2
    _draw(run, capsys, "pop")
    text_sets.save(trend_spool.workspace_of(run), "channel", "exampleedu", look="pop", run=run, note="pop")
    assert [it["id"] for it in _data(run, capsys)["items"]] == ["images-host"]


@pytest.mark.private_data
def test_a_choice_alone_is_the_pick_and_accept_alone_takes_the_suggested_set(first, capsys):
    run, _ = first
    data = _data(run, capsys)
    rows = organic_gates._rows(data, {"text-set": {"choice": "native"}})
    assert (rows["text-set"]["action"], rows["text-set"]["choice"]) == ("accept", "native")
    rows = organic_gates._rows(data, {"text-set": {"action": "accept"}})
    assert rows["text-set"]["choice"] == "outline"
    rows = organic_gates._rows(data, {"images-host": {"choice": "host_v01_1"}})
    assert rows["images-host"]["action"] is None                     # an image's choice alone stays undecided


@pytest.mark.private_data
def test_the_pick_in_chat_approves_and_saves_the_set(first, capsys):
    run, drawn = first
    _ready(run, capsys, "gate_images", "images")
    chat = run.path / "03_wip" / "chat_gate.txt"
    chat.write_text("text-set: akceptuj; wybór: pop; uwaga: ten jest najżywszy\n", encoding="utf-8")
    code, out = _decide(run, capsys, "gate_images", "--text", "03_wip/chat_gate.txt")
    assert code == 0, out
    assert out["text_set"]["look"] == "pop" and out["text_set"]["saved"].endswith("text_style_v01.json")
    saved = text_sets.for_run(run)
    assert saved["look"] == "pop" and saved["note"] == "ten jest najżywszy"
    assert organic_edit.approved_style(run)[0] == drawn["pop"][0]


@pytest.mark.private_data
def test_a_pick_whose_style_changed_stops_before_anything_is_written(first, capsys):
    run, drawn = first
    _ready(run, capsys, "gate_images", "images")
    (run.path / drawn["native"][0]).write_text("{}", encoding="utf-8")
    chat = run.path / "03_wip" / "chat_gate.txt"
    chat.write_text("text-set: accept; choice: native\n", encoding="utf-8")
    code, out = _decide(run, capsys, "gate_images", "--text", "03_wip/chat_gate.txt")
    assert (code, out["status"]) == (2, "stop") and "changed since" in out["message"]
    assert run.latest("03_wip", "decisions_gate_images", "json") is None
    assert text_sets.for_run(run) is None


@pytest.mark.private_data
def test_a_dropped_or_undecided_text_set_saves_nothing(first, capsys):
    run, _ = first
    _ready(run, capsys, "gate_images", "images")
    chat = run.path / "03_wip" / "chat_gate.txt"
    chat.write_text("images-host: accept; choice: host_v01_0\n", encoding="utf-8")
    code, out = _decide(run, capsys, "gate_images", "--text", "03_wip/chat_gate.txt")
    assert code == 0, out
    assert out["text_set"] is None and text_sets.for_run(run) is None


# --- the run page ---------------------------------------------------------------------------------------

def test_one_click_on_the_run_pages_text_set_saves_it_for_the_channel(tmp_path, remotion, capsys):  # noqa: F811
    from test_run_page_organic import _answered, _ask, _html, _new, _pack, _record, _to
    from tm import config, organic_config, run_page
    from tm.cli import main

    run = _new(tmp_path)
    config.save(run, {**organic_config.defaults(), "channels": ["exampleedu"]})
    _pack(run)
    _record(run, "host", 1, ["host_v01_0.png", "host_v01_1.png"])
    _to(run, "images")
    _draw(run, capsys, *LOOKS)
    built = run_page.build(run, _ask(run, "images"))
    now = _html(run, built).split('<section class="decision"')[0]
    assert now.count('name="ovc-text-set"') == 3
    _answered(run, "images", "images_v01", "accept", actions={"images-host": "accept"},
              choices={"images-host": "host_v01_0", "text-set": "native"})
    assert main(["page", "decision", "images", "--run", str(run.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "text set is now native" in out["message"]
    assert text_sets.for_run(run)["look"] == "native"
    assert organic_edit.approved_style(run)[0] == "03_wip/text_style_v04.json"     # the pick, made the latest
    assert page.awaiting(run, run_page.PAGE) is None
