"""tm.trends: TrendsMesh answers read back, saved to the run, pooled; noise; the fields PB04 needs."""

import ast
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from tm import manifest, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop

PLUGIN = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[4]
MOCK_VIDEOS = PLUGIN / "evals" / "mocks" / "trendsmesh" / "fixtures" / "videos_trend_example_01.json"
MOCK_LIST = PLUGIN / "evals" / "mocks" / "trendsmesh" / "fixtures" / "list.json"
PB4_TOOLS = REPO / "handoff" / "trend-research_v01" / "tools"


def _run(tmp_path) -> RunFolder:
    return RunFolder.create(tmp_path, "beauty", date(2026, 11, 7), playbook=TREND_RESEARCH)


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _saved(tool: str, tool_input: dict, answer) -> dict:
    return {"_tool": tool, "_input": tool_input, "_at": "2026-11-07T09:00:00+00:00", "answer": answer}


def _literal(path: Path, name: str):
    """A module-level constant of one of the handoff's tools, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not in {path}")


def test_videos_reads_rest_and_mcp_envelopes():
    a, b = {"asset_id": "a"}, {"asset_id": "b"}
    assert trends.videos({"videos": [a, b], "page": 1, "pages": 2}) == ([a, b], True)
    assert trends.videos({"videos": [b], "page": 2, "pages": 2}) == ([b], False)
    assert trends.videos({"data": [a], "page": 1, "has_more": True}) == ([a], True)
    assert trends.videos({"data": [], "page": 3, "has_more": False}) == ([], False)
    assert trends.videos({"data": [a], "page": 1, "has_more": "false"}) == ([a], False)   # only True means more
    legacy = {"trend_id": "t1", "fetched": "2026-11-04", "total": 2, "videos": [a, b]}
    assert trends.videos(legacy) == ([a, b], False)
    assert trends.videos([a]) == ([a], False)
    mock = json.loads(MOCK_VIDEOS.read_text(encoding="utf-8"))
    vids, more = trends.videos(mock)
    assert len(vids) == len(mock["data"]) > 0 and more is False


def test_load_videos_merges_pages_and_dedups_by_asset_id(tmp_path):
    run = _run(tmp_path)
    folder = run.path / "02_research" / "videos"
    _write(folder / "t1.json", {"trend_id": "t1", "fetched": "2026-11-04", "total": 2,
                                "videos": [{"asset_id": "a", "views": 1}, {"asset_id": "b", "views": 1}]})
    _write(folder / "t1_p01.json", _saved("get_trend_videos", {"trend_id": "t1", "page": 1},
                                          {"data": [{"asset_id": "a", "views": 2}, {"asset_id": "c"}],
                                           "page": 1, "has_more": True}))
    _write(folder / "t1_p02.json", _saved("get_trend_videos", {"trend_id": "t1", "page": 2},
                                          {"videos": [{"asset_id": "d"}], "page": 2, "pages": 2}))
    _write(folder / "t1_p01_v02.json", _saved("get_trend_videos", {"trend_id": "t1", "page": 1},
                                              {"data": [{"asset_id": "a", "views": 3}], "page": 1,
                                               "has_more": True}))
    _write(folder / "t10_p01.json", _saved("get_trend_videos", {"trend_id": "t10"},
                                           {"data": [{"asset_id": "x"}], "page": 1, "has_more": False}))
    _write(folder / "t1_notes.json", {"videos": [{"asset_id": "y"}]})
    got = trends.load_videos(run, "t1")
    assert [v["asset_id"] for v in got] == ["a", "b", "c", "d"]
    assert got[0]["views"] == 3                      # the later file wins
    assert trends.load_videos(run, "t2") == []
    assert [v["asset_id"] for v in trends.load_videos(run, "T1")] == ["a", "b", "c", "d"]   # ids ignore case


def test_creator_falls_back_to_url_handle_then_refuses(tmp_path, capsys):
    assert trends.creator_of({"creator": "ann", "creator_id": "id1", "url": "https://x/@bob/video/1"}) == "ann"
    assert trends.creator_of({"creator": None, "creator_id": "id1", "url": "https://x/@bob/video/1"}) == "id1"
    assert trends.creator_of({"url": "https://www.tiktok.com/@creator.0042/video/77?lang=en"}) == "creator.0042"
    assert trends.creator_of({"url": "https://www.tiktok.com/@creator0042?lang=en"}) == "creator0042"
    assert trends.creator_of({"creator": "  ann ", "creator_id": "id1"}) == "ann"
    assert trends.creator_of({"creator": "   ", "creator_id": "id1"}) == "id1"         # blank falls through
    assert trends.creator_of({"creator": 42, "creator_id": ["x"], "url": "https://x/@bob/video/1"}) == "bob"
    mock = json.loads(MOCK_VIDEOS.read_text(encoding="utf-8"))
    assert mock["data"] and all(trends.creator_of(v) is None for v in mock["data"])

    run = _run(tmp_path)
    trends.save_answer(run, "get_trend_videos", {"trend_id": "trend_example_01"}, mock)
    trends.save_answer(run, "search_trends", {"about": "nail art"},
                       json.loads(MOCK_LIST.read_text(encoding="utf-8")))
    missing = trends.check_fields(run)
    assert "creator" in missing
    assert set(missing) == {"creator", "url", "thumbnail_url", "match"}

    assert main(["trends", "check-fields", "--run", str(run.path), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and out["missing"] == missing


def test_check_fields_passes_on_complete_answers_and_needs_saved_ones(tmp_path, capsys):
    run = _run(tmp_path)
    with pytest.raises(Stop, match="nothing to check"):
        trends.check_fields(run)
    assert main(["trends", "check-fields", "--run", str(run.path), "--json"]) == 2     # a stop, not an error
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "the run continues from the same place" in out["message"]
    video = {"asset_id": "a", "url": "https://www.tiktok.com/@ann/video/1", "published": "2026-11-01T00:00:00Z",
             "views": 10, "thumbnail_url": "https://x/t.jpg"}       # no creator: the url's handle counts
    trends.save_answer(run, "get_trend_videos", {"trend_id": "t1"}, {"data": [video], "page": 1, "has_more": False})
    trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": [{"id": "t1", "kind": "topic_trend",
                                                                             "match": {"score": 50}}]})
    assert trends.check_fields(run) == []
    assert main(["trends", "check-fields", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == []


def test_save_answer_names_and_never_overwrites(tmp_path):
    run = _run(tmp_path)
    research = run.path / "02_research"
    answer = {"data": [{"id": "t1", "kind": "topic_trend"}]}
    first = trends.save_answer(run, "search_trends", {"about": "nail art"}, answer, at="2026-11-07T09:00:00Z")
    second = trends.save_answer(run, "search_trends", {"about": "nail art"}, answer)
    assert first == research / "search" / "search_nail_art.json"
    assert second == research / "search" / "search_nail_art_v02.json"
    saved = json.loads(first.read_text(encoding="utf-8"))
    assert saved == {"_tool": "search_trends", "_input": {"about": "nail art"}, "_at": "2026-11-07T09:00:00Z",
                     "answer": answer}
    assert json.loads(second.read_text(encoding="utf-8"))["_at"]           # stamped when not given
    rows = manifest.rows(run)
    assert [r["file"] for r in rows] == ["02_research/search/search_nail_art.json",
                                         "02_research/search/search_nail_art_v02.json"]
    assert rows[0]["source"] == "TrendsMesh MCP search_trends" and rows[0]["stage"] == "02_research"
    assert json.loads(rows[0]["params"]) == {"about": "nail art"}

    def name(tool, tool_input, at=None):
        return trends.save_answer(run, tool, tool_input, {}, at=at).relative_to(research).as_posix()

    assert name("search_trends", {"about": "Nail Art!", "trend_type": "hook_trend", "page": 2}) == \
        "search/search_nail_art_hook_trend_p02.json"
    assert name("search_trends", {"about": "Uroda, włosy", "page": 1}) == "search/search_uroda_wlosy.json"   # ł kept as l (issue #3)
    assert name("list_trends", {"sort": "rising", "trend_type": "hook_trend"}) == "lists/list_rising_hook_trend_p01.json"
    assert name("list_trends", {"sort": "updated", "page": 3}) == "lists/list_updated_all_p03.json"
    assert name("get_trend", {"trend_id": "t1"}) == "trend_t1.json"
    assert name("get_trend", {"trend_id": "t1"}) == "trend_t1_v02.json"
    assert name("get_trend_videos", {"trend_id": "t1"}) == "videos/t1_p01.json"
    assert name("get_trend_videos", {"trend_id": "t1", "page": 12}) == "videos/t1_p12.json"
    assert name("get_usage", {}, at="2026-11-07T09:05:03Z") == "usage/usage_20261107T090503.json"
    assert name("ads_library_search", {"search_terms": "Glow serum"}) == "ad_library/ads_glow_serum.json"
    assert name("ads_library_search", {"q": "glow  serum"}) == "ad_library/ads_glow_serum_v02.json"
    # a TrendsMesh tool the engine doesn't know yet: saved under a generic name, never refused
    assert name("get_topic_graph", {"trend_id": "t1"}, at="2026-11-07T09:05:03Z") == \
        "other/get_topic_graph_20261107T090503.json"
    assert name("get_topic_graph", {}, at="2026-11-07T09:05:03Z") == "other/get_topic_graph_20261107T090503_v02.json"
    assert manifest.rows(run)[-1]["source"] == "TrendsMesh MCP get_topic_graph"
    assert len(manifest.rows(run)) == 15
    with pytest.raises(ValueError, match="trend_id"):
        trends.save_answer(run, "get_trend", {"trend_id": "../x"}, {})
    for page in (0, -1, "2", 1.5, True):
        with pytest.raises(ValueError, match="page"):
            trends.save_answer(run, "get_trend_videos", {"trend_id": "t1", "page": page}, {})


def _sha8(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def test_answer_names_stay_short_and_readable(tmp_path):
    run = _run(tmp_path)
    research = run.path / "02_research"
    long = "glow serum routine " * 16                     # 304 characters
    path = trends.save_answer(run, "search_trends", {"about": long}, {})
    stem = path.relative_to(research / "search").stem.removeprefix("search_")
    assert len(stem) == 40 and stem.endswith("_" + _sha8(long)) and stem.startswith("glow_serum_routine_")
    other = trends.save_answer(run, "search_trends", {"about": long + "x"}, {})
    assert other.parent == path.parent and other.stem != path.stem and "_v02" not in other.stem

    cyrillic = "уход за кожей"
    path = trends.save_answer(run, "search_trends", {"about": cyrillic}, {})
    assert path.name == f"search_{_sha8(cyrillic)}.json"
    path = trends.save_answer(run, "search_trends", {"about": "красота"}, {})
    assert path.name == f"search_{_sha8('красота')}.json"         # never a bare search_query.json
    path = trends.save_answer(run, "ads_library_search", {"search_terms": cyrillic}, {})
    assert path.name == f"ads_{_sha8(cyrillic)}.json"
    short = trends.save_answer(run, "search_trends", {"about": "nail art"}, {})
    assert short.name == "search_nail_art.json"                       # short ASCII names stay as they are


def test_pool_keeps_best_score_per_query(tmp_path):
    run = _run(tmp_path)
    a = {"id": "A", "kind": "topic_trend", "name": "Nail art first"}
    b = {"id": "B", "kind": "hook_trend", "name": "Nail hook"}
    trends.save_answer(run, "search_trends", {"about": "nail art"},
                       {"data": [{**a, "match": {"score": 30}}, {**b, "match": {"score": 50}}]})
    trends.save_answer(run, "search_trends", {"about": "nail art"},
                       {"data": [{**a, "name": "Nail art later", "match": {"score": 45}}]})
    trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": [{**a, "match": 60}]})
    folder = run.path / "02_research" / "search"
    _write(folder / "search_lashes.json", {"_query": "lashes", "_limit": 50, "items": [{**a, "match": {"score": 20}}]})
    _write(folder / "search_dream_journal.json", [{"id": "C", "kind": "topic_trend", "match": {"score": 70}}])
    _write(folder / "search_brows.json", {"_query": "brows", "items": {"items": [{"id": "D", "kind": "topic_trend"}]}})

    pool = trends.pool(run)
    assert set(pool) == {"A", "B", "C", "D"}
    assert pool["A"]["found_by"] == {"nail art": 45.0, "nails": 60.0, "lashes": 20.0}
    assert pool["A"]["card"]["name"] == "Nail art first"           # the first card seen is kept
    assert pool["B"]["found_by"] == {"nail art": 50.0}
    assert pool["C"]["found_by"] == {"dream journal": 70.0}       # a bare legacy list: the file name
    assert pool["D"]["found_by"] == {"brows": 0.0}
    assert set(trends.pool(run, kinds=("hook_trend",))) == {"B"}


def test_items_reads_cards_in_the_original_key_order(tmp_path):
    card = {"id": "t1", "kind": "topic_trend"}
    assert trends.items([card]) == [card]
    assert trends.items(card) == [card]                           # a single card (get_trend)
    assert trends.items({"trends": [1], "data": [2]}) == [1]
    assert trends.items({"results": [1], "data": [2]}) == [1]
    assert trends.items({"data": [2], "videos": [3]}) == [2]
    assert trends.items({"videos": [3]}) == [3]
    assert trends.items({"kept": [4]}) == []
    assert trends.items(None) == []
    run = _run(tmp_path)
    path = trends.save_answer(run, "get_trend", {"trend_id": "t1"}, card)
    assert trends.answer_of(path) == card
    legacy = run.path / "02_research" / "legacy.json"
    _write(legacy, [card])
    assert trends.answer_of(legacy) == [card]
    assert trends.match_score({"match": {"score": 41}}) == 41.0
    assert trends.match_score({"match": 12.5}) == 12.5
    assert trends.match_score({"match": {"score": None}}) == 0.0
    assert trends.match_score({}) == 0.0


def test_noise_keeps_halloween_makeup_and_curly_vs_straight():
    if not PB4_TOOLS.is_dir():
        pytest.skip(f"The handoff's tools are not in this checkout ({PB4_TOOLS}); the noise lists are "
                    "compared with them, so this test needs handoff/trend-research_v01/tools.")
    assert trends.DEFAULT_NOISE == _literal(PB4_TOOLS / "pb2" / "trend_shortlist.py", "DEFAULT_NOISE")
    assert trends.GENERIC_TOKENS == _literal(PB4_TOOLS / "pb4" / "category_map.py", "GENERIC_TOKENS")
    assert "holiday/seasonal" not in trends.NOISE_GROUPS
    assert "vs" not in trends.NOISE_GROUPS["sport"] and "football" in trends.NOISE_GROUPS["sport"]
    assert trends.SEASONAL == trends.DEFAULT_NOISE["holiday/seasonal"]

    halloween = {"name": "Halloween makeup looks", "what_it_is": "Spooky glam for the night."}
    assert trends.seasonal_tag(halloween) == "halloween"
    assert trends.noise_reasons(halloween, []) == []
    curly = {"name": "Curly vs straight hair", "what_it_is": "Which one wins the match?"}
    assert trends.seasonal_tag(curly) is None
    assert trends.noise_reasons(curly, []) == []

    news = {"name": "Taylor Swift's lip shade", "what_it_is": "Fans copy it after the election scandal."}
    assert trends.noise_reasons(news, ["Lip"]) == [
        "politics/elections: election", "news/disaster/crime: scandal", "excluded term: Lip",
        "possessive proper name (celebrity / news item)"]
