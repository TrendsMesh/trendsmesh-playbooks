"""The animatics of a creative brief (CB11), shared by the playbooks: each drawn in a library style (issue #138
item 4, owner decision #148 line 2 as changed by @piotr-lezon).

    build(run, brief_path, ...)   `tm brief animatic`: each concept's pages from its style module, with `render` the MP4s
    formats_of(run), fps_of(run)  the formats drawn (`animatic.formats`, the audience pick's, or both), the fps
    not_rendered(run, ...)        the concepts' formats with no MP4 in the renders folder
    rendered_gap(run)             the step check `animatics_rendered`
    choose_styles(brief, ids)     each concept's library style, ranked for its format
    style(run, brief_path, ...)   `tm brief animatic --style`: the styles in a new brief, a build prompt per concept

Every animatic is drawn in a library style; there is no sketch (the fixed scenes of the handoff's `scenes.js` no
longer draw animatics, and the plugin no longer ships them). `style` (`tm brief animatic --style auto`, part of D2's
make) writes each named concept's `animatic.style` (the styleId, chosen by `atlas_prompt.ranked` from the concept's
format, no two concepts alike, the channel's own style first with `own`) and `animatic.poster` (the style's poster,
copied into renders/), and a build prompt `<C>_prompt_vNN.txt` (`atlas_prompt.build`, the animatic mode). A subagent
writes the style module `<C>_style_vNN.js`; `build` draws each concept from its latest module (written from its latest
prompt, one beat per beat of the brief: the brief's beats are its own, no frames list is read), a page
`<C>_<fmt>_<ver>.html` per format through `atlas_prompt.module_page`, rendered by `atlas.render`. A concept with no
style is a Stop that names the style step. A beat's `animatic` block gives the prompt its label, its texts and its
`params.image` (a picture of the run, inlined into the page); a `scene` from an older brief is not read. No render
time is kept: the animatics question gives no fixed time (#148 line 157 as changed by @piotr-lezon).

A version is never used twice (the next free `vNN` by default). With `render`, `atlas.render` draws each page into
`03_wip/animatic/renders/<C>_animatic_<fmt>_<ver>.mp4` with its stills and its 720p preview `..._720p.mp4` (issue
#162: what the brief page plays, at most PREVIEW_MAX_BYTES), and a new `04_final/brief_pack_vNN.json` names them
(`animatic/<file>`, the page's paths; the previews as `animatic.preview.<fmt>`, {path, bytes}). Nothing is written when a concept cannot be drawn or the renderer is
not there (a Stop); paths in the answer are run-relative.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from tm import atlas, atlas_prompt, config, manifest, state
from tm.runfolder import RunFolder
from tm.stops import AGAIN_SENTENCE, Stop
from tm.tools import _common as c

WIP = "03_wip/animatic"
RENDERS = f"{WIP}/renders"            # where the renders go, and where the page finds them
PAGE_DIR = "animatic"                 # the brief's path of a render, as the page serves it
FINAL, STEM = "04_final", "brief_pack"
FORMATS = ("9x16", "4x5")
SOURCE = "tm brief animatic"
MODEL = "atlas render.mjs"
AGAIN = AGAIN_SENTENCE
_NOTHING = "Nothing was rendered."      # atlas's words in each of its stops
_ID = re.compile(r"[A-Za-z0-9_-]+")                       # brief_page's concept ids: they name files here
_VERSION = re.compile(r"^v(\d+)$")
_VERSIONED = re.compile(r"_v(\d+)\.(?:js|html|mp4)$")   # a storyboard file or render of a version
# a product picture a beat draws (`params.image`, issue #12): a file of the run, inlined into the page
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}
IMAGE_MAX = 2 * 1024 * 1024
# --- in the run ---------------------------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    return path.relative_to(run.path).as_posix()


def _checked_formats(given: object, where: str) -> list[str]:
    if not isinstance(given, list) or not given or not all(f in FORMATS for f in given):
        raise ValueError(f"{where} is {given!r}: give some of {', '.join(FORMATS)}.")
    return list(dict.fromkeys(given))


def formats_of(run: RunFolder) -> list[str]:
    """The formats drawn: the run's `animatic.formats`, else the audience pick's (R6), else both.
    Stop for a setting that names another format, or a broken config.yaml."""
    try:
        cfg = config.load(run) if (run.path / config.FILE).is_file() else {}
        given = config.get(cfg, "animatic.formats")
        if given is not None:
            return _checked_formats(given, "animatic.formats in config.yaml")
        picked = (state.load(run).audience or {}).get("formats")
        if picked is not None:
            return _checked_formats(picked, "The audience pick's formats")
    except Stop:
        raise
    except ValueError as exc:                     # a file to fix, not a bad argument
        raise Stop(f"{exc} Fix it, then draw the animatics again. Nothing was written. {AGAIN}") from None
    return list(FORMATS)


def fps_of(run: RunFolder) -> int:
    """The run's `animatic.fps` (24 by default)."""
    cfg = config.load(run) if (run.path / config.FILE).is_file() else {}
    return int(config.get(cfg, "animatic.fps") or atlas.FPS)


