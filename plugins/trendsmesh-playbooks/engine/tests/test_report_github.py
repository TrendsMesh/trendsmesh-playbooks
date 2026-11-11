import json
import os
import stat
import subprocess
import sys

import pytest

from tm import cli
import tm.report
from tm.report import github

FAKE = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
import time
stdin = sys.stdin.buffer.read().decode("utf-8") if "-" in args else None
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "stdin": stdin,
                          "env": {k: os.environ.get(k) for k in ("GH_HOST", "GH_REPO", "GH_PROMPT_DISABLED")}}) + "\\n")
time.sleep(float(os.environ.get("FAKE_GH_SLEEP", "0")))
if args[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("FAKE_GH_AUTH", "0")))
if args[:2] == ["issue", "create"]:
    mode = os.environ.get("FAKE_GH_CREATE", "ok")
    if "--label" in args and mode in ("label_refused", "label_then_boom"):
        sys.stderr.write("could not add label: 'bug' not found\\n")
        sys.exit(1)
    if mode == "label_then_boom":
        sys.stderr.write("HTTP 502: bad gateway\\n")
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

    def records():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def calls():
        return [r["args"] for r in records()]

    calls.records = records
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
    assert args == ["issue", "create", "-R", "github.com/TrendsMesh/trendsmesh-playbooks", "--title",
                    "Export fails", "--body-file", "-", "--label", "bug"]


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


def test_auth_checked_on_github_com(fake_gh, body):
    github(body, "bug", "T")
    assert fake_gh()[0] == ["auth", "status", "--hostname", "github.com"]


def test_other_host_and_repo_env_never_reach_gh(fake_gh, body, monkeypatch):
    monkeypatch.setenv("GH_HOST", "enterprise.test")
    monkeypatch.setenv("GH_REPO", "other/repo")
    assert github(body, "bug", "T")["outcome"] == "filed"
    for record in fake_gh.records():
        assert record["env"]["GH_HOST"] is None and record["env"]["GH_REPO"] is None
        assert record["env"]["GH_PROMPT_DISABLED"] == "1"
    (args,) = creates(fake_gh)
    assert args[args.index("-R") + 1] == "github.com/TrendsMesh/trendsmesh-playbooks"


def test_gh_gets_exactly_the_scanned_text(fake_gh, tmp_path):
    p = tmp_path / "draft.md"
    p.write_bytes("\ufeffThe export button does nothing.\nSecond line, caf\u00e9.\n".encode("utf-8"))
    assert github(p, "bug", "T")["outcome"] == "filed"
    (record,) = [r for r in fake_gh.records() if r["args"][:2] == ["issue", "create"]]
    assert record["stdin"] == "The export button does nothing.\nSecond line, caf\u00e9.\n"
    assert str(p) not in record["args"]


def test_auth_timeout_is_no_gh(fake_gh, body, monkeypatch):
    monkeypatch.setattr(tm.report, "_AUTH_TIMEOUT", 0.3)
    monkeypatch.setenv("FAKE_GH_SLEEP", "3")
    assert github(body, "bug", "T") == {"outcome": "no_gh"}
    assert creates(fake_gh) == []


def test_create_timeout_is_failed(fake_gh, body, monkeypatch):
    monkeypatch.setattr(tm.report, "_CREATE_TIMEOUT", 0.3)
    real = subprocess.run

    def run(cmd, **kw):
        if cmd[1:3] == ["issue", "create"]:
            monkeypatch.setenv("FAKE_GH_SLEEP", "3")
            kw["env"] = dict(kw["env"], FAKE_GH_SLEEP="3")
        return real(cmd, **kw)

    monkeypatch.setattr(tm.report.subprocess, "run", run)
    out = github(body, "bug", "T")
    assert out["outcome"] == "failed" and "timed out" in out["reason"]


def test_create_oserror_is_failed(fake_gh, body, monkeypatch):
    real = subprocess.run

    def run(cmd, **kw):
        if cmd[1:3] == ["issue", "create"]:
            raise OSError("exec format error")
        return real(cmd, **kw)

    monkeypatch.setattr(tm.report.subprocess, "run", run)
    out = github(body, "bug", "T")
    assert out["outcome"] == "failed" and "exec format error" in out["reason"]


def test_second_attempt_failure_is_failed(fake_gh, body, monkeypatch):
    monkeypatch.setenv("FAKE_GH_CREATE", "label_then_boom")
    out = github(body, "bug", "T")
    assert out == {"outcome": "failed", "reason": "HTTP 502: bad gateway"}
    assert len(creates(fake_gh)) == 2


def test_cli_title_file(fake_gh, body, tmp_path, capsys):
    title = tmp_path / "title.txt"
    title.write_text("Export can't save\n", encoding="utf-8")
    assert cli.main(["report", "github", str(body), "--kind", "bug", "--title-file", str(title)]) == 0
    (args,) = creates(fake_gh)
    assert args[args.index("--title") + 1] == "Export can't save"
    assert cli.main(["report", "github", str(body), "--kind", "bug", "--title-file", str(tmp_path / "no")]) == 2
    assert "Cannot read" in capsys.readouterr().err
