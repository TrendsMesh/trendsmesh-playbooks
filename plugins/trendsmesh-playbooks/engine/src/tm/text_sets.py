"""The channel's or the brand's text set (issue #117, section 3): one of the 8 looks of `tm.organic_edit` (`LOOKS`)
with its accent, font and logo, picked once and used in every run, organic video's and Create an ad's alike.

    tm brand text-style save --run R --kind channel|brand --name N (--style 03_wip/text_style_vNN.json | --look L)
                             [--accent #RRGGBB] [--font FILE] [--family NAME] [--logo FILE.png] --note "<their words>"
    tm brand text-style show --run R | --name N --kind K [--workspace W]

The set is kept beside the profile, in the same library folder, as its own append-only versions:
`library/brands/<slug>/text_style_vNN.json` or `library/channels/<slug>/text_style_vNN.json`:

    {"schema": "text_style/1", "kind", "name", "look", "accent": "#RRGGBB" | null, "ink": "#111111" | "#FFFFFF",
     "font": {"family", "file"} | null, "logo": "<library file>" | null, "note", "saved", "run"}

Its font and logo are copied once into `<that folder>/text/` (never overwritten), so a later run has them without
the site or the user again. The profile schemas (`brand/1`, `channel/1`) are unchanged: Create an ad has no brand
profile of its own (its brand is config.yaml's `brand.product`), and a set may be kept for a brand that has none yet.

Whose set a run uses (`for_run`): organic video's, its channel's (config.yaml `channels`, the first), else the store
the channel sells; Create an ad's, the brand config.yaml names (`brand.product`). None until one is saved: the
default set is `outline` (`organic_edit.DEFAULT_LOOK`), and the first time three sets that fit are shown
(`suggest_looks`, `native` first for a UGC channel or content meant to look filmed in the app). A single video can
use another set for its format (a ranking, a quiz) without changing the saved one.

`into_run` copies the set's font and logo into the run (`03_wip/text_set/`), where Remotion reads them (the run is
its public folder), with a manifest row naming the library file. The text on the accent is dark or white, whichever
has the higher contrast (`accent_ink`, WCAG's relative luminance).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from tm import brand, cli, config, manifest, paths, state, trend_spool
from tm import organic_edit as oe
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO
from tm.runfolder import RunFolder, slug as _slug
from tm.stops import AGAIN, Stop

SCHEMA = "text_style/1"
STEM = "text_style"
FILES = "text"                       # the set's font and logo, beside it
RUN_DIR = "03_wip/text_set"          # where a run keeps its copies, for Remotion
SOURCE = "tm brand text-style"
FONT_TYPES = (".ttf", ".otf", ".woff", ".woff2")   # Chrome draws them all (ffmpeg could not draw WOFF2)
LOGO_TYPES = (".png",)
DARK, WHITE = "#111111", "#FFFFFF"

# The three sets shown the first time, by the channel's type (issue #85), the best fit first.
FIT = {
    "news_explainers": ["block", "outline", "marker"],
    "howto_education": ["outline", "marker", "block"],
    "entertainment_skits": ["pop", "outline", "karaoke"],
    "music_dance": ["karaoke", "pop", "pill"],
    "lifestyle_vlog": ["quiet", "native", "pill"],
    "shop_product": ["pill", "outline", "native"],
    "other": ["outline", "native", "block"],
}


def _luminance(colour: str) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def accent_ink(accent: str) -> str:
    """The text drawn on the accent: dark (#111111) or white, whichever contrasts more with it."""
    lum = _luminance(accent)
    return DARK if (lum + 0.05) / (_luminance(DARK) + 0.05) >= 1.05 / (lum + 0.05) else WHITE


def suggest_looks(channel_type: str | None, *, ugc: bool = False) -> list[str]:
    """The three sets to show the first time: by the channel's type (the default first when it has none); a UGC
    channel, or content meant to look filmed in the app, gets `native` first."""
    looks = list(FIT.get(channel_type or "", [oe.DEFAULT_LOOK, "native", "block"]))
    if ugc:
        looks = ["native"] + [x for x in looks if x != "native"]
    return looks[:3]


# --- saved in the library ---------------------------------------------------------------------------

def _folder(workspace: Path, kind: str, name: str) -> Path:
    if kind not in brand.KINDS:
        raise Stop(f"--kind must be one of {', '.join(brand.KINDS)}, not {kind!r}; {AGAIN}.")
    key = brand.channel_key(name) if kind == "channel" else _slug(name).lower()
    return Path(workspace) / brand.DIRS[kind] / key


def _usable(source: Path, what: str, types: tuple[str, ...]) -> None:
    if source.suffix.lower() not in types:
        kinds = ", ".join(t.lstrip(".").upper() for t in types)
        raise Stop(f"The {what} {source.name} is not a {kinds} file: give the brand's {what} as {kinds}; {AGAIN}.")
    if not source.is_file():
        raise Stop(f"The {what} {source} does not exist; {AGAIN}.")


def _keep(folder: Path, source: Path, what: str, types: tuple[str, ...]) -> str:
    _usable(source, what, types)
    ext = source.suffix.lower()
    stem = _slug(source.stem).lower() or what
    versions = brand._versions(folder, stem, re.escape(ext.lstrip(".")))
    kept = brand._write_new(folder, stem, source.read_bytes(), (versions[-1][0] if versions else 0) + 1, ext)
    return kept.as_posix()


def problems(look: object, accent: object) -> list[str]:
    """What is wrong with a set's look and accent, one line each (the text style's own rules)."""
    out = [p for p in oe.style_problems({**oe.default_style(caption="", overlay=""), "look": look,
                                        "accent": accent}) if p.startswith(("look", "accent"))]
    if look is None:
        out.insert(0, f"look must be one of {', '.join(oe.LOOKS)}, not None.")
    return out


def save(workspace: Path, kind: str, name: str, *, look: str, accent: str | None = None, font: Path | None = None,
         font_family: str | None = None, logo: Path | None = None, run: RunFolder | None, note: str) -> Path:
    """The set as the next `text_style_vNN.json` of the brand's or channel's library folder (the module docstring)."""
    accent = accent.upper() if isinstance(accent, str) and oe.COLOUR.fullmatch(accent) else accent
    bad = problems(look, accent)
    if bad:
        raise Stop(f"The text set cannot be saved: {' '.join(bad)} Nothing was saved; {AGAIN}.")
    for given, what, types in ((font, "font", FONT_TYPES), (logo, "logo", LOGO_TYPES)):
        if given is not None:
            _usable(Path(given), what, types)       # before anything is written
    folder = _folder(workspace, kind, name)
    ws = Path(workspace)
    kept_font = None
    if font is not None:
        file = Path(_keep(folder / FILES, Path(font), "font", FONT_TYPES)).relative_to(ws).as_posix()
        kept_font = {"family": (font_family or "").strip() or Path(font).stem, "file": file}
    kept_logo = Path(_keep(folder / FILES, Path(logo), "logo", LOGO_TYPES)).relative_to(ws).as_posix() if logo else None
    data = {"schema": SCHEMA, "kind": kind, "name": name, "look": look, "accent": accent,
            "ink": accent_ink(accent) if accent else DARK, "font": kept_font, "logo": kept_logo, "note": note,
            "saved": date.today().isoformat(), "run": run.path.name if run is not None else None}
    versions = brand._versions(folder, STEM)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return brand._write_new(folder, STEM, text, (versions[-1][0] if versions else 0) + 1)


def latest(workspace: Path, kind: str, name: str) -> dict | None:
    """The latest saved set of a brand or channel, with its library `file`, else None."""
    versions = brand._versions(_folder(workspace, kind, name), STEM)
    if not versions:
        return None
    path = versions[-1][1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path.relative_to(Path(workspace)).as_posix()} is damaged (not JSON): save the text set again "
                   f"(tm brand text-style save); {AGAIN}.") from None
    return {**data, "file": path.relative_to(Path(workspace)).as_posix()}


