"""The chosen voice's pace, known before the paid recording (issue #140; the owner's decision #148 line 22).

A voice that reads the script slower than the take needs makes the video longer (the owner's run: Eleven v4 at 2.46
words a second, under `qa.wps_min` 2.8, found only by `tm organic vo-sync` after the voiceover was paid for). So the
pack check estimates the pace of the voice the pack names (`taste.voice`, else `speech.voice`), free, before any
spend:

- **from the channel's earlier recordings** with that voice: every `tm organic vo-sync` whose recorded words match
  the pack's lines appends `{voice_id, name, model, wps, words, seconds, run, date, file}` to the channel's
  `library/channels/<slug>/voice_pace.jsonl` (`record`); the estimate is the median `wps` of that voice's rows;
- **else from its free preview clip** (`tm tool elevenlabs voices` saves it as `preview_<name>_<id8>.mp3` in
  `02_research/voices/`), timed by the local transcription: its words divided by its speech seconds. The transcript
  is kept beside the clip (`<clip stem>.transcript.json`, the shape `tm tool transcribe` writes), and is made in the
  process when the local transcription is installed (`tm env install breakdown`), else the answer names the command.

`check` compares the estimate with the pace the script needs, its said words over `script.seconds` less `qa.tail_s`,
and with `qa.wps_min`. A voice too slow for either is **a warning inside the pack approval** (not a stop, not a
problem): the pack check's answer names the estimate's source and gives three options: cut about N words to fit the
length; a brisker voice by name (the channel's history and the D2 voices whose estimate passes); or accept a longer
video, about X s instead of Y s. The user's pick is recorded with `tm decide pack approve --said "<their words>"`
(or the pack is rewritten and checked again).
"""

from __future__ import annotations

import json
import math
import re
import statistics
from datetime import date
from pathlib import Path

from tm import brand, config, organic, trend_spool
from tm.runfolder import RunFolder

HISTORY = "voice_pace.jsonl"
VOICES = "02_research/voices"
TOL = 1e-9
_WORD = re.compile(r"\w", re.UNICODE)


def history_path(run: RunFolder, channel: str) -> Path:
    return trend_spool.workspace_of(run) / brand.CHANNEL_DIR / brand.channel_key(channel) / HISTORY


def voice_of(pack: dict) -> str | None:
    """The ElevenLabs voice the pack reads with: the taste pick, else the speech's."""
    for value in ((pack.get("taste") or {}).get("voice"), (pack.get("speech") or {}).get("voice")):
        if isinstance(value, str) and value.strip():
            return re.sub(r"\s*\(.*\)\s*$", "", value.strip()) or value.strip()
    return None


def rows(run: RunFolder, channel: str) -> list[dict]:
    """The channel's recorded paces, oldest first; a damaged line is skipped."""
    path = history_path(run, channel)
    out = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("voice_id") and isinstance(row.get("wps"), (int, float)):
            out.append(row)
    return out


def record(run: RunFolder, pack: dict, words: list[dict], words_rel: str, *, today: date | None = None) -> dict | None:
    """Append this recording's pace to the channel's history (after `tm organic vo-sync`), once per recording. The
    row, or None when the pack names no voice or channel, or the words are empty."""
    from tm import organic_pack

    voice, channel = voice_of(pack), pack.get("channel")
    if not voice or not channel or not words:
        return None
    seconds = float(words[-1]["end"]) - float(words[0]["start"])
    if seconds <= 0:
        return None
    row = {"voice_id": voice, "name": _name_of(run, voice), "model": organic_pack.voice_model(pack),
           "wps": round(len(words) / seconds, 3), "words": len(words), "seconds": round(seconds, 2),
           "run": run.path.name, "date": (today or date.today()).isoformat(), "file": words_rel}
    if any(r.get("run") == row["run"] and r.get("file") == words_rel for r in rows(run, channel)):
        return None                                       # this recording is already counted
    path = history_path(run, channel)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _searches(run: RunFolder) -> list[Path]:
    base = run.path / VOICES
    return sorted(base.rglob("search_v*.json")) if base.is_dir() else []


def _name_of(run: RunFolder, voice: str) -> str | None:
    """The voice's name, from the run's saved voice searches."""
    for path in _searches(run):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        for v in (data.get("voices") if isinstance(data, dict) else None) or []:
            if isinstance(v, dict) and v.get("voice_id") == voice and v.get("name"):
                return str(v["name"])
    return None


def preview_of(run: RunFolder, voice: str) -> Path | None:
    base = run.path / VOICES
    found = sorted(base.rglob(f"preview_*_{voice[:8]}.mp3")) if base.is_dir() else []
    return found[-1] if found else None


def transcript_of(preview: Path) -> Path:
    return preview.with_name(preview.stem + ".transcript.json")


def _preview_words(run: RunFolder, preview: Path, transcribe: bool) -> list[dict] | None:
    path = transcript_of(preview)
    if not path.is_file() and transcribe:
        try:
            from tm.tools import transcribe as local
            local.save(run, preview, path, local.DEFAULT_MODEL, None)
        except Exception:                               # not installed, or the clip cannot be read: say so
            return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    words = [w for s in (data.get("segments") or []) for w in (s.get("words") or [])
             if isinstance(w, dict) and _WORD.search(str(w.get("word") or ""))]
    return words or None


