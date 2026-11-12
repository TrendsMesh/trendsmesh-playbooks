"""ElevenLabs for flow V (VARIANTS.md section 4): Voice Isolator, IVC clone, TTS, history search;
and Music for method E (VARIANTS.md section 3c), the continuation of the ad's own track.

    tm tool elevenlabs isolate --run RUN AUDIO --cost CREDITS [--out PATH] [--json]
    tm tool elevenlabs clone-ivc --run RUN --name NAME FILE [FILE ...] --cost CREDITS [--description TEXT] [--json]
    tm tool elevenlabs tts --run RUN --voice-id ID --text TEXT --cost CREDITS [--speed 1.0]
                           [--model eleven_v4] [--language L] [--settings JSON] [--timestamps] [--out PATH] [--json]
    tm tool elevenlabs voices --run RUN --query Q --language L [--gender G] [--age A] [--accent X]
                           [--use-case U] [--limit 10] [--json]     (free)
    tm tool elevenlabs voices --run RUN --mine [--query Q] [--limit 100] [--json]     (free)
    tm tool elevenlabs history-search --run RUN TEXT [--json]
    tm tool elevenlabs scribe --run RUN MEDIA --cost CREDITS [--language L] [--model scribe_v3] [--out PATH] [--json]
    tm tool elevenlabs sts --run RUN TAKE --voice-id ID --cost CREDITS [--model eleven_multilingual_sts_v2]
                           [--remove-noise] [--settings JSON] [--out PATH] [--json]
    tm tool elevenlabs music-upload --run RUN AUDIO --cost CREDITS [--out PATH] [--json]
    tm tool elevenlabs music-compose --run RUN --plan PLAN.json --cost CREDITS [--model music_v2_5]
                           [--format mp3_44100_192] [--out PATH] [--json]
    tm tool elevenlabs music-compose --run RUN --resume 03_wip/audio/<take>.json [--json]     (free)
    tm tool elevenlabs sound-effect --run RUN --text TEXT --seconds S --cost CREDITS [--influence 0.3]
                           [--out PATH] [--json]
    tm tool elevenlabs credits --run RUN [--json]     (free)

- Voice isolation is always ElevenLabs Voice Isolator, `POST /v1/audio-isolation` (never Demucs,
  which stays for the music track only). The answer is MP3; another `--out` extension is converted
  with ffmpeg.
- The key comes from ELEVENLABS_API_KEY, which the engine sets from the plugin's secrets. It goes
  only into the `xi-api-key` header: never into a file, a message or argv.
- Every call reports `credits_used`: the answer's `character-cost` header when there is one,
  otherwise the change of `character_count` in `/v1/user/subscription` across the call (None if the
  key may not read the subscription).
- tts --timestamps calls `POST /v1/text-to-speech/{voice_id}/with-timestamps` (the same cost and budget),
  decodes `audio_base64` into the take and writes beside it `<stem>.words.json` ([{word, start, end}]),
  `<stem>.words.srt` (one word per cue: what `atlas-prompt --srt` takes) and `<stem>.phrases.srt` (cues closed at
  `, . ? ! …` and at five words). Without it `tts` is as before. The sidecars are never overwritten: if one
  exists the call stops before anything is sent.
- voices --mine lists the voices on the user's own account (`GET /v2/voices`, `voice_type=non-default`: their
  clones, the library voices they saved and their workspace's, without ElevenLabs' premade ones; `search` from
  --query), saved as `02_research/voices/mine/search_vNN.json` with the previews beside it. Free, as the search is.
- voices searches the shared voice library (`GET /v1/shared-voices`, `language` from --language) and saves
  `02_research/voices/<slug(query)>/search_vNN.json` with the free preview clips
  `preview_<name>_<id8>.mp3` beside it. It is free and spends nothing. The key goes only to ElevenLabs,
  never to a preview address.
- tts: `speed` must be 0.7 to 1.2 (ElevenLabs' range; R9: a line that must fit a slot is first
  regenerated shorter or faster, stretching is the last resort). A `.wav` output asks for
  `pcm_44100` (V4: PCM 44.1 kHz takes) and wraps it in a WAV header; other extensions get MP3.
  The model defaults to Eleven v4, `eleven_v4`, in every playbook (#88; `tm.tts_models`); Refresh an ad picks
  `eleven_multilingual_v2` for a line among the original's sentences (it keeps the original's pace). v4 has no
  speed setting: its request sends no `speed`, and a speed other than 1.0 is refused before anything is sent.
  `language_code` is the run's market language (`video_fonts.market_language`, its region left out: `pt-BR` ->
  `pt`), or --language; it is sent to every model but multilingual_v2, which does not support it. `--settings`
  overrides the voice's stored settings for this request; with a clone keep similarity_boost at 0.75 or less.
- scribe (issue #94): Speech to Text, `POST /v1/speech-to-text` (multipart `file`, `model_id` `scribe_v3`,
  `timestamps_granularity=word`, `language_code` the run's market language or --language; no audio events, no
  speakers), read from ElevenLabs' API reference on 2026-11-12. Verbatim word times: it keeps a repeat Whisper hides
  and hears a quiet line Whisper's silence filter drops. Written in the shape of a local transcript, so `tm tool
  take_qa --scribe` and the takes' QA read it as they read Whisper's: `<media dir>/qa/<stem>_scribe_vNN.json` =
  {"source": "scribe", "model", "media" (run-relative), "language", "language_probability", "duration",
  "segments": [{start, end, text, words: [{start, end, word, probability}]}] (a segment ends at . ! ? …),
  "credits_used"}. About 330 credits a minute (`tts_models.scribe_credits`).
- sts (issue #95): the Voice Changer (speech to speech), `POST /v1/voice-changer/{voice_id}` (multipart `audio`,
  `model_id` `eleven_multilingual_sts_v2`, `remove_background_noise`, `voice_settings` as a JSON string; query
  `output_format=mp3_44100_128`), read from ElevenLabs' API reference on 2026-11-12 ("Maintain full control over
  emotion, timing and delivery"; at most 5 minutes a request). For a take whose lines and timing are right and only
  its voice is weak (CA6): the take's own sound (a video's audio track, taken out as 44.1 kHz WAV) said again in
  `voice_id`, saved as `03_wip/audio/<take stem>_voice_vNN.mp3`. The answer measures both lengths (`timing`:
  {take_s, voice_s, drift_s}); a drift over STS_DRIFT_S is said, since the lips follow the take's timing. About 1,000
  credits a minute (`tts_models.sts_credits`). The edit lays it under the take's picture at the same start, with the
  take's own sound muted.
- history-search finds earlier generations whose text contains the given text (case, spacing and
  punctuation ignored), to reuse the original voice and settings (V1a) instead of cloning.
- Music endpoints, read from the ElevenLabs Python SDK 2.77.0 (`elevenlabs/music/raw_client.py`,
  `MusicClient.upload` and `.compose`) and the handoff's working calls (ad3-middle-recut/.../inpaint):
  `POST /v1/music/upload`, multipart: file field `file` (the audio) and form field
  `extract_composition_plan=music_v2` (a model id; true/false is deprecated); the answer is JSON
  with `song_id` and `composition_plan`. `POST /v1/music`: query `output_format` (e.g.
  mp3_44100_192), JSON body {"composition_plan": {...}, "model_id": "music_v2_5"}; the answer is
  the audio bytes. A plan chunk that points into the upload is {"song_id", "range": {"start_ms",
  "end_ms"}} (the original kept) or carries a `conditioning_ref` (the continuation).
- The plan's shape is the model's (`tm.music_models`, #93): `music_v2` and `music_v2_5` take chunks,
  {"chunks": [{"text": "[Intro] warm, bright", "duration_ms": 10000, "positive_styles": ["upbeat pop", "no vocals",
  ...]}, {"song_id": "...", "range": {"start_ms": 0, "end_ms": 10000}}]} (`negative_styles`, `conditioning_ref`
  optional); `music_v1` takes positive_global_styles, negative_global_styles and sections. A plan of the other shape
  (ElevenLabs answers 422 "Invalid type of composition_plan") is refused before anything is sent.
- music-upload writes 03_wip/audio/music_upload_vNN.json = {song_id, composition_plan, credits_used}.
  music-compose writes 03_wip/audio/music_take_vNN.mp3 and its record `<take>.json` (ruling R2):
  {"kind": "music_take", "file", "length_s" (measured from the saved file with ffprobe), "model",
  "plan", "credits_used", "credits_source"}, which `tm recut music` reads. A take whose answer has no
  `character-cost` and whose subscription count has not moved yet is read again after the take is saved (the count
  lags, LAG_WAITS); still unknown, it is booked at its measured length times the model's rate (`credits_source`
  "rate", `tm.music_models`), so a take that costs more than its estimate is never hidden (#93). The record is written as "music_pending"
  (with the answer's history-item-id) before the audio is saved: if saving fails, the take is paid
  and `--resume <record>` fetches it from the account's history (free) and completes the record.
  A compose onto a name whose record is still pending sends nothing and names that `--resume`.
  `--out` must be inside 03_wip/audio/, where `tm recut music` looks for takes.
- On the music endpoints a plan refusal, or a 401, 402 or 403 we don't recognise, stops with one message
  (MUSIC_STOP): the plan or key cannot use Music. A wrong key, a missing permission, no credits and a rate limit
  get their own message, as everywhere. Nothing is spent.
- sound-effect (issue 96) makes one effect the plugin's free set (`tm tool sfx_fetch`) does not have, `POST
  /v1/sound-generation` with the words, its length (0.5 to 30 s, so its price is known first) and how closely it
  follows them (`--influence`, 0 to 1): `03_wip/audio/sfx_<words>_vNN.mp3`. Paid, for credits, after the user's yes.
- credits reads `GET /v1/user/subscription` and prints {tier, character_count, character_limit,
  next_character_count_reset_unix, instant_cloning}; it is free and writes nothing. `instant_cloning`
  is the plan's `can_use_instant_voice_cloning` (None when ElevenLabs does not say): refresh-ad's V3
  reads it before preparing a clone, when the readiness check left the plan unknown. Organic video's
  D1 reads it before the speech route is chosen (a key that works but has no credits left is "connected but
  unusable"); a key the account refuses (401, 403) stops like any other call.
- Refusals stop (exit 2) with one message per cause (tm.providers, #66): a wrong or revoked key, a restricted key
  without the permission, no credits (with this step's estimate), a plan without the feature (and which plan has it),
  a rate limit. A 401 or 402 we don't recognise keeps the old message; the mapping is read from ElevenLabs' docs and
  not yet checked against live answers.
- Before a paid call the subscription is read (free) and what is left, counting usage-based billing, is compared
  with the approved estimate (TM_COST_ESTIMATE, from `tm tool`): when it falls short, the call stops before anything
  is sent (#66 point 4). A subscription the key may not read skips that check.
- Paid calls (isolate, clone-ivc, tts, scribe, sts, music-upload, music-compose) need `--cost` (the approved estimate in credits): the
  engine records it against the voice_credits budget before this runs and reconciles it with
  `credits_used`, which is reported to it as soon as ElevenLabs answers (before saving the file).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import tempfile
import time
import wave
from pathlib import Path

import requests

from tm import cli, i18n, music_models, organic_audio, providers, tts_models
from tm.runfolder import slug
from tm.tools import _common as c

API = "https://api.elevenlabs.io"
DEFAULT_MODEL = tts_models.DEFAULT   # Eleven v4 in every playbook (#88)
SPEED_RANGE = (0.7, 1.2)
VOICES_LIMIT = (1, 100)   # voices a shared-library search gives (its page_size)
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
_TIMEOUT = 300
_MAX_HISTORY_PAGES = 20
MUSIC_MODEL = music_models.DEFAULT
LAG_WAITS = (2, 4)   # seconds between the late reads of the subscription after a music take with no reported cost
MUSIC_FORMAT = "mp3_44100_192"
MUSIC_UPLOAD_PLAN = "music_v2"
SFX_FORMAT = "mp3_44100_128"
SFX_SECONDS = (0.5, 30.0)
MUSIC_STOP = ("Your ElevenLabs plan or key cannot use Music, so nothing was generated and nothing was spent. "
              "Open elevenlabs.io, choose Subscription and pick a plan with Music, then tell Claude. "
              "The run continues from the same place.")


def _key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise c.ToolStop("The ElevenLabs key is not set, so nothing was sent and nothing was spent. Open "
                         "/plugin, choose Installed, then trendsmesh-playbooks, then Configure options, set the "
                         "ElevenLabs key, then start a new session. The run continues from the same place.")
    return key


def _call(method: str, path: str, **kw) -> requests.Response:
    with requests.Session() as session:
        session.headers["xi-api-key"] = _key()
        return session.request(method, API + path, timeout=_TIMEOUT, **kw)


def _never_sent(exc: requests.RequestException) -> bool:
    """True only when the request surely never reached ElevenLabs (no connection was made)."""
    if isinstance(exc, requests.ConnectTimeout):
        return True
    text = repr(exc)
    return isinstance(exc, requests.ConnectionError) and any(
        k in text for k in ("NewConnectionError", "NameResolutionError", "Failed to resolve", "Connection refused"))


def _paid(path: str, what: str, **kw) -> requests.Response:
    """A paid POST. If it fails after the request may have reached ElevenLabs (a timeout, a reset),
    the estimate stays spent: the credits may be gone."""
    try:
        return _call("POST", path, **kw)
    except requests.RequestException as exc:
        if _never_sent(exc):
            raise c.ToolError(c.scrub(f"Could not reach ElevenLabs for {what}: {exc}. Nothing was spent.")) from None
        c.report_cost(True)
        raise c.ToolError(c.scrub(f"The connection broke during {what}: {exc}. It may have been charged: check the "
                                  "ElevenLabs history before trying again.")) from None


def _detail(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        return " ".join(str(detail.get(k)) for k in ("status", "message") if detail.get(k)) or json.dumps(detail)
    return str(detail)[:300]


def _body(resp: requests.Response) -> object:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:300]


def _refused(resp: requests.Response, what: str, feature: str | None = None) -> str | None:
    """The message for a refusal whose cause we recognise (tm.providers, #66), else None."""
    why = providers.cause("elevenlabs", resp.status_code, _body(resp))
    if why is None:
        return None
    return providers.refusal("elevenlabs", why, status=resp.status_code, detail=c.scrub(_detail(resp)), what=what,
                             need=providers.need("elevenlabs"), feature=feature)


def _check(resp: requests.Response, what: str, feature: str | None = None) -> None:
    """A refusal stops (exit 2) with one message per cause: the key, its permissions, the credits, the plan, a rate
    limit (tm.providers). A 401 or 402 we don't recognise keeps the old message (keys.elevenlabs.other)."""
    if resp.status_code < 400:
        return
    message = _refused(resp, what, feature)
    if message:
        raise c.ToolStop(c.scrub(message))
    detail = c.scrub(_detail(resp))
    if resp.status_code in (401, 402) or "quota" in detail.lower():
        raise c.ToolStop(c.scrub(providers.refusal("elevenlabs", None, status=resp.status_code, detail=detail,
                                                   what=what)))
    raise c.ToolError(f"ElevenLabs answered {resp.status_code} to {what}: {detail}")


def _check_music(resp: requests.Response, what: str) -> None:
    """Like _check, but a plan refusal (or a 401, 402 or 403 we don't recognise) on a Music endpoint is MUSIC_STOP."""
    if resp.status_code in (401, 402, 403):
        why = providers.cause("elevenlabs", resp.status_code, _body(resp))
        if why in (None, "plan"):
            raise c.ToolStop(MUSIC_STOP)
    _check(resp, what, "music")


def _before_paid(what: str) -> int | None:
    """The character count before a paid call (for its cost), once what is left covers the approved estimate (#66
    point 4): when it doesn't, stop before anything is sent. An unreadable subscription (a key without the User
    permission, a network hiccup) skips the check, as before."""
    try:
        resp = _call("GET", "/v1/user/subscription")
        body = resp.json() if resp.status_code == 200 else None
    except (requests.RequestException, ValueError):
        body = None
    if not isinstance(body, dict):
        return None
    remaining, need = providers.left(body), providers.estimate()
    if remaining is not None and need is not None and remaining < need:
        raise c.ToolStop(i18n.t("keys.elevenlabs.short", left=remaining, what=what, need=providers.need("elevenlabs")))
    try:
        return int(body["character_count"])
    except (KeyError, TypeError, ValueError):
        return None


def _used_characters() -> int | None:
    try:
        resp = _call("GET", "/v1/user/subscription")
        return int(resp.json()["character_count"]) if resp.status_code == 200 else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _credits(resp: requests.Response, before: int | None) -> int | None:
    header = resp.headers.get("character-cost")
    if header and header.strip().isdigit():
        return int(header)
    after = _used_characters()
    if before is None or after is None or after < before:  # unknown, or the monthly count was reset
        return None
    return after - before


def _music_credits(resp: requests.Response, before: int | None) -> int | None:
    """Like _credits, but a missing header with a zero or negative change is unknown, not free: the
    subscription count can lag behind the call, and 0 would replace the approved estimate."""
    if resp.headers.get("character-cost", "").strip().isdigit():
        return _credits(resp, before)
    credits = _credits(resp, before)
    return credits if credits is not None and credits > 0 else None


def _write_whole(path: Path, data: bytes) -> None:
    """Write beside the target and move into place, so a short file never sits under the real name."""
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    os.replace(part, path)


def _response_record(resp: requests.Response) -> dict:
    keep = ("content-type", "character-cost", "request-id", "history-item-id")
    record = {"status": resp.status_code, "headers": {k: resp.headers[k] for k in keep if k in resp.headers}}
    if "json" in resp.headers.get("content-type", ""):
        try:
            record["json"] = resp.json()
        except ValueError:
            record["text"] = resp.text[:2000]
    else:
        record["bytes"] = len(resp.content)
    return record


def isolate(in_audio: Path | str, out: Path | str) -> dict:
    """Voice Isolator: the voice from `in_audio` without music and noise, saved to `out`."""
    in_audio, out = Path(in_audio), Path(out)
    before = _before_paid("the voice isolation")
    with in_audio.open("rb") as fh:
        resp = _paid("/v1/audio-isolation", "the voice isolation", files={"audio": (in_audio.name, fh)})
    _check(resp, "the voice isolation")
    credits = _credits(resp, before)
    c.report_cost(True, credits)  # spent, whatever happens to the file next
    if out.suffix.lower() == ".mp3":
        out.write_bytes(resp.content)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "isolated.mp3"
            mp3.write_bytes(resp.content)
            c.run_ffmpeg(["-i", c.media(mp3), c.media(out)])
    request = {"method": "POST", "url": API + "/v1/audio-isolation", "files": {"audio": in_audio.name}}
    return {"out": str(out), "credits_used": credits, "request": request,
            "response": _response_record(resp)}


def clone_ivc(name: str, files: list[Path | str], description: str | None = None) -> dict:
    """Instant voice clone from `files`; returns the new voice_id (and requires_verification)."""
    paths = [Path(f) for f in files]
    if not paths:
        raise ValueError("An instant clone needs at least one recording.")
    before = _before_paid("the instant voice clone")
    handles = [p.open("rb") for p in paths]
    try:
        data = {"name": name, **({"description": description} if description else {})}
        resp = _paid("/v1/voices/add", "the instant voice clone", data=data,
                     files=[("files", (p.name, h)) for p, h in zip(paths, handles)])
    finally:
        for h in handles:
            h.close()
    _check(resp, "the instant voice clone", "clone")
    credits = _credits(resp, before)
    c.report_cost(True, credits)
    body = resp.json()
    request = {"method": "POST", "url": API + "/v1/voices/add", "data": data, "files": [p.name for p in paths]}
    return {"voice_id": body["voice_id"], "requires_verification": bool(body.get("requires_verification")),
            "credits_used": credits, "request": request, "response": _response_record(resp)}


def tts(voice_id: str, text: str, out: Path | str, speed: float = 1.0, model: str = DEFAULT_MODEL,
        settings: dict | None = None, timestamps: bool = False, language: str | None = None) -> dict:
    """One take of `text` in `voice_id` at `speed`, saved to `out` (.wav = PCM 44.1 kHz). With
    `timestamps` the answer also carries the character alignment (returned as "alignment"). `language` (ISO 639-1)
    goes as `language_code` to a model that takes it."""
    if not SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
        raise ValueError(f"speed must be between {SPEED_RANGE[0]} and {SPEED_RANGE[1]}, got {speed}.")
    if not tts_models.takes_speed(model) and abs(speed - 1.0) > 1e-9:
        raise ValueError(f"{model} has no speed setting, so --speed {speed:g} would not change the take. Nothing was "
                         f"sent. Record it at the model's own pace, or with {tts_models.KEEPS_PACE}, which takes a "
                         "speed.")
    out = Path(out)
    wav = out.suffix.lower() == ".wav"
    fmt = "pcm_44100" if wav else "mp3_44100_128"
    voice_settings = {**(settings or {}), **({"speed": speed} if tts_models.takes_speed(model) else {})}
    body = {"text": text, "model_id": model, "voice_settings": voice_settings,
            **({"language_code": language} if language and tts_models.takes_language(model) else {})}
    before = _before_paid("the text to speech")
    path = f"/v1/text-to-speech/{voice_id}" + ("/with-timestamps" if timestamps else "")
    resp = _paid(path, "the text to speech", params={"output_format": fmt}, json=body)
    _check(resp, "the text to speech")
    credits = _credits(resp, before)
    c.report_cost(True, credits)
    alignment, record = None, None
    if timestamps:
        try:
            answer = resp.json()
            audio = base64.b64decode(answer["audio_base64"])
            alignment = answer.get("alignment") or answer.get("normalized_alignment")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise c.ToolError("ElevenLabs answered the timed text to speech in a form this plugin does not know, "
                              "so no take was saved. It may have been charged: check the ElevenLabs history.") from None
        record = {"status": resp.status_code, "headers": _response_record(resp)["headers"],
                  "json": {k: v for k, v in answer.items() if k != "audio_base64"}, "bytes": len(audio)}
    else:
        audio = resp.content
    if wav:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(audio)
        out.write_bytes(buf.getvalue())
    else:
        out.write_bytes(audio)
    request = {"method": "POST", "url": f"{API}{path}", "params": {"output_format": fmt}, "json": body}
    return {"out": str(out), "credits_used": credits, "request": request,
            "response": record or _response_record(resp), "alignment": alignment}


_SENTENCE_END = tuple(".!?…")
STS_FORMAT = "mp3_44100_128"
STS_DRIFT_S = 0.1   # the voice-changed take may differ from the take by this much before the lips are said to drift


def scribe_segments(words: list[dict]) -> list[dict]:
    """Scribe's words (`type` word, with times) as transcript segments, one per sentence."""
    import math

    segments, current = [], []
    for w in words:
        if not isinstance(w, dict) or w.get("type", "word") != "word":
            continue
        try:
            start, end = round(float(w["start"]), 2), round(float(w["end"]), 2)
        except (KeyError, TypeError, ValueError):
            continue
        logprob = w.get("logprob")
        prob = round(math.exp(logprob), 3) if isinstance(logprob, (int, float)) and logprob <= 0 else None
        current.append({"start": start, "end": end, "word": " " + str(w.get("text", "")).strip(), "probability": prob})
        if current[-1]["word"].rstrip().endswith(_SENTENCE_END):
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return [{"start": seg[0]["start"], "end": seg[-1]["end"], "text": "".join(w["word"] for w in seg).strip(),
             "words": seg} for seg in segments]


def scribe(media: Path | str, model: str = tts_models.SCRIBE_MODEL, language: str | None = None) -> dict:
    """Speech to Text of `media` with word times: {"answer" (the transcript's fields), credits_used, request,
    response}."""
    media = Path(media)
    data = {"model_id": model, "timestamps_granularity": "word", "tag_audio_events": "false", "diarize": "false",
            **({"language_code": language} if language else {})}
    before = _before_paid("the speech to text")
    with media.open("rb") as fh:
        resp = _paid("/v1/speech-to-text", "the speech to text", data=data, files={"file": (media.name, fh)})
    _check(resp, "the speech to text")
    credits = _credits(resp, before)
    c.report_cost(True, credits)
    try:
        body = resp.json()
        words = body["words"]
        if not isinstance(words, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise c.ToolError("ElevenLabs answered the speech to text in a form this plugin does not know, so no "
                          "transcript was saved. It may have been charged: check the ElevenLabs history.") from None
    answer = {"language": body.get("language_code"), "language_probability": body.get("language_probability"),
              "duration": body.get("audio_duration_secs"), "segments": scribe_segments(words)}
    request = {"method": "POST", "url": API + "/v1/speech-to-text", "data": data, "files": {"file": media.name}}
    record = _response_record(resp)
    record.pop("json", None)   # the words are in the transcript itself
    return {"answer": answer, "credits_used": credits, "request": request, "response": record}


def sts(audio: Path | str, voice_id: str, out: Path | str, model: str = tts_models.STS_MODEL,
        remove_noise: bool = False, settings: dict | None = None) -> dict:
    """The Voice Changer: `audio` said again in `voice_id`, its timing kept, saved to `out` (MP3)."""
    audio, out = Path(audio), Path(out)
    data = {"model_id": model, "remove_background_noise": "true" if remove_noise else "false",
            **({"voice_settings": json.dumps(settings)} if settings else {})}
    path = f"/v1/voice-changer/{voice_id}"
    before = _before_paid("the voice change")
    with audio.open("rb") as fh:
        resp = _paid(path, "the voice change", params={"output_format": STS_FORMAT}, data=data,
                     files={"audio": (audio.name, fh)})
    _check(resp, "the voice change")
    credits = _credits(resp, before)
    c.report_cost(True, credits)  # spent, whatever happens to the file next
    _write_whole(out, resp.content)
    request = {"method": "POST", "url": API + path, "params": {"output_format": STS_FORMAT}, "data": data,
               "files": {"audio": audio.name}}
    return {"out": str(out), "credits_used": credits, "request": request, "response": _response_record(resp)}


def music_upload(audio: Path | str, out: Path | str) -> dict:
    """Upload the ad's track for inpainting and extract its composition plan; saved to `out` (JSON)."""
    audio, out = Path(audio), Path(out)
    before = _before_paid("the music upload")
    with audio.open("rb") as fh:
        resp = _paid("/v1/music/upload", "the music upload", data={"extract_composition_plan": MUSIC_UPLOAD_PLAN},
                     files={"file": (audio.name, fh)})
    _check_music(resp, "the music upload")
    credits = _music_credits(resp, before)
    c.report_cost(True, credits)
    body = resp.json()
    if not isinstance(body, dict) or not body.get("song_id"):
        raise c.ToolError("ElevenLabs answered the music upload without a song_id. It may have been charged: "
                          "check the ElevenLabs history before trying again.")
    saved = {"song_id": body["song_id"], "composition_plan": body.get("composition_plan"), "credits_used": credits}
    c.write_json(out, saved)
    request = {"method": "POST", "url": API + "/v1/music/upload", "files": {"file": audio.name},
               "data": {"extract_composition_plan": MUSIC_UPLOAD_PLAN}}
    return {**saved, "out": str(out), "request": request, "response": _response_record(resp)}


def _record_path(take: Path) -> Path:
    return take.with_name(take.name + ".json")


def _late_credits(before: int | None, length: float, model: str) -> tuple[int, str]:
    """A take with no reported cost (#93): the subscription read again, as its count lags behind the call; else its
    measured length at the model's rate. (credits, where they come from)."""
    if before is not None:
        for wait in LAG_WAITS:
            time.sleep(wait)
            after = _used_characters()
            if after is not None and after > before:
                return after - before, "subscription"
    return music_models.credits(length, model), "rate"


def _complete_take(take: Path, record: dict, before: int | None = None, price: bool = False) -> dict:
    """The take is on disk: measure it and write the record `tm recut music` reads. With `price`, a take whose cost
    is not known yet gets it now and reports it to the engine (`_late_credits`)."""
    length = float(c.probe(take)["duration"])
    if length <= 0:
        raise c.ToolError(f"{take.name} was saved but has no audio length (is it a music file?). The take is "
                          "paid; its record stays pending.")
    credits, source = record.get("credits_used"), record.get("credits_source")
    if price and credits is None:
        credits, source = _late_credits(before, length, record["model"])
        c.report_cost(True, credits)
    done = {"kind": "music_take", "file": take.name, "length_s": round(length, 3), "model": record["model"],
            "plan": record["plan"], "credits_used": credits, **({"credits_source": source} if source else {})}
    c.write_json(_record_path(take), done)
    return done


def music_compose(plan: dict, out: Path | str, model: str = MUSIC_MODEL, fmt: str = MUSIC_FORMAT) -> dict:
    """One take from a composition plan, saved to `out` with its record `<out>.json`."""
    out = Path(out)
    rec_path = _record_path(out)
    if rec_path.exists():
        raise c.ToolError(f"{rec_path.name} already exists, and files are never overwritten. Nothing was sent.")
    shape = music_models.plan_problems(plan, model)
    if shape:
        example = f" An example for {model}: {json.dumps(music_models.V2_EXAMPLE)}" if model.startswith("music_v2") \
            else ""
        raise c.ToolError(" ".join(shape) + " Nothing was sent." + example)
    before = _before_paid("the music take")
    resp = _paid("/v1/music", "the music take", params={"output_format": fmt},
                 json={"composition_plan": plan, "model_id": model})
    _check_music(resp, "the music take")
    credits = _music_credits(resp, before)
    c.report_cost(True, credits)  # spent, whatever happens to the file next
    source = None if credits is None else (
        "header" if resp.headers.get("character-cost", "").strip().isdigit() else "subscription")
    pending = {"kind": "music_pending", "file": out.name, "history_item_id": resp.headers.get("history-item-id"),
               "model": model, "plan": plan, "format": fmt, "credits_used": credits,
               **({"credits_source": source} if source else {})}
    c.write_json(rec_path, pending)
    _write_whole(out, resp.content)
    request = {"method": "POST", "url": API + "/v1/music", "params": {"output_format": fmt},
               "json": {"composition_plan": plan, "model_id": model}}
    done = _complete_take(out, pending, before, price=True)
    return {**done, "out": str(out), "request": request, "response": _response_record(resp)}


def sound_effect(text: str, seconds: float, influence: float, out: Path | str) -> dict:
    """One sound effect from its words and length, saved to `out` (mp3)."""
    out = Path(out)
    body = {"text": text, "duration_seconds": seconds, "prompt_influence": influence}
    before = _before_paid("the sound effect")
    resp = _paid("/v1/sound-generation", "the sound effect", params={"output_format": SFX_FORMAT}, json=body)
    _check(resp, "the sound effect", "sound_effects")
    credits = _music_credits(resp, before)
    c.report_cost(True, credits)   # spent, whatever happens to the file next
    if not resp.content:
        raise c.ToolError("ElevenLabs answered the sound effect with no sound. It may have been charged: check the "
                          "ElevenLabs history before trying again.")
    _write_whole(out, resp.content)
    request = {"method": "POST", "url": API + "/v1/sound-generation", "params": {"output_format": SFX_FORMAT},
               "json": body}
    return {"out": str(out), "credits_used": credits, "request": request, "response": _response_record(resp)}


def music_resume(record_path: Path | str) -> dict:
    """Finish a paid take whose audio was not saved: fetch it from the account's history (free)."""
    record_path = Path(record_path)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise c.ToolError(f"{record_path.name} is not a readable music record. Nothing was run.") from None
    if not isinstance(record, dict) or record.get("kind") not in ("music_pending", "music_take"):
        raise c.ToolError(f"{record_path.name} is not a music take record. Nothing was run.")
    name = record.get("file")
    if not isinstance(name, str) or not name or Path(name).name != name or name in (".", ".."):
        raise c.ToolError(f"{record_path.name} names no take file inside 03_wip/audio. Nothing was run.")
    if not isinstance(record.get("model"), str) or not isinstance(record.get("plan"), dict):
        raise c.ToolError(f"{record_path.name} is missing its model or plan, so it cannot be finished. "
                          "Nothing was run.")
    take = record_path.with_name(name)
    if record["kind"] == "music_take":
        raise c.ToolError(f"{take.name} is already complete; there is nothing to resume.")
    item = record.get("history_item_id")
    if not item:
        raise c.ToolError("This take has no history item id, so it cannot be fetched again. Open the "
                          "ElevenLabs history, download the take, and save it under this name in "
                          "03_wip/audio.")
    # a pending take on disk may be a partial write: always fetch it again (the tool's own file)
    resp = _call("GET", f"/v1/history/{item}/audio")
    _check_music(resp, "the music download")
    _write_whole(take, resp.content)
    return {**_complete_take(take, record), "out": str(take)}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def history_search(text: str) -> dict:
    """Earlier generations on this account whose text contains `text` -> {"items": [...], ...}."""
    want = _norm(text)
    if not want:
        raise ValueError("Give the text to look for.")
    before = _used_characters()
    items, after_id, pages, resp = [], None, 0, None
    while pages < _MAX_HISTORY_PAGES:
        params = {"page_size": 1000, **({"start_after_history_item_id": after_id} if after_id else {})}
        resp = _call("GET", "/v1/history", params=params)
        _check(resp, "the history search")
        page = resp.json()
        pages += 1
        for item in page.get("history", []):
            if want in _norm(item.get("text") or ""):
                items.append({k: item.get(k) for k in ("history_item_id", "voice_id", "voice_name", "model_id",
                                                        "text", "date_unix", "settings")})
        after_id = page.get("last_history_item_id")
        if not page.get("has_more") or not after_id:
            break
    request = {"method": "GET", "url": API + "/v1/history", "query": text, "pages": pages}
    return {"items": items, "pages": pages, "credits_used": _credits(resp, before) if resp is not None else 0,
            "request": request, "response": {"status": 200, "matches": len(items)}}


def credits() -> dict:
    """The account's plan and character use -> {tier, character_count, character_limit,
    next_character_count_reset_unix, instant_cloning}. Free: it is one read of the subscription.
    `instant_cloning` is True or False only when ElevenLabs says so as a boolean, else None."""
    try:
        resp = _call("GET", "/v1/user/subscription")
    except requests.RequestException as exc:
        raise c.ToolError(c.scrub(f"Could not reach ElevenLabs to read the credits: {exc}. Nothing was spent.")) from None
    _check(resp, "reading the credits")
    try:
        body = resp.json()
        return {"tier": body.get("tier"), "character_count": int(body["character_count"]),
                "character_limit": int(body["character_limit"]),
                "next_character_count_reset_unix": body.get("next_character_count_reset_unix"),
                "instant_cloning": cloning if isinstance(cloning := body.get("can_use_instant_voice_cloning"), bool)
                else None}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise c.ToolError("ElevenLabs answered the credits read in a form this plugin does not know, so the "
                          "credits are not checked. Nothing was spent.") from None


def my_voices(query: str | None = None, limit: int = 100) -> dict:
    """The voices on the user's own account -> {voices: [...], answer, request}. Free: one read."""
    params = {"voice_type": "non-default", "page_size": limit, "sort": "name", **({"search": query} if query else {})}
    try:
        resp = _call("GET", "/v2/voices", params=params)
    except requests.RequestException as exc:
        raise c.ToolError(c.scrub(f"Could not reach ElevenLabs to list your voices: {exc}. "
                                  "Nothing was spent.")) from None
    _check(resp, "listing your voices")
    try:
        answer = resp.json()
        found = answer["voices"]
        if not isinstance(found, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise c.ToolError("ElevenLabs answered the list of your voices in a form this plugin does not know. "
                          "Nothing was spent.") from None
    return {"voices": found, "answer": answer, "request": {"method": "GET", "url": f"{API}/v2/voices",
                                                           "params": params}}


def voices(query: str, language: str, *, gender: str | None = None, age: str | None = None,
           accent: str | None = None, use_case: str | None = None, limit: int = 10) -> dict:
    """Search the shared voice library -> {voices: [...], answer, request}. Free."""
    params = {"search": query, "gender": gender, "age": age, "accent": accent, "use_cases": use_case,
              "language": language, "page_size": limit, "sort": "trending"}
    params = {k: v for k, v in params.items() if v is not None}
    try:
        resp = _call("GET", "/v1/shared-voices", params=params)
    except requests.RequestException as exc:
        raise c.ToolError(c.scrub(f"Could not reach ElevenLabs to search the voices: {exc}. "
                                  "Nothing was spent.")) from None
    _check(resp, "searching the voices")
    try:
        answer = resp.json()
        found = answer["voices"]
        if not isinstance(found, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise c.ToolError("ElevenLabs answered the voice search in a form this plugin does not know. "
                          "Nothing was spent.") from None
    return {"voices": found, "answer": answer, "request": {"method": "GET", "url": f"{API}/v1/shared-voices",
                                                           "params": params}}


def _preview(url: object, target: Path) -> bool:
    """One free preview clip, saved whole beside the search. The ElevenLabs key is not sent."""
    if not isinstance(url, str) or not url.startswith("https://") or target.exists():
        return target.exists()
    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException:
        return False
    if resp.status_code != 200 or not resp.content:
        return False
    _write_whole(target, resp.content)
    return True


# CLI ---------------------------------------------------------------------------------------

def _cost(res: dict) -> str:
    return f"{res['credits_used']} credits" if res["credits_used"] is not None else "credits unknown"


def _cmd_isolate(a: argparse.Namespace, run) -> int:
    out = c.output(run, a.out, "wip", "isolated", "mp3")
    res = isolate(a.audio, out)
    parent = c.parent_ref(run, a.audio)
    c.record(run, out, "ElevenLabs Voice Isolator", parent, cost=_cost(res), model="audio-isolation",
             before_after=f"after (before: {parent})", request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs isolate", "outputs": [c.rel(run, out)],
                        "credits_used": res["credits_used"]},
                    f"Isolated voice saved to {c.rel(run, out)} ({_cost(res)}).")


def _cmd_clone(a: argparse.Namespace, run) -> int:
    out = c.output(run, a.out, "wip", "voice_clone", "json")
    res = clone_ivc(a.name, a.files, a.description)
    summary = {k: res[k] for k in ("voice_id", "requires_verification", "credits_used")}
    c.write_json(out, {"name": a.name, **summary, "files": [c.parent_ref(run, f) for f in a.files]})
    c.record(run, out, "ElevenLabs instant voice clone", ", ".join(c.parent_ref(run, f) for f in a.files),
             params={"name": a.name}, model="ivc", cost=_cost(res), request=res["request"], response=res["response"])
    note = (" ElevenLabs asks to verify this voice: it may be a protected library voice, so search the "
            "library instead of working around it." if res["requires_verification"] else "")
    return c.finish(a, {"tool": "elevenlabs clone-ivc", "outputs": [c.rel(run, out)], **summary},
                    f"Voice cloned: {res['voice_id']} ({_cost(res)}).{note}")


def _cmd_tts(a: argparse.Namespace, run) -> int:
    settings = cli.json_arg(a.settings) if a.settings else None
    out = c.output(run, a.out, "wip", "vo_take", "wav")
    side = {kind: out.with_name(f"{out.stem}.{kind}") for kind in ("words.json", "words.srt", "phrases.srt")}
    if a.timestamps:  # before anything is sent: the sidecars are never overwritten
        taken = [c.rel(run, p) for p in side.values() if p.exists()]
        if taken:
            raise c.ToolError(f"{', '.join(taken)} already exists, and files are never overwritten. Use another "
                              "--out, or leave it out to get the next version. Nothing was sent.")
    language = _language(run, a.language) if tts_models.takes_language(a.model) else None
    res = tts(a.voice_id, a.text, out, speed=a.speed, model=a.model, settings=settings, timestamps=a.timestamps,
              language=language)
    c.record(run, out, "ElevenLabs text to speech", a.voice_id, prompt=a.text,
             params={"voice_id": a.voice_id, "speed": a.speed, "settings": settings,
                     **({"language_code": language} if language else {}),
                     **({"timestamps": True} if a.timestamps else {})},   # a plain take's row as before
             model=a.model, cost=_cost(res), request=res["request"], response=res["response"])
    outputs = [c.rel(run, out)]
    if a.timestamps:
        if not res["alignment"]:
            raise c.ToolError(f"The take is saved to {c.rel(run, out)} ({_cost(res)}), but ElevenLabs sent no "
                              "alignment, so there are no word times. Try the line again.")
        words = organic_audio.words_from_alignment(res["alignment"])
        c.write_json(side["words.json"], words, newline="\n")
        side["words.srt"].write_text(organic_audio.to_srt(words), encoding="utf-8", newline="\n")
        side["phrases.srt"].write_text(organic_audio.to_srt(organic_audio.phrases(words)),
                                       encoding="utf-8", newline="\n")
        for p in side.values():
            c.record(run, p, "ElevenLabs timestamps", c.rel(run, out), cost="0 credits")
            outputs.append(c.rel(run, p))
    return c.finish(a, {"tool": "elevenlabs tts", "outputs": outputs, "credits_used": res["credits_used"]},
                    f"Take saved to {c.rel(run, out)} ({_cost(res)})."
                    + (f" Word and phrase times beside it ({len(words)} words)." if a.timestamps else ""))


def _cmd_scribe(a: argparse.Namespace, run) -> int:
    media = Path(a.media)
    if not media.is_file():
        raise c.ToolError(f"{c.name_of(a.media)} does not exist. Nothing was sent.")
    try:
        rel = c.rel(run, media)
        stage = f"{c.rel(run, media.parent)}/qa"
    except ValueError:
        raise c.ToolError(f"{c.name_of(a.media)} is not inside the run folder {run.path}. Nothing was sent.") from None
    out = c.output(run, a.out, stage, f"{media.stem}_scribe", "json")
    language = _language(run, a.language)
    res = scribe(media, a.model, language)
    words = sum(len(seg["words"]) for seg in res["answer"]["segments"])
    c.write_json(out, {"source": "scribe", "model": a.model, "media": rel, **res["answer"],
                       "credits_used": res["credits_used"]})
    c.record(run, out, "ElevenLabs Speech to Text (Scribe)", rel, params={"language_code": language}, model=a.model,
             cost=_cost(res), request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs scribe", "outputs": [c.rel(run, out)], "words": words,
                        "credits_used": res["credits_used"]},
                    f"Scribe's transcript of {rel} saved to {c.rel(run, out)}: {words} word(s) ({_cost(res)}). "
                    f"Check the take with it: tm tool take_qa --run {a.run} {rel} --lang <its language> --script "
                    f"<its lines> --scribe {c.rel(run, out)}.")


def _cmd_sts(a: argparse.Namespace, run) -> int:
    take = Path(a.take)
    if not take.is_file():
        raise c.ToolError(f"{c.name_of(a.take)} does not exist. Nothing was sent.")
    try:
        rel = c.rel(run, take)
    except ValueError:
        raise c.ToolError(f"{c.name_of(a.take)} is not inside the run folder {run.path}. Nothing was sent.") from None
    if not c.probe(take).get("has_audio"):
        raise c.ToolError(f"{rel} has no sound to change. Nothing was sent.")
    settings = cli.json_arg(a.settings) if a.settings else None
    out = _audio_target(run, a.out, f"{take.stem}_voice", "mp3")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / f"{take.stem}.wav"
        c.run_ffmpeg(["-i", c.media(take), "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", c.media(wav)])
        take_s = float(c.probe(wav)["duration"])
        res = sts(wav, a.voice_id, out, model=a.model, remove_noise=a.remove_noise, settings=settings)
    voice_s = float(c.probe(out)["duration"])
    timing = {"take_s": round(take_s, 3), "voice_s": round(voice_s, 3), "drift_s": round(voice_s - take_s, 3)}
    c.record(run, out, "ElevenLabs Voice Changer", rel, params={"voice_id": a.voice_id, "settings": settings,
             "remove_background_noise": a.remove_noise, "timing": timing}, model=a.model, cost=_cost(res),
             request=res["request"], response=res["response"])
    text = (f"The take's voice changed into {c.rel(run, out)} ({_cost(res)}): {timing['voice_s']:g} s against the "
            f"take's {timing['take_s']:g} s.")
    if abs(timing["drift_s"]) > STS_DRIFT_S:
        text += (f" It is {abs(timing['drift_s']):g} s {'longer' if timing['drift_s'] > 0 else 'shorter'}: the "
                 "lips follow the take's timing, so watch the mouth in the edit before showing it.")
    else:
        text += " The timing is kept: lay it under the take's picture at the same start, the take's own sound muted."
    return c.finish(a, {"tool": "elevenlabs sts", "outputs": [c.rel(run, out)], "timing": timing,
                        "credits_used": res["credits_used"]}, text)


def _language(run, given: str | None) -> str | None:
    """The `language_code` of a take: --language, else the run's market language; its primary subtag (`pt-BR` ->
    `pt`), as ElevenLabs takes ISO 639-1 (and 639-3 for a few). None when the run names no market language."""
    if given and given.strip():
        return i18n.primary(given.strip())
    from tm import video_fonts   # the one reading of a run's market language, the channel profile's too

    tag, _ = video_fonts.market_language(run)
    return i18n.primary(tag) if tag else None


def _search_folder(query: str) -> str:
    """The search's folder name, `slug(query)`, never a name Windows reserves (`con`, `nul`, `com1`…)."""
    name = slug(query)
    return f"q-{name}" if name.split(".")[0].upper() in WINDOWS_RESERVED else name


def _cmd_voices(a: argparse.Namespace, run) -> int:
    low, high = VOICES_LIMIT
    limit = a.limit if a.limit is not None else (high if a.mine else 10)
    if not low <= limit <= high:
        raise c.ToolError(f"--limit is {limit}, and ElevenLabs gives {low} to {high} voices a search. "
                          "Nothing was searched.")
    if a.mine:
        res = my_voices(a.query, limit)
        stage, source, params = "02_research/voices/mine", "ElevenLabs voices on the account", {"query": a.query}
    else:
        missing = [flag for flag, value in (("--query", a.query), ("--language", a.language)) if not value]
        if missing:
            raise c.ToolError(f"The library search needs {' and '.join(missing)} (or --mine for the voices on your "
                              "own account). Nothing was searched.")
        res = voices(a.query, a.language, gender=a.gender, age=a.age, accent=a.accent, use_case=a.use_case,
                     limit=limit)
        stage, source = f"02_research/voices/{_search_folder(a.query)}", "ElevenLabs shared voices"
        params = {"query": a.query, "language": a.language}
    out = c.output(run, a.out, stage, "search", "json")
    c.write_json(out, res["answer"])
    c.record(run, out, source, None, params=params, cost="free", request=res["request"], response={"status": 200})
    rows = []
    for v in res["voices"]:
        vid = str(v.get("voice_id") or "")
        name = re.sub(r"[^\w]+", "_", str(v.get("name") or vid)).strip("_") or vid[:8]
        target = out.parent / f"preview_{name}_{vid[:8]}.mp3"
        saved = bool(vid) and _preview(v.get("preview_url"), target)
        if saved:
            c.record(run, target, "ElevenLabs voice preview", c.rel(run, out), cost="free")
        labels = v.get("labels") if isinstance(v.get("labels"), dict) else {}   # an own voice's are in its labels
        rows.append({"voice_id": vid, "name": v.get("name"),
                     **{k: v.get(k) or labels.get(k) for k in ("gender", "age", "accent", "use_case")},
                     **({"category": v.get("category")} if a.mine else {}),
                     "description": v.get("description"), "preview_file": c.rel(run, target) if saved else None})
    lines = [f"{r['voice_id']} | {r['name']} | {r['gender']} {r['age']} {r['accent']} | {r['use_case']} | "
             f"{(r['description'] or '')[:110]}" for r in rows]
    return c.finish(a, {"tool": "elevenlabs voices", "outputs": [c.rel(run, out)], "voices": rows},
                    "\n".join([*lines, f"{len(rows)} voice(s); search saved to {c.rel(run, out)}, "
                                f"{sum(bool(r['preview_file']) for r in rows)} preview clip(s) beside it. Free."]))


def _cmd_history(a: argparse.Namespace, run) -> int:
    out = c.output(run, a.out, "research", "elevenlabs_history", "json")
    res = history_search(a.text)
    c.write_json(out, {"query": a.text, "items": res["items"]})
    c.record(run, out, "ElevenLabs history", None, params={"query": a.text}, cost=_cost(res),
             request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs history-search", "outputs": [c.rel(run, out)],
                        "matches": len(res["items"]), "credits_used": res["credits_used"]},
                    f"{len(res['items'])} earlier generation(s) with this text; saved to {c.rel(run, out)}.")


def _cmd_credits(a: argparse.Namespace, run) -> int:
    res = credits()
    left = res["character_limit"] - res["character_count"]
    account = f"plan {res['tier']}" if res["tier"] else "account"
    rest = f"{left} left" if left >= 0 else f"over the limit by {-left}"
    return c.finish(a, {"tool": "elevenlabs credits", **res, "left": max(left, 0)},
                    f"ElevenLabs {account}: {res['character_count']} of {res['character_limit']} "
                    f"credits used, {rest}.")


def _audio_target(run, out: str | None, stem: str, ext: str) -> Path:
    """03_wip/audio/<stem>_vNN.<ext>, the next version (or --out, which is never overwritten)."""
    if out:
        return c.output(run, out, "wip", stem, ext)
    folder = run.path / "03_wip" / "audio"
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)\.{re.escape(ext)}$")
    highest = max([int(m.group(1)) for e in (folder.iterdir() if folder.is_dir() else [])
                   if (m := pattern.match(e.name))] or [0])
    target = folder / f"{stem}_v{highest + 1:02d}.{ext}"
    run.assert_writable(target)
    folder.mkdir(parents=True, exist_ok=True)
    return target


