"""The voiceover laid under a take for the video check-in page (organic video F2, issue #83 point 4).

    voiceover(run)                          the run's latest voiceover take (ElevenLabs text to speech), run-relative
    narrated(pack)                          whether the video's voice is a separate voiceover (an off-screen narrator
                                            from ElevenLabs, or an animation's voiceover)
    offsets(pack)                           each video item's start in the video (seconds): its section's `from`, else
                                            the earlier takes' seconds added up
    laid_under(run, video, vo, offset)      showcase/<video>__<vo>_vo.mp4: the video with the voiceover from `offset`
                                            under it and the video's own sound turned down to VIDEO_GAIN

A preview only, never the edit: a mux of the picture (copied, not re-encoded) with the two sounds, made on this
computer with ffmpeg (free, nothing is sent anywhere). The music comes in the edit (G1). A mux made from the same
files is reused; a newer video or voiceover makes a new one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tm import manifest
from tm.runfolder import RunFolder
from tm.tools import _common as c

TTS = "ElevenLabs text to speech"            # the manifest source of a voiceover take
SHOWCASE = "showcase"
SOURCE = "tm organic page gate (voiceover laid under)"
VIDEO_GAIN = 0.2                             # the take's own sound under the voiceover
NARRATOR_ROUTES = ("elevenlabs_narrator",)   # a lip-synced line is already in the take


def voiceover(run: RunFolder) -> str | None:
    """The latest voiceover take recorded in the run that is still there."""
    found = [r["file"] for r in manifest.rows(run) if r["source"] == TTS and (run.path / r["file"]).is_file()
             and Path(r["file"]).suffix.lower() in (".mp3", ".wav", ".m4a")]
    return found[-1] if found else None


def narrated(pack: dict) -> bool:
    from tm import organic_pack
    route = (pack.get("speech") or {}).get("route")
    return route in NARRATOR_ROUTES or bool(organic_pack.animated(pack))


def offsets(pack: dict) -> dict[str, float]:
    """Each video item's start in the whole video, by name; an animated item's by its id."""
    from tm import organic_pack
    sections = {str(s["id"]): float(s.get("from") or 0) for s in pack.get("sections") or []}
    out: dict[str, float] = {}
    at = 0.0
    for st in pack.get("stages") or []:
        if st.get("stage") != organic_pack.VIDEO_STAGE:
            continue
        for item in st.get("items") or []:
            sec = item.get("section")
            out[item["name"]] = sections.get(str(sec), at) if sec is not None else at
            at += float(item.get("seconds") or 0)
    for item in organic_pack.animated(pack):
        out[item] = sections.get(item, 0.0)
    return out


def _has_audio(path: Path) -> bool:
    got = subprocess.run([c.ffprobe_bin(), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "json", c.media(path)], capture_output=True)
    try:
        return bool(json.loads(got.stdout.decode("utf-8", "replace") or "{}").get("streams"))
    except ValueError:
        return False


def laid_under(run: RunFolder, video: str, vo: str, offset: float = 0.0) -> str | None:
    """The preview with the voiceover laid under `video` from `offset` seconds of the voiceover, run-relative; None
    when ffmpeg cannot make it (the page then shows the take as it is)."""
    src, voice = run.path / video, run.path / vo
    out = run.path / SHOWCASE / f"{Path(video).stem}__{Path(vo).stem}_vo.mp4"
    if out.is_file() and out.stat().st_mtime >= max(src.stat().st_mtime, voice.stat().st_mtime):
        return out.relative_to(run.path).as_posix()
    out.parent.mkdir(parents=True, exist_ok=True)
    if _has_audio(src):
        mix = (f"[1:a]apad[vo];[0:a]volume={VIDEO_GAIN}[own];[own][vo]amix=inputs=2:duration=first:"
               "dropout_transition=0:normalize=0[a]")
    else:
        mix = "[1:a]apad[a]"
    cmd = [c.ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", c.media(src),
           "-ss", f"{max(0.0, offset):.3f}", "-i", c.media(voice), "-filter_complex", mix, "-map", "0:v:0",
           "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", c.media(out)]
    done = subprocess.run(cmd, capture_output=True)
    if done.returncode != 0 or not out.is_file():
        out.unlink(missing_ok=True)
        return None
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, SHOWCASE, SOURCE, parent=video,
                    params={"voiceover": vo, "offset_s": round(offset, 3), "video_gain": VIDEO_GAIN})
    return rel
