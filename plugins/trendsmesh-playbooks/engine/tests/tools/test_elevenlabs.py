"""elevenlabs: Voice Isolator, IVC clone, TTS with speed, history search. Network mocked."""

import io
import json
import shutil
import subprocess
import wave

import pytest
import requests

from tm import recut_plan
from tm.tools import elevenlabs
from tm.tools import Tool, TOOLS

KEY = "xi_TEST_secret_key_0123456789abcdef"
MP3 = b"ID3\x04fake isolated voice"


class Api:
    """Fake ElevenLabs: answers by method and path, counts characters like the subscription does."""

    def __init__(self):
        self.calls = []
        self.used = 1000
        self.routes = {}

    def send(self, session, prepared, **kw):
        self.calls.append(prepared)
        path = prepared.path_url.split("?")[0]
        handler = self.routes.get((prepared.method, path))
        if path == "/v1/user/subscription" and handler is None:
            return self._json(prepared, {"character_count": self.used, "character_limit": 500000})
        if handler is None:
            return self._json(prepared, {"detail": "not found"}, 404)
        return handler(prepared)

    @staticmethod
    def _json(prepared, body, status=200, headers=None):
        return Api._raw(prepared, json.dumps(body).encode(), status, {"content-type": "application/json",
                                                                     **(headers or {})})

    @staticmethod
    def _raw(prepared, content, status=200, headers=None):
        r = requests.Response()
        r.status_code, r._content, r.request, r.url = status, content, prepared, prepared.url
        r.headers.update(headers or {})
        return r


@pytest.fixture
def api(monkeypatch):
    fake = Api()
    monkeypatch.setattr(requests.Session, "send", lambda self, prepared, **kw: fake.send(self, prepared, **kw))
    monkeypatch.setenv("ELEVENLABS_API_KEY", KEY)
    return fake


def _no_key_anywhere(run, capsys):
    printed = capsys.readouterr()
    assert KEY not in printed.out + printed.err
    for f in run.path.rglob("*"):
        if f.is_file():
            assert KEY.encode() not in f.read_bytes(), f


def test_elevenlabs_isolate_posts_to_audio_isolation(api, run, tmp_path, capsys):
    def isolate(prepared):
        api.used += 1000  # one minute of audio
        return Api._raw(prepared, MP3, headers={"content-type": "audio/mpeg"})

    api.routes[("POST", "/v1/audio-isolation")] = isolate
    src = tmp_path / "głos z reklamy.wav"
    src.write_bytes(b"RIFF fake wav")
    assert elevenlabs.main(["isolate", "--run", str(run.path), str(src), "--json"]) == 0
    post = next(c for c in api.calls if c.method == "POST")
    assert post.url == "https://api.elevenlabs.io/v1/audio-isolation"
    assert post.headers["xi-api-key"] == KEY
    assert b'name="audio"' in post.body and b"RIFF fake wav" in post.body
    out = run.path / "03_wip" / "isolated_v01.mp3"
    assert out.read_bytes() == MP3
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["credits_used"] == 1000
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "03_wip/isolated_v01.mp3" in manifest and "1000 credits" in manifest
    side = json.loads((out.parent / "isolated_v01.mp3.response.json").read_text(encoding="utf-8"))
    assert side["request"]["url"].endswith("/v1/audio-isolation")
    assert side["response"]["status"] == 200
    _no_key_anywhere(run, capsys)


def test_isolate_function_reports_credits(api, tmp_path):
    api.routes[("POST", "/v1/audio-isolation")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "250"})
    src = tmp_path / "a.wav"
    src.write_bytes(b"x")
    res = elevenlabs.isolate(src, tmp_path / "out.mp3")
    assert res["credits_used"] == 250 and (tmp_path / "out.mp3").read_bytes() == MP3


def test_clone_ivc_returns_voice_id(api, tmp_path):
    def add(prepared):
        api.used += 0
        return Api._json(prepared, {"voice_id": "v123", "requires_verification": False})

    api.routes[("POST", "/v1/voices/add")] = add
    files = []
    for name in ("fragment 1.mp3", "fragment 2.mp3"):
        (tmp_path / name).write_bytes(b"audio " + name.encode())
        files.append(tmp_path / name)
    res = elevenlabs.clone_ivc("Lektor PL1", files)
    assert res["voice_id"] == "v123" and res["credits_used"] == 0
    post = next(c for c in api.calls if c.method == "POST")
    assert post.body.count(b'name="files"') == 2 and b"Lektor PL1" in post.body


def test_tts_sends_speed_and_writes_wav(api, tmp_path):
    pcm = b"\x00\x01" * 4410

    def tts(prepared):
        api.used += 42
        return Api._raw(prepared, pcm, headers={"content-type": "audio/pcm"})

    api.routes[("POST", "/v1/text-to-speech/v123")] = tts
    out = tmp_path / "take 1.wav"
    res = elevenlabs.tts("v123", "Zimowa wyprzedaż już jest", out, speed=1.08, model="eleven_multilingual_v2")
    post = next(c for c in api.calls if c.method == "POST")
    body = json.loads(post.body)
    assert body["voice_settings"]["speed"] == 1.08
    assert body["model_id"] == "eleven_multilingual_v2" and "language_code" not in body
    assert "output_format=pcm_44100" in post.url
    with wave.open(io.BytesIO(out.read_bytes())) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (44100, 1, 4410)
    assert res["credits_used"] == 42


def test_tts_refuses_speed_out_of_range(api, tmp_path):
    with pytest.raises(ValueError, match="0.7"):
        elevenlabs.tts("v123", "x", tmp_path / "t.wav", speed=1.5)
    assert not any(c.method == "POST" for c in api.calls)