def _cmd_music_upload(a: argparse.Namespace, run) -> int:
    out = _audio_target(run, a.out, "music_upload", "json")
    res = music_upload(a.audio, out)
    c.record(run, out, "ElevenLabs Music upload", c.parent_ref(run, a.audio), model=MUSIC_UPLOAD_PLAN,
             cost=_cost(res), request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs music-upload", "outputs": [c.rel(run, out)], "song_id": res["song_id"],
                        "credits_used": res["credits_used"]},
                    f"Track uploaded as {res['song_id']}; its plan is in {c.rel(run, out)} ({_cost(res)}).")


def _cmd_music_compose(a: argparse.Namespace, run) -> int:
    if a.resume is not None:
        record = _inside(run, a.resume)
        res = music_resume(record)
        take = Path(res["out"])
        c.record(run, take, "ElevenLabs Music (resumed from history)", None, model=res["model"],
                 cost="paid before (resumed)")
        return c.finish(a, {"tool": "elevenlabs music-compose", "outputs": [c.rel(run, take)],
                            "length_s": res["length_s"], "credits_used": res["credits_used"]},
                        f"Take completed: {c.rel(run, take)}, {res['length_s']} s (paid before, no new charge).")
    if not a.plan:
        raise c.ToolError("Give --plan <composition plan JSON> (or --resume <record>). Nothing was run.")
    if not a.format.startswith("mp3_"):
        raise c.ToolError(f"--format must be an mp3 format such as {MUSIC_FORMAT}, got {a.format}. Nothing was run.")
    plan_arg = a.plan
    if plan_arg.strip()[:1] not in ("{", "[") and not Path(plan_arg).exists() and (run.path / plan_arg).is_file():
        plan_arg = str(run.path / plan_arg)  # relative to the run folder, as the other paths are
    plan = cli.json_arg(plan_arg)
    if not isinstance(plan, dict):
        raise c.ToolError("The plan must be a JSON object (the composition plan). Nothing was run.")
    if a.out and not a.out.lower().endswith(".mp3"):
        raise c.ToolError(f"--out must end in .mp3 (the take is an mp3), got {a.out}. Nothing was run.")
    if a.out:
        target = Path(a.out) if Path(a.out).is_absolute() else run.path / a.out
        try:
            target.resolve().relative_to((run.path / "03_wip" / "audio").resolve())
        except ValueError:
            raise c.ToolError(f"--out must be inside 03_wip/audio/, where tm recut music finds the takes, got "
                              f"{a.out}. Nothing was run. Leave out --out for the next music_take_vNN.mp3.") from None
    out = _audio_target(run, a.out, "music_take", "mp3")
    rec = _record_path(out)
    if rec.exists():
        try:
            kind = json.loads(rec.read_text(encoding="utf-8")).get("kind")
        except (OSError, ValueError, AttributeError):
            kind = None
        todo = (f" It is a paid take that was not saved: finish it for free with --resume {c.rel(run, rec)}."
                if kind == "music_pending" else "")
        raise c.ToolError(f"{rec.name} already exists, and files are never overwritten. Nothing was sent.{todo}")
    res = music_compose(plan, out, model=a.model, fmt=a.format)
    c.record(run, out, "ElevenLabs Music", None, params={"format": a.format}, model=a.model, cost=_cost(res),
             request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs music-compose", "outputs": [c.rel(run, out)],
                        "length_s": res["length_s"], "credits_used": res["credits_used"]},
                    f"Take saved to {c.rel(run, out)}, {res['length_s']} s ({_cost(res)}).")


