"""Our animation styles and their build prompt (organic video F1/F2).

    styles()                 the library's styles, in their order
    find_style(key)          one style, by its number or its styleId; a ValueError names the closest
    build(style, ...)        the ready-to-paste build prompt for an animation in that style
    page(style, ...)         the style's own reference animation as a page (window.seek / DURATION, or a storyboard)

    module_page(text, ...)   a page built from a style module Claude wrote (tm organic atlas-page)

The library is engine data, `data/styles/` (written by us, from scratch): `styles.json` (one card per
style: name, family, description, what it suits, its look, palette, fonts, finishing passes, motion, how it
explains, its sound, what to avoid), `lib/` (brush.js, the shared drawing helpers; sound.js, the synthesized sound
kit; player.js, the page runtime; page.html, the page template), `styles/NN_<styleId>.js` (each style's reference
animation), `prompt/` (the prompt's parts: build.md always, voiceover.md and storyboard.md by mode) and README.md.
The build prompt is those parts with the content, the voiceover's word SRT and the frame filled in, then the style's
card, then the libraries' API (README.md's module, Brush and SOUND sections) and the code of the style's reference
animation. Claude writes only a style module; the page is built from it with the libraries inlined, so neither the
prompt nor Claude's answer carries the libraries' 100k characters.
"""

from __future__ import annotations

import difflib
import functools
import hashlib
import html
import json
import re
from pathlib import Path

from tm import paths

ROOT = paths.bundled_data() / "styles"
LIB = ("brush.js", "sound.js", "player.js")
CONTENT_PH = "[Describe your topic or paste your script here. If this is left as is, ask for it before building.]"
SRT_PH = ("[Paste the word-timed SRT of the voiceover here. If this is left as is, ask for it before "
          "building.]")
# The frame of each format; no --aspect builds 16:9.
WIDE = (1280, 720)
ASPECTS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}
API_SECTIONS = ("## A style module", "## Brush (window.Brush)", "## SOUND (window.SOUND)")
CARD_FIELDS = (("Looks", "look"), ("Finishing passes, on every frame", "finish"), ("Motion", "motion"),
               ("How it explains", "explaining"), ("Sound", "sound"), ("Avoid", "avoid"))


@functools.lru_cache(maxsize=1)
def _styles() -> tuple[dict, ...]:
    return tuple(json.loads((ROOT / "styles.json").read_text(encoding="utf-8-sig")))


def styles() -> list[dict]:
    """The styles (order, styleId, name, category, description, suits, look, palette, fonts ...), in their order."""
    return [dict(s) for s in _styles()]


def find_style(key: str) -> dict:
    """The style numbered `key` or with the styleId `key`. A ValueError names the closest ones."""
    key = str(key).strip()
    for s in _styles():
        if key == s["styleId"] or (key.isdigit() and int(key) == s["order"]):
            return dict(s)
    names = {s["styleId"]: s for s in _styles()}
    names.update({s["name"].lower(): s for s in _styles()})
    close = difflib.get_close_matches(key.lower(), list(names), n=3, cutoff=0.4)
    shown = list(dict.fromkeys(f"{names[c]['order']} {names[c]['styleId']} ({names[c]['name']})" for c in close))
    hint = f" The closest: {'; '.join(shown)}." if shown else ""
    raise ValueError(f"Unknown style {key!r}: give its number (1-{len(_styles())}) or its styleId "
                     f"(tm organic atlas-styles lists them).{hint}")


def module_path(s: dict) -> Path:
    """The style's reference animation, `styles/NN_<styleId>.js`."""
    return ROOT / "styles" / f"{s['order']:02d}_{s['styleId']}.js"


# --- previews and tags (issue #116) ---------------------------------------------------------------------------

PREVIEWS = ROOT / "previews"
# A card's `tags`: the channel types it suits (the profile's `type` ids, brand.CHANNEL_TYPES without "other"), 2 to 3
# tone words from TONES, its energy, and whether it shows numbers clearly (data/styles/README.md, "Adding a style").
CHANNEL_TYPES = ("news_explainers", "howto_education", "entertainment_skits", "music_dance", "lifestyle_vlog",
                 "shop_product")
TONES = ("serious", "playful", "premium", "retro", "warm", "edgy", "calm", "technical", "dreamy", "bold", "nostalgic",
         "friendly", "raw", "elegant", "futuristic")
ENERGIES = ("calm", "medium", "high")


@functools.lru_cache(maxsize=1)
def _previews() -> dict:
    return json.loads((PREVIEWS / "previews.json").read_text(encoding="utf-8-sig"))