def owners(run: RunFolder) -> list[tuple[str, str]]:
    """Whose sets a run reads, in order: (kind, name)."""
    try:
        cfg = config.load(run)
    except ValueError:
        return []
    pb = state.load(run).playbook
    if pb == ORGANIC_VIDEO:
        channels = cfg.get("channels") or []
        if not channels:
            return []
        out = [("channel", str(channels[0]))]
        profile = brand.latest(trend_spool.workspace_of(run), str(channels[0]), kind="channel")
        if isinstance(profile, dict) and isinstance(profile.get("store"), str) and profile["store"].strip():
            out.append(("brand", profile["store"]))
        return out
    if pb == CREATE_AD:
        product = (cfg.get("brand") or {}).get("product")
        return [("brand", str(product))] if isinstance(product, str) and product.strip() else []
    return []


def for_run(run: RunFolder) -> dict | None:
    """The saved set a run uses (the module docstring), else None."""
    ws = trend_spool.workspace_of(run)
    for kind, name in owners(run):
        found = latest(ws, kind, name)
        if found is not None:
            return found
    return None


def _copy(run: RunFolder, ws: Path, library: str, what: str) -> str:
    source = ws / library
    if not source.is_file():
        raise Stop(f"The text set's {what} {library} is missing from the library: save the set again with the "
                   f"{what} (tm brand text-style save ... --{what} <file>); {AGAIN}.")
    data = source.read_bytes()
    target = run.path / RUN_DIR / source.name
    rel = f"{RUN_DIR}/{source.name}"
    if target.is_file() and target.read_bytes() == data:
        return rel
    if target.exists():
        target = run.unique_path(rel)
        rel = target.relative_to(run.path).as_posix()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as fh:
        fh.write(data)
    manifest.record(run, rel, "03_wip", SOURCE, params={"library": library})
    return rel