def _cmd_sound_effect(a: argparse.Namespace, run) -> int:
    text = (a.text or "").strip()
    if not text:
        raise c.ToolError("Give --text, what the effect sounds like (e.g. \"a soft paper swipe\"). Nothing was sent.")
    lo, hi = SFX_SECONDS
    if not lo <= a.seconds <= hi:
        raise c.ToolError(f"--seconds is {lo:g} to {hi:g}: the effect's length, which sets its price. Nothing was "
                          "sent.")
    if not 0 <= a.influence <= 1:
        raise c.ToolError("--influence is 0 to 1 (how closely the effect follows the words). Nothing was sent.")
    if a.out and not a.out.lower().endswith(".mp3"):
        raise c.ToolError(f"--out must end in .mp3, got {a.out}. Nothing was sent.")
    out = _audio_target(run, a.out, f"sfx_{slug(text).lower()[:40].strip('-') or 'effect'}", "mp3")
    res = sound_effect(text, a.seconds, a.influence, out)
    c.record(run, out, "ElevenLabs Sound Effects", None, prompt=text,
             params={"seconds": a.seconds, "influence": a.influence, "format": SFX_FORMAT},
             model="eleven sound effects", cost=_cost(res), request=res["request"], response=res["response"])
    return c.finish(a, {"tool": "elevenlabs sound-effect", "outputs": [c.rel(run, out)],
                        "credits_used": res["credits_used"]},
                    f"Sound effect saved to {c.rel(run, out)}, {a.seconds:g} s ({_cost(res)}).")