def estimate(run: RunFolder, voice: str, channel: str | None, *, transcribe: bool = True) -> dict | None:
    """{wps, source, n, said} of the voice: the median of the channel's earlier recordings with it, else its preview
    clip timed locally; None when neither can be read."""
    paces = [float(r["wps"]) for r in rows(run, channel) if r.get("voice_id") == voice] if channel else []
    if paces:
        n = len(paces)
        return {"voice_id": voice, "wps": round(statistics.median(paces), 2), "source": "history", "n": n,
                "said": f"from {n} earlier recording{'s' if n != 1 else ''} of this voice on the channel"}
    preview = preview_of(run, voice)
    if preview is None:
        return None
    words = _preview_words(run, preview, transcribe)
    if not words:
        return None
    seconds = float(words[-1]["end"]) - float(words[0]["start"])
    if seconds <= 0:
        return None
    return {"voice_id": voice, "wps": round(len(words) / seconds, 2), "source": "preview", "n": 1,
            "said": "from its free preview clip, timed on this computer",
            "file": preview.relative_to(run.path).as_posix()}


def _candidates(run: RunFolder, voice: str, channel: str | None) -> dict[str, str | None]:
    """Other voices to offer: the channel's history and the voices the D2 page offered (its latest options file)."""
    out: dict[str, str | None] = {}
    for r in rows(run, channel) if channel else []:
        if r["voice_id"] != voice:
            out.setdefault(r["voice_id"], r.get("name"))
    latest = run.latest("03_wip", "taste_options", "json")
    try:
        offered = json.loads(latest.read_text(encoding="utf-8-sig")).get("voices") if latest else []
    except (OSError, ValueError, AttributeError):
        offered = []
    for v in offered or []:
        if isinstance(v, dict) and v.get("voice_id") and v["voice_id"] != voice:
            out.setdefault(str(v["voice_id"]), v.get("name"))
    return out


def check(run: RunFolder, pack: dict, cfg: dict, *, transcribe: bool = True) -> dict | None:
    """The pace warning of an ElevenLabs voiceover, before it is paid for (the module docstring): None when the pack
    reads no ElevenLabs voice; else {voice, estimate, needed, wps_min, slow, options, message}."""
    from tm import organic_pack

    if (pack.get("speech") or {}).get("route") not in organic.ELEVENLABS_ROUTES:
        return None
    voice = voice_of(pack)
    said = sum(len(str(t).split()) for t in organic_pack.voice_text(pack))
    if not voice or not said:
        return None
    least, tail = config.get(cfg, "qa.wps_min"), config.get(cfg, "qa.tail_s") or 0.0
    seconds = float(pack["script"]["seconds"])
    span = seconds - tail
    needed = round(said / span, 2) if span > TOL else None
    channel = pack.get("channel")
    got = estimate(run, voice, channel, transcribe=transcribe)
    name = _name_of(run, voice) or voice
    if got is None:
        preview = preview_of(run, voice)
        todo = (f"time its preview clip on this computer (free): tm tool transcribe --run {organic_pack._run_arg(run)} "
                f"{preview.relative_to(run.path).as_posix()} --out "
                f"{transcript_of(preview).relative_to(run.path).as_posix()}, then check the pack again"
                if preview else "save its preview clip with tm tool elevenlabs voices (free), then check again")
        return {"voice": voice, "name": name, "estimate": None, "needed": needed, "wps_min": least, "slow": None,
                "options": None, "message": f"The pace of the voice {name} is not known yet: {todo}."}
    wps = got["wps"]
    floor = max(x for x in (needed, least) if x is not None) if (needed or least) else None
    slow = floor is not None and wps < floor - TOL
    out = {"voice": voice, "name": name, "estimate": got, "needed": needed, "wps_min": least, "slow": slow,
           "options": None}
    if not slow:
        need = f"the script needs {needed:g}, so it fits {seconds:g} s" if needed is not None else "it fits"
        out["message"] = f"The voice {name} reads about {wps:g} words a second ({got['said']}): {need}."
        return out
    fits = math.floor(wps * span + TOL) if span > TOL else said
    cut = max(1, said - fits)
    longer = round(said / wps + tail, 1)
    brisker = []
    for other, other_name in _candidates(run, voice, channel).items():
        est = estimate(run, other, channel, transcribe=transcribe)
        if est and est["wps"] >= floor - TOL:
            brisker.append({"voice_id": other, "name": other_name or _name_of(run, other) or other, "wps": est["wps"],
                            "said": est["said"]})
    fits_length = said <= fits                          # only under qa.wps_min: the length holds, the pace does not
    out["options"] = {"cut": {"words": cut, "seconds": seconds,
                              "said": f"cut about {cut} word{'s' if cut != 1 else ''} to fit {seconds:g} s"
                              if not fits_length else "shortening the text does not make this voice faster"},
                      "brisker": brisker,
                      "longer": {"seconds": max(longer, seconds), "instead_of": seconds,
                                 "said": f"accept a longer video: about {longer:g} s instead of {seconds:g} s"
                                 if not fits_length else f"accept it as it is: {seconds:g} s read at about {wps:g} "
                                 "words a second, which the take QA will call slow"}}
    under = [f"the {needed:g} the script needs" if needed is not None and wps < needed - TOL else None,
             f"qa.wps_min {least:g}" if least is not None and wps < least - TOL else None]
    names = "; ".join(f"{b['name']} (about {b['wps']:g}, {b['said']})" for b in brisker)
    out["message"] = (f"Before the voiceover is paid for: the voice {name} reads about {wps:g} words a second "
                      f"({got['said']}), under {' and '.join(u for u in under if u)}. Ask it inside the pack "
                      f"approval, with three options: {out['options']['cut']['said']}; a brisker voice"
                      + (f": {names}" if brisker else " (none of the voices known so far passes: search again in "
                         "D2)") + f"; or {out['options']['longer']['said']}. A shorter text or another voice is a "
                      "new pack version, checked again; a longer video is their yes to this pack, recorded with "
                      "their words (tm decide pack approve --said \"<their words>\").")
    return out
