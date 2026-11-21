"""The animatics of a creative brief (CB11), shared by the playbooks: the port of the handoff's
`build_animatic.py`.

    scene_names()                 the scenes `scenes.js` draws (`tm brief check` takes only these)
    build_anim(concept)           a concept's `window.ANIM` (the handoff's, verbatim)
    build(run, brief_path, ...)   `tm brief animatic`: the storyboard files, and with `render` the MP4s
    formats_of(run), fps_of(run)  the formats drawn (`animatic.formats`, the audience pick's, or both), the fps
    not_rendered(run, ...)        the concepts' formats with no MP4 in the renders folder
    rendered_gap(run)             the step check `animatics_rendered`
    choose_styles(brief, ids)     each concept's library style, ranked for its format (issue #138 item 4)
    style(run, brief_path, ...)   `tm brief animatic --style`: the styles in a new brief, a build prompt per concept
    minutes_per_concept()         about how long a styled animatic takes here

The sketch (scenes.js) is the default. A styled animatic is an option (owner decision #148 line 2), made only when
the user asks for one: `style` (`tm brief animatic --style`) writes each named concept's
`animatic.style` (the styleId, chosen by `atlas_prompt.ranked` from the concept's format, no two concepts alike, the
channel's own style first with `own`) and `animatic.poster` (the style's poster, copied into renders/), and a build
prompt `<C>_prompt_vNN.txt` (`atlas_prompt.build`, the animatic mode). A subagent writes the style module
`<C>_style_vNN.js`; `build` draws a concept with a style from its latest module (written from its latest prompt, one
beat per beat of the brief: the brief's beats are its own, no frames list is read), a page per format through
`atlas_prompt.module_page`, rendered by `atlas.render`; the hook probe and scenes.js are the sketch's alone. A concept
with no style is drawn as the sketch, exactly as described below. Each styled render's time
per concept is kept in the plugin data folder (`TIMING`).

The handoff's animatic engine and scene library are copied (LF) into `animatic_js/`; the folder is
not named `animatic/`, which would sit beside this module. One change to them (issue #12): the
product scenes draw a generic product screen (`K.productScreen`: the product's name, what is on
its screen, a picture of it), the dry run's book only as a fixture (`params.fixture: "book"`). A
brief's beats name their scene (`beats[].animatic.scene`); a beat's `params.image`, a picture in
the run, is inlined into the storyboard as a data URI (`with_images`).

`build` writes, per concept, `03_wip/animatic/<C>_anim_<ver>.js` (`window.ANIM`) and a page
`<C>_<fmt>_<ver>.html` per format, beside copies of `engine.js` and `scenes.js`, so the folder
draws on its own. With `render`, before any file is written, each hook (a text at `top`, `center`
or `bottom`) is kept clear of what its beat draws (issue #139): `probe` draws every beat with node
and a measuring canvas (`animatic_js/probe.js`; the scenes `K.mark` faces, screens and the brand's
name), and `fit_hooks` moves a hook that covers one to the free place, else makes it smaller; the
items' `hook_changes` say what changed, and a check that cannot run is said, never a stop. A version is never used twice (the next free `vNN` by default). With `render`,
`atlas.render` draws each page into `03_wip/animatic/renders/<C>_animatic_<fmt>_<ver>.mp4` with
its stills, and a new `04_final/brief_pack_vNN.json` names them (`animatic/<file>`, the page's
paths). Nothing is written when a beat has no scene or the renderer is not there (a Stop). The
port's changes: a Stop or ValueError for the original's `sys.exit`; the version is checked for the
whole folder, before anything is written; paths in the answer are run-relative.
"""

from __future__ import annotations

import base64
import copy
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

from tm import atlas, atlas_prompt, config, manifest, paths, state
from tm.runfolder import RunFolder
from tm.stops import AGAIN_SENTENCE, Stop
from tm.tools import _common as c

