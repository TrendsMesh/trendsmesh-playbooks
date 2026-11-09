"""replicate_run: the key comes from the environment, the network is mocked, the key is never shown."""

import json

import pytest

pytestmark = pytest.mark.tools
httpx = pytest.importorskip("httpx")
pytest.importorskip("replicate")

from tm.tools import replicate_run  # noqa: E402

TOKEN = "r8_TEST_secret_token_0123456789abcdef"
PNG = b"\x89PNG\r\n\x1a\n fake image bytes"
FILE = {"id": "file1", "name": "ref image.png", "content_type": "image/png", "size": 10, "etag": "e",
        "checksums": {}, "metadata": {}, "created_at": "2026-11-05T00:00:00Z", "expires_at": None,
        "urls": {"get": "https://api.replicate.com/v1/files/file1"}}


@pytest.fixture
def replicate_api(monkeypatch):
    """Answers Replicate's API and the output download; records every request."""
    seen = []
    polls = {"n": 0}
    broken = {"download": False}

    def handle(self, request):
        seen.append(request)
        url = str(request.url)
        if request.method == "POST" and url.endswith("/v1/files"):
            request.read()  # the upload is streamed: read it so the test can look at it
            return httpx.Response(201, json=FILE, request=request)
        if request.method == "POST" and "/v1/models/" in url and url.endswith("/predictions"):
            return httpx.Response(201, json={"id": "p1", "status": "starting", "model": "openai/gpt-image-2",
                                             "version": "v", "input": {}, "urls": {}}, request=request)
        if request.method == "GET" and url.endswith("/v1/predictions/p1"):
            polls["n"] += 1
            return httpx.Response(200, json={
                "id": "p1", "status": "succeeded", "model": "openai/gpt-image-2", "version": "v",
                "input": {}, "output": ["https://replicate.delivery/abc/out.png"], "error": None,
                "logs": "done", "metrics": {"predict_time": 4.2}, "urls": {}}, request=request)
        if request.method == "GET" and url == "https://replicate.delivery/abc/out.png":
            if broken["download"]:
                raise httpx.ConnectError("connection reset", request=request)
            return httpx.Response(200, content=PNG, request=request)
        return httpx.Response(404, json={"detail": f"unexpected {request.method} {url}"}, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    monkeypatch.setenv("REPLICATE_POLL_INTERVAL", "0")
    handle.seen, handle.broken = seen, broken
    return handle


def _spec(run, tmp_path):
    ref = tmp_path / "ref image.png"
    ref.write_bytes(PNG)
    spec = run.path / "03_wip" / "hook card.json"
    spec.write_text(json.dumps({"model": "openai/gpt-image-2",
                                "input": {"prompt": "A snowy street, 4:5", "image": str(ref)}}))
    return spec


def test_replicate_run_reads_key_from_env_never_prints(run, tmp_path, monkeypatch, capsys, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    spec = _spec(run, tmp_path)
    code = replicate_run.main(["--run", str(run.path), str(spec), "--name", "hook", "--cost", "0.04", "--json"])
    assert code == 0
    auth = {r.headers.get("authorization") for r in replicate_api.seen if "api.replicate.com" in str(r.url)}
    assert auth == {f"Bearer {TOKEN}"}  # the key from the environment, on every API call
    out = run.path / "03_wip" / "hook_v01_0.png"
    assert out.read_bytes() == PNG
    record = json.loads((run.path / "03_wip" / "hook_v01.run.json").read_text(encoding="utf-8"))
    assert record["prediction_id"] == "p1" and record["outputs"] == ["hook_v01_0.png"]
    printed = capsys.readouterr()
    assert TOKEN not in printed.out + printed.err
    for f in run.path.rglob("*"):
        if f.is_file():
            assert TOKEN.encode() not in f.read_bytes(), f
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "03_wip/hook_v01_0.png" in manifest and "openai/gpt-image-2" in manifest
    assert "0.04 USD" in manifest and "03_wip/hook_v01.run.json" in manifest
    assert (run.path / "03_wip" / "hook_v01_0.png.response.json").is_file()
    assert (run.path / "03_wip" / "hook_v01_0.png.prompt.txt").read_text() == "A snowy street, 4:5"


def test_missing_key_stops(run, tmp_path, monkeypatch, capsys, replicate_api):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path))]) == 2
    assert replicate_api.seen == []
    assert "Replicate" in capsys.readouterr().out


