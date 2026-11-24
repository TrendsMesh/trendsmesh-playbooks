"""The channel's or the brand's text set (issue #117, section 3): one of the 8 looks of `tm.organic_edit` (`LOOKS`)
with its accent, font and logo, picked once and used in every run, organic video's and Create an ad's alike.

    tm brand text-style save --run R --kind channel|brand --name N (--style 03_wip/text_style_vNN.json | --look L)
                             [--accent #RRGGBB] [--font FILE] [--family NAME] [--logo FILE.png] [--no-brand-files]
                             --note "<their words>"
    tm brand text-style show --run R | --name N --kind K [--workspace W]

The set is kept beside the profile, in the same library folder, as its own append-only versions:
`library/brands/<slug>/text_style_vNN.json` or `library/channels/<slug>/text_style_vNN.json`:

    {"schema": "text_style/1", "kind", "name", "look", "accent": "#RRGGBB" | null, "ink": "#111111" | "#FFFFFF",
     "font": {"family", "file"} | null, "logo": "<library file>" | null, "note", "saved", "run",
     "brand_files"?: {"font"?, "logo"?: where the save took them from}}

Its font and logo are copied once into `<that folder>/text/` (never overwritten), so a later run has them without
the site or the user again. A save given no font or no logo adds the brand's by itself when the plugin has it
(`brand_kit`, #176 line 74): the run's `02_research/brand_vNN.json` (`tm tool site brand`), else the saved set of a
brand the run is for; `brand_files` says where from. A font or logo given wins; `--no-brand-files` leaves them out. The profile schemas (`brand/1`, `channel/1`) are unchanged: Create an ad has no brand
profile of its own (its brand is config.yaml's `brand.product`), and a set may be kept for a brand that has none yet.

Whose set a run uses (`for_run`): organic video's, its channel's (config.yaml `channels`, the first), else the store
the channel sells; Create an ad's, the brand config.yaml names (`brand.product`); refresh-ad's, the product it
advertises (`product.name`), whose HookSwap cards and WordCaptions words `tm render` draws in it (`fill_props`). None until one is saved: the
default set is `outline` (`organic_edit.DEFAULT_LOOK`), and the first time three sets that fit are shown
(`suggest_looks`, `native` first for a UGC channel or content meant to look filmed in the app). A single video can
use another set for its format (a ranking, a quiz) without changing the saved one.

`into_run` copies the set's font and logo into the run (`03_wip/text_set/`), where Remotion reads them (the run is
its public folder), with a manifest row naming the library file.

Create an ad's first ad of a brand (issue #166): with no saved set, `tm ad text` draws a run-only set
(`from_inventory`), the default look with the brand's font and logo from `tm tool site brand`'s inventory
(`02_research/brand_vNN.json`); the user approves it with the edit at the review, and `tm brand text-style save`
keeps it then. refresh-ad's `fill_props` and organic video read only a saved set. The text on the accent is dark or white, whichever
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
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO, REFRESH_AD
from tm.runfolder import RunFolder, slug as _slug
from tm.stops import AGAIN, Stop

SCHEMA = "text_style/1"
STEM = "text_style"
FILES = "text"                       # the set's font and logo, beside it
RUN_DIR = "03_wip/text_set"          # where a run keeps its copies, for Remotion
SOURCE = "tm brand text-style"
FONT_TYPES = (".ttf", ".otf", ".woff", ".woff2")   # Chrome draws them all (ffmpeg could not draw WOFF2)
LOGO_TYPES = (".png",)
DARK = oe.DARK_INK

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


# The set that fits an animation's style family (issue #139): each `category` of data/styles/styles.json. A set that
# draws over a hand-drawn board in white with a stroke fights the board; `tm organic text look` suggests this one
# beside the saved set, and the saved set is never changed by it.
FAMILY_LOOKS = {
    "Hand-drawn": "marker", "Painterly": "marker", "Paper and craft": "marker", "Illustration": "marker",
    "Clean explainer": "block", "Data": "block", "Product and UI": "block",
    "Design movements": "block", "Print": "block", "Type and pattern": "block", "Collage": "block",
    "Retro digital": "pop", "Retro desktop": "pop",
    "Dimensional": "outline", "Light and imaging": "outline", "Cosmic": "outline",
}

accent_ink = oe.accent_ink   # the text drawn on the accent, dark or white by contrast


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
    stem = _slug(re.sub(r"_v\d+$", "", source.stem)).lower() or what   # another set's kept file: no second _vNN
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
         font_family: str | None = None, logo: Path | None = None, run: RunFolder | None, note: str,
         brand_files: bool = True) -> Path:
    """The set as the next `text_style_vNN.json` of the brand's or channel's library folder (the module docstring).
    A font or logo not given is the brand's, when the plugin has it (`brand_kit`; `brand_files=False` leaves them
    out); the saved file's `brand_files` names where each one added came from."""
    accent = accent.upper() if isinstance(accent, str) and oe.COLOUR.fullmatch(accent) else accent
    bad = problems(look, accent)
    if bad:
        raise Stop(f"The text set cannot be saved: {' '.join(bad)} Nothing was saved; {AGAIN}.")
    for given, what, types in ((font, "font", FONT_TYPES), (logo, "logo", LOGO_TYPES)):
        if given is not None:
            _usable(Path(given), what, types)       # before anything is written
    added = {}
    if run is not None and brand_files and (font is None or logo is None):
        kit = brand_kit(run)
        if font is None and kit["font"]:
            font, font_family = kit["font"]["path"], font_family or kit["font"]["family"]
            added["font"] = kit["font"]["from"]
        if logo is None and kit["logo"]:
            logo, added["logo"] = kit["logo"]["path"], kit["logo"]["from"]
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
    if added:
        data["brand_files"] = added
    versions = brand._versions(folder, STEM)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return brand._write_new(folder, STEM, text, (versions[-1][0] if versions else 0) + 1)