JS_DIR = Path(__file__).parent / "animatic_js"
SCENES_JS = JS_DIR / "scenes.js"
LIBRARY = ("engine.js", "scenes.js")
WIP = "03_wip/animatic"
RENDERS = f"{WIP}/renders"            # where the renders go, and where the page finds them
PAGE_DIR = "animatic"                 # the brief's path of a render, as the page serves it
FINAL, STEM = "04_final", "brief_pack"
FORMATS = ("9x16", "4x5")
SOURCE = "tm brief animatic"
MODEL = "atlas render.mjs"
AGAIN = AGAIN_SENTENCE
_NOTHING = "Nothing was rendered."      # atlas's words in each of its stops
_SCENES_START = "window.SCENES = {"
# a scene is a top-level member of window.SCENES: `name(K, p, ...) {` or `name: (...) =>`
_SCENE = re.compile(r"^  ([A-Za-z_$][\w$]*)\s*[(:]", re.MULTILINE)
_ID = re.compile(r"[A-Za-z0-9_-]+")                       # brief_page's concept ids: they name files here
_VERSION = re.compile(r"^v(\d+)$")
_VERSIONED = re.compile(r"_v(\d+)\.(?:js|html|mp4)$")   # a storyboard file or render of a version
# a product picture a beat draws (`params.image`, issue #12): a file of the run, inlined into the
# storyboard as a data URI, so the page draws it from anywhere and its canvas can still be read
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}
IMAGE_MAX = 2 * 1024 * 1024
_HTML = ('<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>{0} animatic {1}</title></head><body>\n'
         '<script>window.FMT="{1}";</script>\n<script src="scenes.js"></script>\n'
         '<script src="{2}"></script>\n<script src="engine.js"></script>\n</body></html>\n')


def scene_names(path: Path = SCENES_JS) -> set[str]:
    """The scenes `scenes.js` draws: the keys of its `window.SCENES` object. ValueError for a file
    without that object (a broken copy)."""
    text = Path(path).read_text(encoding="utf-8")
    start = text.find(_SCENES_START)
    if start < 0:
        raise ValueError(f"{Path(path).name} has no {_SCENES_START!r}, so its scenes are unknown.")
    return set(_SCENE.findall(text[start + len(_SCENES_START):]))


# --- the handoff's ------------------------------------------------------------------------------

class MissingScene(ValueError):
    """A beat without `animatic.scene`."""


def vo_text(hear: str) -> str:
    h = (hear or '').strip()
    return ('VO: ' + h) if h.startswith('"') else h


def build_anim(concept: dict) -> dict:
    beats = []
    for i, b in enumerate(concept['beats'], 1):
        a = b.get('animatic')
        if not a or not a.get('scene'):
            raise MissingScene(f"{concept['id']} beat {i}: missing animatic.scene")
        beats.append({
            't0': b['t0'], 't1': b['t1'],
            'label': f"BEAT {i} · {a.get('label', '').upper()}".rstrip(' ·'),
            'scene': a['scene'], 'params': a.get('params', {}),
            'zoom': a.get('zoom', [1, 1.04]),
            'texts': a.get('texts', []),
            'vo': vo_text(b.get('hear', '')),
        })
    dur = concept.get('length_s') or concept['beats'][-1]['t1']
    return {'id': concept['id'], 'duration': dur, 'beats': beats}


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


def _anims(rel: str, brief: dict, concepts: list[str] | None,
           sketch: bool = True) -> list[tuple[dict, dict | None]]:
    """(concept, its window.ANIM) for the concepts asked for (default: all), before anything is written; None for a
    concept drawn in a library style (`style_of`), which has no window.ANIM, and for every concept without `sketch`
    (the style step, which only checks the ids)."""
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
        return [(x, None if style_of(x) or not sketch else build_anim(x)) for x in listed
                if not concepts or x["id"] in concepts]
    except MissingScene as exc:
        raise Stop(f"{rel}: {exc}. Give every beat its scene (beats[].animatic.scene, one that scenes.js draws), "
                   f"write the brief again (a new version), then make the animatics again. Nothing was written. "
                   f"{AGAIN}") from None
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise Stop(f"{rel} is not in its shape ({type(exc).__name__}: {exc}), so no animatic can be drawn from it. "
                   f"Check it with tm brief check, fix it (a new version), then make the animatics again. Nothing "
                   f"was written. {AGAIN}") from None


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