def test_history_search_finds_by_text(api):
    pages = [
        {"history": [{"history_item_id": "h1", "voice_id": "v1", "voice_name": "Marek", "model_id": "m",
                      "text": "Zimowa wyprzedaż już jest!", "date_unix": 1, "settings": {"speed": 1.0}},
                     {"history_item_id": "h2", "voice_id": "v2", "voice_name": "Ola", "text": "Inny tekst"}],
         "has_more": True, "last_history_item_id": "h2"},
        {"history": [{"history_item_id": "h3", "voice_id": "v1", "voice_name": "Marek",
                      "text": "zimowa   WYPRZEDAŻ już jest"}], "has_more": False},
    ]
    api.routes[("GET", "/v1/history")] = lambda p: Api._json(p, pages.pop(0))
    found = elevenlabs.history_search("Zimowa wyprzedaż już jest")
    assert [h["history_item_id"] for h in found["items"]] == ["h1", "h3"]
    assert found["credits_used"] == 0
    second = [c for c in api.calls if c.path_url.startswith("/v1/history")][1]
    assert "start_after_history_item_id=h2" in second.url


def test_missing_key_stops(monkeypatch, run, tmp_path, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    (tmp_path / "a.wav").write_bytes(b"x")
    assert elevenlabs.main(["isolate", "--run", str(run.path), str(tmp_path / "a.wav")]) == 2
    assert "ElevenLabs" in capsys.readouterr().out


def test_api_error_never_shows_the_key(api, run, tmp_path, capsys):
    api.routes[("POST", "/v1/audio-isolation")] = lambda p: Api._json(
        p, {"detail": {"status": "quota_exceeded", "message": f"key {KEY} has no credits"}}, 401)
    (tmp_path / "a.wav").write_bytes(b"x")
    assert elevenlabs.main(["isolate", "--run", str(run.path), str(tmp_path / "a.wav")]) == 2
    out = capsys.readouterr().out
    assert "quota_exceeded" in out and KEY not in out


@pytest.mark.parametrize("body", [{"detail": {"type": "authorization_error", "code": "feature_not_available",
                                               "message": "This feature is not available on your current plan."}},
                                   {"detail": "no"}])
def test_plan_without_the_feature_stops_with_a_todo(api, run, tmp_path, capsys, body):
    """#66: a plan refusal (or a 403 we don't recognise, as before) says which plan has the feature."""
    api.routes[("POST", "/v1/voices/add")] = lambda p: Api._json(p, body, 403)
    (tmp_path / "a.mp3").write_bytes(b"x")
    assert elevenlabs.main(["clone-ivc", "--run", str(run.path), "--name", "PL1", str(tmp_path / "a.mp3"),
                            "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "your plan doesn't include the instant voice clone" in out["message"]
    assert "Starter plan" in out["message"] and "https://elevenlabs.io/app/subscription" in out["message"]
    assert "continues from the same place" in out["message"]


# --- issue #66: one message per cause, and what is left before a paid step ---------------------------------------

def _paid_tts(run, *extra):
    return elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v1", "--text", "Cześć", "--cost", "1200",
                            "--json", *extra])


@pytest.mark.parametrize("status,body,says", [
    (401, {"detail": {"type": "authentication_error", "code": "invalid_api_key",
                      "message": "The provided API key is invalid."}},
     ["it is wrong, or it was revoked", "https://elevenlabs.io/app/settings/api-keys", "/plugin"]),
    (401, {"detail": {"status": "missing_permissions",
                      "message": "The API key you used is missing the permission text_to_speech"}},
     ["it is restricted", "Text to Speech", "User (read)"]),
    (403, {"detail": {"code": "insufficient_permissions"}}, ["it is restricted", "Text to Speech"]),
    (402, {"detail": {"type": "payment_required", "code": "insufficient_credits"}},
     ["not enough credits", "This step needed about 1200 credits", "https://elevenlabs.io/app/subscription"]),
    (401, {"detail": {"status": "quota_exceeded",
                      "message": "This request exceeds your quota. You have 3 credits remaining."}},
     ["not enough credits", "1200 credits"]),
    (429, {"detail": {"type": "rate_limit_error", "code": "concurrent_limit_exceeded"}},
     ["too many requests at once", "Wait a minute"]),
    (401, {"detail": "invalid key"}, ["Check the key, the credits and that the plan includes this feature"]),
])
def test_each_refusal_cause_has_its_own_message(api, run, monkeypatch, capsys, status, body, says):
    monkeypatch.setenv("TM_COST_ESTIMATE", "1200")
    api.routes[("POST", "/v1/text-to-speech/v1")] = lambda p: Api._json(p, body, status)
    assert _paid_tts(run) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "Nothing was" in out["message"] and "same place" in out["message"]
    for words in says:
        assert words in out["message"]
    assert not list((run.path / "03_wip").glob("*.mp3"))
    _no_key_anywhere(run, capsys)


@pytest.mark.parametrize("sub,stops", [
    ({"character_count": 9500, "character_limit": 10000}, True),             # 500 left, 1200 needed
    ({"character_count": 9500, "character_limit": 10000, "can_extend_character_limit": True,
      "max_credit_limit_extension": 5000}, False),                            # usage-based billing covers it
    ({"character_count": 9500, "character_limit": 10000, "can_extend_character_limit": True,
      "max_credit_limit_extension": "unlimited"}, False),
    ({"character_count": 1000, "character_limit": 10000}, False),
])
def test_what_is_left_is_checked_before_paying(api, run, monkeypatch, capsys, sub, stops):
    monkeypatch.setenv("TM_COST_ESTIMATE", "1200")
    report = run.path.parent / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, sub)
    api.routes[("POST", "/v1/text-to-speech/v1")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "6"})
    code = _paid_tts(run)
    out = json.loads(capsys.readouterr().out)
    posts = [c for c in api.calls if c.method == "POST"]
    if stops:
        assert code == 2 and posts == []
        assert out["message"].startswith("ElevenLabs has 500 credits left, and the text to speech needs about "
                                         "1200 credits")
        assert "Nothing was sent and nothing was spent" in out["message"]
        assert json.loads(report.read_text()) == {"spent": False, "actual": None}
    else:
        assert code == 0 and len(posts) == 1


def test_no_balance_check_without_an_estimate_or_a_readable_subscription(api, run, monkeypatch, capsys):
    """Called on its own (no `tm tool`, so no estimate), or with a key that may not read the subscription: the call
    goes on as before."""
    api.routes[("POST", "/v1/text-to-speech/v1")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "6"})
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, {"character_count": 10,
                                                                          "character_limit": 10})
    assert _paid_tts(run) == 0
    monkeypatch.setenv("TM_COST_ESTIMATE", "1200")
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(
        p, {"detail": {"status": "missing_permissions"}}, 401)
    assert _paid_tts(run) == 0
    capsys.readouterr()


