"""The animatics of a creative brief (CB11), shared by the playbooks: the port of the handoff's
`build_animatic.py`.

    scene_names()                 the scenes `scenes.js` draws (`tm brief check` takes only these)
    build_anim(concept)           a concept's `window.ANIM` (the handoff's, verbatim)
    build(run, brief_path, ...)   `tm brief animatic`: the storyboard files, and with `render` the MP4s
    formats_of(run), fps_of(run)  the formats drawn (`animatic.formats`, the audience pick's, or both), the fps
    not_rendered(run, ...)        the concepts' formats with no MP4 in the renders folder
    rendered_gap(run)             the step check `animatics_rendered`

The handoff's animatic engine and scene library are copied unchanged (LF) into `animatic_js/`; the
folder is not named `animatic/`, which would sit beside this module. A brief's beats name their
scene (`beats[].animatic.scene`).

`build` writes, per concept, `03_wip/animatic/<C>_anim_<ver>.js` (`window.ANIM`) and a page
`<C>_<fmt>_<ver>.html` per format, beside copies of `engine.js` and `scenes.js`, so the folder
draws on its own. A version is never used twice (the next free `vNN` by default). With `render`,
`atlas.render` draws each page into `03_wip/animatic/renders/<C>_animatic_<fmt>_<ver>.mp4` with
its stills, and a new `04_final/brief_pack_vNN.json` names them (`animatic/<file>`, the page's
paths). Nothing is written when a beat has no scene or the renderer is not there (a Stop). The
port's changes: a Stop or ValueError for the original's `sys.exit`; the version is checked for the
whole folder, before anything is written; paths in the answer are run-relative.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path

from tm import atlas, config, manifest, state
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


def _anims(rel: str, brief: dict, concepts: list[str] | None) -> list[tuple[dict, dict]]:
    """(concept, its window.ANIM) for the concepts asked for (default: all), before anything is written."""
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
        return [(x, build_anim(x)) for x in listed if not concepts or x["id"] in concepts]
    except MissingScene as exc:
        raise Stop(f"{rel}: {exc}. Give every beat its scene (beats[].animatic.scene, one that scenes.js draws), "
                   f"write the brief again (a new version), then make the animatics again. Nothing was written. "
                   f"{AGAIN}") from None
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise Stop(f"{rel} is not in its shape ({type(exc).__name__}: {exc}), so no animatic can be drawn from it. "
                   f"Check it with tm brief check, fix it (a new version), then make the animatics again. Nothing "
                   f"was written. {AGAIN}") from None


def write_new(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as fh:     # never over an earlier file
        fh.write(text)


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
            own = concept["animatic"].get("default") if isinstance(concept.get("animatic"), dict) else None
            default = own if isinstance(own, str) and own in drawn else formats[0]
            concept["animatic"] = {**drawn, "default": default}
    target = run.next_version(FINAL, STEM, "json")
    write_new(target, json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    out = _rel(run, target)
    manifest.record(run, out, FINAL, SOURCE, parent=rel, params={"animatics": version})
    return out


def build(run: RunFolder, brief_path: Path, *, concepts: list[str] | None = None,
          formats: list[str] | None = None, version: str | None = None, render: bool = False,
          fps: int = atlas.FPS) -> list[dict]:
    """`tm brief animatic`: the storyboard of each concept (default: all) in each format (default:
    `formats_of`) as version `version` (default: the next free one), and with `render` the MP4s and
    a new brief that names them. One dict per page: concept, format, html, and with `render` mp4,
    stills, render_s, page_errors and brief. Stop for a beat without a scene or a renderer that is
    not there, ValueError for a bad argument or a version already used: nothing is written then."""
    from tm import brief_page   # brief_page -> brief_checks -> this module

    _, rel, brief = brief_page.load_brief(run, brief_path)
    drawn = formats_of(run) if formats is None else _checked_formats(formats, "--formats")
    anims = _anims(rel, brief, concepts)
    folder = run.path / WIP
    version = _version(folder, version)
    if render:
        try:
            atlas.need()                          # the tier, its setup and a browser, before any file
        except c.ToolStop as exc:
            raise Stop(str(exc)) from None
    folder.mkdir(parents=True, exist_ok=True)
    _copy_library(folder)
    items: list[dict] = []
    for concept, anim in anims:
        js = folder / f"{concept['id']}_anim_{version}.js"
        write_new(js, 'window.ANIM = ' + json.dumps(anim, ensure_ascii=False, indent=1) + ';\n')
        manifest.record(run, _rel(run, js), "03_wip", SOURCE, parent=rel, params={"version": version})
        for fmt in drawn:
            html = folder / f"{concept['id']}_{fmt}_{version}.html"
            write_new(html, _HTML.format(concept['id'], fmt, js.name))
            manifest.record(run, _rel(run, html), "03_wip", SOURCE, parent=_rel(run, js), params={"format": fmt})
            items.append({"concept": concept["id"], "format": fmt, "version": version, "html": _rel(run, html)})
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


def rendered_gap(run: RunFolder) -> str | None:
    """`animatics_rendered`: every chosen concept in the latest brief names an MP4 per format
    (`formats_of`), and each is in 03_wip/animatic/renders/."""
    chosen = ((state.load(run).brief or {}).get("chosen") or {}).get("concepts") or []
    if not chosen:
        return ("the concepts to brief are chosen (tm brief choose) and their animatics rendered "
                "(tm brief animatic --render)")
    latest = run.latest(FINAL, STEM, "json")
    if latest is None:
        return f"{FINAL}/{STEM}_vNN.json is written and its animatics rendered (tm brief animatic --render)"
    try:
        concepts = {x["id"]: x for x in json.loads(latest.read_text(encoding="utf-8-sig"))["concepts"]}
    except (ValueError, KeyError, TypeError):
        return f"the latest {STEM}, {latest.name}, is readable, with the chosen concepts' animatics in it"
    try:
        drawn = formats_of(run)
    except ValueError as exc:
        return f"the formats to draw are known: {exc}"
    missing = not_rendered(run, concepts, chosen, drawn)
    if missing:
        return (f"every chosen concept in {latest.name} names its animatic MP4 in each format ({', '.join(drawn)}), "
                f"rendered into {RENDERS} (tm brief animatic --render); missing: {', '.join(missing)}")
    return None