def with_images(run: RunFolder, rel: str, anim: dict) -> dict:
    """`anim` with each beat's `params.image` (a path in the run) as a data URI; Stop for one that
    is not an image file of the run, before anything is written."""
    out = copy.deepcopy(anim)
    for i, beat in enumerate(out["beats"], 1):
        params = beat.get("params")
        if not isinstance(params, dict) or "image" not in params:
            continue
        path = _image(run, params["image"])
        if path is None:
            raise Stop(f"{rel}: {anim['id']} beat {i} names the image {params['image']!r}. A beat's image is a picture "
                       f"of the product kept in the run ({', '.join(t.lstrip('.') for t in IMAGE_TYPES)}, up to "
                       f"{IMAGE_MAX // (1024 * 1024)} MiB), named by its path from the run folder, like "
                       "01_base/product.png; or leave it out. Fix it (a new version), then make the animatics again. "
                       f"Nothing was written. {AGAIN}")
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        params["image"] = f"data:{IMAGE_TYPES[path.suffix.lower()]};base64,{data}"
    return out


def write_new(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as fh:     # never over an earlier file
        fh.write(text)


# --- the hook clear of what the scene draws (issue #139) --------------------------------------------

PROBE_JS = JS_DIR / "probe.js"
PLACES = ("top", "center", "bottom")
MARGIN = 12                     # px between a hook and what it must not cover
MARKED = {"face": "the face", "screen": "the product screen", "brand": "the brand's name"}


def probe(anim: dict, fmt: str) -> dict:
    """What each beat of `anim` draws that a hook must keep clear of, and each hook's box at each place and size, in
    format `fmt` (probe.js, run by the `video` environment's node, as the renderer is). A ToolError when it cannot
    run."""
    from tm import render as remotion

    with tempfile.TemporaryDirectory(prefix="tm-hooks-") as tmp:
        js = Path(tmp) / "anim.js"
        js.write_text("window.ANIM = " + json.dumps(anim, ensure_ascii=False) + ";\n", encoding="utf-8")
        argv = [*remotion._prefix(), "node", str(PROBE_JS), str(SCENES_JS), str(js), str(JS_DIR / "engine.js"), fmt]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=180, env=remotion._env())
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise c.ToolError(f"the hook check could not start ({exc})") from None
    lines = [x for x in (proc.stdout or "").splitlines() if x.strip()]
    if proc.returncode != 0 or not lines:
        tail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
        raise c.ToolError(f"the hook check failed: {tail}")
    return json.loads(lines[-1])


def covers(a: list, b: list, margin: int = MARGIN) -> bool:
    """Two [x, y, w, h] boxes meet, `margin` px around them counted."""
    return (a[0] < b[0] + b[2] + margin and b[0] < a[0] + a[2] + margin
            and a[1] < b[1] + b[3] + margin and b[1] < a[1] + a[3] + margin)


def fit_hooks(anim: dict, found: dict) -> tuple[dict, list[str]]:
    """(the animatic with each hook clear of what its beat draws, what was changed in words). A hook that covers a
    face, the product screen or the brand's name (`probe`) moves to the first free place (its own first, then top,
    center, bottom), else is made smaller step by step (x 0.85, never under 32) at the first place it clears; one
    that clears nowhere stays, and is named."""
    out = copy.deepcopy(anim)
    changes: list[str] = []
    for n, (beat, seen) in enumerate(zip(out["beats"], found.get("beats") or []), 1):
        marks = [m for m in seen.get("marks") or [] if isinstance(m, dict)]
        for text in seen.get("texts") or []:
            o = beat["texts"][text["index"]]
            place, boxes = o.get("style"), text["boxes"]

            def hit(where: str, step: int) -> list[str]:
                return [m["kind"] for m in marks if covers(boxes[where][step][1], m["box"])]

            now = hit(place, 0)
            if not now:
                continue
            what = MARKED.get(now[0], now[0])
            said = f"{anim['id']} beat {n}: the hook \"{o.get('str', '')}\""
            order = [place] + [p for p in PLACES if p != place]
            fix = next(((p, step) for step in range(len(boxes[place])) for p in order
                        if (p, step) != (place, 0) and step < len(boxes[p]) and not hit(p, step)), None)
            if fix is None:
                changes.append(f"{said} still covers {what}: no place or size clears it, so change the scene or "
                               "the text")
                continue
            where, step = fix
            size, new = boxes[place][0][0], boxes[where][step][0]
            o["style"] = where
            if step:
                o["size"] = new
            moved = f"moved from {place} to {where}" if where != place else ""
            smaller = f"made smaller ({size} to {new})" if step else ""
            changes.append(f"{said} {' and '.join(x for x in (moved, smaller) if x)} (it covered {what})")
    return out, changes