def check_pick(run: RunFolder, style: str, sha256: str | None) -> dict:
    """The style of the set the user picked (issue #165), checked before anything is written: it is a usable style,
    unchanged since its look was drawn (`sha256`, the still's stamp). The style's data; a Stop otherwise."""
    path, rel = oe._inside(run, style, "text style")
    if sha256 is not None and oe._sha(path) != sha256:
        raise Stop(f"The picked text set's style {rel} changed since its look was drawn, so it is not the one the user "
                   f"saw. Draw the set again (tm organic text look --style {rel}), build the page and ask again; "
                   f"nothing was written; {AGAIN}.")
    return oe._style_at(run, style)[2]


def take_pick(run: RunFolder, style: str, *, note: str, sha256: str | None = None, by: str = "user") -> dict:
    """The user's pick of the sets drawn the first time (issue #165): the picked style made the latest (its bytes as
    the next `03_wip/text_style_vNN.json` when it is not, so the still drawn from it is still its look), approved
    (`organic_edit.approve`) and saved for the run's first owner, the channel (`save`). {style, picked_from, look,
    approved, saved: the library file | None, owner: [kind, name] | None, brand_files: {font?, logo?: where the save took the
    brand's from} (`save`), font_family}; a run that names no owner is approved only."""
    data = check_pick(run, style, sha256)
    path, rel, _ = oe._style_at(run, style)
    latest_style = run.latest(oe.WIP, oe.STYLE_STEM, "json")
    target_rel = rel
    if latest_style is None or latest_style.resolve() != path.resolve():
        target = run.next_version("wip", oe.STYLE_STEM, "json")
        with open(target, "xb") as fh:
            fh.write(path.read_bytes())
        target_rel = target.relative_to(run.path).as_posix()
        manifest.record(run, target_rel, oe.WIP, SOURCE, parent=rel,
                        params={"look": data.get("look"), "picked_from": rel})
    approved = oe.approve(run, target_rel, by=by, note=note)
    whose = owners(run)
    saved, added, family = None, {}, None
    if whose:
        kind, name = whose[0]
        given = _from_style(run, target_rel)
        file = save(trend_spool.workspace_of(run), kind, name, look=given["look"], accent=given["accent"],
                    font=given["font"], font_family=given["font_family"], logo=given["logo"], run=run, note=note)
        saved = file.relative_to(trend_spool.workspace_of(run)).as_posix()
        kept = json.loads(file.read_text(encoding="utf-8"))
        added = kept.get("brand_files") or {}
        family = kept["font"]["family"] if kept.get("font") else None
    return {"style": target_rel, "picked_from": rel, "look": data.get("look"), "approved": approved,
            "saved": saved, "owner": list(whose[0]) if whose else None, "brand_files": added, "font_family": family}


def latest(workspace: Path, kind: str, name: str) -> dict | None:
    """The latest saved set of a brand or channel, with its library `file`, else None."""
    versions = brand._versions(_folder(workspace, kind, name), STEM)
    if not versions:
        return None
    path = versions[-1][1]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
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
    if pb == REFRESH_AD:     # the product the ad sells (config.yaml `product.name`) is the brand (issue #139)
        product = (cfg.get("product") or {}).get("name")
        return [("brand", str(product))] if isinstance(product, str) and product.strip() else []
    return []