def into_run(run: RunFolder, saved: dict) -> dict:
    """{look, accent, ink, font: {family, src} | None, logo: src | None} with the files copied into the run."""
    ws = trend_spool.workspace_of(run)
    font = saved.get("font") if isinstance(saved.get("font"), dict) else None
    return {"look": saved["look"], "accent": saved.get("accent"),
            "ink": saved.get("ink") or (accent_ink(saved["accent"]) if saved.get("accent") else DARK),
            "font": {"family": font["family"], "src": _copy(run, ws, font["file"], "font")} if font else None,
            "logo": _copy(run, ws, saved["logo"], "logo") if saved.get("logo") else None}


# --- tm brand text-style --------------------------------------------------------------------------------

def add_parser(sub) -> None:
    t = sub.add_parser("text-style", help="the brand's or channel's text set, kept for every run (issue #117)")
    t.add_argument("ts_action", choices=("save", "show"))
    t.add_argument("--run", help="the run folder (show: whose set it uses)")
    t.add_argument("--kind", choices=brand.KINDS)
    t.add_argument("--name", help="the brand's or channel's name")
    t.add_argument("--style", help="save: the approved 03_wip/text_style_vNN.json (its look, accent, font, logo)")
    t.add_argument("--look", choices=oe.LOOKS)
    t.add_argument("--accent", help="the brand colour, #RRGGBB")
    t.add_argument("--font", help="the brand's font file (TTF, OTF, WOFF, WOFF2), in the run")
    t.add_argument("--family", help="the font's family name (default: the file's name)")
    t.add_argument("--logo", help="the brand's logo, a PNG in the run")
    t.add_argument("--note", help="save: the user's words")
    t.add_argument("--workspace", help="show without --run: default the current workspace")
    t.add_argument("--json", action="store_true")


def _from_style(run: RunFolder, given: str) -> dict:
    path = run.given(given)
    try:
        style = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"The text style {given} cannot be read ({exc}); {AGAIN}.") from None
    font = style.get("font") if isinstance(style.get("font"), dict) else None
    return {"look": style.get("look"), "accent": style.get("accent"),
            "font": run.given(font["src"]) if font and font.get("src") else None,
            "font_family": font.get("family") if font else None,
            "logo": run.given(style["logo"]) if isinstance(style.get("logo"), str) else None}


def run_cli(args: argparse.Namespace) -> int:
    if args.ts_action == "show":
        if args.run:
            run = RunFolder.open(Path(args.run))
            found = for_run(run)
            whose = owners(run)
        else:
            if not (args.name and args.kind):
                return cli.fail(args, "Give --run, or --name and --kind.")
            ws = Path(args.workspace) if args.workspace else paths.workspace()
            found, whose = latest(ws, args.kind, args.name), [(args.kind, args.name)]
        suggested = suggest_looks(None)
        message = (f"The text set is {found['look']} ({found['file']})." if found else
                   f"No text set is saved for {' or '.join(f'{k} {n}' for k, n in whose) or 'this run'}: the default "
                   f"is {oe.DEFAULT_LOOK}; the first time, show three sets that fit (suggested: "
                   f"{', '.join(suggested)}).")
        cli.emit(args, {"status": "done", "text_style": found, "suggested": suggested, "message": message}, message)
        return 0
    if not (args.run and args.kind and args.name and args.note):
        return cli.fail(args, "save needs --run, --kind, --name and --note (the user's words).")
    run = RunFolder.open(Path(args.run))
    given = _from_style(run, args.style) if args.style else {"look": None, "accent": None, "font": None,
                                                              "font_family": None, "logo": None}
    look = args.look or given["look"]
    saved = save(trend_spool.workspace_of(run), args.kind, args.name, look=look,
                 accent=args.accent or given["accent"],
                 font=run.given(args.font) if args.font else given["font"],
                 font_family=args.family or given["font_family"],
                 logo=run.given(args.logo) if args.logo else given["logo"], run=run, note=args.note)
    rel = saved.relative_to(trend_spool.workspace_of(run)).as_posix()
    message = f"Saved {rel}: every run of this {args.kind} uses the {look} set from now on."
    cli.emit(args, {"status": "done", "file": rel, "message": message}, message)
    return 0