def _used(folder: Path) -> set[int]:
    """The version numbers taken in the animatic folder and its renders."""
    return {int(m.group(1)) for d in (folder, folder / "renders") if d.is_dir()
            for f in d.iterdir() if (m := _VERSIONED.search(f.name))}


def _version(folder: Path, given: str | None) -> str:
    used = _used(folder)
    free = f"v{max(used, default=0) + 1:02d}"
    if given is None:
        return free
    m = _VERSION.fullmatch(given)
    if m is None:
        raise ValueError(f"{given!r} is not an animatic version: write it like v01.")
    version = f"v{int(m.group(1)):02d}"
    if int(m.group(1)) in used:
        raise ValueError(f"Animatic {version} already exists in {WIP}, and files are never overwritten: leave the "
                         f"version out for the next free one ({free}).")
    return version


def _concepts(rel: str, brief: dict, concepts: list[str] | None) -> list[dict]:
    """The concepts asked for (default: all), checked before anything is written: each id names the animatic's files."""
    try:
        listed = [x for x in brief["concepts"] if isinstance(x, dict)]
        ids = [x["id"] for x in listed]
        unknown = [cid for cid in concepts or [] if cid not in ids]
        if unknown:
            raise ValueError(f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not a concept of {rel} "
                             f"({', '.join(map(str, ids))}).")
        if not listed:
            raise KeyError("concepts")
        bad = [repr(cid) for cid in ids if not (isinstance(cid, str) and _ID.fullmatch(cid))]
        if bad:
            raise Stop(f"{rel} names the concept id{'' if len(bad) == 1 else 's'} {', '.join(bad)}: an id is letters, "
                       "digits, _ and - (e.g. C1), as it names the animatic's files. Fix it (a new version), then make "
                       f"the animatics again. Nothing was written. {AGAIN}")
        return [x for x in listed if not concepts or x["id"] in concepts]
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise Stop(f"{rel} is not in its shape ({type(exc).__name__}: {exc}), so no animatic can be drawn from it. "
                   f"Check it with tm brief check, fix it (a new version), then make the animatics again. Nothing "
                   f"was written. {AGAIN}") from None


def _no_style(rel: str, ids: list[str]) -> Stop:
    """The stop for concepts with no library style yet: every animatic is drawn in one (#148 line 2)."""
    joined = ",".join(ids)
    named = " and ".join([", ".join(ids[:-1]), ids[-1]] if len(ids) > 1 else ids)
    return Stop(f"{rel}: {named} {'has' if len(ids) == 1 else 'have'} no animatic style yet, and every animatic is "
                f"drawn in a library style. Choose {'it' if len(ids) == 1 else 'them'} with tm brief animatic --style "
                f"auto --concepts {joined} (with --own <style> for a channel with its own look), have a subagent write "
                f"each style module from its build prompt, then render. Nothing was written. {AGAIN}")


def _image(run: RunFolder, ref: object) -> Path | None:
    """The run's file a beat's `params.image` names (its path from the run folder), or None when it
    is not an image file of the run within IMAGE_MAX."""
    if not isinstance(ref, str) or not ref or "://" in ref or ref.startswith("data:"):
        return None
    text = ref.replace("\\", "/")
    if PurePosixPath(text).is_absolute() or PureWindowsPath(ref).drive or ".." in text.split("/"):
        return None
    path = run.path / text
    try:
        path.resolve().relative_to(run.path.resolve())
    except ValueError:
        return None
    if path.suffix.lower() not in IMAGE_TYPES or not path.is_file() or path.stat().st_size > IMAGE_MAX:
        return None
    return path