def test_failed_prediction_is_an_error_without_the_key(run, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    monkeypatch.setenv("REPLICATE_POLL_INTERVAL", "0")

    def handle(self, request):
        if request.method == "POST" and "/predictions" in str(request.url):
            return httpx.Response(201, json={"id": "p2", "model": "openai/gpt-image-2", "status": "failed",
                                             "error": f"bad token {TOKEN}",
                                             "input": {}, "urls": {}, "version": "v"}, request=request)
        return httpx.Response(201, json=FILE, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path))]) == 1
    printed = capsys.readouterr()
    assert "failed" in printed.out and TOKEN not in printed.out + printed.err


def _record_of(run):
    return json.loads(next((run.path / "03_wip").glob("*.run.json")).read_text(encoding="utf-8"))


@pytest.mark.parametrize("status", ["failed", "canceled"])
def test_failed_prediction_reports_zero_cost(run, tmp_path, monkeypatch, capsys, replicate_api, status):
    """Decision 8 (HANDOFF §4, "failed validations cost $0"): no output, $0, and the record says to confirm it."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    original = httpx.HTTPTransport.handle_request

    def failed(self, request):
        if request.method == "GET" and str(request.url).endswith("/v1/predictions/p1"):
            return httpx.Response(200, json={"id": "p1", "status": status, "model": "minimax/h3", "version": "v",
                                             "input": {}, "output": None, "error": "E006: first frame with references",
                                             "urls": {}}, request=request)
        return original(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", failed)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--name", "take",
                               "--cost", "1.2", "--json"]) == 1
    assert json.loads(report.read_text()) == {"spent": True, "actual": 0.0}
    record = _record_of(run)
    assert record["status"] == status and record["prediction_id"] == "p1"
    assert record["cost_note"] == "failed before any output: $0 expected; confirm on the Replicate dashboard"
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == "error" and "confirm on the Replicate dashboard" in out["message"]


def test_failed_prediction_with_an_output_keeps_the_estimate(run, tmp_path, monkeypatch, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    original = httpx.HTTPTransport.handle_request

    def failed(self, request):
        if request.method == "GET" and str(request.url).endswith("/v1/predictions/p1"):
            return httpx.Response(200, json={"id": "p1", "status": "failed", "model": "m", "version": "v", "input": {},
                                             "output": ["https://replicate.delivery/abc/out.png"], "error": "late",
                                             "urls": {}}, request=request)
        return original(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", failed)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--cost", "1.2"]) == 1
    assert json.loads(report.read_text()) == {"spent": True, "actual": None}
    assert "cost_note" not in _record_of(run)


def test_refused_at_creation_has_cost_note(run, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))

    def handle(self, request):
        if request.method == "POST" and str(request.url).endswith("/predictions"):
            return httpx.Response(422, json={"title": "Invalid input", "detail": "E006", "status": 422}, request=request)
        return httpx.Response(201, json=FILE, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--cost", "1.2", "--json"]) == 1
    assert json.loads(report.read_text()) == {"spent": False, "actual": None}   # nothing spent, as before
    record = _record_of(run)
    assert record["status"] == "refused" and record["prediction_id"] is None
    assert record["cost_note"] == "failed before any output: $0 expected; confirm on the Replicate dashboard"
    assert "Nothing was spent" in json.loads(capsys.readouterr().out)["message"]


def _creates(seen):
    return [r for r in seen if r.method == "POST" and str(r.url).endswith("/predictions")]


def test_failed_download_keeps_the_paid_prediction_and_resume_does_not_pay_again(
        run, tmp_path, monkeypatch, capsys, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    replicate_api.broken["download"] = True
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--name", "hook",
                               "--cost", "0.04", "--json"]) == 1
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == "error" and "--resume 03_wip/hook_v01.run.json" in out["message"]
    record = json.loads((run.path / "03_wip" / "hook_v01.run.json").read_text(encoding="utf-8"))
    assert record["prediction_id"] == "p1" and record["status"] == "succeeded"
    assert record["output"] == ["https://replicate.delivery/abc/out.png"] and record["outputs"] == []
    assert not list((run.path / "03_wip").glob("hook_v01_0*"))
    assert len(_creates(replicate_api.seen)) == 1

    replicate_api.broken["download"] = False
    assert replicate_run.main(["--run", str(run.path), "--resume", "03_wip/hook_v01.run.json", "--json"]) == 0
    assert (run.path / "03_wip" / "hook_v01_0.png").read_bytes() == PNG
    assert len(_creates(replicate_api.seen)) == 1  # the same prediction, not a second paid one
    assert "03_wip/hook_v01_0.png" in (run.path / "manifest.md").read_text(encoding="utf-8")


def test_a_name_in_use_is_refused_before_paying(run, tmp_path, monkeypatch, capsys, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    (run.path / "03_wip" / "hook_v01_0.png").write_bytes(b"older")
    with pytest.raises(replicate_run.c.ToolError, match="already used"):
        replicate_run.run(_spec(run, tmp_path), run.path / "03_wip", "hook_v01")
    assert replicate_api.seen == [] and (run.path / "03_wip" / "hook_v01_0.png").read_bytes() == b"older"


def test_text_output_is_kept_and_refused(run, tmp_path, monkeypatch, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    original = httpx.HTTPTransport.handle_request

    def text_answer(self, request):
        if request.method == "GET" and str(request.url).endswith("/v1/predictions/p1"):
            return httpx.Response(200, json={"id": "p1", "status": "succeeded", "model": "m", "version": "v",
                                             "input": {}, "output": "just words", "urls": {}}, request=request)
        return original(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", text_answer)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--cost", "0.01"]) == 1
    record = json.loads(next((run.path / "03_wip").glob("*.run.json")).read_text(encoding="utf-8"))
    assert record["output"] == "just words" and record["outputs"] == []


@pytest.mark.parametrize("value", ["", "   ", "/etc/passwd.run.json", "../other/x_v01.run.json",
                                   "03_wip/../../x.run.json", "03_wip/nothing_v01.run.json"])
def test_resume_must_be_a_record_inside_the_run(run, monkeypatch, capsys, replicate_api, value):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    assert replicate_run.main(["--run", str(run.path), "--resume", value, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert replicate_api.seen == []


def test_an_empty_resume_does_not_run_the_spec(run, tmp_path, monkeypatch, replicate_api):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    assert replicate_run.main(["--run", str(run.path), str(_spec(run, tmp_path)), "--resume", "",
                               "--cost", "0.04"]) == 1
    assert _creates(replicate_api.seen) == []


def test_veo_last_frame_local_file_is_sent_as_file(run, tmp_path, monkeypatch, replicate_api):
    """Method E's bridge clip: a first and a last frame on disk go out as files (data URIs), like any input."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    first, last = tmp_path / "first frame.png", tmp_path / "last frame.png"
    first.write_bytes(PNG)
    last.write_bytes(PNG + b" last")
    spec = run.path / "03_wip" / "bridge.json"
    spec.write_text(json.dumps({"model": "google/veo-3.1", "file_encoding": "base64",
                                "input": {"prompt": "the same room, a second later", "image": str(first),
                                          "last_frame": str(last)}}))
    assert replicate_api and replicate_run.main(["--run", str(run.path), str(spec), "--name", "bridge",
                                                 "--cost", "1.2", "--json"]) == 0
    post = next(r for r in replicate_api.seen if r.method == "POST" and str(r.url).endswith("/predictions"))
    sent = json.loads(post.content)["input"]
    # Both frames left the machine as files, never as local path strings. (For an official model the
    # replicate library ignores file_encoding and uses its Files API, so these are file URLs; a
    # pinned owner/name:version gets data URIs. Either way the two frames are sent as files.)
    uploads = [r for r in replicate_api.seen if r.method == "POST" and str(r.url).endswith("/v1/files")]
    assert len(uploads) == 2 and PNG in uploads[0].content and PNG + b" last" in uploads[1].content
    for key in ("image", "last_frame"):
        assert sent[key].startswith(("https://api.replicate.com/v1/files/", "data:image/png;base64,"))
        assert str(tmp_path) not in sent[key]
    assert sent["prompt"] == "the same room, a second later"


def test_a_run_relative_spec_is_read_from_the_workspace(run, tmp_path, monkeypatch, replicate_api):
    """PR C review I3: the skills name a spec run-relative from the workspace (03_wip/<item>_vNN.json); a spec that
    is not in the working folder is the run's own, as the organic guard reads it. A path that is there is read as
    given (refresh-ad unchanged)."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    _spec(run, tmp_path)
    monkeypatch.chdir(tmp_path)                                   # not the run folder
    assert replicate_run.main(["--run", str(run.path), "03_wip/hook card.json", "--name", "hook",
                               "--cost", "0.04"]) == 0
    record = json.loads((run.path / "03_wip" / "hook_v01.run.json").read_text(encoding="utf-8"))
    assert record["model"] == "openai/gpt-image-2" and record["outputs"] == ["hook_v01_0.png"]