def test_spend_is_reported_even_when_saving_fails(api, tmp_path, monkeypatch):
    api.routes[("POST", "/v1/audio-isolation")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "300"})
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))

    def broken(args):
        raise OSError("disk full")

    monkeypatch.setattr(elevenlabs.c, "run_ffmpeg", broken)
    (tmp_path / "a.wav").write_bytes(b"x")
    with pytest.raises(OSError):
        elevenlabs.isolate(tmp_path / "a.wav", tmp_path / "isolated.wav")
    assert json.loads(report.read_text()) == {"spent": True, "actual": 300}


def test_a_timeout_after_sending_keeps_the_spend(api, tmp_path, monkeypatch):
    def timeout(prepared):
        raise requests.ReadTimeout("read timed out")

    api.routes[("POST", "/v1/text-to-speech/v1")] = timeout
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    with pytest.raises(elevenlabs.c.ToolError, match="may have been charged"):
        elevenlabs.tts("v1", "x", tmp_path / "t.wav")
    assert json.loads(report.read_text()) == {"spent": True, "actual": None}


def test_no_connection_at_all_spends_nothing(api, tmp_path, monkeypatch):
    def refused(prepared):
        raise requests.ConnectTimeout("connect timed out")

    api.routes[("POST", "/v1/text-to-speech/v1")] = refused
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    with pytest.raises(elevenlabs.c.ToolError, match="Nothing was spent"):
        elevenlabs.tts("v1", "x", tmp_path / "t.wav")
    assert not report.exists()


def test_a_monthly_reset_gives_unknown_credits_not_negative(api, tmp_path):
    def tts(prepared):
        api.used = 10  # the count started again from zero
        return Api._raw(prepared, b"\x00\x00" * 10, headers={"content-type": "audio/pcm"})

    api.routes[("POST", "/v1/text-to-speech/v1")] = tts
    assert elevenlabs.tts("v1", "x", tmp_path / "t.wav")["credits_used"] is None


# Music (method E) --------------------------------------------------------------------------

PLAN = {"chunks": [{"song_id": "song_1", "range": {"start_ms": 0, "end_ms": 10000}},
                   {"text": "[Main Theme]", "duration_ms": 10000, "positive_styles": ["ambient"]}]}
PLAN_MESSAGE = ("Your ElevenLabs plan or key cannot use Music, so nothing was generated and nothing was spent. "
                "Open elevenlabs.io, choose Subscription and pick a plan with Music, then tell Claude. "
                "The run continues from the same place.")


@pytest.fixture
def mp3_bytes(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not on PATH (run the tests through pixi)")
    path = tmp_path / "tone.mp3"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=44100:duration=2", str(path)], check=True)
    return path.read_bytes()


def test_music_upload_sends_extract_plan(api, run, tmp_path, capsys):
    def upload(prepared):
        return Api._json(prepared, {"song_id": "song_1", "composition_plan": PLAN},
                         headers={"character-cost": "700"})

    api.routes[("POST", "/v1/music/upload")] = upload
    src = tmp_path / "ścieżka reklamy.mp3"
    src.write_bytes(b"ID3 the ad's track")
    assert elevenlabs.main(["music-upload", "--run", str(run.path), str(src), "--cost", "700", "--json"]) == 0
    post = next(c for c in api.calls if c.method == "POST")
    assert post.url == "https://api.elevenlabs.io/v1/music/upload"
    assert post.headers["xi-api-key"] == KEY
    assert b'name="file"' in post.body and b"the ad's track" in post.body
    assert b'name="extract_composition_plan"' in post.body and b"music_v2" in post.body
    saved = json.loads((run.path / "03_wip" / "audio" / "music_upload_v01.json").read_text(encoding="utf-8"))
    assert saved == {"song_id": "song_1", "composition_plan": PLAN, "credits_used": 700}
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["song_id"] == "song_1" and result["credits_used"] == 700
    _no_key_anywhere(run, capsys)


def _plan_file(run):
    path = run.path / "03_wip" / "audio" / "plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(PLAN), encoding="utf-8")
    return path


def test_music_compose_writes_take_and_length(api, run, mp3_bytes, capsys):
    def compose(prepared):
        return Api._raw(prepared, mp3_bytes, headers={"content-type": "audio/mpeg", "character-cost": "5000",
                                                      "history-item-id": "h9"})

    api.routes[("POST", "/v1/music")] = compose
    plan = _plan_file(run)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(plan), "--cost", "5000",
                            "--json"]) == 0
    post = next(c for c in api.calls if c.method == "POST")
    assert post.url == ("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192")
    assert post.headers["xi-api-key"] == KEY
    body = json.loads(post.body)
    assert body["composition_plan"] == PLAN and body["model_id"] == "music_v2_5"
    take = run.path / "03_wip" / "audio" / "music_take_v01.mp3"
    assert take.read_bytes() == mp3_bytes
    rec = json.loads((take.parent / "music_take_v01.mp3.json").read_text(encoding="utf-8"))
    assert rec["kind"] == "music_take" and rec["file"] == "music_take_v01.mp3"
    assert rec["model"] == "music_v2_5" and rec["plan"] == PLAN and rec["credits_used"] == 5000
    assert 1.8 < rec["length_s"] < 2.3  # measured from the saved file
    found, skipped = recut_plan.takes(run)  # the reader of `tm recut music` accepts it as written
    assert skipped == [] and [t["file"] for t in found] == ["03_wip/audio/music_take_v01.mp3"]
    assert found[0]["length_s"] == rec["length_s"] and found[0]["credits_used"] == 5000
    # a second take gets the next version, nothing is overwritten
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(plan), "--cost", "5000"]) == 0
    assert (take.parent / "music_take_v02.mp3").is_file() and take.read_bytes() == mp3_bytes
    _no_key_anywhere(run, capsys)


@pytest.mark.parametrize("status,body", [(401, {"detail": "no"}), (403, {"detail": "no"}),
                                         (403, {"detail": {"code": "feature_not_available"}})])
