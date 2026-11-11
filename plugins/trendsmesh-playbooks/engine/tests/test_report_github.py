import json
import os
import stat
import sys

import pytest

from tm import cli
from tm.report import github

FAKE = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("FAKE_GH_AUTH", "0")))
if args[:2] == ["issue", "create"]:
    mode = os.environ.get("FAKE_GH_CREATE", "ok")
    if "--label" in args and mode == "label_refused":
        sys.stderr.write("could not add label: 'bug' not found\\n")
        sys.exit(1)
    if mode == "boom":
        sys.stderr.write("first line\\nHTTP 500: server error\\n")
        sys.exit(1)
    if mode == "no_url":
        print("done")
        sys.exit(0)
    print("Creating issue in TrendsMesh/trendsmesh-playbooks")
    print("")
    print("https://github.com/TrendsMesh/trendsmesh-playbooks/issues/7")
    sys.exit(0)
sys.exit(2)
"""


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "gh.log"
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_GH_LOG", str(log))

    def calls():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return calls


@pytest.fixture
def body(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("The export button does nothing.\n", encoding="utf-8")
    return p


def creates(calls):
    return [c for c in calls() if c[:2] == ["issue", "create"]]


def test_filed_with_label(fake_gh, body):
    out = github(body, "bug", "Export fails")
    assert out == {"outcome": "filed", "url": "https://github.com/TrendsMesh/trendsmesh-playbooks/issues/7"}
    (args,) = creates(fake_gh)
    assert args == ["issue", "create", "-R", "TrendsMesh/trendsmesh-playbooks", "--title", "Export fails",
                    "--body-file", str(body), "--label", "bug"]


def test_change_uses_enhancement(fake_gh, body):
    assert github(body, "change", "Add export")["outcome"] == "filed"
    (args,) = creates(fake_gh)
    assert args[-2:] == ["--label", "enhancement"]


def test_label_refused_retries_without(fake_gh, body, monkeypatch):
    monkeypatch.setenv("FAKE_GH_CREATE", "label_refused")
    out = github(body, "bug", "Export fails")
    assert out["outcome"] == "filed"
    first, second = creates(fake_gh)
    assert "--label" in first and "--label" not in second


def test_other_failure_is_failed_with_last_line(fake_gh, body, monkeypatch):
    monkeypatch.setenv("FAKE_GH_CREATE", "boom")
    out = github(body, "bug", "T")
    assert out == {"outcome": "failed", "reason": "HTTP 500: server error"}
    assert len(creates(fake_gh)) == 1


def test_no_url_is_failed(fake_gh, body, monkeypatch):
    monkeypatch.setenv("FAKE_GH_CREATE", "no_url")
    assert github(body, "bug", "T")["outcome"] == "failed"


def test_signed_out_is_no_gh(fake_gh, body, monkeypatch):
    monkeypatch.setenv("FAKE_GH_AUTH", "1")
    assert github(body, "bug", "T") == {"outcome": "no_gh"}
    assert creates(fake_gh) == []


def test_missing_gh_is_no_gh(tmp_path, body, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert github(body, "bug", "T") == {"outcome": "no_gh"}


def test_refuses_unclean_body(fake_gh, tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("Ask ann@shop.test about act_12345678.\n", encoding="utf-8")
    out = github(p, "bug", "T")
    assert out["outcome"] == "not_clean"
    assert {f["kind"] for f in out["findings"]} == {"email", "account_id"}
    assert fake_gh() == []


def test_refuses_unclean_title(fake_gh, body):
    out = github(body, "bug", "Broken for ann@shop.test")
    assert out["outcome"] == "not_clean" and out["findings"][0]["kind"] == "email"
    assert fake_gh() == []


def test_cli_prints_one_json_line(fake_gh, body, capsys):
    code = cli.main(["report", "github", str(body), "--kind", "bug", "--title", "T"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "filed"


def test_cli_exits_nonzero_unless_filed(fake_gh, body, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GH_AUTH", "1")
    code = cli.main(["report", "github", str(body), "--kind", "change", "--title", "T"])
    assert code == 1
    assert json.loads(capsys.readouterr().out) == {"outcome": "no_gh"}


def test_cli_unreadable_file_exits_2(fake_gh, tmp_path, capsys):
    code = cli.main(["report", "github", str(tmp_path / "nope.md"), "--kind", "bug", "--title", "T"])
    assert code == 2
    assert "Cannot read" in capsys.readouterr().err