def _clear_hooks(anim: dict, formats: list[str], said: list[str]) -> dict:
    """`anim` with its hooks clear in each format drawn (`probe`, `fit_hooks`), in turn; what changed goes to `said`.
    A check that cannot run is said, and never stops the render."""
    for fmt in formats:
        try:
            anim, changes = fit_hooks(anim, probe(anim, fmt))
        except (c.ToolError, ValueError, KeyError, TypeError, IndexError) as exc:
            said.append(f"{anim['id']} {fmt}: {exc}; look at its stills for a hook over the screen or a face")
            continue
        said += [x for x in changes if x not in said]
    return anim


def _copy_library(folder: Path) -> None:
    """engine.js and scenes.js beside the pages, so the folder draws on its own (the plugin's copy)."""
    for name in LIBRARY:
        src, dest = JS_DIR / name, folder / name
        if dest.is_file() and dest.read_bytes() == src.read_bytes():
            continue
        tmp = dest.with_name(f".{name}.{os.getpid()}.tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)


def _render(run: RunFolder, items: list[dict], version: str, fps: int) -> None:
    """Each page drawn into renders/ with its stills, each file with a manifest row."""
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


def _brief_with_renders(run: RunFolder, rel: str, brief: dict, items: list[dict], formats: list[str],
                        version: str) -> str:
    """A new 04_final/brief_pack_vNN.json: each rendered concept's `animatic` names its MP4s. Its
    `default` (the format the page plays first) stays the concept's own when that one was drawn,
    else the first format drawn."""
    paths: dict[str, dict] = {}
    for item in items:
        paths.setdefault(item["concept"], {})[item["format"]] = f"{PAGE_DIR}/{Path(item['mp4']).name}"
    new = copy.deepcopy(brief)
    for concept in new["concepts"]:
        if isinstance(concept, dict) and concept.get("id") in paths:
            drawn = paths[concept["id"]]
            before = concept["animatic"] if isinstance(concept.get("animatic"), dict) else {}
            own = before.get("default")
            default = own if isinstance(own, str) and own in drawn else formats[0]
            kept = {k: before[k] for k in STYLE_KEYS if k in before}       # a styled concept's style and poster
            concept["animatic"] = {**drawn, "default": default, **kept}
    target = run.next_version(FINAL, STEM, "json")
    write_new(target, json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    out = _rel(run, target)
    manifest.record(run, out, FINAL, SOURCE, parent=rel, params={"animatics": version})
    return out


# --- an animatic in a library style (issue #138 item 4, owner decision #148 line 2) ----------------------------------

STYLE_KEYS = ("style", "poster")        # a styled concept's `animatic` keeps them through a render
STYLE_SOURCE = "tm brief animatic --style"
ASPECTS = {"9x16": "9:16", "4x5": "4:5"}
DEFAULT_MINUTES = 3                     # a styled animatic per concept before this computer drew one (measured)
TIMING = "animatic_timing.json"         # in the plugin data folder: this computer's last styled render
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
    """The library style a concept's animatic is drawn in (`animatic.style`), or None: drawn as the sketch."""
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
    new brief version, as `animatic.style` with its poster (`animatic.poster`, copied beside the renders; a sketch's
    earlier MP4s are left out), and a build prompt `03_wip/animatic/<C>_prompt_vNN.txt` (`atlas_prompt.build`, the
    animatic mode, at the first format's frame) for the subagent that writes the style module `<C>_style_vNN.js`.
    {brief, formats, styles: [{concept, style, name, reason, why, poster, prompt, module}]}. ValueError for an
    unknown style or concept, Stop for a brief or picture that cannot be drawn: nothing is written then."""
    from tm import brief_page   # brief_page -> brief_checks -> this module

    _, rel, brief = brief_page.load_brief(run, brief_path)
    drawn = formats_of(run) if formats is None else _checked_formats(formats, "--formats")
    named = [concept["id"] for concept, _ in _anims(rel, brief, concepts, sketch=False)]
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
            item.update(hook_changes=[], layout_problems=_layout_problems(html))
        out.append(item)
    return out


def _record_time(items: list[dict], elapsed: float) -> None:
    """This computer's time per concept of a call that drew a styled one (its formats, layout checks and renders
    together: the call's time over its concepts, at least a concept's own render time), for the question's minutes
    (`minutes_per_concept`). Not kept when the plugin data folder is not there: never a stop."""
    per: dict[str, float] = {}
    for item in items:
        if isinstance(item.get("render_s"), (int, float)):
            per[item["concept"]] = per.get(item["concept"], 0.0) + float(item["render_s"])
    if not per or not any(item.get("style") for item in items):
        return
    seconds = max(elapsed / len(per), sum(per.values()) / len(per))
    try:
        path = paths.data_dir() / TIMING
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{TIMING}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"seconds_per_concept": round(seconds, 1), "concepts": len(per)}) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
    except (OSError, RuntimeError):
        return


def minutes_per_concept() -> tuple[int, bool]:
    """(about how many minutes a styled animatic takes per concept on this computer, measured): the last styled render's
    time, rounded up; DEFAULT_MINUTES before there is one."""
    try:
        data = json.loads((paths.data_dir() / TIMING).read_text(encoding="utf-8-sig"))
        seconds = float(data["seconds_per_concept"])
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return DEFAULT_MINUTES, False
    return max(1, math.ceil(seconds / 60)), True


def build(run: RunFolder, brief_path: Path, *, concepts: list[str] | None = None,
          formats: list[str] | None = None, version: str | None = None, render: bool = False,
          fps: int = atlas.FPS) -> list[dict]:
    """`tm brief animatic`: the storyboard of each concept (default: all) in each format (default:
    `formats_of`) as version `version` (default: the next free one), and with `render` the MP4s and
    a new brief that names them. One dict per page: concept, format, html, and with `render` mp4,
    stills, render_s, page_errors and brief. Stop for a beat without a scene or a renderer that is
    not there, ValueError for a bad argument or a version already used: nothing is written then."""
    from tm import brief_page   # brief_page -> brief_checks -> this module

    started = time.monotonic()
    _, rel, brief = brief_page.load_brief(run, brief_path)
    drawn = formats_of(run) if formats is None else _checked_formats(formats, "--formats")
    anims = [(concept, anim if anim is None else with_images(run, rel, anim))
             for concept, anim in _anims(rel, brief, concepts)]
    modules = {concept["id"]: _styled_module(run, rel, concept) for concept, anim in anims if anim is None}
    folder = run.path / WIP
    version = _version(folder, version)
    hooks: dict[str, list[str]] = {}
    if render:
        try:
            atlas.need()                          # the tier, its setup and a browser, before any file
        except c.ToolStop as exc:
            raise Stop(str(exc)) from None
        anims = [(concept, anim if anim is None else _clear_hooks(anim, drawn, hooks.setdefault(concept["id"], [])))
                 for concept, anim in anims]
    folder.mkdir(parents=True, exist_ok=True)
    if any(anim is not None for _, anim in anims):
        _copy_library(folder)
    items: list[dict] = []
    for concept, anim in anims:
        if anim is None:                           # drawn in a library style, from its module (issue #138 item 4)
            items += _styled_pages(run, concept, modules[concept["id"]], drawn, version, render)
            continue
        js = folder / f"{concept['id']}_anim_{version}.js"
        write_new(js, 'window.ANIM = ' + json.dumps(anim, ensure_ascii=False, indent=1) + ';\n')
        manifest.record(run, _rel(run, js), "03_wip", SOURCE, parent=rel, params={"version": version})
        for fmt in drawn:
            html = folder / f"{concept['id']}_{fmt}_{version}.html"
            write_new(html, _HTML.format(concept['id'], fmt, js.name))
            manifest.record(run, _rel(run, html), "03_wip", SOURCE, parent=_rel(run, js), params={"format": fmt})
            items.append({"concept": concept["id"], "format": fmt, "version": version, "html": _rel(run, html),
                          **({"hook_changes": hooks[concept["id"]]} if render else {})})
    if render:
        _render(run, items, version, fps)
        _record_time(items, time.monotonic() - started)
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
                "C1,C3) and rendered (tm brief animatic --render --concepts C1,C3)")
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