def test_music_402_stops_with_plan_message(api, run, status, body, capsys):
    """A plan refusal, or a 401 or 403 we don't recognise, on Music is the plan message, as before."""
    api.routes[("POST", "/v1/music")] = lambda p: Api._json(p, body, status)
    plan = _plan_file(run)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(plan), "--cost", "5000",
                            "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and out["message"] == PLAN_MESSAGE
    assert not list((run.path / "03_wip" / "audio").glob("music_take*"))


def test_music_without_credits_says_credits_not_plan(api, run, monkeypatch, capsys):
    """#66: no credits on a Music call is the credits message with this take's estimate, not "pick a plan"."""
    monkeypatch.setenv("TM_COST_ESTIMATE", "5000")
    api.routes[("POST", "/v1/music")] = lambda p: Api._json(
        p, {"detail": {"type": "payment_required", "code": "insufficient_credits"}}, 402)
    plan = _plan_file(run)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(plan), "--cost", "5000",
                            "--json"]) == 2
    message = json.loads(capsys.readouterr().out)["message"]
    assert "not enough credits for the music take" in message and "5000 credits" in message


def test_music_upload_403_stops_with_plan_message(api, run, tmp_path, capsys):
    api.routes[("POST", "/v1/music/upload")] = lambda p: Api._json(p, {"detail": "no"}, 403)
    src = tmp_path / "a.mp3"
    src.write_bytes(b"x")
    assert elevenlabs.main(["music-upload", "--run", str(run.path), str(src), "--cost", "1", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["message"] == PLAN_MESSAGE


def test_compose_resume_is_free(api, run, mp3_bytes, capsys, monkeypatch):
    """The take was paid but not saved: --resume fetches it from the history, with no --cost and no spend."""
    api.routes[("POST", "/v1/music")] = lambda p: Api._raw(
        p, mp3_bytes, headers={"character-cost": "5000", "history-item-id": "h9"})
    api.routes[("GET", "/v1/history/h9/audio")] = lambda p: Api._raw(p, mp3_bytes, headers={"content-type": "audio/mpeg"})
    plan = _plan_file(run)
    real = elevenlabs.Path.write_bytes

    def broken(self, data):  # the disk fails on the take only
        if self.name.startswith("music_take_v01.mp3"):
            raise OSError("disk full")
        return real(self, data)

    monkeypatch.setattr(elevenlabs.Path, "write_bytes", broken)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(plan), "--cost", "5000",
                            "--json"]) == 1
    monkeypatch.setattr(elevenlabs.Path, "write_bytes", real)
    audio = run.path / "03_wip" / "audio"
    pending = audio / "music_take_v01.mp3.json"
    assert not (audio / "music_take_v01.mp3").exists()
    assert json.loads(pending.read_text(encoding="utf-8"))["kind"] != "music_take"  # not a take yet
    report = run.path.parent / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    api.calls.clear()
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--resume",
                            "03_wip/audio/music_take_v01.mp3.json", "--json"]) == 0
    assert not any(c.method == "POST" for c in api.calls)  # nothing generated again
    assert json.loads(report.read_text()) == {"spent": False, "actual": None}
    rec = json.loads(pending.read_text(encoding="utf-8"))
    assert rec["kind"] == "music_take" and rec["credits_used"] == 5000 and rec["length_s"] > 1.5
    assert (audio / "music_take_v01.mp3").read_bytes() == mp3_bytes
    assert recut_plan.takes(run)[0][0]["file"] == "03_wip/audio/music_take_v01.mp3"


def test_music_is_paid_and_resume_is_free_in_the_engine_guard():
    tool = TOOLS["elevenlabs"]
    assert tool.kind_for(["music-upload", "--run", "r", "a.mp3"]) == "voice_credits"
    assert tool.kind_for(["music-compose", "--run", "r", "--plan", "p.json"]) == "voice_credits"
    assert tool.kind_for(["music-compose", "--run", "r", "--resume", "03_wip/audio/x.mp3.json"]) is None
    assert tool.kind_for(["history-search", "--run", "r", "x"]) is None


def _pending(run, plan=PLAN, **over):
    audio = run.path / "03_wip" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    rec = {"kind": "music_pending", "file": "music_take_v01.mp3", "history_item_id": "h9", "model": "music_v2_5",
           "plan": plan, "format": "mp3_44100_192", "credits_used": 5000, **over}
    (audio / "music_take_v01.mp3.json").write_text(json.dumps(rec), encoding="utf-8")
    return audio


def test_resume_replaces_a_truncated_take(api, run, mp3_bytes):
    audio = _pending(run)
    (audio / "music_take_v01.mp3").write_bytes(mp3_bytes[:100])  # a partial write left this behind
    api.routes[("GET", "/v1/history/h9/audio")] = lambda p: Api._raw(p, mp3_bytes)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--resume",
                            "03_wip/audio/music_take_v01.mp3.json"]) == 0
    assert any(c.method == "GET" and "/v1/history/h9/audio" in c.url for c in api.calls)
    assert (audio / "music_take_v01.mp3").read_bytes() == mp3_bytes
    assert not list(audio.glob("*.part"))
    assert json.loads((audio / "music_take_v01.mp3.json").read_text())["kind"] == "music_take"


def test_a_take_is_written_whole_or_not_at_all(api, run, mp3_bytes, monkeypatch):
    api.routes[("POST", "/v1/music")] = lambda p: Api._raw(p, mp3_bytes, headers={"character-cost": "5"})
    real = elevenlabs.os.replace

    def crash(src, dst):
        raise OSError("crash before the move")

    monkeypatch.setattr(elevenlabs.os, "replace", crash)
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5"]) == 1
    monkeypatch.setattr(elevenlabs.os, "replace", real)
    assert not (run.path / "03_wip" / "audio" / "music_take_v01.mp3").exists()


@pytest.mark.parametrize("delta", [0, -5])
def test_no_header_and_a_zero_delta_is_unknown_not_free(api, run, mp3_bytes, tmp_path, monkeypatch, delta):
    def compose(prepared):
        api.used += delta
        return Api._raw(prepared, mp3_bytes)

    api.routes[("POST", "/v1/music")] = compose
    report = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(report))
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5000"]) == 0
    assert json.loads(report.read_text()) == {"spent": True, "actual": None}
    rec = json.loads((run.path / "03_wip" / "audio" / "music_take_v01.mp3.json").read_text())
    assert rec["credits_used"] is None


