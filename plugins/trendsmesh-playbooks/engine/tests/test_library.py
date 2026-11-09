"""R5: the results library."""

import json
from pathlib import Path

import pytest

from tm import library
from tm.cli import main


def row(**kw):
    base = {"account": "act_1", "product": "Ebook", "market": "PL", "category": "ebooks",
            "diagnosis": "hook", "trend": {"id": "t1", "type": "sound", "status_on_test_day": "rising"},
            "change": {"layer": "text", "method": "hook_swap"}, "decision_metric": "hook_rate",
            "result_vs_control": 0.31, "events": 420, "decision": "scale",
            "run": "2026-11-05_ad-3", "variant": "A"}
    base.update(kw)
    return base


@pytest.fixture
def ws(tmp_path):
    p = tmp_path / "Moje reklamy Łódź"
    p.mkdir()
    return p


def test_add_appends_without_touching_earlier_rows(ws):
    library.add(ws, row())
    first = (ws / "library" / "results.jsonl").read_bytes()
    library.add(ws, row(decision="kill", trend={"id": "t2", "type": "format", "status_on_test_day": "peak"}))
    data = (ws / "library" / "results.jsonl").read_bytes()
    assert data.startswith(first) and len(data.splitlines()) == 2
    assert json.loads(data.splitlines()[1])["trend"]["id"] == "t2"


def test_add_refuses_a_row_missing_fields(ws):
    bad = row()
    del bad["decision"], bad["run"], bad["variant"]
    with pytest.raises(ValueError, match="decision, run, variant"):
        library.add(ws, bad)
    assert not (ws / "library" / "results.jsonl").exists()


def test_summary_counts_by_trend_and_method(ws):
    library.add(ws, row())
    library.add(ws, row(decision="kill"))
    library.add(ws, row(decision="scale", trend={"id": "t2", "type": "sound", "status_on_test_day": "rising"},
                        change={"layer": "text", "method": "ending_card"}))
    library.add(ws, row(decision="no_verdict"))
    s = library.summary(ws, "ebooks", "PL")
    assert s["trend:t1"] == {"won": 1, "lost": 1}
    assert s["method:hook_swap"] == {"won": 1, "lost": 1}
    assert s["trend:t2"] == {"won": 1, "lost": 0} and s["method:ending_card"] == {"won": 1, "lost": 0}


def test_summary_filters_category_and_market(ws):
    library.add(ws, row())
    library.add(ws, row(market="DE"))
    library.add(ws, row(category="travel"))
    assert library.summary(ws, "ebooks", "PL")["trend:t1"] == {"won": 1, "lost": 0}
    assert library.summary(ws, "ebooks", "FR") == {}


def test_summary_without_a_library_is_empty(ws):
    assert library.summary(ws, "ebooks", "PL") == {}


def test_cli_add_and_summary(ws, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    f = ws / "row.json"
    f.write_text(json.dumps(row()), encoding="utf-8")
    assert main(["library", "add", "--json", str(f)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
    assert main(["library", "summary", "--category", "ebooks", "--market", "PL", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["trend:t1"] == {"won": 1, "lost": 0}
    assert main(["library", "add", "--row", str(ws / "none.json")]) == 1


def test_variants_for_run_counts_a_repeat_once(ws):
    library.add(ws, row(variant="A"))
    library.add(ws, row(variant="A"))
    library.add(ws, row(variant="B"))
    library.add(ws, row(variant="C", run="other"))
    assert library.variants_for_run(ws, "2026-11-05_ad-3") == ["A", "B"]


# --- the shared JSONL reader and appender (results, trend_calls, seeds) -------------------------

SEPARATORS = "line para next\u0085end"      # str.splitlines breaks at each; ensure_ascii=False keeps them


def test_rows_with_unicode_line_separators_read_back_whole(ws):
    library.add(ws, row(diagnosis=SEPARATORS))
    library.add(ws, row(variant="B"))
    raw = (ws / "library" / "results.jsonl").read_text(encoding="utf-8")
    assert " " in raw                                  # written unescaped
    got = library.rows(ws)
    assert [r["diagnosis"] for r in got] == [SEPARATORS, "hook"]
    rows, damaged = library.read_jsonl(ws / "library" / "results.jsonl")
    assert damaged == [] and len(rows) == 2

    path = ws / "library" / "other.jsonl"
    library.append_jsonl(path, [{"text": SEPARATORS}, {"n": 2}])
    assert library.read_jsonl(path) == ([{"text": SEPARATORS}, {"n": 2}], [])


def test_jsonl_read_skips_a_bom_and_crlf_line_ends(ws):
    path = ws / "library" / "seeds.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}\r\n{"b": 2}\r\nnot json\r\n')   # saved by Notepad
    assert library.read_jsonl(path) == ([{"a": 1}, {"b": 2}], [3])
    library.append_jsonl(path, [{"c": 3}])
    assert library.read_jsonl(path) == ([{"a": 1}, {"b": 2}, {"c": 3}], [3])

    (ws / "library" / "results.jsonl").write_bytes(b"\xef\xbb\xbf" + json.dumps(row()).encode("utf-8") + b"\n")
    assert [r["variant"] for r in library.rows(ws)] == ["A"]          # PB01's reader is the same one
