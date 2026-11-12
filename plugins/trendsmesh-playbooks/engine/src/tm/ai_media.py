"""The facts behind Meta's AI disclosure (refresh-ad E1, issue #24), read from the run's manifest.

    tm ai-media --run R --file F [--file F ...] [--json]

Meta's `self_ai_disclosure` can only be set when a creative is created, and Meta asks the advertiser,
never the agent, to decide it. So before G10 (and again at E2, before the creatives) the run lists what it
made or edited with a generative AI tool, for each file an ad will use: the manifest rows in that file's
ancestry (the `parent` column, followed back) whose source or model names such a tool. It also lists the
files it cannot trace: the original's (`00_raw`, `01_base`: the run does not know how they were made) and any
file without a manifest row. The answer is facts for the card, never the decision.

`kind`: `voice` (a synthetic, cloned or AI-processed voice), `music` (generated music) or `picture` (a
generated or AI-edited video or image: an AI shot, frames inpainted by a model such as ProPainter, an interpolated
frame). The free caption removal (`tm tool inpaint`, OpenCV Telea: classical image processing, no model) is not
AI media (issue #56): its plate and mask carry their own source, `opencv-telea`, and the plate recorded before
that, as "tm tool inpaint budget (...)", reads the same way. Only media files
count (video, audio, images); the JSON beside them (voice ids, histories, previews' lists) does not.
`classical`: the free plates in a file's ancestry, edited without a model, for the card to name (not AI media).
`elsewhere`: AI media in the run that none of the given files uses (a take not kept, for example).
"""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath

from tm import cli, manifest
from tm.runfolder import RunFolder

MEDIA = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
         ".png", ".jpg", ".jpeg", ".webp", ".gif"}
# A source or model naming one of these made or edited the file with generative AI (lower case, substrings).
AI_MARKERS = ("elevenlabs", "replicate", "veo", "propainter", "inpaint", "frame-interpolation", "kling",
              "seedance", "minimax", "runway", "sora", "flux", "imagen", "gpt-image", "midjourney",
              "stable-diffusion", "stable diffusion", "dall-e", "dalle", "luma", "pika", "hailuo", "wan-")
# Not ad media even when a marker matches: a shared voice's sample, a price page.
NOT_MEDIA_SOURCES = ("voice preview", "model page", "run record")
# Classical edits, no model (issue #56): the free plate's source (`tm.tools.inpaint.SOURCE`) and the one it was
# recorded with before (which says "inpaint"). A source starting so is not AI unless its model names one.
CLASSICAL_SOURCES = ("opencv-telea", "tm tool inpaint budget")
UNTRACED_STAGES = ("00_raw", "01_base")


def _kind(text: str) -> str:
    if "music" in text:
        return "music"
    if any(w in text for w in ("speech", "voice", "isolat", "tts")):
        return "voice"
    return "picture"


def _is_classical(row: dict) -> bool:
    """The free caption removal's plate (or mask): a media file edited without a model (issue #56)."""
    return (PurePosixPath(row["file"]).suffix.lower() in MEDIA and row["source"].lower().startswith(CLASSICAL_SOURCES)
            and not _is_ai(row))


def _is_ai(row: dict) -> bool:
    if PurePosixPath(row["file"]).suffix.lower() not in MEDIA:
        return False
    source, model = row["source"].lower(), row["model"].lower()
    if source.startswith(CLASSICAL_SOURCES):
        source = ""
    text = f"{source} {model}"
    return not any(s in text for s in NOT_MEDIA_SOURCES) and any(m in text for m in AI_MARKERS)


def _entry(row: dict) -> dict:
    return {"file": row["file"], "source": row["source"], "model": row["model"],
            "kind": _kind(f"{row['source']} {row['model']}".lower())}


def _inside(run: RunFolder, text: str) -> str:
    """A --file as given (run-relative, or absolute inside the run) as a run-relative posix path."""
    path = Path(text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(run.path.resolve()).as_posix()
        except ValueError:
            raise ValueError(f"{text} is not inside the run folder.") from None
    rel = text.replace("\\", "/")
    if not rel or ".." in PurePosixPath(rel).parts:
        raise ValueError(f"{text!r} must be a path inside the run folder.")
    return rel


def facts(run: RunFolder, files: list[str]) -> dict:
    """For each file: whether it has a manifest row, the AI media in its ancestry and the files it can't trace;
    then the AI media no given file uses."""
    rows = manifest.rows(run)
    by_file: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for r in rows:   # a later row of the same file wins, as it is the latest record
        by_file[r["file"]] = r
        by_name[PurePosixPath(r["file"]).name] = r
    used: set[str] = set()
    out = []
    for f in files:
        ai, classical, untraced, seen = [], [], [], set()
        todo = [f]
        while todo:
            name = todo.pop(0)
            row = by_file.get(name) or (by_name.get(name) if "/" not in name else None)
            key = row["file"] if row else name
            if key in seen:
                continue
            seen.add(key)
            if row is None:
                if PurePosixPath(name).suffix.lower() in MEDIA or name == f:
                    untraced.append(name)   # a parent that is a voice id or a URL is no file to trace
                continue
            if key.split("/", 1)[0] in UNTRACED_STAGES:
                untraced.append(key)
            if _is_ai(row):
                ai.append(_entry(row))
            elif _is_classical(row):
                classical.append({"file": row["file"], "source": row["source"]})
            todo.extend(p.strip() for p in row["parent"].split(",") if p.strip())
        used |= seen
        out.append({"file": f, "recorded": f in by_file, "ai": ai, "classical": classical, "untraced": untraced})
    elsewhere = [_entry(r) for r in by_file.values() if _is_ai(r) and r["file"] not in used]
    return {"files": out, "elsewhere": elsewhere}


def message(result: dict) -> str:
    lines = []
    for e in result["files"]:
        made = "; ".join(f"{a['file']} ({a['source']}{', ' + a['model'] if a['model'] else ''}: {a['kind']})"
                         for a in e["ai"]) or "nothing this run made with generative AI"
        lines.append(f"{e['file']}: {made}.")
        if e["classical"]:
            lines.append("  Edited without AI (the free OpenCV caption removal, no model; not AI media): "
                         + ", ".join(c["file"] for c in e["classical"]) + ".")
        if e["untraced"]:
            lines.append(f"  Not traceable from the run's records (ask the user): {', '.join(e['untraced'])}.")
    if result["elsewhere"]:
        lines.append("AI media in the run that these files don't use: "
                     + ", ".join(a["file"] for a in result["elsewhere"]) + ".")
    lines.append("These are the facts for the card. Meta's AI disclosure is the advertiser's decision: never set "
                 "or infer it for them.")
    return "\n".join(lines)


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--file", action="append", required=True,
                   help="a file an ad will use (run-relative); repeat for each")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        result = facts(run, [_inside(run, f) for f in args.file])
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    text = message(result)
    cli.emit(args, {"status": "done", **result, "message": text}, text)
    return 0


cli.register("ai-media", _setup, _run)