def test_upload_zero_delta_is_unknown_too(api, run, tmp_path):
    api.routes[("POST", "/v1/music/upload")] = lambda p: Api._json(p, {"song_id": "s", "composition_plan": PLAN})
    src = tmp_path / "a.mp3"
    src.write_bytes(b"x")
    assert elevenlabs.main(["music-upload", "--run", str(run.path), str(src), "--cost", "9"]) == 0
    saved = json.loads((run.path / "03_wip" / "audio" / "music_upload_v01.json").read_text())
    assert saved["credits_used"] is None


@pytest.mark.parametrize("over", [{"model": None}, {"plan": None}, {"file": None}, {"file": "../x.mp3"},
                                  {"file": "sub/x.mp3"}])
def test_resume_of_a_bad_record_is_an_error_not_a_crash(api, run, over, capsys):
    _pending(run, **{k: v for k, v in over.items()})
    rec_path = run.path / "03_wip" / "audio" / "music_take_v01.mp3.json"
    rec = json.loads(rec_path.read_text())
    for k, v in over.items():
        if v is None:
            rec.pop(k)
    rec_path.write_text(json.dumps(rec))
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--resume",
                            "03_wip/audio/music_take_v01.mp3.json", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert not any(c.method == "GET" and "history" in c.url for c in api.calls)


def test_compose_out_must_be_mp3(api, run, capsys):
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5", "--out", "03_wip/audio/take.wav", "--json"]) == 1
    assert ".mp3" in json.loads(capsys.readouterr().out)["message"]
    assert not any(c.method == "POST" for c in api.calls)


@pytest.mark.parametrize("args", [["music-compose", "--resume", ""], ["music-upload", "--resume", "X"],
                                  ["--resume", "X", "music-compose"], ["music-compose", "--resume", "  "]])
def test_adversarial_resume_is_paid(args):
    assert TOOLS["elevenlabs"].kind_for(args) == "voice_credits"


# --- PR B fix wave --------------------------------------------------------------------------

@pytest.mark.parametrize("out", ["03_wip/take_v01.mp3", "04_final/take.mp3", "03_wip/audio/../take.mp3"])
def test_compose_out_must_be_in_the_audio_folder(api, run, out, capsys):
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5", "--out", out, "--json"]) == 1
    assert "03_wip/audio/" in json.loads(capsys.readouterr().out)["message"]
    assert not any(c.method == "POST" for c in api.calls)


def test_compose_in_the_audio_folder_is_fine(api, run, mp3_bytes):
    api.routes[("POST", "/v1/music")] = lambda p: Api._raw(p, mp3_bytes, headers={"character-cost": "5"})
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5", "--out", "03_wip/audio/R1 muzyka.mp3"]) == 0
    assert recut_plan.takes(run)[0][0]["file"] == "03_wip/audio/R1 muzyka.mp3"


def test_compose_onto_a_pending_take_names_its_resume(api, run, capsys):
    _pending(run)  # paid, but the mp3 was never saved
    assert elevenlabs.main(["music-compose", "--run", str(run.path), "--plan", str(_plan_file(run)),
                            "--cost", "5", "--json"]) == 1
    message = json.loads(capsys.readouterr().out)["message"]
    assert "--resume 03_wip/audio/music_take_v01.mp3.json" in message and "Nothing was sent" in message
    assert not any(c.method == "POST" for c in api.calls)