def previews() -> dict:
    """`previews/previews.json`: per styleId its poster, loop, poster time, loop window, sizes and the hash of the
    module and card they were made from (atlas/previews.mjs)."""
    return {k: dict(v) for k, v in _previews().items()}


def preview_files(s: dict) -> tuple[Path, Path]:
    """The style's poster (`NN_<styleId>.jpg`, 540x960) and loop (`NN_<styleId>.mp4`, 4 s, 360x640, muted)."""
    stem = f"{s['order']:02d}_{s['styleId']}"
    return PREVIEWS / f"{stem}.jpg", PREVIEWS / f"{stem}.mp4"


def preview_hash(s: dict) -> str:
    """What atlas/previews.mjs stores as a preview's `hash`: sha256 of the module's bytes and the card's compact JSON,
    16 hex digits. A style whose module or card changed no longer matches its preview."""
    card = json.dumps(s, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(module_path(s).read_bytes() + card).hexdigest()[:16]


def style_id(key: object) -> str | None:
    """The styleId of a style named by its number, styleId or `<number> <name>`; None when it is not one of ours."""
    if isinstance(key, bool) or not isinstance(key, (str, int)):
        return None
    text = str(key).strip()
    head = text.split(" ", 1)[0] if text[:1].isdigit() else text
    try:
        return find_style(head)["styleId"]
    except ValueError:
        return None


def ranked(*, channel_type: str | None = None, tone=(), numbers: bool = False, own: object = None,
           rejected=()) -> list[dict]:
    """Every style in the order it is suggested (issue #116), each card with `reason` and `shared_tone`:

    1. `own`, the channel's own style (the card nearest its `video_style`, or one it picked 3 times or more): `channel`;
    2. the styles whose tags.channels has `channel_type` (`type`), then the others (`tone` when they share a tone word,
       else `other`); within each, most of `tone` in common first, then (with `numbers`, the idea has a key number)
       the styles that show numbers well, then the library's order. A channel of type `other` (or none) is ranked by
       the tone alone;
    3. a style the user rejected for this channel (`rejected`) last (`rejected`), never the channel's own.

    `own` and `rejected` name styles by number, styleId or `<number> <name>`; an unknown one is passed over. A
    ValueError for a tone word outside TONES or an unknown channel type."""
    tone = [str(w).strip().lower() for w in tone or () if str(w).strip()]
    bad = [w for w in tone if w not in TONES]
    if bad:
        raise ValueError(f"Unknown tone word {', '.join(map(repr, bad))}: use {', '.join(TONES)}.")
    if channel_type is not None and channel_type not in (*CHANNEL_TYPES, "other"):
        raise ValueError(f"Unknown channel type {channel_type!r}: one of {', '.join(CHANNEL_TYPES)} or other.")
    own_id = style_id(own) if own is not None else None
    out_ids = {i for i in (style_id(r) for r in rejected or ()) if i} - {own_id}
    head, typed, rest, last = [], [], [], []
    for s in styles():
        s["shared_tone"] = [w for w in tone if w in s["tags"]["tone"]]
        if s["styleId"] == own_id:
            head.append({**s, "reason": "channel"})
        elif s["styleId"] in out_ids:
            last.append({**s, "reason": "rejected"})
        elif channel_type in CHANNEL_TYPES and channel_type in s["tags"]["channels"]:
            typed.append({**s, "reason": "type"})
        else:
            rest.append({**s, "reason": "tone" if s["shared_tone"] else "other"})

    def key(s: dict) -> tuple:
        return -len(s["shared_tone"]), bool(numbers) and not s["tags"]["numbers"], s["order"]

    return head + sorted(typed, key=key) + sorted(rest, key=key) + sorted(last, key=key)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r", "")


def frame(aspect: str | None) -> tuple[int, int]:
    """The canvas of a format: ASPECTS[aspect], or 1280x720 without one."""
    return ASPECTS[aspect] if aspect else WIDE


def safe_area(aspect: str | None) -> tuple[int, int]:
    """Pixels kept free at the top and the bottom: in a vertical feed the platform's own buttons and captions sit
    there (14 % and 20 % of the height); a 16:9 or square frame keeps a small margin."""
    w, h = frame(aspect)
    if h > w:
        return round(h * 0.14), round(h * 0.20)
    return round(h * 0.05), round(h * 0.05)


def text_sizes(aspect: str | None) -> str:
    short = min(frame(aspect))
    return (f"headlines at least {round(short * 0.06)} px, every label the story needs at least "
            f"{round(short * 0.038)} px, key numbers at least {round(short * 0.09)} px.")


def card(s: dict) -> str:
    """The style's card as prompt text."""
    lines = [f"Style {s['order']}: {s['name']} ({s['category']})", "", s["description"], "", f"Suits: {s['suits']}",
             "", "Palette: " + ", ".join(f"{p['role']} {p['hex']}" for p in s["palette"]),
             "Fonts: " + ", ".join(s["fonts"])]
    for title, key in CARD_FIELDS:
        lines += ["", f"{title}:", *(f"- {item}" for item in s[key])]
    return "\n".join(lines)


def api() -> str:
    """The libraries' API: README.md's sections on a style module, Brush and SOUND."""
    readme = _read("README.md")
    parts = []
    for heading in API_SECTIONS:
        body = readme.split("\n" + heading + "\n", 1)[1].split("\n## ", 1)[0]
        parts.append("#" + heading + "\n" + body.rstrip())
    return "\n\n".join(parts)


def build(style, voiceover=False, storyboard=False, content=None, srt=None, aspect=None, extra=None) -> str:
    """The build prompt for an animation in `style`: the prompt's parts for the modes asked for, filled in, then the
    style's card, the libraries' API and the style's reference animation. `aspect` re-composes it for that format
    (ASPECTS; 16:9 without one); `extra` adds rules (an insert's caption band)."""
    w, h = frame(aspect)
    top, bottom = safe_area(aspect)
    parts = ["build.md"] + (["voiceover.md"] if voiceover else []) + (["storyboard.md"] if storyboard else [])
    fill = {"{{STYLE_NAME}}": style["name"], "{{WIDTH}}": str(w), "{{HEIGHT}}": str(h),
            "{{ASPECT}}": aspect or "16:9", "{{SAFE_TOP}}": str(top), "{{SAFE_BOTTOM}}": str(bottom),
            "{{TEXT_SIZES}}": text_sizes(aspect), "{{EXTRA_RULES}}": (extra or "").strip(),
            "{{CONTENT}}": (content or "").strip() or CONTENT_PH, "{{SRT}}": (srt or "").strip() or SRT_PH}
    text = "\n\n".join(_read(f"prompt/{p}").strip() for p in parts)
    for key, value in fill.items():
        text = text.replace(key, value)
    rel = module_path(style).relative_to(ROOT).as_posix()
    return (text + "\n\n## The style\n\n" + card(style) + "\n\n## The libraries' API\n\n" + api()
            + f"\n\n## The reference module ({style['name']}, `{rel}`)\n\n```js\n{_read(rel).rstrip()}\n```\n")


FONTS_URL = re.compile(r"https://fonts\.googleapis\.com/css2\?[^\"'`\s]+")


def fonts_link(module: str) -> str:
    """The Google Fonts <link> of a style module: the css2 URL it names (empty when it names none)."""
    found = FONTS_URL.search(module)
    if not found:
        return ""
    return ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{html.escape(found.group(0))}">')


def module_page(module: str, title: str, aspect: str | None = None, storyboard: bool = False, panels: int = 6,
                voiceover: bool = False) -> str:
    """A self-contained page from a style module: lib/page.html with the frame, the mode, the fonts <link> the module
    names and the three libraries, then the module, inlined. Play mode gives window.seek, window.DURATION and
    window.scoreSound; storyboard mode `panels` panels on canvases p1 ... pN and window.makeSheet()."""
    w, h = frame(aspect)
    config = {"width": w, "height": h, "mode": "storyboard" if storyboard else "play",
              "panels": panels if storyboard else 0, "voiceover": bool(voiceover)}
    code = [_read(f"lib/{n}") for n in LIB] + [module.replace("\r", "")]
    scripts = "\n".join("<script>\n" + c.rstrip().replace("</script", "<\\/script") + "\n</script>" for c in code)
    fill = {"{{TITLE}}": html.escape(title + (" - storyboard" if storyboard else "")),
            "{{FONTS_LINK}}": fonts_link(module), "{{CONFIG}}": json.dumps(config), "{{SCRIPTS}}": scripts}
    text = _read("lib/page.html")
    for key, value in fill.items():
        text = text.replace(key, value)
    return text


def page(style, aspect: str | None = None, storyboard: bool = False, panels: int = 6) -> str:
    """The style's own reference animation as a page (`module_page`)."""
    return module_page(_read(module_path(style).relative_to(ROOT).as_posix()), style["name"], aspect, storyboard,
                       panels)
