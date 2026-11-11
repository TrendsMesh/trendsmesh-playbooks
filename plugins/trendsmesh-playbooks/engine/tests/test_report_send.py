import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tm import __version__, cli
from tm.report import send


class Fake:
    def __init__(self):
        self.requests = []
        self.status, self.body, self.headers, self.delay = 201, b"{}", {}, 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                fake.requests.append((self.path, dict(self.headers), raw))
                time.sleep(fake.delay)
                try:
                    self.send_response(fake.status)
                    for k, v in fake.headers.items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(fake.body)))
                    self.end_headers()
                    self.wfile.write(fake.body)
                except OSError:
                    pass

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/issue-reports"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, status, payload=None, headers=None, raw=None):
        self.status = status
        self.body = raw if raw is not None else json.dumps(payload).encode()
        self.headers = headers or {}


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.server.shutdown()
    f.server.server_close()


@pytest.fixture
def body(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("The export button does nothing.\n", encoding="utf-8")
    return p


def call(fake, body, **kw):
    args = dict(kind="bug", title="Export fails", contact=None, url=fake.url)
    args.update(kw)
    return send(body, **args)


def test_received(fake, body):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1", "extra": 1}})
    assert call(fake, body) == {"outcome": "received", "reportId": "r1"}


def test_request_matches_contract(fake, body):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1"}})
    call(fake, body)
    path, headers, raw = fake.requests[0]
    sent = json.loads(raw)
    assert path == "/v1/issue-reports"
    assert set(sent) == {"kind", "title", "body", "source", "os"}
    assert sent["kind"] == "bug" and sent["title"] == "Export fails"
    assert sent["body"] == "The export button does nothing.\n"
    assert sent["source"] == {"name": "trendsmesh-playbooks", "version": __version__}
    assert sent["os"] in {"macos", "linux", "windows", "other"}
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == f"trendsmesh-playbooks/{__version__}"


def test_contact_only_when_given(fake, body):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1"}})
    call(fake, body, contact="ann@shop.test")
    assert json.loads(fake.requests[0][2])["contact"] == "ann@shop.test"


@pytest.mark.parametrize("platform,expected", [
    ("darwin", "macos"), ("linux", "linux"), ("linux2", "linux"), ("win32", "windows"),
    ("cygwin", "windows"), ("freebsd13", "other")])
def test_os_mapping(fake, body, monkeypatch, platform, expected):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1"}})
    monkeypatch.setattr(sys, "platform", platform)
    call(fake, body)
    assert json.loads(fake.requests[0][2])["os"] == expected


def test_invalid_names_field(fake, body):
    fake.answer(400, {"ok": False, "error": {"code": "ISSUE_REPORT_INVALID", "data": {"field": "title"}}})
    assert call(fake, body) == {"outcome": "invalid", "field": "title"}


def test_invalid_without_field_or_json(fake, body):
    fake.answer(400, {"ok": False, "error": {"code": "ISSUE_REPORT_INVALID"}})
    assert call(fake, body) == {"outcome": "invalid", "field": None}
    fake.answer(400, raw=b"<html>")
    assert call(fake, body) == {"outcome": "invalid", "field": None}


def test_too_large(fake, body):
    fake.answer(413, raw=b"nope")
    assert call(fake, body) == {"outcome": "too_large"}


def test_rate_limited_reads_retry_after(fake, body):
    fake.answer(429, {"ok": False}, headers={"Retry-After": "120"})
    assert call(fake, body) == {"outcome": "rate_limited", "retryAfter": 120}


def test_rate_limited_without_usable_header(fake, body):
    fake.answer(429, raw=b"x")
    assert call(fake, body) == {"outcome": "rate_limited", "retryAfter": None}
    fake.answer(429, raw=b"x", headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    assert call(fake, body) == {"outcome": "rate_limited", "retryAfter": None}


def test_404_is_unavailable(fake, body):
    fake.answer(404, raw=b"not found")
    assert call(fake, body) == {"outcome": "unavailable", "reason": "404"}


def test_non_json_201_is_unavailable(fake, body):
    fake.answer(201, raw=b"ok")
    out = call(fake, body)
    assert out["outcome"] == "unavailable" and out["reason"]


def test_connection_refused_is_unavailable(fake, body):
    fake.server.shutdown()
    fake.server.server_close()
    out = call(fake, body, timeout=2)
    assert out["outcome"] == "unavailable" and out["reason"]


def test_timeout_is_unavailable(fake, body):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1"}})
    fake.delay = 2
    start = time.monotonic()
    out = call(fake, body, timeout=0.5)
    assert time.monotonic() - start < 1.5
    assert out["outcome"] == "unavailable" and out["reason"]


def test_refuses_unclean_body_without_request(fake, tmp_path):
    p = tmp_path / "d.md"
    p.write_text("ok\nmy account act_12345678\n", encoding="utf-8")
    out = call(fake, p)
    assert out["outcome"] == "not_clean"
    assert out["findings"] == [{"line": 2, "kind": "account_id", "value": "act_12345678"}]
    assert fake.requests == []


def test_refuses_unclean_title_without_request(fake, body):
    out = call(fake, body, title="Broken for ann@shop.test")
    assert out["outcome"] == "not_clean" and out["findings"][0]["kind"] == "email"
    assert fake.requests == []


def test_cli_prints_one_json_line(fake, body, monkeypatch, capsys):
    fake.answer(201, {"ok": True, "data": {"reportId": "r1"}})
    monkeypatch.setenv("TM_REPORT_URL", fake.url)
    code = cli.main(["report", "send", str(body), "--kind", "bug", "--title", "T"])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"outcome": "received", "reportId": "r1"}


def test_cli_exits_nonzero_unless_received(fake, body, monkeypatch, capsys):
    fake.answer(404, raw=b"")
    monkeypatch.setenv("TM_REPORT_URL", fake.url)
    code = cli.main(["report", "send", str(body), "--kind", "change", "--title", "T", "--contact", "a@b.test"])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["outcome"] == "unavailable"