def _inside(run, value: str) -> Path:
    """A --resume record: a non-empty path relative to the run folder, never outside it."""
    if not value.strip():
        raise c.ToolError("--resume needs the take's record (03_wip/audio/<take>.json). Nothing was run.")
    path = Path(value) if Path(value).is_absolute() else run.path / value
    try:
        path.resolve().relative_to(run.path.resolve())
    except ValueError:
        raise c.ToolError(f"--resume must be a path inside the run folder, got {value!r}. Nothing was run.") from None
    return path


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tm tool elevenlabs", description="ElevenLabs calls for flow V.",
                                allow_abbrev=False)
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("isolate", allow_abbrev=False, help="Voice Isolator (POST /v1/audio-isolation)")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("audio")
    s = sub.add_parser("clone-ivc", allow_abbrev=False, help="instant voice clone from recordings")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("--name", required=True)
    s.add_argument("--description", default=None)
    s.add_argument("files", nargs="+")
    s = sub.add_parser("tts", allow_abbrev=False, help="one take of a line")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("--voice-id", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--speed", type=float, default=1.0)
    s.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"default {DEFAULT_MODEL}; {tts_models.KEEPS_PACE} keeps an original's pace (Refresh an ad)")
    s.add_argument("--language", default=None,
                   help="the language_code, e.g. pl (default: the run's market language)")
    s.add_argument("--settings", default=None, help="voice settings: a JSON file (or inline JSON), e.g. {\"stability\": 0.5}")
    s.add_argument("--timestamps", action="store_true",
                   help="use with-timestamps and write <stem>.words.json, .words.srt and .phrases.srt")
    s = sub.add_parser("scribe", allow_abbrev=False, help="Speech to Text with word times (Scribe), for a take's QA")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits (about 330 a minute)")
    s.add_argument("--model", default=tts_models.SCRIBE_MODEL)
    s.add_argument("--language", default=None, help="the language_code, e.g. pl (default: the run's market language)")
    s.add_argument("media", help="the take or the edit, inside the run")
    s = sub.add_parser("sts", allow_abbrev=False, help="the Voice Changer: a take's own voice changed, its timing kept")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits (about 1,000 a minute)")
    s.add_argument("--voice-id", required=True)
    s.add_argument("--model", default=tts_models.STS_MODEL)
    s.add_argument("--remove-noise", action="store_true", help="remove the background noise as well")
    s.add_argument("--settings", default=None, help="voice settings: a JSON file (or inline JSON)")
    s.add_argument("take", help="the take (a video or its sound), inside the run")
    s = sub.add_parser("history-search", allow_abbrev=False, help="earlier generations with this text")
    c.add_common(s)
    s.add_argument("text")
    s = sub.add_parser("voices", allow_abbrev=False,
                       help="search the shared voice library, or list your own voices (--mine), with previews (free)")
    c.add_common(s)
    s.add_argument("--mine", action="store_true", help="the voices on your own account, not the library")
    s.add_argument("--query", default=None, help="what to search for (needed for the library)")
    s.add_argument("--language", default=None, help="the voice's language code, e.g. pl or en (the library)")
    s.add_argument("--gender", default=None)
    s.add_argument("--age", default=None)
    s.add_argument("--accent", default=None)
    s.add_argument("--use-case", default=None, help="e.g. social_media, narrative_story, conversational")
    s.add_argument("--limit", type=int, default=None, help="voices to list, 1 to 100 (default 10, or 100 with --mine)")
    s = sub.add_parser("credits", allow_abbrev=False, help="the plan and the credits left (free)")
    c.add_common(s)
    s = sub.add_parser("music-upload", allow_abbrev=False, help="upload the ad's track and extract its plan")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("audio")
    s = sub.add_parser("music-compose", allow_abbrev=False, help="one music take from a composition plan")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("--plan", default=None, help="the composition plan: a JSON file (or inline JSON)")
    s.add_argument("--model", default=MUSIC_MODEL)
    s.add_argument("--format", default=MUSIC_FORMAT, help="output format (an mp3_* format)")
    s.add_argument("--resume", default=None, help="a take record (relative to the run folder) to finish, free")
    s = sub.add_parser("sound-effect", allow_abbrev=False, help="one sound effect from its words (paid)")
    c.add_common(s)
    s.add_argument("--cost", type=float, default=None, help="the approved estimate in credits")
    s.add_argument("--text", required=True, help="what the effect sounds like")
    s.add_argument("--seconds", type=float, required=True, help="its length, 0.5 to 30 s")
    s.add_argument("--influence", type=float, default=0.3, help="how closely it follows the words, 0 to 1")
    a = p.parse_args(argv)
    c.report_cost(False)
    run = c.open_run(a.run)
    c.inputs(run, a, "audio", "files", "settings", "media", "take")   # a run-relative input, whatever the working folder
    _key()  # stop before writing anything when the key is missing
    return {"isolate": _cmd_isolate, "clone-ivc": _cmd_clone, "tts": _cmd_tts,
            "history-search": _cmd_history, "scribe": _cmd_scribe, "sts": _cmd_sts,
            "music-upload": _cmd_music_upload,
            "music-compose": _cmd_music_compose, "credits": _cmd_credits, "sound-effect": _cmd_sound_effect,
            "voices": _cmd_voices}[a.action](a, run)


if __name__ == "__main__":
    raise SystemExit(main())