TEXT_SET_COMPS = ("HookSwap", "WordCaptions")


def fill_props(run: RunFolder, comp: str, data: dict) -> tuple[dict, bool]:
    """(the props, whether anything was filled in): HookSwap's cards and WordCaptions' words are drawn in the run's
    saved set (refresh-ad, issue #139), as `textSet` {look, accent, ink, font, logo} (`into_run`), when the props
    name none. `"textSet": null` keeps the original ad's look."""
    if comp not in TEXT_SET_COMPS or "textSet" in data:
        return data, False
    saved = for_run(run)
    if saved is None:
        return data, False
    return {**data, "textSet": into_run(run, saved)}, True


def channel_type(run: RunFolder) -> str | None:
    """The type (issue #85) of the channel an organic run is for, else None."""
    for kind, name in owners(run):
        if kind == "channel":
            profile = brand.latest(trend_spool.workspace_of(run), name, kind="channel")
            return profile.get("type") if isinstance(profile, dict) else None
    return None


def for_run(run: RunFolder) -> dict | None:
    """The saved set a run uses (the module docstring), else None."""
    ws = trend_spool.workspace_of(run)
    for kind, name in owners(run):
        found = latest(ws, kind, name)
        if found is not None:
            return found
    return None


INVENTORY = ("02_research", "brand", "json")   # `tm tool site brand`'s inventory of the brand's font and logo


def _inventory(run: RunFolder) -> tuple[dict | None, str | None, str] | None:
    """(font {"family", "file"} | None, logo | None, the inventory) of the run's latest `02_research/brand_vNN.json`
    (`tm tool site brand`): its first font file the sets draw, and its first logo PNG that names the brand and is not
    flagged too small, both in the run; None without a readable inventory."""
    path = run.latest(*INVENTORY)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    font = None
    for fam in data.get("fonts") or []:
        files = fam.get("files") if isinstance(fam, dict) else None
        first = next((x["file"] for x in files or [] if isinstance(x, dict) and isinstance(x.get("file"), str)
                      and Path(x["file"]).suffix.lower() in FONT_TYPES and (run.path / x["file"]).is_file()), None)
        if first:
            font = {"family": str(fam.get("family") or Path(first).stem), "file": first}
            break
    logo = next((x["png"] for x in data.get("logos") or [] if isinstance(x, dict) and x.get("names_brand")
                 and not x.get("small") and isinstance(x.get("png"), str) and (run.path / x["png"]).is_file()),
                None)
    return font, logo, path.relative_to(run.path).as_posix()


def from_inventory(run: RunFolder) -> dict | None:
    """A run-only set for Create an ad's first ad of a brand (issue #166), when no set is saved: the default look
    with the first font file and the first logo PNG that names the brand (not one flagged too small) of the latest
    `02_research/brand_vNN.json`, as {"look", "accent": None, "ink", "font": {"family", "file"} | None,
    "logo": file | None, "file": the inventory, "run_only": True}, the files relative to the run (already in it).
    None when the run is not an ad's, or the inventory has neither a font nor a logo. Never saved: the user approves
    it with the edit, and `tm brand text-style save` keeps it then."""
    if state.load(run).playbook != CREATE_AD:
        return None
    found = _inventory(run)
    if found is None or (found[0] is None and found[1] is None):
        return None
    font, logo, file = found
    return {"look": oe.DEFAULT_LOOK, "accent": None, "ink": DARK, "font": font, "logo": logo,
            "file": file, "run_only": True}