def test_credits_reads_the_subscription_and_is_free(api, run, capsys):
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(
        p, {"tier": "creator", "character_count": 1200, "character_limit": 100000,
            "next_character_count_reset_unix": 1796000000, "status": "active"})
    assert elevenlabs.credits() == {"tier": "creator", "character_count": 1200, "character_limit": 100000,
                                    "next_character_count_reset_unix": 1796000000, "instant_cloning": None}
    capsys.readouterr()
    assert elevenlabs.main(["credits", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "done", "tool": "elevenlabs credits", "tier": "creator", "character_count": 1200,
                   "character_limit": 100000, "next_character_count_reset_unix": 1796000000,
                   "instant_cloning": None, "left": 98800}
    assert elevenlabs.main(["credits", "--run", str(run.path)]) == 0
    assert capsys.readouterr().out.strip() == "ElevenLabs plan creator: 1200 of 100000 credits used, 98800 left."
    assert not any(c.method == "POST" for c in api.calls)
    assert KEY not in json.dumps(out)


@pytest.mark.parametrize("given,read", [(True, True), (False, False), ("yes", None), (None, None)])
def test_credits_reads_whether_the_plan_includes_instant_cloning(api, run, capsys, given, read):
    """#5: refresh-ad's V3 reads the plan from the key instead of asking the user; only a real true or false
    counts, anything else is unknown (None) and the user is asked."""
    body = {"tier": "starter", "character_count": 0, "character_limit": 30000}
    if given is not None:
        body["can_use_instant_voice_cloning"] = given
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, body)
    assert elevenlabs.credits()["instant_cloning"] is read
    assert elevenlabs.main(["credits", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()


def test_credits_stops_when_the_key_is_refused_and_errors_on_a_strange_answer(api, run, capsys):
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, {"detail": "invalid key"}, 401)
    assert elevenlabs.main(["credits", "--run", str(run.path), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, {"tier": "free"})
    assert elevenlabs.main(["credits", "--run", str(run.path), "--json"]) == 1


@pytest.mark.parametrize("body,said,left", [
    ({"character_count": 10, "character_limit": 10000}, "ElevenLabs account: 10 of 10000 credits used, 9990 left.",
     9990),
    ({"tier": "free", "character_count": 10300, "character_limit": 10000},
     "ElevenLabs plan free: 10300 of 10000 credits used, over the limit by 300.", 0)])
def test_credits_line_without_a_tier_or_over_the_limit(api, run, capsys, body, said, left):
    api.routes[("GET", "/v1/user/subscription")] = lambda p: Api._json(p, body)
    capsys.readouterr()
    assert elevenlabs.main(["credits", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["left"] == left
    assert elevenlabs.main(["credits", "--run", str(run.path)]) == 0
    assert capsys.readouterr().out.strip() == said


# --- Task 14: timestamps and voice previews -----------------------------------------------------

import base64  # noqa: E402

from tm import organic_audio  # noqa: E402

LINE = "Co daje dziecku nowa gra"


def _alignment(text, step=0.1):
    return {"characters": list(text),
            "character_start_times_seconds": [round(i * step, 3) for i in range(len(text))],
            "character_end_times_seconds": [round((i + 1) * step, 3) for i in range(len(text))]}


def _stamped(api, audio=MP3, text=LINE, cost="27"):
    api.routes[("POST", "/v1/text-to-speech/v9/with-timestamps")] = lambda p: Api._json(
        p, {"audio_base64": base64.b64encode(audio).decode(), "alignment": _alignment(text),
            "normalized_alignment": _alignment(text)}, headers={"character-cost": cost})


def test_tts_timestamps_words_and_srt(api, run, capsys):
    _stamped(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "27",
                            "--timestamps", "--out", "03_wip/audio/vo.mp3", "--json"]) == 0
    post = next(c for c in api.calls if c.method == "POST")
    assert post.path_url.split("?")[0] == "/v1/text-to-speech/v9/with-timestamps"
    assert json.loads(post.body)["text"] == LINE
    audio = run.path / "03_wip" / "audio"
    assert (audio / "vo.mp3").read_bytes() == MP3  # decoded from audio_base64
    words = json.loads((audio / "vo.words.json").read_text(encoding="utf-8"))
    assert [w["word"] for w in words] == ["Co", "daje", "dziecku", "nowa", "gra"]
    assert set(words[0]) == {"word", "start", "end"} and words[0]["end"] == pytest.approx(0.2)
    word_srt = (audio / "vo.words.srt").read_text(encoding="utf-8")
    assert word_srt.startswith("1\n00:00:00,000 --> 00:00:00,200\nCo\n\n2\n")
    assert word_srt.count(" --> ") == 5 and "\r" not in word_srt
    assert (audio / "vo.phrases.srt").read_text(encoding="utf-8") == organic_audio.to_srt(
        organic_audio.phrases(words))
    assert "Co daje dziecku nowa gra" in (audio / "vo.phrases.srt").read_text(encoding="utf-8")
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["credits_used"] == 27
    assert sorted(result["outputs"]) == sorted(f"03_wip/audio/vo{e}" for e in
                                               (".mp3", ".words.json", ".words.srt", ".phrases.srt"))
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "vo.words.srt" in manifest
    side = (audio / "vo.mp3.response.json").read_text(encoding="utf-8")
    assert "audio_base64" not in side and KEY not in side  # the audio is not copied into the record
    _no_key_anywhere(run, capsys)


def test_tts_without_timestamps_is_unchanged(api, run, capsys):
    api.routes[("POST", "/v1/text-to-speech/v9")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "5"})
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5",
                            "--json"]) == 0
    assert not any("with-timestamps" in c.url for c in api.calls)
    assert not list((run.path / "03_wip").rglob("*.words.*"))


def test_timestamps_refuses_sidecars_that_exist_before_paying(api, run, capsys):
    _stamped(api)
    audio = run.path / "03_wip" / "audio"
    audio.mkdir(parents=True)
    (audio / "vo.words.srt").write_text("mine", encoding="utf-8")
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "27",
                            "--timestamps", "--out", "03_wip/audio/vo.mp3", "--json"]) == 1
    assert "already exists" in json.loads(capsys.readouterr().out)["message"]
    assert not any(c.method == "POST" for c in api.calls)
    assert (audio / "vo.words.srt").read_text(encoding="utf-8") == "mine"


def _voices(api, language_seen=None):
    def shared(prepared):
        if language_seen is not None:
            language_seen.append(prepared.url)
        return Api._json(prepared, {"voices": [
            {"voice_id": "abcdefgh12345", "name": "Asia Łukasz", "gender": "female", "age": "young",
             "accent": "standard", "use_case": "narrative_story", "description": "calm",
             "preview_url": "https://storage.example.com/previews/asia.mp3"},
            {"voice_id": "zzzzzzzz9", "name": "No preview", "preview_url": None}], "has_more": False})

    api.routes[("GET", "/v1/shared-voices")] = shared
    api.routes[("GET", "/previews/asia.mp3")] = lambda p: Api._raw(p, MP3, headers={"content-type": "audio/mpeg"})


def test_voices_search_free_saves_previews(api, run, capsys):
    _voices(api)
    assert TOOLS["elevenlabs"].kind_for(["voices"]) is None  # free: no --cost, no budget
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "calm narrator", "--language", "pl",
                            "--gender", "female", "--limit", "5", "--json"]) == 0
    folder = run.path / "02_research" / "voices" / "calm-narrator"
    saved = json.loads((folder / "search_v01.json").read_text(encoding="utf-8"))
    assert [v["voice_id"] for v in saved["voices"]] == ["abcdefgh12345", "zzzzzzzz9"]
    assert (folder / "preview_Asia_Łukasz_abcdefgh.mp3").read_bytes() == MP3
    assert len(list(folder.glob("preview_*.mp3"))) == 1
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["voices"][0]["preview_file"].endswith("preview_Asia_Łukasz_abcdefgh.mp3")
    assert result["voices"][1]["preview_file"] is None
    get = next(c for c in api.calls if c.path_url.startswith("/v1/shared-voices"))
    assert "search=calm+narrator" in get.url and "gender=female" in get.url and "page_size=5" in get.url
    assert not any(c.method == "POST" for c in api.calls)
    preview = next(c for c in api.calls if c.path_url == "/previews/asia.mp3")
    assert "xi-api-key" not in preview.headers  # the key never goes to a preview address
    # a second search is a new version, and earlier files are kept
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "calm narrator", "--language", "pl"]) == 0
    assert (folder / "search_v02.json").is_file() and (folder / "search_v01.json").is_file()