def write_new(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as fh:     # never over an earlier file
        fh.write(text)


# --- the page's preview of a render (issue #162 item 1) ------------------------------------------------------------
# A render is drawn at its frame (1080 wide) with no bitrate cap, so a styled animatic runs to tens of MB, over the
# Artifact tool's 15 MB a file. The page plays a 720p preview instead, its bitrate set from its length so it stays at
# or under PREVIEW_MAX_BYTES; the full-size file stays beside it, as it was.
PREVIEW_SHORT = 720                     # the preview's shorter side
PREVIEW_MAX_BYTES = 12 * 10**6          # under page.MAX_FILE_BYTES, with room for the container
PREVIEW_AUDIO_KBPS = 128
PREVIEW_KBPS_MAX = 2500                 # a short animatic's cap: plenty for 720p; CRF keeps simple frames smaller
PREVIEW_KBPS_MIN = 100
PREVIEW_CRF = 23
PREVIEW_STEP = 0.75                     # each try's bitrate after one over the budget, as tools/deliver.py steps down
PREVIEW_TRIES = 4
PREVIEW_MODEL = "ffmpeg libx264 (720p preview)"


def preview_of(mp4: Path) -> Path:
    """Where a render's preview is kept: beside it, `<stem>_720p.mp4`."""
    return Path(mp4).with_name(f"{Path(mp4).stem}_720p.mp4")


def preview_kbps(seconds: float, budget: int | None = None) -> int:
    """The video bitrate (kb/s) that keeps a preview of `seconds` with its sound under `budget` (PREVIEW_MAX_BYTES),
    8 % kept for the container; at most PREVIEW_KBPS_MAX, at least PREVIEW_KBPS_MIN."""
    budget = PREVIEW_MAX_BYTES if budget is None else budget
    total = budget * 8 / 1000 * 0.92 / max(float(seconds), 0.1)
    return int(max(PREVIEW_KBPS_MIN, min(PREVIEW_KBPS_MAX, total - PREVIEW_AUDIO_KBPS)))


def _encode_preview(src: Path, part: Path, kbps: int, scale: str, sound: bool) -> None:
    c.run_ffmpeg(["-i", c.media(src), "-map", "0:v:0", *(["-map", "0:a:0"] if sound else []), "-vf", scale,
                  "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-crf", str(PREVIEW_CRF),
                  "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k",
                  *(["-c:a", "aac", "-b:a", f"{PREVIEW_AUDIO_KBPS}k"] if sound else ["-an"]),
                  "-movflags", "+faststart", "-f", "mp4", str(part)])


def make_preview(src: Path, duration: float | None = None) -> dict:
    """The 720p preview of the render `src` (`preview_of`): its shorter side PREVIEW_SHORT (never scaled up), its
    bitrate from its length (`preview_kbps`), stepped down (PREVIEW_STEP, PREVIEW_TRIES tries) while it is over
    PREVIEW_MAX_BYTES; the last try is kept when none fits (the page then leaves it out). {path, bytes, kbps}.
    FileExistsError when the preview is there already (never over a file); ffmpeg's error when it cannot be read."""
    src = Path(src)
    out = preview_of(src)
    if out.exists():
        raise FileExistsError(f"{out.name} already exists, and files are never overwritten.")
    info = c.probe(src)
    if not info.get("has_video"):
        raise ValueError(f"{src.name} has no video to preview.")
    seconds = duration or info.get("duration") or 1
    w, h = info["width"], info["height"]
    side = min(PREVIEW_SHORT, w, h)
    scale = (f"scale={side}:-2" if w <= h else f"scale=-2:{side}") + ":flags=lanczos"
    part = out.with_name(f".{out.stem}.{os.getpid()}.part.mp4")
    kbps, size, step = preview_kbps(seconds), 0, preview_kbps(seconds)
    try:
        for _ in range(PREVIEW_TRIES):
            kbps = step
            part.unlink(missing_ok=True)
            _encode_preview(src, part, kbps, scale, bool(info.get("has_audio")))
            size = part.stat().st_size
            if size <= PREVIEW_MAX_BYTES:
                break
            step = max(PREVIEW_KBPS_MIN, int(kbps * PREVIEW_STEP))
        if out.exists():
            raise FileExistsError(f"{out.name} already exists, and files are never overwritten.")
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    return {"path": out, "bytes": size, "kbps": kbps}


def _render(run: RunFolder, items: list[dict], version: str, fps: int) -> None:
    """Each page drawn into renders/ with its stills and its 720p preview (`make_preview`; one that cannot be made is
    `preview_error`, and the page serves the full-size file), each file with a manifest row."""
    renders = run.path / RENDERS
    renders.mkdir(parents=True, exist_ok=True)
    for done, item in enumerate(items):
        mp4 = renders / f"{item['concept']}_animatic_{item['format']}_{version}.mp4"
        try:
            info = atlas.render(run.path / item["html"], mp4, fps=fps)
        except c.ToolStop as exc:
            # atlas says "Nothing was rendered": true of this page, not of the set
            said = (f"{done} of {len(items)} animatics were rendered, so animatic {version} is not complete and no "
                    "brief names it; rendering again makes the next version.")
            text = str(exc)
            raise Stop(text.replace(_NOTHING, said) if _NOTHING in text else f"{said} {text}") from None
        except c.ToolError as exc:
            raise ValueError(f"{exc} Animatic {version} is not complete, so no brief names it. Make the animatics "
                             "again (the next version).") from None
        stills = sorted(_rel(run, p) for p in renders.glob(f"{mp4.stem}_still_*.png"))
        item.update(mp4=_rel(run, mp4), stills=stills, render_s=info.get("render_s"),
                    page_errors=info.get("page_errors") or [])
        manifest.record(run, item["mp4"], "03_wip", SOURCE, parent=item["html"], model=MODEL, cost="0",
                        params={"fps": fps, "render_s": item["render_s"], "page_errors": item["page_errors"]})
        for still in stills:
            manifest.record(run, still, "03_wip", SOURCE, parent=item["mp4"], model=MODEL, cost="0")
        try:
            made = make_preview(mp4, info.get("duration") if isinstance(info.get("duration"), (int, float)) else None)
        except (subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError) as exc:
            said = exc.stderr.decode("utf-8", "replace").strip() if isinstance(exc, subprocess.CalledProcessError) \
                and exc.stderr else str(exc)
            item["preview_error"] = (said.splitlines() or [type(exc).__name__])[-1]
            continue
        item["preview"] = {"path": _rel(run, made["path"]), "bytes": made["bytes"]}
        manifest.record(run, item["preview"]["path"], "03_wip", SOURCE, parent=item["mp4"], model=PREVIEW_MODEL,
                        cost="0", params={"kbps": made["kbps"], "bytes": made["bytes"]})


def _brief_with_renders(run: RunFolder, rel: str, brief: dict, items: list[dict], formats: list[str],
                        version: str) -> str:
    """A new 04_final/brief_pack_vNN.json: each rendered concept's `animatic` names its MP4s. Its
    `default` (the format the page plays first) stays the concept's own when that one was drawn,
    else the first format drawn."""
    paths: dict[str, dict] = {}
    previews: dict[str, dict] = {}
    for item in items:
        paths.setdefault(item["concept"], {})[item["format"]] = f"{PAGE_DIR}/{Path(item['mp4']).name}"
        if item.get("preview"):                                             # the page's 720p copy (issue #162)
            previews.setdefault(item["concept"], {})[item["format"]] = {
                "path": f"{PAGE_DIR}/{Path(item['preview']['path']).name}", "bytes": item["preview"]["bytes"]}
    new = copy.deepcopy(brief)
    for concept in new["concepts"]:
        if isinstance(concept, dict) and concept.get("id") in paths:
            drawn = paths[concept["id"]]
            before = concept["animatic"] if isinstance(concept.get("animatic"), dict) else {}
            own = before.get("default")
            default = own if isinstance(own, str) and own in drawn else formats[0]
            kept = {k: before[k] for k in STYLE_KEYS if k in before}       # a styled concept's style and poster
            shown = {"preview": previews[concept["id"]]} if concept["id"] in previews else {}
            concept["animatic"] = {**drawn, "default": default, **kept, **shown}
    target = run.next_version(FINAL, STEM, "json")
    write_new(target, json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    out = _rel(run, target)
    manifest.record(run, out, FINAL, SOURCE, parent=rel, params={"animatics": version})
    return out


# --- the library style (issue #138 item 4, owner decision #148 line 2) -------------------------------------------

STYLE_KEYS = ("style", "poster")        # a styled concept's `animatic` keeps them through a render
STYLE_SOURCE = "tm brief animatic --style"
ASPECTS = {"9x16": "9:16", "4x5": "4:5"}
# A concept's format (an ad's plugin.axes.format, an organic brief's organic.format), as words, to the channel type
# and tone `atlas_prompt.ranked` takes: the first row with a word in it wins.
FORMAT_RANKS = (
    (("screen recording", "screencast", "demo", "tutorial", "how to", "how-to", "walkthrough", "explainer", "tips"),
     "howto_education", ("technical", "calm")),
    (("ugc", "phone video", "unboxing", "review", "haul", "before and after", "comparison", "product"),
     "shop_product", ("raw", "bold")),
    (("talking head", "selfie", "testimonial", "confession", "vlog", "story", "day in", "routine", "interview"),
     "lifestyle_vlog", ("warm", "friendly")),
    (("skit", "pov", "comedy", "meme", "prank", "sketch", "reaction"), "entertainment_skits", ("playful", "bold")),
    (("news", "stat", "stats", "data", "chart", "ranking", "quiz", "list", "facts"), "news_explainers",
     ("serious", "bold")),
    (("dance", "music", "song", "lip sync", "lip-sync", "transition"), "music_dance", ("bold", "edgy")),
)
REASONS = {"given": "the style asked for", "channel": "the channel's own style", "type": "it suits this format",
           "tone": "its tone fits this format", "other": "the library's next free style",
           "rejected": "the library's next free style"}


def style_of(concept: object) -> str | None:
    """The library style a concept's animatic is drawn in (`animatic.style`), or None: none chosen yet, so no animatic
    can be drawn for it."""
    a = concept.get("animatic") if isinstance(concept, dict) else None
    s = a.get("style") if isinstance(a, dict) else None
    return s.strip() if isinstance(s, str) and s.strip() else None


def concept_format(concept: dict) -> str | None:
    """The concept's format in words: an organic brief's `organic.format`, else an ad's `plugin.axes.format`."""
    organic = concept.get("organic") if isinstance(concept.get("organic"), dict) else {}
    axes = ((concept.get("plugin") or {}).get("axes") or {}) if isinstance(concept.get("plugin"), dict) else {}
    for value in (organic.get("format"), axes.get("format") if isinstance(axes, dict) else None):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def rank_args(fmt: str | None) -> tuple[str | None, tuple[str, ...]]:
    """(channel type, tone words) for `atlas_prompt.ranked` from a format in words (FORMAT_RANKS); (None, ()) for one
    it does not know: the library's order."""
    text = (fmt or "").lower()
    for words, kind, tone in FORMAT_RANKS:
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return kind, tone
    return None, ()


def _card(key: object) -> dict:
    """A library style by its number, styleId or `<number> <name>`; a ValueError names the closest."""
    sid = atlas_prompt.style_id(key)
    return atlas_prompt.find_style(sid if sid else str(key).strip())


def choose_styles(brief: dict, concepts: list[str], given: str | None = "auto", own: object = None) -> dict[str, dict]:
    """{concept id: its style card with `reason`}: `given` (a number or styleId) for every concept named, else each
    concept's first style in `atlas_prompt.ranked` for its format (`rank_args`), the channel's own style (`own`)
    first, else one no other concept of the brief has (three formats get three looks). A ValueError for an unknown
    style."""
    if given not in (None, "auto"):
        card = _card(given)
        return {cid: {**card, "reason": "given"} for cid in concepts}
    own_id = _card(own)["styleId"] if own is not None else None
    listed = [x for x in brief.get("concepts") or [] if isinstance(x, dict)]
    taken = [sid for x in listed if x.get("id") not in concepts and (sid := atlas_prompt.style_id(style_of(x)))]
    out: dict[str, dict] = {}
    for x in listed:
        if x.get("id") not in concepts:
            continue
        kind, tone = rank_args(concept_format(x))
        ranked = atlas_prompt.ranked(channel_type=kind, tone=tone, own=own_id)
        pick = ranked[0] if own_id else next((s for s in ranked if s["styleId"] not in taken), ranked[0])
        taken.append(pick["styleId"])
        out[x["id"]] = pick
    return out


def _pictures(run: RunFolder, rel: str, concept: dict) -> dict[str, Path]:
    """The product pictures a styled concept's beats name (`params.image`, a file of the run), by the first beat that
    shows each (`beat2`), for `atlas_prompt.module_page`; Stop for one that is not a picture of the run a page holds."""
    out: dict[str, Path] = {}
    for k, beat in enumerate(concept.get("beats") or [], 1):
        params = ((beat.get("animatic") or {}).get("params") or {}) if isinstance(beat, dict) else {}
        if not isinstance(params, dict) or "image" not in params:
            continue
        path = _image(run, params["image"])
        if path is None or path.suffix.lower() not in atlas_prompt.PICTURE_TYPES:
            kinds = ", ".join(t.lstrip(".") for t in atlas_prompt.PICTURE_TYPES)
            raise Stop(f"{rel}: {concept['id']} beat {k} names the image {params['image']!r}. A beat's image is a "
                       f"picture of the product kept in the run ({kinds}, up "
                       f"to {IMAGE_MAX // (1024 * 1024)} MiB), named by its path from the run folder, like "
                       "01_base/product.png; or leave it out. Fix it (a new version), then make the animatics again. "
                       f"Nothing was written. {AGAIN}")
        if path not in out.values():
            out[f"beat{k}"] = path
    return out


def _says(text: object) -> str:
    return " ".join(str(text).split()) if isinstance(text, (str, int, float)) else ""


def content(brief: dict, concept: dict) -> str:
    """The concept as the build prompt's topic: what it is, its format and hook, then each beat (its times, what is
    seen and heard, its on-screen texts word for word)."""
    meta = brief.get("meta") if isinstance(brief.get("meta"), dict) else {}
    product = _says((meta.get("product") or {}).get("name")) if isinstance(meta.get("product"), dict) else ""
    kind = "an organic video" if meta.get("kind") == "organic" else "an ad"
    beats = [b for b in concept.get("beats") or [] if isinstance(b, dict)]
    length = concept.get("length_s") or (beats[-1].get("t1") if beats else None)
    lines = [f"The concept: {kind}" + (f" for {product}" if product else "") + f', "{_says(concept.get("title"))}".'
             + (f" {_says(concept.get('one_liner'))}" if concept.get("one_liner") else "")]
    if concept_format(concept):
        lines.append(f"Its format: {concept_format(concept)}.")
    hook = concept.get("hook") if isinstance(concept.get("hook"), dict) else {}
    if hook.get("text"):
        where = _says(hook.get("style")) or "center"
        lines.append(f'The hook, on screen from the first frame: "{_says(hook["text"])}" ({where}).')
    starts = ", ".join(f"{b.get('t0', 0):g}" for b in beats)
    lines.append(f"Length: {length:g} s, in {len(beats)} beats; beats: [{starts}]." if isinstance(length, (int, float))
                 else f"{len(beats)} beats; beats: [{starts}].")
    for k, b in enumerate(beats, 1):
        anim = b.get("animatic") if isinstance(b.get("animatic"), dict) else {}
        label = _says(anim.get("label"))
        lines += ["", f"Beat {k}, {b.get('t0', 0):g} to {b.get('t1', 0):g} s" + (f" ({label})" if label else "") + ":"]
        if b.get("see"):
            lines.append(f"- Seen: {_says(b['see'])}")
        if b.get("hear"):
            lines.append(f"- Heard: {_says(b['hear'])}")
        texts = [x for x in anim.get("texts") or [] if isinstance(x, (dict, str))]
        for x in texts:
            words, where = (x, "center") if isinstance(x, str) else (x.get("str"), x.get("style") or "center")
            at = "" if isinstance(x, str) or x.get("at") is None else f", from {x['at']:g} s"
            if _says(words):
                lines.append(f'- On screen, word for word: "{_says(words)}" ({where}{at})')
        if not texts and b.get("ost"):
            lines.append(f'- On screen, word for word: "{_says(b["ost"])}"')
    return "\n".join(lines)


def _extra(drawn: list[str]) -> str:
    """The build prompt's extra rule when the module is drawn in a second format too."""
    rest = [f for f in drawn[1:]]
    if not rest:
        return ""
    frames = " and ".join(f"{atlas_prompt.frame(ASPECTS[f])[0]}x{atlas_prompt.frame(ASPECTS[f])[1]} "
                          f"({ASPECTS[f]})" for f in rest)
    return (f"- The same module is drawn at {frames} as well: lay every beat out from W and H (`Brush.frame(W, H)`), "
            "so it composes for each frame, never a crop of the first; check it in each.")


def _poster(run: RunFolder, card: dict) -> str:
    """The style's poster copied into the renders folder (where the page finds it); its path as the brief names it."""
    name = f"style_{card['order']:02d}_{card['styleId']}.jpg"
    src, dest = atlas_prompt.preview_files(card)[0], run.path / RENDERS / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not (dest.is_file() and dest.read_bytes() == src.read_bytes()):
        tmp = dest.with_name(f".{name}.{os.getpid()}.tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    return f"{PAGE_DIR}/{name}"


def _number(path: Path) -> int:
    m = re.search(r"_v(\d+)\.\w+$", path.name)
    return int(m.group(1)) if m else 0


def style(run: RunFolder, brief_path: Path | None, *, concepts: list[str] | None = None, given: str | None = "auto",
          own: object = None, formats: list[str] | None = None) -> dict:
    """`tm brief animatic --style`: each concept named (default: all) gets its library style (`choose_styles`) in a
    new brief version, as `animatic.style` with its poster (`animatic.poster`, copied beside the renders; earlier MP4s
    are left out), and a build prompt `03_wip/animatic/<C>_prompt_vNN.txt` (`atlas_prompt.build`, the
    animatic mode, at the first format's frame) for the subagent that writes the style module `<C>_style_vNN.js`.
    {brief, formats, styles: [{concept, style, name, reason, why, poster, prompt, module}]}. ValueError for an
    unknown style or concept, Stop for a brief or picture that cannot be drawn: nothing is written then."""
    from tm import brief_page   # brief_page -> brief_checks -> this module

    _, rel, brief = brief_page.load_brief(run, brief_path)
    drawn = formats_of(run) if formats is None else _checked_formats(formats, "--formats")
    named = [concept["id"] for concept in _concepts(rel, brief, concepts)]
    picked = choose_styles(brief, named, given, own)
    pictures = {x["id"]: _pictures(run, rel, x) for x in brief["concepts"]
                if isinstance(x, dict) and x.get("id") in picked}
    new = copy.deepcopy(brief)
    for concept in new["concepts"]:
        card = picked.get(concept.get("id")) if isinstance(concept, dict) else None
        if card is None:
            continue
        before = concept["animatic"] if isinstance(concept.get("animatic"), dict) else {}
        kept = {"default": before["default"]} if before.get("default") in FORMATS else {}
        concept["animatic"] = {**kept, "style": card["styleId"], "poster": _poster(run, card)}
    target = run.next_version(FINAL, STEM, "json")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_new(target, json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    out = _rel(run, target)
    manifest.record(run, out, FINAL, STYLE_SOURCE, parent=rel,
                    params={"animatic_styles": {cid: card["styleId"] for cid, card in picked.items()}})
    (run.path / WIP).mkdir(parents=True, exist_ok=True)
    rows = []
    for concept in new["concepts"]:
        card = picked.get(concept.get("id")) if isinstance(concept, dict) else None
        if card is None:
            continue
        cid = concept["id"]
        pics = [{"name": name, "file": _rel(run, path), "what": "the product",
                 **dict(zip(("width", "height"), atlas_prompt.picture_size(path) or ()))}
                for name, path in pictures[cid].items()]
        beats = [b for b in concept.get("beats") or [] if isinstance(b, dict)]
        length = concept.get("length_s") or (beats[-1].get("t1") if beats else None)
        text = atlas_prompt.build(card, content=content(new, concept), aspect=ASPECTS[drawn[0]], extra=_extra(drawn),
                                  duration=length if isinstance(length, (int, float)) else None,
                                  animatic={"pictures": pics})
        prompt = run.next_version(WIP, f"{cid}_prompt", "txt")
        module = f"{WIP}/{cid}_style_v{_number(prompt):02d}.js"
        write_new(prompt, text)
        manifest.record(run, _rel(run, prompt), "03_wip", STYLE_SOURCE, parent=out, cost="0",
                        params={"style": card["styleId"], "formats": drawn, "module": module,
                                "pictures": {p["name"]: p["file"] for p in pics}})
        rows.append({"concept": cid, "style": card["styleId"], "name": card["name"], "reason": card["reason"],
                     "why": REASONS.get(card["reason"], ""), "poster": concept["animatic"]["poster"],
                     "prompt": _rel(run, prompt), "module": module})
    return {"brief": out, "formats": drawn, "styles": rows}


def _prompt_row(run: RunFolder, rel: str) -> dict:
    """The params of the style step's row for the build prompt `rel` ({} without one)."""
    for row in reversed(manifest.rows(run)):
        if row["source"] == STYLE_SOURCE and row["file"] == rel:
            try:
                params = json.loads(row["params"]) if row["params"] else {}
            except ValueError:
                params = {}
            return params if isinstance(params, dict) else {}
    return {}


def _styled_module(run: RunFolder, rel: str, concept: dict) -> dict:
    """The style module a styled concept is drawn from: the latest `<C>_style_vNN.js`, written from the concept's
    latest build prompt in its style, with one beat per beat of the brief (the brief's beats are its own: no frames
    list is read). {file, code, style, pictures}; Stop when there is none yet, or it does not fit, before anything is
    written."""
    from tm.organic import module_beats   # the parse atlas-page uses (issue 141): a literal `beats: [...]`

    cid, given = concept["id"], style_of(concept)
    sid = atlas_prompt.style_id(given)
    if sid is None:
        raise Stop(f"{rel}: {cid}'s animatic.style {given!r} is not one of the library's styles. Choose it again with "
                   f"tm brief animatic --style auto --concepts {cid}, then render. Nothing was written. {AGAIN}")
    card = atlas_prompt.find_style(sid)
    prompt = run.latest(WIP, f"{cid}_prompt", "txt")
    made = _prompt_row(run, _rel(run, prompt)) if prompt is not None else {}
    if prompt is None or made.get("style") != sid:
        raise Stop(f"{cid}'s animatic is drawn in {card['name']}, and it has no build prompt in that style yet: make "
                   f"it with tm brief animatic --style {sid} --concepts {cid}, have a subagent write the style module "
                   f"from it, then render. Nothing was written. {AGAIN}")
    want = made.get("module") or f"{WIP}/{cid}_style_v{_number(prompt):02d}.js"
    module = run.latest(WIP, f"{cid}_style", "js")
    if module is None or _number(module) < _number(prompt):
        raise Stop(f"{cid}'s animatic is drawn in {card['name']}: have a subagent write its style module {want} from "
                   f"{_rel(run, prompt)} first (the build prompt says how), then render again. Nothing was written. "
                   f"{AGAIN}")
    code = module.read_text(encoding="utf-8-sig")
    pictures = _pictures(run, rel, concept)
    beats = module_beats(code) or _page_beats(code, pictures)
    count = len([b for b in concept.get("beats") or [] if isinstance(b, dict)])
    if beats is not None and len(beats) != count:       # not known (no literal list, no browser): drawn as it is
        nxt = f"{WIP}/{cid}_style_v{_number(module) + 1:02d}.js"
        raise Stop(f"{_rel(run, module)} has {len(beats)} beats and {cid} has {count} beats in the brief: give the "
                   f"module one beat per beat of the brief (`beats: [...]`, their start times), in a new version "
                   f"({nxt}), then render again. Nothing was written. {AGAIN}")
    return {"file": _rel(run, module), "code": code, "style": card, "pictures": pictures}


def _page_beats(code: str, pictures: dict[str, Path]) -> list | None:
    """A module's beats as its page registers them (the layout check runs it, as `tm organic atlas-page` does), for a
    module whose `beats` is not a literal list; None when it cannot run."""
    if atlas.missing() is not None:
        return None
    with tempfile.TemporaryDirectory(prefix="tm-beats-") as tmp:
        page_path = Path(tmp) / "module.html"
        page_path.write_text(atlas_prompt.module_page(code, "beats", ASPECTS["9x16"], pictures=pictures),
                             encoding="utf-8")
        try:
            beats = atlas.layout(page_path).get("beats")
        except (c.ToolStop, c.ToolError, AttributeError):
            return None
    return beats if isinstance(beats, list) else None


def _layout_problems(page_path: Path) -> list[str]:
    """What the layout check finds on a styled page (atlas.layout); none when it cannot run: never a stop."""
    try:
        return atlas.layout_problems(atlas.layout(page_path))
    except (c.ToolStop, c.ToolError, ValueError, KeyError, TypeError):
        return []


def _styled_pages(run: RunFolder, concept: dict, module: dict, drawn: list[str], version: str,
                  render: bool) -> list[dict]:
    """A styled concept's page per format, `<C>_<fmt>_<ver>.html`: its style module with the libraries and its
    pictures inlined (`atlas_prompt.module_page`, play mode, the format's frame). With `render`, each page's layout
    problems."""
    cid, sid = concept["id"], module["style"]["styleId"]
    out = []
    for fmt in drawn:
        html = run.path / WIP / f"{cid}_{fmt}_{version}.html"
        write_new(html, atlas_prompt.module_page(module["code"], f"{cid} animatic {fmt}", ASPECTS[fmt],
                                                 pictures=module["pictures"]))
        manifest.record(run, _rel(run, html), "03_wip", SOURCE, parent=module["file"], params={"format": fmt,
                                                                                              "style": sid})
        item = {"concept": cid, "format": fmt, "version": version, "html": _rel(run, html), "style": sid}
        if render:
            item.update(layout_problems=_layout_problems(html))
        out.append(item)
    return out


def build(run: RunFolder, brief_path: Path, *, concepts: list[str] | None = None,
          formats: list[str] | None = None, version: str | None = None, render: bool = False,
          fps: int = atlas.FPS) -> list[dict]:
    """`tm brief animatic`: each concept's (default: all) page per format (default: `formats_of`) from its style
    module, as version `version` (default: the next free one), and with `render` the MP4s and a new brief that names
    them. One dict per page: concept, format, version, html, style, and with `render` layout_problems, mp4, stills,
    render_s, page_errors and brief. Stop for a concept with no style or no module that fits, or a renderer that is
    not there, ValueError for a bad argument or a version already used: nothing is written then."""
    from tm import brief_page   # brief_page -> brief_checks -> this module

    _, rel, brief = brief_page.load_brief(run, brief_path)
    drawn = formats_of(run) if formats is None else _checked_formats(formats, "--formats")
    listed = _concepts(rel, brief, concepts)
    unstyled = [concept["id"] for concept in listed if not style_of(concept)]
    if unstyled:
        raise _no_style(rel, unstyled)
    modules = {concept["id"]: _styled_module(run, rel, concept) for concept in listed}
    folder = run.path / WIP
    version = _version(folder, version)
    if render:
        try:
            atlas.need()                          # the tier, its setup and a browser, before any file
        except c.ToolStop as exc:
            raise Stop(str(exc)) from None
    folder.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for concept in listed:
        items += _styled_pages(run, concept, modules[concept["id"]], drawn, version, render)
    if render:
        _render(run, items, version, fps)
        new = _brief_with_renders(run, rel, brief, items, drawn, version)
        for item in items:
            item["brief"] = new
    return items


def _rendered(run: RunFolder, ref: object) -> bool:
    from tm import brief_page   # brief_page -> brief_checks -> this module
    if not isinstance(ref, str) or not ref.lower().endswith(".mp4"):
        return False
    return brief_page.find_media(run, ref, (RENDERS,)) is not None


def not_rendered(run: RunFolder, concepts: dict[str, dict], ids: list[str], formats: list[str]) -> list[str]:
    """"<id> <format>" for each of the concepts (id -> concept) whose `animatic` names no MP4 of that
    format in 03_wip/animatic/renders/."""
    out = []
    for cid in ids:
        a = (concepts.get(cid) or {}).get("animatic")
        out += [f"{cid} {fmt}" for fmt in formats if not _rendered(run, a.get(fmt) if isinstance(a, dict) else None)]
    return out


def wanted(run: RunFolder) -> list[str]:
    """The concepts whose animatics the user asked for (issue #145): the latest `animatics` decision's `make`
    concepts; none on `skip`, or before it is decided. A run started before animatics were on request has its
    concepts recorded there (tm.state); a run with no `animatics` decision at all falls back to its chosen
    concepts, as before."""
    s = state.load(run)
    last = next((d for d in reversed(s.decisions) if isinstance(d, dict) and d.get("checkin") == "animatics"), None)
    if last is None:
        return list(((s.brief or {}).get("chosen") or {}).get("concepts") or [])
    named = last.get("concepts") if last.get("choice") == "make" else None
    return [c for c in named if isinstance(c, str)] if isinstance(named, list) else []


def rendered_gap(run: RunFolder) -> str | None:
    """`animatics_rendered` (D2, on `animatics make`): each concept the user named (`wanted`) is in the latest
    brief and names an MP4 per format (`formats_of`), each in 03_wip/animatic/renders/. The other concepts need
    none."""
    chosen = wanted(run)
    if not chosen:
        return ("the concepts whose animatics the user asked for are named (tm decide animatics make --concepts "
                "C1,C3) and drawn in their styles (tm brief animatic --style auto --concepts C1,C3, a subagent's style "
                "module per concept, then tm brief animatic --render --concepts C1,C3)")
    latest = run.latest(FINAL, STEM, "json")
    if latest is None:
        return f"{FINAL}/{STEM}_vNN.json is written and its animatics rendered (tm brief animatic --render)"
    try:
        concepts = {x["id"]: x for x in json.loads(latest.read_text(encoding="utf-8-sig"))["concepts"]}
    except (ValueError, KeyError, TypeError):
        return f"the latest {STEM}, {latest.name}, is readable, with the named concepts' animatics in it"
    gone = [c for c in chosen if c not in concepts]
    if gone:
        return (f"the concepts named for animatics are in the latest brief ({latest.name} has no {', '.join(gone)}): "
                "name them again (tm decide animatics make --change --concepts ...)")
    try:
        drawn = formats_of(run)
    except ValueError as exc:
        return f"the formats to draw are known: {exc}"
    missing = not_rendered(run, concepts, chosen, drawn)
    if missing:
        return (f"every concept named for animatics in {latest.name} names its MP4 in each format ({', '.join(drawn)}), "
                f"rendered into {RENDERS} (tm brief animatic --render); missing: {', '.join(missing)}")
    return None
