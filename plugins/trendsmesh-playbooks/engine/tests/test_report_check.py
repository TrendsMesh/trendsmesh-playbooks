import json

import pytest

from tm import cli
from tm.report import findings, workspace_values


@pytest.mark.parametrize("text,kind", [
    ("account act_12345678", "account_id"), ("id 1234567890123456", "account_id"),
    ("mail ann@shop.test", "email"), ("token r8_" + "a" * 24, "key"), ("key sk_" + "0" * 48, "key"),
    ("EAA" + "B" * 30, "key"), ("ghp_" + "x" * 36, "key"), ("github_pat_" + "Z" * 24, "key"),
    ("/Users/ann/ws", "home_path"), ("/home/ann/ws", "home_path"),
    (r"C:\Users\ann\ws", "home_path"), (r"c:\Users\ann\ws", "home_path"),
    ("spent $1,234.50", "amount"), ("1 234 zł", "amount"), ("12 PLN", "amount"), ("EUR 40", "amount"),
    ("£9", "amount"), ("12 pln", "amount"), ("12 usd", "amount"), ("usd 12", "amount"),
    ("C:\\\\Users\\\\ann\\\\ws", "home_path"), ("C:/Users/ann/ws", "home_path"),
    ("/USERS/ann/ws", "home_path"), ("/HOME/ann/ws", "home_path"), ("/Home/ann", "home_path"),
    ("id 1234567890123456789", "account_id")])
def test_finds_each_pattern(text, kind):
    assert [f[1] for f in findings(text, set())] == [kind]


def test_allows_public_addresses():
    assert findings("contact@trendsmesh.com and a@example.com, b@example.org c@example.net", set()) == []


def test_placeholder_path_is_clean():
    assert findings("/Users/<user>/ws and C:\\Users\\<user>\\ws", set()) == []


def test_plain_numbers_are_not_amounts():
    assert findings("12 files, 3 ads, 1234567890 rows", set()) == []


def test_digit_runs_need_word_boundaries():
    assert findings("v1234567890123 1234567890123x", set()) == []
    assert [f[1] for f in findings("12345678901234567890", set())] == ["account_id"]


def test_key_prefix_is_not_a_second_account_id():
    assert [f[1] for f in findings("sk_" + "0" * 48, set())] == ["key"]
    assert [f[1] for f in findings("act_12345678", set())] == ["account_id"]


def test_known_value_whole_word_only():
    assert [f[1] for f in findings("Fresh ads, refresh", {"Fresh"})] == ["workspace_value"]


def test_known_value_is_case_insensitive_and_reported_as_found():
    assert findings("my SHOP x here", {"Shop X"}) == [(1, "workspace_value", "SHOP x")]


def test_known_value_found_by_another_kind_is_reported_once():
    assert [f[1] for f in findings("ann@shop.test", {"shop"})] == ["email"]
    assert [f[1] for f in findings("act_12345678", {"act_12345678"})] == ["account_id"]


def test_reports_line_numbers_sorted():
    text = "ok\nact_12345678 and ann@shop.test\n$5"
    assert [(f[0], f[1]) for f in findings(text, set())] == [(2, "account_id"), (2, "email"), (3, "amount")]


def test_workspace_values_from_saved_json(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "a.json").write_text(
        json.dumps({"data": [{"account_name": "Shop X", "id": "1", "handle": "ab", "brand": 5}]}), encoding="utf-8")
    assert workspace_values(tmp_path) == {"Shop X"}


def test_workspace_values_numbers_count_booleans_do_not(tmp_path):
    (tmp_path / "n.json").write_text('{"account_id": 1234567890, "page_id": true, "brand": false}', encoding="utf-8")
    assert workspace_values(tmp_path) == {"1234567890"}


def test_workspace_values_skip_pixi_and_big_files(tmp_path):
    for folder in (".pixi", "node_modules", ".git"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "x.json").write_text('{"brand": "Hidden"}', encoding="utf-8")
    (tmp_path / "big.json").write_text('{"brand": "Huge", "pad": "' + "x" * (5 * 1024 * 1024) + '"}', encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "ok.json").write_text('{"page_name": "Visible"}', encoding="utf-8")
    assert workspace_values(tmp_path) == {"Visible"}


def test_workspace_values_include_secrets(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "secrets.env").write_text("A_KEY=sekret-value\nB=ab\n", encoding="utf-8")
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    ws = tmp_path / "ws"
    ws.mkdir()
    assert workspace_values(ws) == {"sekret-value"}


def test_cli_exit_codes(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "nodata"))
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "s.json").write_text('{"brand": "Acme Shoes"}', encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text("fine\nwrite ann@shop.test about acme shoes\n", encoding="utf-8")
    assert cli.main(["report", "check", str(dirty), "--workspace", str(ws)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out == ["2\temail\tann@shop.test", "2\tworkspace_value\tacme shoes"]
    clean = tmp_path / "clean.md"
    clean.write_text("nothing private here\n", encoding="utf-8")
    assert cli.main(["report", "check", str(clean), "--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == "clean"