@pytest.mark.parametrize("language", ["pl", "en", "de"])
def test_voices_language_from_argument(api, run, language):
    seen = []
    _voices(api, seen)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "x", "--language", language]) == 0
    assert f"language={language}" in seen[0]


def test_voices_needs_a_language(api, run):
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "x"]) == 1
    assert not any(c.method == "GET" and "shared-voices" in c.url for c in api.calls)


# --- the PR C fix wave (Task 14 review M2-M5) ----------------------------------------------------

from tm import manifest  # noqa: E402


def _tts(run, *extra, out="03_wip/audio/vo.mp3"):
    return elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "27",
                            "--out", out, *extra, "--json"])


def _params(run, file):
    row = next(r for r in manifest.rows(run) if r["file"] == file)
    return json.loads(row["params"])


def test_timestamps_is_a_paid_tts_and_its_param_only_when_set(api, run, capsys):
    """M3, M4: tts --timestamps is the same voice_credits spend; a plain take's manifest params are as before
    (no timestamps key), a timed one says timestamps: true."""
    assert TOOLS["elevenlabs"].kind_for(["tts", "--timestamps"]) == "voice_credits"
    assert TOOLS["elevenlabs"].kind_for(["tts"]) == "voice_credits"
    api.routes[("POST", "/v1/text-to-speech/v9")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "5"})
    assert _tts(run, out="03_wip/audio/plain.mp3") == 0
    assert _params(run, "03_wip/audio/plain.mp3") == {"voice_id": "v9", "speed": 1.0, "settings": None}
    _stamped(api)
    assert _tts(run, "--timestamps") == 0
    assert _params(run, "03_wip/audio/vo.mp3")["timestamps"] is True


def test_timestamps_fall_back_to_the_normalized_alignment(api, run, capsys):
    """M3: an answer with only `normalized_alignment` still gives the word times."""
    api.routes[("POST", "/v1/text-to-speech/v9/with-timestamps")] = lambda p: Api._json(
        p, {"audio_base64": base64.b64encode(MP3).decode(), "alignment": None,
            "normalized_alignment": _alignment(LINE)}, headers={"character-cost": "27"})
    assert _tts(run, "--timestamps") == 0
    words = json.loads((run.path / "03_wip" / "audio" / "vo.words.json").read_text(encoding="utf-8"))
    assert [w["word"] for w in words] == ["Co", "daje", "dziecku", "nowa", "gra"]


def test_timestamps_without_an_alignment_keep_the_take_and_say_so(api, run, capsys):
    """M3: no alignment at all: the paid take is saved and recorded, the tool exits 1 and writes no word times."""
    api.routes[("POST", "/v1/text-to-speech/v9/with-timestamps")] = lambda p: Api._json(
        p, {"audio_base64": base64.b64encode(MP3).decode()}, headers={"character-cost": "27"})
    assert _tts(run, "--timestamps") == 1
    message = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["message"]
    assert "The take is saved to 03_wip/audio/vo.mp3 (27 credits)" in message and "no alignment" in message
    audio = run.path / "03_wip" / "audio"
    assert (audio / "vo.mp3").read_bytes() == MP3 and not list(audio.glob("vo.*.srt"))
    assert not (audio / "vo.words.json").exists()
    assert any(r["file"] == "03_wip/audio/vo.mp3" for r in manifest.rows(run))


@pytest.mark.parametrize("body", [{"audio": "no base64 key"}, ["a", "list"], {"audio_base64": 5}])
def test_timestamps_answer_of_an_unknown_shape_saves_nothing_and_says_it_may_be_charged(api, run, capsys, body):
    """M3: an answer the plugin does not know: no take, a clear error naming the history check."""
    api.routes[("POST", "/v1/text-to-speech/v9/with-timestamps")] = lambda p: Api._json(
        p, body, headers={"character-cost": "27"})
    assert _tts(run, "--timestamps") == 1
    message = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["message"]
    assert "a form this plugin does not know" in message and "ElevenLabs history" in message
    assert not list((run.path / "03_wip").rglob("vo.*"))


def test_timestamps_words_json_is_lf(api, run, capsys):
    """M5: words.json is written with LF, as the two SRT files are (Windows writes CRLF otherwise)."""
    _stamped(api)
    assert _tts(run, "--timestamps") == 0
    for name in ("vo.words.json", "vo.words.srt", "vo.phrases.srt"):
        assert b"\r" not in (run.path / "03_wip" / "audio" / name).read_bytes(), name


def test_voices_failed_preview_download_is_no_file(api, run, capsys):
    """M3: a preview whose download fails (non-200) gives preview_file null and no file."""
    _voices(api)
    api.routes[("GET", "/previews/asia.mp3")] = lambda p: Api._raw(p, b"gone", 404)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "calm", "--language", "pl", "--json"]) == 0
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert [v["preview_file"] for v in result["voices"]] == [None, None]
    assert not list((run.path / "02_research" / "voices" / "calm").glob("preview_*"))


def test_voices_keeps_an_existing_preview(api, run, capsys):
    """M3: a later search keeps the preview already saved: never downloaded again, never overwritten."""
    _voices(api)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "calm", "--language", "pl"]) == 0
    clip = run.path / "02_research" / "voices" / "calm" / "preview_Asia_Łukasz_abcdefgh.mp3"
    clip.write_bytes(b"the first download")
    before = sum(c.path_url == "/previews/asia.mp3" for c in api.calls)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "calm", "--language", "pl", "--json"]) == 0
    assert sum(c.path_url == "/previews/asia.mp3" for c in api.calls) == before
    assert clip.read_bytes() == b"the first download"
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["voices"][0]["preview_file"].endswith("preview_Asia_Łukasz_abcdefgh.mp3")


@pytest.mark.parametrize("query,folder", [("con", "q-con"), ("NUL", "q-NUL"), ("com1", "q-com1"),
                                          ("lpt9", "q-lpt9"), ("console", "console")])
def test_voices_folder_is_never_a_windows_reserved_name(api, run, capsys, query, folder):
    """M2: a query like `con` or `nul` would be a reserved folder name on Windows."""
    _voices(api)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", query, "--language", "pl"]) == 0
    assert (run.path / "02_research" / "voices" / folder / "search_v01.json").is_file()