def brand_kit(run: RunFolder) -> dict:
    """The brand's font and logo that a save adds when it is given none (#176 line 74, the gap of issue #166), each
    from the first place that has it: the run's inventory (`_inventory`, `tm tool site brand`), else the latest saved
    set of a brand the run is for (`owners`: Create an ad's brand, the store an organic channel sells, refresh-ad's
    product) whose library file is there. {"font": {"family", "path", "from"} | None, "logo": {"path", "from"} | None};
    only files the plugin already has, nothing is downloaded."""
    kit: dict = {"font": None, "logo": None}
    found = _inventory(run)
    if found is not None:
        font, logo, file = found
        if font:
            kit["font"] = {"family": font["family"], "path": run.path / font["file"], "from": file}
        if logo:
            kit["logo"] = {"path": run.path / logo, "from": file}
    ws = trend_spool.workspace_of(run)
    for kind, name in owners(run):
        if kit["font"] and kit["logo"]:
            break
        if kind != "brand":
            continue
        try:
            saved = latest(ws, kind, name)
        except Stop:
            continue
        if not saved:
            continue
        font = saved.get("font") if isinstance(saved.get("font"), dict) else None
        if kit["font"] is None and font and isinstance(font.get("file"), str) and (ws / font["file"]).is_file():
            kit["font"] = {"family": font.get("family") or Path(font["file"]).stem, "path": ws / font["file"],
                           "from": saved["file"]}
        logo = saved.get("logo")
        if kit["logo"] is None and isinstance(logo, str) and (ws / logo).is_file():
            kit["logo"] = {"path": ws / logo, "from": saved["file"]}
    return kit


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
    """{look, accent, ink, font: {family, src} | None, logo: src | None} with the files copied into the run; a
    run-only set (`from_inventory`) names the run's own files, nothing is copied."""
    font = saved.get("font") if isinstance(saved.get("font"), dict) else None
    if saved.get("run_only"):
        return {"look": saved["look"], "accent": saved.get("accent"), "ink": saved.get("ink") or DARK,
                "font": {"family": font["family"], "src": font["file"]} if font else None,
                "logo": saved.get("logo")}
    ws = trend_spool.workspace_of(run)
    return {"look": saved["look"], "accent": saved.get("accent"),
            "ink": saved.get("ink") or (accent_ink(saved["accent"]) if saved.get("accent") else DARK),
            "font": {"family": font["family"], "src": _copy(run, ws, font["file"], "font")} if font else None,
            "logo": _copy(run, ws, saved["logo"], "logo") if saved.get("logo") else None}


def brand_files_said(added: dict, family: str | None) -> str:
    """" with the brand's font F and logo (where from)" for what a save added by itself, "" when nothing."""
    parts = []
    if added.get("font"):
        parts.append(f"font {family}" if family else "font")
    if added.get("logo"):
        parts.append("logo")
    if not parts:
        return ""
    sources = list(dict.fromkeys(v for v in (added.get("font"), added.get("logo")) if v))
    return f" with the brand's {' and '.join(parts)} ({', '.join(sources)})"


# --- tm brand text-style --------------------------------------------------------------------------------

def add_parser(sub) -> None:
    t = sub.add_parser("text-style", help="the brand's or channel's text set, kept for every run (issue #117)")
    t.add_argument("ts_action", choices=("save", "show"))
    t.add_argument("--run", help="the run folder (show: whose set it uses)")
    t.add_argument("--kind", choices=brand.KINDS)
    t.add_argument("--name", help="the brand's or channel's name")
    t.add_argument("--style",
                   help="save: the approved 03_wip/text_style_vNN.json (its look, accent, font, logo), relative to the run folder")
    t.add_argument("--look", choices=oe.LOOKS)
    t.add_argument("--accent", help="the brand colour, #RRGGBB")
    t.add_argument("--font", help="the brand's font file (TTF, OTF, WOFF, WOFF2), in the run")
    t.add_argument("--family", help="the font's family name (default: the file's name)")
    t.add_argument("--logo", help="the brand's logo, a PNG in the run")
    t.add_argument("--no-brand-files", action="store_true",
                   help="save: without the brand's font and logo the save adds by itself when none is given")
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
        kind_of = None
        if args.run:
            run = RunFolder.open(Path(args.run))
            found = for_run(run)
            whose = owners(run)
            kind_of = channel_type(run)
        else:
            if not (args.name and args.kind):
                return cli.fail(args, "Give --run, or --name and --kind.")
            ws = Path(args.workspace) if args.workspace else paths.workspace()
            found, whose = latest(ws, args.kind, args.name), [(args.kind, args.name)]
        suggested = suggest_looks(kind_of)   # by the channel's type; native first is the agent's call for UGC
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
                 logo=run.given(args.logo) if args.logo else given["logo"], run=run, note=args.note,
                 brand_files=not args.no_brand_files)
    rel = saved.relative_to(trend_spool.workspace_of(run)).as_posix()
    kept = json.loads(saved.read_text(encoding="utf-8"))
    added = kept.get("brand_files") or {}
    message = (f"Saved {rel}: every run of this {args.kind} uses the {look} set from now on"
               f"{brand_files_said(added, kept['font']['family'] if kept.get('font') else None)}.")
    cli.emit(args, {"status": "done", "file": rel, "brand_files": added, "message": message}, message)
    return 0
