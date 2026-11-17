"""Organic AI video on Free (issue #106): the guessed trends, their check, and how proposals and pages use them."""

import json
from datetime import date

import pytest

from tm import evidence, organic_guesses, organic_proposals, organic_research, state, trends
from tm.cli import main
from tm.config import Problem
from tm.runfolder import RunFolder
from tm.stops import Stop

TODAY = date(2026, 11, 14)


def _guess(i=1, **kw):
    return {"id": f"g{i}", "kind": "hook_trend", "name": f"POV: you finally {i}", "what": "a first-person opener",
            "source": "creative_center", "url": "https://ads.tiktok.com/business/creativecenter/x", "seen_on":
            "2026-11-13", "quote": None, **kw}


def _file(n=3, **kw):
    return {"lang": "en", "guesses": [_guess(i, **kw) for i in range(1, n + 1)]}


def _fields(problems):
    return [p.field for p in problems]


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    r = RunFolder.create(ws, "chan", TODAY, playbook="organic-video")
    s = state.load(r)
    s.evidence = evidence.GUESS          # the user chose Free (recorded through the guard in real runs)
    state.save(r, s)
    return r


def _checked(run, capsys, data=None):
    path = run.next_version("03_wip", organic_guesses.STEM, "json")
    path.write_text(json.dumps(data or _file()), encoding="utf-8")
    capsys.readouterr()
    code = main(["organic", "guesses", "check", "--run", str(run.path), "--file", "03_wip/" + path.name, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_a_good_file_passes():
    assert organic_guesses.check(_file(), today=TODAY) == []
    assert organic_guesses.check(_file(source="own_knowledge", url=None), today=TODAY) == []


@pytest.mark.parametrize("change,field", [
    ({"name": "POV hook, rising fast"}, "guesses[0].name"),              # a lifecycle stage is TrendsMesh's
    ({"what": "too late for most brands"}, "guesses[0].what"),
    ({"what": "on 1.2M videos this week"}, "guesses[0].what"),           # a count outside quote
    ({"what": "12 creators used it"}, "guesses[0].what"),
    ({"quote": "1.2M views", "url": None, "source": "own_knowledge"}, "guesses[0].source"),
    ({"url": None}, "guesses[0].url"),                                   # seen somewhere, no link to where
    ({"url": "http://example.com"}, "guesses[0].url"),
    ({"source": "trendsmesh"}, "guesses[0].source"),
    ({"kind": "meme_trend"}, "guesses[0].kind"),
    ({"seen_on": "2026-11-20"}, "guesses[0].seen_on"),
    ({"quote": "rising: 1.2M views"}, "guesses[0].quote"),
])
def test_what_would_pass_a_guess_off_as_data_is_refused(change, field):
    data = _file()
    data["guesses"][0].update(change)
    assert field in _fields(organic_guesses.check(data, today=TODAY))


def test_polish_stage_words_are_refused_too():
    data = _file()
    data["guesses"][0]["what"] = "temat, który rośnie"
    assert "guesses[0].what" in _fields(organic_guesses.check(data, today=TODAY))


def test_count_and_ids():
    assert "guesses" in _fields(organic_guesses.check(_file(n=2), today=TODAY))
    data = _file()
    data["guesses"][1]["id"] = "g1"
    assert "guesses[1].id" in _fields(organic_guesses.check(data, today=TODAY))


def test_a_quote_with_its_link_passes():
    assert organic_guesses.check(_file(quote="1.2M views on the hashtag page"), today=TODAY) == []


def test_the_check_marks_the_file_and_b2_b3_ask_for_it(run, capsys):
    assert organic_research.shortlist_gap(run) is not None and organic_research.evidence_gap(run) is not None
    code, out = _checked(run, capsys)
    assert code == 0 and out["guesses"] == 3
    assert organic_research.shortlist_gap(run) is None and organic_research.evidence_gap(run) is None


def test_a_paid_run_has_no_guesses(tmp_path, capsys):
    (tmp_path / "ws").mkdir()
    paid = RunFolder.create(tmp_path / "ws", "chan", TODAY, playbook="organic-video")
    path = paid.next_version("03_wip", organic_guesses.STEM, "json")
    path.write_text(json.dumps(_file()), encoding="utf-8")
    capsys.readouterr()
    assert main(["organic", "guesses", "check", "--run", str(paid.path), "--file", "03_wip/" + path.name]) == 1
    assert "not on Free" in "".join(capsys.readouterr())
    assert organic_guesses.latest(paid) == {}


def test_a_guess_resolves_to_its_key_and_has_no_videos(run, capsys):
    _checked(run, capsys)
    key, card = organic_research.resolve(run, "g1")
    assert key == organic_guesses.used_key(_guess(1)) and key.startswith("guess-hook-")
    assert card["guess"]["source"] == "creative_center" and card["kind"] == "hook_trend"
    assert organic_research.resolve(run, key) == (key, card)
    assert organic_research.card(run, key)[0] == card
    with pytest.raises(Stop):
        organic_research.videos(run, "g1")
    with pytest.raises(ValueError):
        organic_research.resolve(run, "g9")


def test_the_used_key_is_a_trend_id_and_stable():
    a = organic_guesses.used_key({"kind": "topic_trend", "name": "Zakazane gry  wideo"})
    assert a == organic_guesses.used_key({"kind": "topic_trend", "name": "zakazane gry wideo"})
    assert trends.TREND_ID.fullmatch(a)
    assert organic_research.used_rows([{"trend_id": a, "kind": "topic_trend", "run": "r", "video": "m1"}])


def _proposal(**kw):
    return {"id": "m1", "title": "t", "approach": "Inspire", "trends": [{"id": "g1", "role": "the hook"}],
            "plugin": {"transfer": False, "weak_link": "loose", "series": None, "seed": None}, **kw}


def test_proposals_on_free_name_guesses_without_picks(run, capsys):
    _checked(run, capsys)
    out: list[Problem] = []
    found = organic_proposals._trends(run, _proposal(), "m1", out)
    assert out == [] and list(found) == [organic_guesses.used_key(_guess(1))]
    out = []
    organic_proposals._trends(run, _proposal(trends=[{"id": "g1", "role": "x", "pick": [0, 1]}]), "m1", out)
    assert _fields(out) == ["m1.trends[0].pick"]


def test_no_recreate_on_free(run, capsys):
    _checked(run, capsys)
    out: list[Problem] = []
    found = organic_proposals._trends(run, _proposal(), "m1", out)
    organic_proposals._approach(_proposal(approach="Recreate"), "m1", found, out)
    assert _fields(out) == ["m1.approach"] and "only TrendsMesh" in out[0].what
    out = []
    organic_proposals._approach(_proposal(approach="Inspiracja"), "m1", found, out)
    assert out == []


def test_the_source_line_names_where_never_a_stage():
    words = {"creative_center": "Seen on TikTok Creative Center", "own_knowledge": "My own knowledge, no source"}
    assert organic_guesses.source_line(_guess(1, quote="1.2M views"), words) == \
        "Seen on TikTok Creative Center, 2026-11-13 · 1.2M views"
    assert organic_guesses.source_line(_guess(1, source="own_knowledge", url=None), words) == \
        "My own knowledge, no source"


def test_the_ideas_page_shows_the_guess_and_what_trendsmesh_would_add():
    from tm.run_page import organic_plan
    from tm.run_page.words import tx
    w = {k: tx("organic.proposals." + k, "en") for k in organic_plan.PROPOSAL_UI if k != "needs"} | \
        {k: tx("organic." + k, "en") for k in organic_plan.SHARED_UI}
    it = {"recipe": [], "beats": [], "risks": [], "risk_line": "", "cost": [0, 0], "cost_note": "", "facts": "",
          "why": "", "trends": [{"kind": "Hook", "name": "POV: you finally", "stats": "Seen on TikTok Creative Center, "
                                 "2026-11-13", "role": "the opener", "videos": [], "guess": True,
                                 "url": "https://ads.tiktok.com/x"}]}
    html = organic_plan._proposal_body(it, w)
    assert "What it&#x27;s based on (my guess)" in html or "What it's based on (my guess)" in html
    assert "With TrendsMesh" in html and "— creators · — videos · stage —" in html
    assert "Recreate needs TrendsMesh" in html and ">Guess<" in html
    assert html.count("With TrendsMesh") == 1      # one box per idea, never one per trend