@pytest.mark.parametrize("limit", ["0", "-3", "101"])
def test_voices_limit_is_1_to_100(api, run, capsys, limit):
    """M2: --limit is checked before any call (the shared library pages at most 100)."""
    _voices(api)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--query", "x", "--language", "pl", "--limit", limit,
                            "--json"]) == 1
    assert "--limit" in json.loads(capsys.readouterr().out.strip().splitlines()[-1])["message"]
    assert not any("shared-voices" in c.url for c in api.calls)


# --- #88: Eleven v4 by default, the market language, the user's own voices --------------------------

def _market(run, lang="pl"):
    (run.path / "config.yaml").write_text(f"languages:\n  working: en\n  market: {lang}\n", encoding="utf-8")


def _plain(api, voice="v9"):
    api.routes[("POST", f"/v1/text-to-speech/{voice}")] = lambda p: Api._raw(p, MP3, headers={"character-cost": "5"})


def _body(api):
    return json.loads(next(c for c in api.calls if c.method == "POST").body)


def test_tts_default_is_v4_in_the_market_language_without_a_speed(api, run, capsys):
    """Point 1: v4 is the default in every playbook. Point 2: the run's market language goes as `language_code`
    (a year or a count read in the wrong case otherwise). v4 has no speed setting, so none is sent."""
    from tm import tts_models

    assert elevenlabs.DEFAULT_MODEL == tts_models.DEFAULT == "eleven_v4"
    _market(run)
    _plain(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5",
                            "--json"]) == 0
    body = _body(api)
    assert body["model_id"] == "eleven_v4" and body["language_code"] == "pl"
    assert "speed" not in body["voice_settings"]
    row = next(r for r in manifest.rows(run) if r["file"] == "03_wip/vo_take_v01.wav")
    assert json.loads(row["params"])["language_code"] == "pl" and row["model"] == "eleven_v4"


def test_tts_language_is_the_region_free_code_and_can_be_given(api, run, capsys):
    _market(run, "pt-BR")
    _plain(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5"]) == 0
    assert _body(api)["language_code"] == "pt"
    api.calls.clear()
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5",
                            "--language", "de"]) == 0
    assert _body(api)["language_code"] == "de"


def test_tts_without_a_market_language_sends_none(api, run, capsys):
    _plain(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5"]) == 0
    assert "language_code" not in _body(api)


def test_multilingual_v2_keeps_the_pace_and_takes_no_language_code(api, run, capsys):
    """Refresh an ad picks v2 to keep the original's pace: it takes a speed, and ElevenLabs does not support
    `language_code` on multilingual_v2, so none is sent."""
    _market(run)
    _plain(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5",
                            "--model", "eleven_multilingual_v2", "--speed", "1.1"]) == 0
    body = _body(api)
    assert body["model_id"] == "eleven_multilingual_v2" and "language_code" not in body
    assert body["voice_settings"]["speed"] == 1.1


def test_a_speed_on_v4_is_refused_before_anything_is_sent(api, run, capsys):
    _plain(api)
    assert elevenlabs.main(["tts", "--run", str(run.path), "--voice-id", "v9", "--text", LINE, "--cost", "5",
                            "--speed", "1.1", "--json"]) == 1
    message = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["message"]
    assert "eleven_v4" in message and "eleven_multilingual_v2" in message
    assert not any(c.method == "POST" for c in api.calls)


def _mine(api, seen=None):
    def own(prepared):
        if seen is not None:
            seen.append(prepared.url)
        return Api._json(prepared, {"voices": [
            {"voice_id": "mine12345678", "name": "Mój lektor", "category": "cloned",
             "labels": {"gender": "male", "age": "middle_aged", "accent": "polish", "use_case": "narration"},
             "description": "the brand voice", "preview_url": "https://storage.example.com/previews/mine.mp3"},
            {"voice_id": "saved9999", "name": "Saved from the library", "category": "professional",
             "labels": {}, "preview_url": None}], "has_more": False, "total_count": 2})

    api.routes[("GET", "/v2/voices")] = own
    api.routes[("GET", "/previews/mine.mp3")] = lambda p: Api._raw(p, MP3, headers={"content-type": "audio/mpeg"})


def test_voices_mine_lists_the_accounts_own_voices_free(api, run, capsys):
    """Point 5: `voices --mine` reads the account's own voices (GET /v2/voices, the premade ones left out), free,
    with no query and no language; the key goes only in the header."""
    seen = []
    _mine(api, seen)
    assert TOOLS["elevenlabs"].kind_for(["voices", "--mine"]) is None
    assert elevenlabs.main(["voices", "--run", str(run.path), "--mine", "--json"]) == 0
    assert "voice_type=non-default" in seen[0] and "page_size=100" in seen[0]
    folder = run.path / "02_research" / "voices" / "mine"
    assert [v["voice_id"] for v in json.loads((folder / "search_v01.json").read_text(encoding="utf-8"))["voices"]] \
        == ["mine12345678", "saved9999"]
    assert (folder / "preview_Mój_lektor_mine1234.mp3").read_bytes() == MP3
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["voices"][0] == {"voice_id": "mine12345678", "name": "Mój lektor", "gender": "male",
                                   "age": "middle_aged", "accent": "polish", "use_case": "narration",
                                   "category": "cloned", "description": "the brand voice",
                                   "preview_file": "02_research/voices/mine/preview_Mój_lektor_mine1234.mp3"}
    assert not any(c.method == "POST" for c in api.calls)
    assert "xi-api-key" not in next(c for c in api.calls if c.path_url == "/previews/mine.mp3").headers
    _no_key_anywhere(run, capsys)


def test_voices_mine_takes_a_query(api, run, capsys):
    seen = []
    _mine(api, seen)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--mine", "--query", "lektor", "--limit", "5"]) == 0
    assert "search=lektor" in seen[0] and "page_size=5" in seen[0]


def test_the_library_search_still_needs_a_query_and_a_language(api, run, capsys):
    _voices(api)
    assert elevenlabs.main(["voices", "--run", str(run.path), "--language", "pl", "--json"]) == 1
    assert "--query" in json.loads(capsys.readouterr().out.strip().splitlines()[-1])["message"]
    assert not api.calls
