"""The organic AI video's recipe and generation pack (FLOWS.md D1 to E2): live prices, the check, the
Markdown beside the pack and the two step checks.

The agent writes `03_wip/pack_vNN.json` (`pack/1`, `schemas/pb3_pack.schema.json`) in the page language.
At D1 it holds the recipe (production type, sections, product, host, script, taste, style spec) and is
checked with `tm organic pack check --stage recipe`; at E2 the whole pack (models, speech, stages,
resolution, cost, facts, risk, sound) with `--stage pack`. `check` gives the problems; a pass marks the
file (`stepchecks.mark`, key `recipe` or `pack`), writes `pack_vNN.md` beside it (`render_md`) and, at
the pack stage, plans the money: run.json `planned` = the pack's totals per budget kind and `planned_at`
= now, so the pack check-in's yes must come after it (flow's `approval_gap`, preflight P3-F1); a re-check
with the same items and no higher total keeps the earlier yes (`record`).

What the pack stage holds the pack to, beyond the recipe:
- models (OV6): a video model is the configured tier's (`TIERS`), unless the user named it and all six
  `CRITERIA` are answered; a person described in text goes to Seedance 2.0, a host image to MiniMax H3
  whatever the tier, and Seedance never takes a photoreal face (E005); a sound-led format never goes to the budget
  tier; one video model per section; each model has its recipe in `references/model-prompting/` and a
  ranking no older than `pricing.max_age_days`;
- speech (OV7): a talking character speaks natively on H3 unless a reason is given; native speech fits one
  take (`qa.wps_max` words a second, `qa.tail_s` after the last line, `qa.take_max_s` long); a voice
  reference only on the user's words, its sample at most 14 s; no ElevenLabs route the stack lacks; an ElevenLabs
  voiceover over takes is held to the same `qa.wps_min` over the whole video, and every one says its numbers in
  words (#88);
- resolution (OV8): 768p (or 720p), 1080p and the base with Pruna's upscale, each with its cost;
- redos (PR C review I4): a line marked `"redo": true` prices one redo the user asked for (`tm organic redo`, a
  page's redo, or the automatic image redo that did not fit), priced like its item's own line; at most one per
  request, so a redo raises the total and needs the pack check-in's yes again (`--change`);
- cost: each paid stage item (its `images` or `seconds`) has one `ai_usd` line of its model and units, a take
  or an upscale priced at the chosen resolution, and the chosen option's cost is the takes' lines; each line
  is priced from a saved price file (`price_of`) checked no more than `pricing.max_age_days` ago, with units,
  price and cost above 0 and the cost unit price × units; voice credits are the said lines' characters, on
  an ElevenLabs route, at the line's text-to-speech model's credit rate (`tts_models.rate`, #88); the totals are
  the sums and within `budget.per_run_usd`, and a week slot's `ai_usd`
  within the week's remainder too (`organic_week.week_left`: the week run's `budget.per_week_usd` minus what the week's other
  slot runs planned, approved or spent); money is in USD, with
  `1 USD = <rate> <CODE>` for an account in another currency;
- facts with sources; risk hits from the nine OV4 items, each with a mitigation, and no percentages.

An animation (the whole video, or a section of it) is drawn in the user's own browser by the Atlas renderer, so
the recipe check holds it to what drawing needs (drift check 13: no doctor row can say a pack animates): the
`animatic` tier set up and a browser (`atlas.missing()`, in PB02's words). Its items (`animated`) are the pack's
id for a whole animation, else each animation section's id; each has a storyboard, whose pick goes stale after a
pack check that changed what it shows: its scenes (each script line's `shot` and its `on_screen` text, in order), its
style or its section (`item_marks`, key `storyboard_key`). The spoken `text` (what goes to the voice) is not drawn, so a
change to it alone keeps the storyboard's accept (issue #90).

Stills with motion graphics (FLOWS.md F4, a quiz or a ranking): pictures (GPT Image 2 cards, paid and picked at
F1, or the user's own pictures, an images item with no model) in a QuizGrid, RankingList or RankingSplit render
(F2, free). Its items (`stills`) are the pack's id, else each stills section's id. A generated item of any pack is
made on Replicate, so the pack stage refuses one when the run's stack has no Replicate key.

A video in sections (FLOWS.md F5): `sections` follow each other (the `to` of one is the `from` of the next, each
`from` before its `to`); every footage or talking section is made with the same video model, and an animation insert or
a stills section names none; each section's type passes as the whole video's would. The pack's id and each section's
id name folders (`03_wip/<id>/`), so each is ASCII letters, digits, '_' and '-', never a Windows device name (`id_gap`),
and no two section ids differ only in case (PR D review I2). G1's `sections_covered`
(`organic_final.sections_gap`) checks the edit against them.

The copied look (OV3, lesson 21): a `style_spec` (needed for a Recreate) is `{layout, font_class, colours,
number_style, extras, evidence}`, its `evidence` at least 2 distinct URLs of saved videos of the idea's own trends;
the images check-in shows them beside a still of the composition (`organic_gates`).
"""

from __future__ import annotations

import functools
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Literal

from tm import atlas, brand, config, flow, i18n, json_schema, manifest, organic, organic_config, organic_proposals, \
    organic_research, paths, playbooks, runfolder, state, stepchecks, trend_spool, trends, tts_models
from tm.config import Problem
from tm.organic_config import ISSUES
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

WIP = "03_wip"
STEM = "pack"
NAME = re.compile(rf"^{WIP}/{STEM}_v(?P<n>\d+)\.json$")
FILE_PATTERN = f"{WIP}/{STEM}_vNN.json"
SCHEMA = Path(__file__).parent / "schemas" / "pb3_pack.schema.json"
STAGES = ("recipe", "pack")             # also the stepchecks.mark keys
SOURCE = "tm organic pack check"
PACK_KEYS = ("speech", "models", "stages", "resolution", "cost", "facts", "risk", "sound")   # the pack stage's own
TIERS = {"budget": "bytedance/seedance-1.5-pro", "default": "minimax/h3", "top": "bytedance/seedance-2.0",
         "premium": "bytedance/seedance-2.5"}   # OV6; premium only when the user asks for it
DESCRIBED_PERSON = "bytedance/seedance-2.0"   # a person from a description: no face image, so Seedance takes it
FACE_HOST = "minimax/h3"                       # a host image goes to H3, whatever the tier (Seedance refuses it)
FACE_BLOCKED = "bytedance/seedance"            # Seedance refuses photoreal faces in its inputs (Replicate E005)
VIDEO_TYPES = ("ai_footage", "talking_character")   # the section types a video model makes
ROUTES = ("h3_native", "h3_narrator", "elevenlabs_narrator", "elevenlabs_lipsync", "none")
# The six questions a model the user names is checked against (resources/model-prompting/README.md,
# "The user names another model"): each answered true, false or "not needed".
CRITERIA = {
    "photoreal_person": "a photoreal AI person image is accepted (when a specific influencer is used)",
    "product_with_person": "the product enters from an image together with the person",
    "speech": "native speech with lip sync, or the ElevenLabs and lip-sync route",
    "vertical": "9:16",
    "take_length": "a take long enough for the script",
    "live_price": "available at the user's provider with a live price",
}
VOICE_SAMPLE_MAX_S = 14   # OV7: a voice reference's sample, at most 14 s
RECIPES = paths.bundled_data().parent / "references" / "model-prompting"   # the plugin's recipes (Task 18)
RECIPE_PREFIX = "references/model-prompting/"
UPSCALE = "pruna"                              # the upscale option is <base>_pruna
UPSCALER = "prunaai/p-video-upscale"           # OV8's default upscaler, an item of the upscale stage
IMAGES_STAGE, VIDEO_STAGE, UPSCALE_STAGE = "images", "video", "upscale"   # an images item makes images; any other, seconds
RESOLUTION_WORDS = {"base": ("720p", "768p"), "1080p": ("1080p", "2k")}   # a price tier's target resolution (H3: 768P, 2K)
NOT_YET = ("A talking piece longer than one take is not supported yet (the voice can change between takes): "
           f"shorten the lines or move a beat to B-roll ({ISSUES})")
TOL = 1e-9
REDO_LINE = "redo"                             # a cost line `"redo": true` prices one requested redo of its item
REDO_REQUEST = "request"                       # run.json organic.redos[<stem>][].kind of a redo the user asked for
_PERCENT = re.compile(r"%")
_TARGET = re.compile(r"target resolution=([^,]+)", re.IGNORECASE)
_RATE = re.compile(r"^1 USD = (\d+(?:[.,]\d+)?) ([A-Z]{3})$")
_SHAPE_TODO = f"Write the pack in the plugin's schema (schemas/{SCHEMA.name}), as a new version."
# The pack's id and each section's id name folders and files of the run (03_wip/<id>/, 04_final/<id>_final_vNN.mp4),
# so each is ASCII letters, digits, '_' and '-' and never a name Windows keeps for a device (PR D review I2).
FOLDER_ID = re.compile(r"[A-Za-z0-9_-]+")
WINDOWS_DEVICES = frozenset({"CON", "PRN", "AUX", "NUL", *(f"{d}{n}" for d in ("COM", "LPT") for n in range(1, 10))})
ID_TODO = "Name it S1, S2, ... or another id of ASCII letters, digits, '_' and '-'"


def price_of(price_file: Path, model: str, criteria: str | None = None) -> tuple[float, str, str]:
    """(price as a number, unit, checked) of `model` in a `tm tool replicate_price` file. `criteria` is
    a tier's criteria text as the file holds it ("target resolution=720p"); it may be left out only
    when the model has one tier. A ValueError names the tiers when the criteria match not exactly one."""
    entries = json.loads(Path(price_file).read_text(encoding="utf-8"))
    entry = next((e for e in entries if isinstance(e, dict) and e.get("model") == model), None)
    if entry is None:
        raise ValueError(f"{model} is not in {Path(price_file).name}.")
    if "error" in entry:
        raise ValueError(f"{model} has no price in {Path(price_file).name}: {entry['error']}.")
    tiers = entry.get("tiers") or []
    found = [t for t in tiers if criteria is None or t.get("criteria") == criteria]
    if len(found) != 1:
        names = "; ".join(f"{t.get('criteria')} = {t.get('price')} per {t.get('unit')}" for t in tiers) or "none"
        what = "no criteria were given" if criteria is None else f"criteria {criteria!r} match {len(found)}"
        raise ValueError(f"{model}: {what}, and exactly one tier is needed. Tiers: {names}.")
    tier = found[0]
    text = str(tier.get("price") or "").replace("$", "").replace(",", "").strip()
    try:
        price = float(text)
    except ValueError:
        price = float("nan")
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"{model}: the price {tier.get('price')!r} is not a number above zero.")
    return price, str(tier.get("unit") or ""), str(entry.get("checked") or "")


# --- the check ------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _schema() -> dict:
    return json_schema.load(SCHEMA)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _usd(amount: float) -> str:
    return f"${amount:.2f}"


def _day(text: object) -> date | None:
    try:
        return date.fromisoformat(str(text))
    except ValueError:
        return None


def _proposal(run: RunFolder) -> dict:
    """The idea this production run was started from (`00_raw/proposal.json`), or {} without one."""
    path = run.path / organic_proposals.PROPOSAL_FILE
    if not path.is_file():
        return {}
    try:
        kept = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError:
        raise Stop(f"{organic_proposals.PROPOSAL_FILE} is not valid JSON; this run's start is damaged. Start the idea "
                   f"again; {AGAIN}.") from None
    return kept if isinstance(kept, dict) else {}


def idea_of(run: RunFolder) -> dict:
    """The proposal itself (its trends, approach, ...) from `00_raw/proposal.json`, or {} without one."""
    idea = _proposal(run).get("proposal")
    return idea if isinstance(idea, dict) else {}


def id_gap(value: object) -> str | None:
    """Why `value` cannot name a folder of the run (`FOLDER_ID`, `WINDOWS_DEVICES`), or None."""
    text = str(value)
    if not FOLDER_ID.fullmatch(text):
        return f"{text!r} cannot name a folder: an id holds only ASCII letters, digits, '_' and '-'"
    if text.upper() in WINDOWS_DEVICES:
        return (f"{text!r} cannot name a folder: it is a name Windows keeps for a device (CON, PRN, AUX, NUL, COM1 to "
                "COM9, LPT1 to LPT9, in any case)")
    return None


def _types(pack: dict) -> set[str]:
    """The production types the pack uses: its own and its sections'."""
    return {pack["production"]} | {s["type"] for s in pack["sections"]}


def shape(pack: object, stage: str) -> list[Problem]:
    """What breaks the schema (and, at the pack stage, a missing pack key), as problems."""
    if not isinstance(pack, dict):
        return [Problem("pack", "The pack is not one JSON object.", "Write one JSON object.")]
    out = [Problem(line.split(" ", 1)[0].removeprefix("pack."), line, _SHAPE_TODO)
           for line in json_schema.problems(pack, _schema(), name="pack")]
    if stage == "pack":
        out += [Problem(k, f"The pack has no {k}.", f"Write {k}: the pack stage needs {', '.join(PACK_KEYS)}.")
                for k in PACK_KEYS if k not in pack]
    return out


def check(run: RunFolder, pack: dict, cfg: dict, *, stage: Literal["recipe", "pack"], today: date) -> list[Problem]:
    """Everything wrong in the pack at this stage (the module docstring), each with what to do. Empty means
    it passes."""
    if stage not in STAGES:
        raise ValueError(f"stage is one of {', '.join(STAGES)}, not {stage!r}.")
    out = shape(pack, stage)
    if out:
        return out
    _recipe(run, pack, cfg, out)
    if stage == "pack":
        _pack(run, pack, cfg, today, out)
    return out


def _bad(out: list[Problem], field: str, what: str, todo: str) -> None:
    out.append(Problem(field, what, todo))


def _dated(when: date | None, today: date, max_age: int | None, what: str) -> str | None:
    """Why a price or ranking date cannot be used today, or None: unreadable, after today, or too old."""
    if when is None:
        return f"{what} has no date (YYYY-MM-DD)"
    if when > today:
        return f"{what} is dated {when}, after today ({today}): the date is wrong"
    if max_age is not None and (today - when).days > max_age:
        return f"{what} was checked on {when}, more than {max_age} days before {today}"
    return None


def _recipe(run: RunFolder, pack: dict, cfg: dict, out: list[Problem]) -> None:
    s = state.load(run)
    own = s.organic or {}
    if _text(own.get("proposal")) and str(pack["id"]).lower() != own["proposal"].lower():
        _bad(out, "id", f"This production run was started for {own['proposal']}, and the pack is for {pack['id']!r}.",
             f"Write the pack for {own['proposal']} in this run; another idea's pack goes in its own run.")
    if why := id_gap(pack["id"]):
        _bad(out, "id", f"The pack's id {why} (03_wip/<id>/ of a whole animation, 04_final/<id>_final_vNN.mp4).",
             "Write the pack under the idea's id; an idea whose id is not such a name is proposed again under one.")
    channel = own.get("channel") or next(iter(cfg.get("channels") or []), None)
    if channel and brand.channel_key(pack["channel"]) != channel:
        _bad(out, "channel", f"This run is for the channel {channel}, and the pack names {pack['channel']!r}.",
             f"Set channel to {channel}.")
    if i18n.tag(pack["lang"]) != organic_config.page_lang(cfg):
        _bad(out, "lang", f"The pack is in {pack['lang']!r} and the run's pages are in "
                          f"{organic_config.page_lang(cfg)!r} (config.yaml languages.working).",
             "Write the pack in the page language.")
    hidden = organic.hidden_types(organic.stack_of(run))
    productions = organic_proposals.PRODUCTIONS
    undrawn = False
    for field, kind in [("production", pack["production"])] + [(f"sections[{i}].type", x["type"])
                                                               for i, x in enumerate(pack["sections"])]:
        allowed = productions if field == "production" else tuple(p for p in productions if p != "sections")
        if kind not in allowed:
            _bad(out, field, f"{kind!r} is not a production type: one of {', '.join(allowed)}.",
                 "Name the production type.")
        elif kind in hidden:
            _bad(out, field, f"{_made(field, kind)}: that needs {organic_proposals.NEEDS[kind][1]}, which this run's "
                 "stack does not have.",
                 "Record the stack again once it is set up (tm organic stack), or make this idea as a script to film.")
        elif kind == "animation" and not undrawn and (gap := atlas.missing()) is not None:
            undrawn = True                       # said once, for the whole animation or its first section
            _bad(out, field, f"{_made(field, kind)}. {gap[1]}",
                 f"{gap[2]}, then check the pack again; or make this idea as a script to film.")
    _sections(pack, out)
    _product(run, pack, out)
    idea = idea_of(run)
    approach = organic_proposals.APPROACHES.get(str(idea.get("approach", "")).strip().lower())
    if approach == "Recreate" and not pack["style_spec"]:
        _bad(out, "style_spec", "The idea recreates its evidence (Recreate), and the pack has no style spec.",
             "Write style_spec from at least 2 of the saved evidence videos (OV3).")
    elif pack["style_spec"]:
        _style_spec(run, pack["style_spec"], idea, out)
    _taste(pack, out)


def _sections(pack: dict, out: list[Problem]) -> None:
    """FLOWS.md F5: the sections follow each other, one video model for every footage or talking section, none for an
    animation insert or a stills section."""
    secs = pack["sections"]
    seen: dict[str, int] = {}
    for i, sec in enumerate(secs):
        key = str(sec["id"]).casefold()
        if why := id_gap(sec["id"]):
            _bad(out, f"sections[{i}].id", f"Section {i + 1}'s id {why} (03_wip/<id>/ holds an insert's prompt, "
                 "storyboard and renders).", f"{ID_TODO}.")
        elif key in seen:
            _bad(out, f"sections[{i}].id", f"Section {i + 1}'s id {sec['id']!r} is section {seen[key] + 1}'s id too, "
                 "in any case (Windows and macOS see one folder for both).", f"Give each section its own id: {ID_TODO}.")
        seen.setdefault(key, i)
    if abs(secs[0]["from"]) > TOL:                         # PR D review M3
        _bad(out, "sections[0].from", f"Section 1 starts at {secs[0]['from']:g} s, and the video starts at 0 s.",
             "Start section 1 at 0: the sections cover the video from its start.")
    production = pack["production"]
    words = organic_proposals.PRODUCTION_WORDS
    if production != "sections" and production in words:
        if len(secs) > 1:
            _bad(out, "sections", f"The pack lists {len(secs)} sections, and its production is {words[production]}: "
                 "several sections are a video in sections.",
                 "Set production to sections (each section's type its own), or list one section of the production's "
                 "type.")
        elif secs[0]["type"] != production and secs[0]["type"] in words:
            _bad(out, "sections[0].type", f"{_made('sections[0].type', secs[0]['type'])}, and the pack's production is "
                 f"{words[production]}.", f"Give the one section the production's type, {production}.")
    for i, sec in enumerate(secs):
        if i and abs(sec["from"] - secs[i - 1]["to"]) > TOL:
            _bad(out, f"sections[{i}].from", f"Section {i + 1} starts at {sec['from']:g} s, and section {i} ends at "
                 f"{secs[i - 1]['to']:g} s.", f"Start it at {secs[i - 1]['to']:g} s: the sections follow each other.")
        if not sec["to"] > sec["from"]:
            _bad(out, f"sections[{i}].to", f"Section {i + 1} ends at {sec['to']:g} s, not after its start "
                 f"({sec['from']:g} s).", "Give each section its length: its to after its from.")
    first = None
    for i, sec in enumerate(secs):
        model = sec["model"]
        if sec["type"] in VIDEO_TYPES:
            if not _text(model):
                continue                         # the pack stage asks for its model (_models)
            if first is None:
                first = model
            elif model != first:
                _bad(out, f"sections[{i}].model", f"Section {i + 1} is made with {model}, and an earlier footage or "
                     f"talking section with {first}: one video model for every one of them (OV6).",
                     f"Make it with {first} too; another model only for a separate kind of section (an animation insert).")
        elif _text(model) and sec["type"] in organic_proposals.PRODUCTIONS:
            _bad(out, f"sections[{i}].model", f"{_made(f'sections[{i}].type', sec['type'])}, and it names the video "
                 f"model {model}.", "Set its model to null: an animation insert or stills section uses no video model.")


STYLE_TEXT = ("layout", "font_class", "number_style")   # OV3's style spec, read from the evidence (lesson 21)
STYLE_LISTS = ("colours", "extras")


def _style_spec(run: RunFolder, spec: object, idea: dict, out: list[Problem]) -> None:
    """OV3: the look read from at least 2 saved evidence videos of the idea's own trends, named by their URLs."""
    if not isinstance(spec, dict):
        _bad(out, "style_spec", "The style spec is not one object.", "Write style_spec as one JSON object.")
        return
    for key in STYLE_TEXT:
        if not _text(spec.get(key)):
            _bad(out, f"style_spec.{key}", f"The style spec has no {key}.",
                 f"Write its {key} as read from the evidence videos (OV3: layout, font class, colours, number style, "
                 "extras).")
    for key in STYLE_LISTS:
        value = spec.get(key)
        if not (isinstance(value, list) and all(_text(v) for v in value) and (value or key == "extras")):
            _bad(out, f"style_spec.{key}", f"The style spec's {key} is not a list of words"
                 + (" with at least one" if key == "colours" else "") + ".", f"Write {key} as a list of short texts.")
    given = spec.get("evidence")
    urls = [u.strip() for u in given if _text(u)] if isinstance(given, list) else []
    if len(set(urls)) < 2:
        _bad(out, "style_spec.evidence", f"The style spec names {len(set(urls))} evidence video"
             f"{'' if len(set(urls)) == 1 else 's'}; it is read from at least 2 distinct ones.",
             "Name at least 2 different evidence videos by their URLs (tm organic videos lists them).")
        return
    saved, trend_ids = evidence_videos(run, idea)
    for url in dict.fromkeys(urls):
        if url not in saved:
            _bad(out, "style_spec.evidence", f"{url} is not a saved video of this idea's trends "
                 f"({', '.join(trend_ids) or 'none'}).",
                 "Name evidence videos of the idea's own trends by the URL tm organic videos shows.")


def evidence_videos(run: RunFolder, idea: dict) -> tuple[dict[str, dict], list[str]]:
    """The saved videos of the idea's trends by URL, and the trend ids as the proposal gives them. A trend with no saved
    card adds none."""
    by_url: dict[str, dict] = {}
    ids = [str(t.get("id")) for t in idea.get("trends") or [] if isinstance(t, dict) and _text(t.get("id"))]
    for given in ids:
        try:
            tid, _ = organic_research.resolve(run, given)
        except ValueError:            # no card (a Stop) or not one: no saved videos to match
            continue
        for video in trends.load_videos(run, tid):
            if isinstance(video, dict) and _text(video.get("url")):
                by_url.setdefault(video["url"].strip(), video)
    return by_url, ids


def _made(field: str, kind: str) -> str:
    """The pack's production type (`production`) or a section's (`sections[i].type`), in the user's words."""
    words = organic_proposals.PRODUCTION_WORDS[kind]
    if field == "production":
        return f"This idea is {words}"
    return f"Section {int(field.split('[')[1].split(']')[0]) + 1} is {words}"


def _product(run: RunFolder, pack: dict, out: list[Problem]) -> None:
    """OV5: a product that is featured or the hero comes from a packshot of the store's catalogue."""
    level = organic_proposals.PRODUCT_WORDS.get(str(pack["product"]["level"]).strip().lower())
    if level is None:
        _bad(out, "product.level", f"{pack['product']['level']!r} is not a product level.",
             f"Use one of {', '.join(organic_proposals.PRODUCT_LEVELS)}.")
        return
    if level not in ("featured", "hero"):
        return
    shots = pack["product"]["packshots"]
    if not shots:
        _bad(out, "product.packshots", f"The product is {level}, and the pack names no packshot.",
             "Name the product's packshot from the store's catalogue (made once with tm brand packshot) (OV5).")
        return
    workspace = trend_spool.workspace_of(run)
    try:
        profile = brand.latest(workspace, pack["channel"], kind="channel") or {}
        store = brand.latest(workspace, profile["store"]) if _text(profile.get("store")) else None
    except ValueError:
        store = None
    known = {p.get("packshot") for p in ((store or {}).get("catalog") or {}).get("products") or []
             if isinstance(p, dict) and _text(p.get("packshot"))}
    for i, shot in enumerate(shots):
        if shot not in known:
            _bad(out, f"product.packshots[{i}]", f"{shot} is not a packshot of the channel's store catalogue.",
                 "Name a packshot the store's catalogue holds (tm brand show), or save one with tm brand packshot.")
        elif not (workspace / shot).is_file():
            _bad(out, f"product.packshots[{i}]", f"{shot} is named in the catalogue, and the file is missing.",
                 "Save the packshot again with tm brand packshot.")


def _taste(pack: dict, out: list[Problem]) -> None:
    """D2 asks only where needed: a style for an animation, a voice for lines someone says, and music."""
    taste = pack["taste"]
    if taste["style"] is not None and "animation" not in _types(pack):
        _bad(out, "taste.style", "A style is picked, and nothing in this video is animated.",
             "Set taste.style to null: the style is asked only for an animation.")
    if taste["voice"] is not None and all(line["speaker"] == "none" for line in pack["script"]["lines"]):
        _bad(out, "taste.voice", "A voice is picked, and no line is said.",
             "Set taste.voice to null: the voice is asked only when someone speaks.")
    picked = any(taste[k] is not None for k in ("style", "voice", "music"))
    if picked and taste["by"] == "agent" and not _text(taste["why"]):
        _bad(out, "taste.why", "The agent picked the taste, and the reason is not logged.",
             "Write why: Hands-off logs the agent's pick with its reason.")


def _pack(run: RunFolder, pack: dict, cfg: dict, today: date, out: list[Problem]) -> None:
    made = [item["name"] for st in pack["stages"] for item in st["items"] if _text(item["model"])]
    if made and (organic.stack_of(run) or {}).get("replicate") != "ok":
        _bad(out, "stages", f"{', '.join(made)} {'is' if len(made) == 1 else 'are'} generated on Replicate, and this "
             "run's stack has no Replicate key (REPLICATE_API_TOKEN).",
             "Set the key up and record the stack again (tm organic stack); or, for stills with motion graphics, use "
             "the user's own pictures (an images item with no model); or make this idea as a script to film.")
    video = _models(pack, cfg, today, out)
    _speech(run, pack, cfg, out)
    _resolution(pack, video, out)
    _cost(run, pack, cfg, today, video, out)
    for i, fact in enumerate(pack["facts"]):
        if not (_text(fact["claim"]) and _text(fact["source"])):
            _bad(out, f"facts[{i}]", f"Fact {i + 1} has no claim or no source.",
                 "Give every fact its source (OV14); the sources stay in the pack, never in the post.")
    for i, hit in enumerate(pack["risk"]["hits"]):
        if hit["item"] not in organic_proposals.RISK_ITEMS:
            _bad(out, f"risk.hits[{i}].item", f"{hit['item']!r} is not a risk item.",
                 f"Use one of {', '.join(organic_proposals.RISK_ITEMS)} (OV4).")
        if not _text(hit["mitigation"]):
            _bad(out, f"risk.hits[{i}].mitigation", f"The risk {hit['item']!r} has no mitigation.",
                 "Say how the risk is kept down.")
    if _PERCENT.search(json.dumps(pack["risk"], ensure_ascii=False)):
        _bad(out, "risk", "The risk holds a percentage.",
             "Name the risk and its mitigation in words, without percentages (OV4).")


def _fixed_model(pack: dict) -> tuple[str, str] | None:
    """(model, why) when the host decides the video model whatever the tier, else None."""
    host = pack["host"]["kind"]
    if host == "description":
        return DESCRIBED_PERSON, "a person described in text goes to Seedance 2.0"
    if host == "image":
        return FACE_HOST, "a host image goes to MiniMax H3, whatever the tier"
    return None


def _models(pack: dict, cfg: dict, today: date, out: list[Problem]) -> set[str]:
    """OV6. The video models the pack uses (its sections' and its video stage's), checked."""
    listed = {m["model"]: (i, m) for i, m in enumerate(pack["models"])}
    video: set[str] = set()
    section_models = set()
    for i, sec in enumerate(pack["sections"]):
        if sec["type"] in VIDEO_TYPES and not _text(sec["model"]):
            _bad(out, f"sections[{i}].model", f"Section {sec['id']} is {sec['type']} and names no video model.",
                 "Name its one video model.")
        if _text(sec["model"]):
            section_models.add(sec["model"])
    video |= section_models
    for si, st in enumerate(pack["stages"]):
        for ii, item in enumerate(st["items"]):
            if not _text(item["model"]):
                continue
            if item["model"] not in listed:
                _bad(out, f"stages[{si}].items[{ii}].model", f"{item['model']} is used and not listed in models.",
                     "List it in models with why, its recipe and its ranking.")
            if st["stage"] == VIDEO_STAGE:
                video.add(item["model"])
                if item["model"] not in section_models:
                    _bad(out, f"stages[{si}].items[{ii}].model",
                         f"{item['name']} is made with {item['model']}, which no section names: one video model per "
                         "section.", "Make every take of a section with that section's model; another model needs a "
                         "section of its own.")
    for model in sorted(section_models - set(listed)):
        _bad(out, "models", f"{model} is used by a section and not listed in models.",
             "List it in models with why, its recipe and its ranking.")
    tier = cfg.get("generation", {}).get("quality_tier") if isinstance(cfg.get("generation"), dict) else None
    tier = tier if tier in TIERS else "default"
    expected, why = _fixed_model(pack) or (TIERS[tier], f"the {tier} tier's model")
    for model in sorted(video):
        i, entry = listed.get(model, (None, {}))
        field = f"models[{i}]" if i is not None else "models"
        if pack["host"]["kind"] == "image" and model.startswith(FACE_BLOCKED):
            _bad(out, f"{field}.model", f"{model} refuses a photoreal face as input (Replicate E005), and the host is an "
                 "image.", f"Use {FACE_HOST} for a host image, or describe the person in text for Seedance 2.0.")
        if pack["sound_led"] and model == TIERS["budget"]:
            _bad(out, f"{field}.model", f"This format is sound-led, and {model} is the budget tier, whose native sound is "
                 "weak.", "Use MiniMax H3, Seedance 2.0 or Veo 3.1 for a sound-led format (OV6).")
        if entry.get("user_named"):
            _criteria(entry, field, out)
        elif model != expected:
            _bad(out, f"{field}.model", f"{model} is not the video model here: {why} is {expected}.",
                 f"Use {expected}, or, when the user names another model, set user_named and answer the six criteria.")
    max_age = config.get(cfg, "pricing.max_age_days")
    for model, (i, m) in listed.items():
        recipe = m["recipe"]
        if not (_text(recipe) and recipe.startswith(RECIPE_PREFIX) and "/" not in recipe[len(RECIPE_PREFIX):]
                and (RECIPES / recipe[len(RECIPE_PREFIX):]).is_file()):
            _bad(out, f"models[{i}].recipe", f"{model} has no recipe in {RECIPE_PREFIX}"
                 + (f" ({recipe} is not there)." if _text(recipe) else "."),
                 f"Write its recipe first ({RECIPE_PREFIX}<model>.md, from the model's own prompting guide), then name it.")
        if not _text(m["ranking"]["source"]):
            _bad(out, f"models[{i}].ranking", f"{model}'s ranking names no source.", "Name the ranking read.")
        late = _dated(_day(m["ranking"]["date"]), today, max_age, f"{model}'s ranking")
        if late:
            _bad(out, f"models[{i}].ranking.date", f"{late}.", "Read the ranking again today and update the date.")
    return video


def _criteria(entry: dict, field: str, out: list[Problem]) -> None:
    """A model the user named passes when all six criteria are answered and none fails."""
    answers = entry["criteria"] if isinstance(entry["criteria"], dict) else {}
    unanswered = [k for k in CRITERIA if answers.get(k) not in (True, False, "not needed")]
    failing = [k for k in CRITERIA if answers.get(k) is False]
    if unanswered:
        _bad(out, f"{field}.criteria", f"The user named {entry['model']}, and these criteria are not answered: "
             + "; ".join(f"{k} ({CRITERIA[k]})" for k in unanswered) + ".",
             "Answer each with true, false or \"not needed\".")
    if failing:
        _bad(out, f"{field}.criteria", f"{entry['model']} fails: "
             + "; ".join(f"{k} ({CRITERIA[k]})" for k in failing) + ".",
             "Tell the user which one fails and suggest the tier's model.")


def _said(pack: dict) -> list[str]:
    return [line["text"] for line in pack["script"]["lines"] if line["speaker"] != "none"]


def _speech(run: RunFolder, pack: dict, cfg: dict, out: list[Problem]) -> None:
    """OV7."""
    speech, script = pack["speech"], pack["script"]
    route = speech["route"]
    if "talking_character" in _types(pack) and route != "h3_native" and not _text(speech["alternative_reason"]):
        _bad(out, "speech.route", f"A talking character speaks natively on H3 by default, and the route is {route}.",
             "Use h3_native, or give alternative_reason (the user's request, exact wording or a brand voice).")
    said = sum(len(text.split()) for text in _said(pack))
    if said != script["words"]:
        _bad(out, "script.words", f"script.words is {script['words']}, and the lines said hold {said} words.",
             f"Set words to {said}.")
    if route == "h3_native":
        most, tail, take = (config.get(cfg, k) for k in ("qa.wps_max", "qa.tail_s", "qa.take_max_s"))
        if take is not None and script["seconds"] > take + TOL:
            _bad(out, "script.seconds", f"The talking piece is {script['seconds']:g} s, longer than one {take:g} s take. "
                 f"{NOT_YET}.", "Shorten the lines or move a beat to B-roll.")
        elif most is not None and tail is not None and said > most * (script["seconds"] - tail) + TOL:
            fit = most * (script["seconds"] - tail)
            _bad(out, "script.words", f"{said} words do not fit {script['seconds']:g} s: at most {fit:g} fit ({most:g} "
                 f"words a second, {tail:g} s after the last line).", "Cut words, or move a line to B-roll.")
        else:
            _slow(pack, cfg, said, out)
    elif route == "h3_narrator":
        take = config.get(cfg, "qa.take_max_s")
        if take is not None and script["seconds"] <= take + TOL:     # r3: one narrator take, measured by the QA too
            _slow(pack, cfg, said, out)
    elif route in organic.ELEVENLABS_ROUTES and _types(pack) & set(VIDEO_TYPES):
        _slow(pack, cfg, said, out)   # #88: one recording over the takes, held to their pace (an animation is drawn on
        # the voice's own times; `tm organic vo-sync` measures every recorded voiceover)
    _numbers(pack, out)
    ref = speech["voice_reference"]
    if ref is not None:
        if not _text(ref["user_words"]):
            _bad(out, "speech.voice_reference", "A voice reference is used, and the user did not ask for it.",
                 "Set voice_reference to null, or write the user's own words asking for it.")
        if not 0 < ref["sample_s"] <= VOICE_SAMPLE_MAX_S:
            _bad(out, "speech.voice_reference.sample_s", f"The voice sample is {ref['sample_s']:g} s; at most "
                 f"{VOICE_SAMPLE_MAX_S} s is used.", f"Cut the sample to {VOICE_SAMPLE_MAX_S} s or less, with the same text.")
    if route in organic.unavailable_routes(organic.stack_of(run)):
        _bad(out, "speech.route", f"{route} needs ElevenLabs, which this run's stack does not have (no key, no credits, "
             "or not checked yet).", "Use h3_native or h3_narrator, or check ElevenLabs again (tm organic stack).")


_DIGITS = re.compile(r"\d+(?:[.,:]\d+)*\s?%?")


def _numbers(pack: dict, out: list[Problem]) -> None:
    """OV7 (#88 point 2): an ElevenLabs voiceover writes numbers, dates and percentages out as words, in the case the
    sentence needs, in the market's language (a year or a count in digits was read in the wrong form). The captions
    and the picture may keep digits."""
    if pack["speech"]["route"] not in organic.ELEVENLABS_ROUTES:
        return
    for i, line in enumerate(pack["script"]["lines"]):
        if line["speaker"] == "none":
            continue
        found = [m.group(0).replace(" ", "") for m in _DIGITS.finditer(line["text"])]
        if found:
            _bad(out, f"script.lines[{i}].text", f"Line {line['n']} says {', '.join(found)} in digits, and the voice "
                 "reads digits in a form of its own.", "Write each number, date and percentage out as words, in the "
                 "case the sentence needs, in the market's language; the captions may keep the digits.")


def _slow(pack: dict, cfg: dict, said: int, out: list[Problem]) -> None:
    """A take that speaks its lines (route h3_native, one take, the route the `qa.wps_max` fit is checked on; or one
    h3_narrator take, PR E r3: the take QA measures the pace of both, `organic_qa.SPEECH_IN_TAKE`) is planned at no
    less than `qa.wps_min` words a second over its speech (its seconds less `qa.tail_s`), the pace the take QA holds it
    to (`organic_qa.rubric_takes`): a pack never pays for a take the QA finds slow (Task 22's E2 pack, Task 21 fix
    round 2). A narrator over several takes is not: its seconds are the whole video's. The todo names the lengths both
    pace checks pass (r2), and the whole-second takes among them."""
    script = pack["script"]
    least, most, tail = (config.get(cfg, k) for k in ("qa.wps_min", "qa.wps_max", "qa.tail_s"))
    if pack["speech"]["route"] not in ("h3_native", "h3_narrator", *organic.ELEVENLABS_ROUTES) or least is None \
            or tail is None or not said:
        return
    span = script["seconds"] - tail
    if span > TOL and said < least * span - TOL:
        hi = math.floor((said / least + tail) * 10 + TOL) / 10
        lo = math.ceil((said / most + tail) * 10 - TOL) / 10 if most else None
        whole = [n for n in range(math.ceil(lo if lo is not None else 0), math.floor(hi) + 1) if n > 0]
        if lo is None:
            todo = f"Add words to the lines, or shorten the take (to {math.floor(hi)} s or less), and price it again."
        elif whole:
            took = f"{whole[0]}" if len(whole) == 1 else f"{whole[0]} to {whole[-1]}"
            todo = (f"Add words to the lines, or shorten the take to {took} s ({said} words pass both qa.wps_min and "
                    f"qa.wps_max from {lo:g} to {hi:g} s), and price it again.")
        else:
            todo = (f"Add words to the lines: {said} words pass both qa.wps_min and qa.wps_max only between {lo:g} and "
                    f"{hi:g} s, which holds no whole-second take. Then price it again.")
        _bad(out, "script.words", f"{said} words over {span:g} s of speech ({script['seconds']:g} s less {tail:g} s after "
             f"the last line) is {said / span:.2f} words a second, under {least:g} (qa.wps_min, the take QA's pace): "
             "the take would come out slow.", todo)


def _resolution(pack: dict, video: set[str], out: list[Problem]) -> None:
    """OV8: with a video model, the three options, each costed, and the choice among them; the Pruna option
    is an upscale item in the stages, and only that option has one."""
    if not video:
        return
    res = pack["resolution"]
    if res is None:
        _bad(out, "resolution", "The pack makes video and asks no resolution.",
             "Offer 768p (or 720p), 1080p and the base with Pruna's upscale, each with its cost.")
        return
    ids = [o["id"] for o in res["options"]]
    base = next((b for b in ("768p", "720p") if b in ids), "768p")
    wanted = {base, "1080p", f"{base}_{UPSCALE}"}
    if len(ids) != 3 or set(ids) != wanted:
        _bad(out, "resolution.options", f"The options are {', '.join(ids) or 'none'}; the question has exactly "
             f"{', '.join(sorted(wanted))}.", "Offer those three, each with its cost for the chosen model.")
    for i, o in enumerate(res["options"]):
        if not o["cost"] > 0:
            _bad(out, f"resolution.options[{i}].cost", f"The option {o['id']} has no cost.",
                 "Give its cost from the price file.")
    if res["choice"] not in ids:
        _bad(out, "resolution.choice", f"The choice {res['choice']!r} is not one of the options.",
             "Choose one of the options.")
    upscales = [item["name"] for st in pack["stages"] if st["stage"] == UPSCALE_STAGE for item in st["items"]
                if item["model"] == UPSCALER]
    if str(res["choice"]).endswith(f"_{UPSCALE}") and not upscales:
        _bad(out, "stages", f"The chosen resolution {res['choice']} upscales, and no {UPSCALE_STAGE} stage item uses "
             f"{UPSCALER}.", f"Add an {UPSCALE_STAGE} stage with the upscale item and its seconds, and its cost line.")
    elif upscales and not str(res["choice"]).endswith(f"_{UPSCALE}"):
        _bad(out, "stages", f"{', '.join(upscales)} upscales, and the chosen resolution {res['choice']} does not.",
             f"Remove the {UPSCALE_STAGE} stage, or choose the option with the upscale.")


def _generated(pack: dict, out: list[Problem]) -> dict[str, tuple[str, dict]]:
    """Each paid stage item by name -> (stage, item); each says what it makes: `images` in the images stage,
    `seconds` in any other."""
    items: dict[str, tuple[str, dict]] = {}
    for si, st in enumerate(pack["stages"]):
        for ii, item in enumerate(st["items"]):
            if not _text(item["model"]):
                continue
            field = f"stages[{si}].items[{ii}]"
            if item["name"] in items:
                _bad(out, f"{field}.name", f"Two items are named {item['name']!r}.", "Give each item its own name.")
            key = "images" if st["stage"] == IMAGES_STAGE else "seconds"
            value = item.get(key)
            if not (_number(value) and value > 0 and (key == "seconds" or isinstance(value, int))):
                _bad(out, f"{field}.{key}", f"{item['name']} does not say how many {key} it makes.",
                     f"Give {key} (a number above 0): its cost line is priced on it.")
            items[item["name"]] = (st["stage"], item)
    return items


def _cost(run: RunFolder, pack: dict, cfg: dict, today: date, video: set[str], out: list[Problem]) -> None:
    kinds = playbooks.get(ORGANIC_VIDEO).budgets
    max_age = config.get(cfg, "pricing.max_age_days")
    items = _generated(pack, out)
    choice = (pack.get("resolution") or {}).get("choice")
    sums = {k: 0.0 for k in kinds}
    priced: dict[str, float] = {}     # item name -> its line's cost
    redo_lines: list[tuple[str, dict]] = []   # (field, line) of each line marked "redo": true
    voice_units = 0.0
    voice_lines = []
    for i, line in enumerate(pack["cost"]["lines"]):
        field = f"cost.lines[{i}]"
        if line["kind"] not in kinds:
            _bad(out, f"{field}.kind", f"{line['kind']!r} is not a budget kind.", f"Use one of {', '.join(kinds)}.")
            continue
        low = [k for k in ("unit_price", "units", "cost") if not line[k] > 0]
        if low:
            _bad(out, f"{field}.{low[0]}", f"{line['what']}: {', '.join(low)} must be above 0.",
                 "A cost line pays for something: give its price, units and cost, or remove the line.")
            continue
        if abs(line["cost"] - round(line["unit_price"] * line["units"], 2)) > TOL:
            _bad(out, f"{field}.cost", f"{line['what']}: {line['unit_price']:g} × {line['units']:g} is "
                 f"{round(line['unit_price'] * line['units'], 2):g}, not {line['cost']:g}.",
                 "Write the cost as unit price × units, rounded to the cent.")
        sums[line["kind"]] += line["cost"]
        if line["kind"] == "ai_usd":
            _priced(run, line, field, today, max_age, out)
            if line.get(REDO_LINE) is True:
                redo_lines.append((field, line))
            else:
                _paid_item(line, field, items, choice, priced, out)
        elif line.get(REDO_LINE) is True:
            _bad(out, f"{field}.{REDO_LINE}", f"{line['what']} is a redo line of kind {line['kind']}.",
                 "A redo line prices a generated item again (kind ai_usd); remove the redo mark.")
        else:
            voice_units += line["units"]
            voice_lines.append(i)
    _redos(run, pack, items, redo_lines, out)
    for name, (stage, item) in items.items():
        if name not in priced:
            _bad(out, "cost.lines", f"{name} ({item['model']}) is generated and has no cost line.",
                 f"Add its ai_usd line (item {name!r}), priced from a saved price file.")
    _voice(pack, voice_units, voice_lines, out)
    res = pack.get("resolution") or {}
    chosen = next((o["cost"] for o in res.get("options") or [] if o["id"] == choice), None)
    made = round(sum(cost for name, cost in priced.items() if items[name][0] != IMAGES_STAGE), 2)
    if video and chosen is not None and priced and abs(chosen - made) > TOL:
        _bad(out, "resolution.options", f"The chosen option {choice} costs {_usd(chosen)}, and the video lines add up to "
             f"{_usd(made)}.", "Price the takes (and the upscale) at the chosen resolution, and give the option that cost.")
    for kind in kinds:
        if abs(pack["cost"]["totals"][kind] - round(sums[kind], 2)) > TOL:
            _bad(out, f"cost.totals.{kind}", f"The {kind} total is {pack['cost']['totals'][kind]:g}, and the lines add "
                 f"up to {round(sums[kind], 2):g}.", "Write the totals as the sums of the lines.")
    budget = config.get(cfg, "budget.per_run_usd")
    total = pack["cost"]["totals"]["ai_usd"]
    if budget is not None and total > budget + TOL:
        _bad(out, "cost.totals.ai_usd", f"The pack costs {_usd(total)}, over the run's budget of {_usd(budget)}.",
             "Cheaper: " + "; ".join(_cheaper(pack, video)) + ". Or ask the user to raise the budget.")
    from tm import organic_week   # it starts production runs (organic_proposals): imported where it is used

    week = organic_week.week_left(run)
    if week is not None and total > week[2] + TOL:
        _bad(out, "cost.totals.ai_usd", f"The pack costs {_usd(total)}, over the week's remainder of {_usd(week[2])} "
             f"(the week's budget is {_usd(week[0])}, and its other videos planned, approved or spent {_usd(week[1])}).",
             "Cheaper: " + "; ".join(_cheaper(pack, video)) + ". Or ask the user to raise the week's budget, and on "
             f"their word set it (tm organic week budget --run {(state.load(run).organic or {}).get('week')} --usd "
             "<amount> --note \"<their words>\"); the week then needs their yes again.")
    currency = str(cfg.get("currency") or "USD").upper()
    if currency != "USD":
        rate = cfg.get("fx_rate")
        note = pack["cost"]["currency_note"]
        m = _RATE.match(note.strip()) if isinstance(note, str) else None
        if not _number(rate):
            _bad(out, "cost.currency_note", f"The account is in {currency}, and the config has no fx_rate.",
                 f"Set fx_rate (how many {currency} one USD buys today), then write currency_note.")
        elif m is None or m[2] != currency or abs(float(m[1].replace(",", ".")) - rate) > TOL:
            _bad(out, "cost.currency_note", f"The account is in {currency}: the pack's money is in USD with the rate, "
                 f"and currency_note is {note!r}.", f"Write currency_note as \"1 USD = {rate:g} {currency}\".")


def _paid_item(line: dict, field: str, items: dict, choice: object, priced: dict, out: list[Problem]) -> None:
    """An ai_usd line pays for one stage item: its model, its units (images or seconds), and, for a take or
    an upscale, the chosen resolution."""
    name = line["item"]
    if name not in items:
        _bad(out, f"{field}.item", f"{line['what']} names the item {name!r}, which the pack's stages do not generate.",
             "Name the stage item the line pays for, or remove the line.")
        return
    if name in priced:
        _bad(out, f"{field}.item", f"{name} has two cost lines.", "Price each item once.")
        return
    priced[name] = line["cost"]
    stage, item = items[name]
    if line["model"] != item["model"]:
        _bad(out, f"{field}.model", f"{line['what']} prices {line['model']}, and {name} is made with {item['model']}.",
             f"Price {item['model']}.")
    key = "images" if stage == IMAGES_STAGE else "seconds"
    if _number(item.get(key)) and abs(line["units"] - item[key]) > TOL:
        _bad(out, f"{field}.units", f"{line['what']} prices {line['units']:g} units, and {name} makes {item[key]:g} {key}.",
             f"Set units to {item[key]:g}.")
    target = _TARGET.search(line["criteria"] or "")
    if target is None or stage not in (VIDEO_STAGE, UPSCALE_STAGE) or not isinstance(choice, str):
        return
    want = "1080p" if stage == UPSCALE_STAGE or choice == "1080p" else "base"
    if target[1].strip().lower() not in RESOLUTION_WORDS[want]:
        res = "1080p" if want == "1080p" else choice.removesuffix(f"_{UPSCALE}")
        _bad(out, f"{field}.criteria", f"{line['what']} is priced at {target[1].strip()}, and {name} is made at {res} "
             f"(the chosen resolution {choice}).", "Price it at the chosen resolution, from the price file.")


def redos_asked(s: state.RunState, stem: str) -> int:
    """How many redos of the item run under `stem` the user asked for: its requests in run.json `organic.redos`
    (`tm organic redo`, a redo on a page, or the automatic image redo that did not fit the budget), one per take they
    were asked after."""
    rows = ((s.organic or {}).get("redos") or {}).get(stem) or []
    return len({r.get("after") for r in rows if isinstance(r, dict) and r.get("kind") == REDO_REQUEST})


def redo_lines(pack: dict, stem: str) -> int:
    """How many redo lines of the item run under `stem` the pack holds."""
    return sum(1 for line in pack["cost"]["lines"] if line.get(REDO_LINE) is True and line.get("kind") == "ai_usd"
               and isinstance(line.get("item"), str) and runfolder.slug(Path(line["item"]).stem) == stem)


def _redos(run: RunFolder, pack: dict, items: dict, found: list[tuple[str, dict]], out: list[Problem]) -> None:
    """A requested redo is priced (PR C review I4): each `"redo": true` line names a priced stage item, is priced like
    that item's own line (model, tier, price, units, cost), and an item has at most one redo line per redo the user
    asked for (`redos_asked`)."""
    own: dict[str, dict] = {}
    for line in pack["cost"]["lines"]:
        if line["kind"] == "ai_usd" and line.get(REDO_LINE) is not True and line["item"] in items:
            own.setdefault(line["item"], line)
    count: dict[str, int] = {}
    for field, line in found:
        name = line["item"]
        base = own.get(name)
        if base is None:
            _bad(out, f"{field}.item", f"{line['what']} prices a redo of {name!r}, which the pack does not generate "
                 "and price.", "A redo line names a stage item with its own cost line.")
            continue
        unlike = [k for k in ("model", "criteria", "unit") if line[k] != base[k]]
        unlike += [k for k in ("unit_price", "units", "cost") if abs(line[k] - base[k]) > TOL]
        if unlike:
            _bad(out, f"{field}.{unlike[0]}", f"{line['what']} is priced unlike {name}'s line ({', '.join(unlike)}).",
                 f"A redo is priced like the item: copy {name}'s line ({base['what']}) and mark it \"redo\": true.")
        count[name] = count.get(name, 0) + 1
    s = state.load(run)
    for name, n in count.items():
        asked = redos_asked(s, runfolder.slug(Path(name).stem))
        if n > asked:
            _bad(out, "cost.lines", f"{name} has {n} redo line{'s' if n > 1 else ''}, and the user asked for {asked} "
                 f"redo{'s' if asked != 1 else ''} of it.",
                 "Price one redo per request (tm organic redo records the user's words), or remove the line.")


def _voice(pack: dict, units: float, lines: list[int], out: list[Problem]) -> None:
    """Voice credits are ElevenLabs characters: the lines said, on an ElevenLabs route only, each line priced at its
    text-to-speech model's credit rate (`tts_models`, #88: v4 is half a credit a character, not one)."""
    route = pack["speech"]["route"]
    chars = sum(len(text) for text in _said(pack))
    if route in organic.ELEVENLABS_ROUTES and chars:
        if abs(units - chars) > TOL:
            _bad(out, "cost.lines", f"The voice credits price {units:g} characters, and the lines said hold {chars}.",
                 f"Price {chars} characters of ElevenLabs credits (kind voice_credits).")
        for i in lines:
            line, field = pack["cost"]["lines"][i], f"cost.lines[{i}]"
            model = str(line.get("model"))   # a model the table does not list (an older pack's "elevenlabs" too) is
            rate = tts_models.rate(model)    # priced at the general 1 a character, the higher rate
            if abs(line["unit_price"] - rate) > TOL or line["unit"] != "character":
                _bad(out, f"{field}.unit_price", f"{line['what']}: {model} costs {rate:g} credits a character, not "
                     f"{line['unit_price']:g} per {line['unit']}.",
                     f"Set unit_price to {rate:g} and unit to character, and the cost to {rate:g} × the characters.")
    elif lines:
        _bad(out, f"cost.lines[{lines[0]}].kind", f"Voice credits are priced, and the route is {route}.",
             "Voice credits are for an ElevenLabs route; remove the line.")


def _run_arg(run: RunFolder) -> str:
    """The run as `--run` names it from the workspace (runs/<playbook>/<run>)."""
    return run.path.resolve().relative_to(trend_spool.workspace_of(run)).as_posix()


def _priced(run: RunFolder, line: dict, field: str, today: date, max_age: int | None, out: list[Problem]) -> None:
    """A paid line's price is the saved price file's, checked recently."""
    rel = line["price_file"]
    fetch = f"tm tool replicate_price --run {_run_arg(run)} {line['model']}"
    path = (run.path / rel).resolve() if _text(rel) else None
    try:
        inside = path is not None and path.is_relative_to(run.path.resolve()) and path.is_file()
    except OSError:
        inside = False
    if not inside:
        _bad(out, f"{field}.price_file", f"{line['what']}: the price file {rel!r} is not a file of this run.",
             f"Read the price with {fetch}, then name the file it writes.")
        return
    try:
        price, unit, checked = price_of(path, line["model"], line["criteria"])
    except (OSError, ValueError, TypeError, AttributeError) as exc:   # a file not in the tool's shape
        _bad(out, f"{field}.criteria", f"{line['what']}: {exc}", "Name the model and the tier as the price file holds them.")
        return
    if abs(price - line["unit_price"]) > TOL or unit != line["unit"]:
        _bad(out, f"{field}.unit_price", f"{line['what']}: {rel} prices {line['model']} at {price:g} per {unit}, "
             f"not {line['unit_price']:g} per {line['unit']}.", "Copy the price and its unit from the file.")
    if line["checked"] != checked:
        _bad(out, f"{field}.checked", f"{line['what']}: the file was checked on {checked}, not {line['checked']}.",
             f"Set checked to {checked}.")
    late = _dated(_day(checked), today, max_age, f"{line['what']}: the prices in {rel}")
    if late:
        _bad(out, f"{field}.price_file", f"{late}; such prices are not used.",
             f"Read them again ({fetch}) and update the line from the new file.")


def _cheaper(pack: dict, video: set[str]) -> list[str]:
    """What would cost less and still pass: a cheaper resolution, a lower tier (unless the host fixes the
    model, or a sound-led format rules the budget tier out), a shorter script, a script to film."""
    found = []
    res = pack.get("resolution") or {}
    options = {o["id"]: o["cost"] for o in res.get("options") or []}
    chosen = options.get(res.get("choice"))
    if chosen is not None:
        found += [f"resolution {rid} ({_usd(cost)})" for rid, cost in options.items() if cost < chosen - TOL]
    if _fixed_model(pack) is None:
        order = list(TIERS)
        for model in sorted(video):
            tier = next((t for t, m in TIERS.items() if m == model), None)
            if tier is None:
                continue
            lower = [t for t in order[:order.index(tier)] if not (pack["sound_led"] and t == "budget")]
            found += [f"the {t} tier ({TIERS[t]})" for t in lower]
    found += ["a shorter script (fewer seconds of video)", "a script to film instead ($0)"]
    return found


# --- after a pass: the plan, the Markdown, the mark -----------------------------------------------

def items_of(pack: dict) -> list[list]:
    """What the pack generates: [stage, name, model, images, seconds] per paid stage item. A re-check with the
    same items and a total no higher keeps the user's yes."""
    return [[st["stage"], item["name"], item["model"], item.get("images"), item.get("seconds")]
            for st in pack["stages"] for item in st["items"] if _text(item["model"])]


def animated(pack: dict) -> list[str]:
    """The items the pack draws as an animation: its id when the whole video is one, else each animation
    section's id (`tm organic storyboard --item`, the folder `03_wip/<item>/`)."""
    if pack["production"] == "animation":
        return [str(pack["id"])]
    return [str(sec["id"]) for sec in pack["sections"] if sec["type"] == "animation"]


def stills(pack: dict) -> list[str]:
    """The items the pack makes as stills with motion graphics (a QuizGrid, RankingList or RankingSplit render): its id
    when the whole video is one, else each stills section's id."""
    if pack["production"] == "stills_motion":
        return [str(pack["id"])]
    return [str(sec["id"]) for sec in pack["sections"] if sec["type"] == "stills_motion"]


def storyboard_key(item: str) -> str:
    """The key of an animated item's storyboard in `item_marks` (run.json `checked.pack.since`)."""
    return runfolder.slug(f"{item} storyboard")


def motion_key(item: str) -> str:
    """The key of a stills item's motion-graphics render in `item_marks` (PR D review M1)."""
    return runfolder.slug(f"{item} motion")


def item_marks(pack: dict) -> dict[str, list]:
    """What a pick of each generated item depends on, by its stem: [stage, name, model, images, seconds, face,
    resolution.choice, its redo lines]. A re-check that leaves an item's mark as it was keeps that item's picks
    (the controller's ruling, PR C fix wave part 3: a redo paid for in a re-plan stales only the redone item).
    An animated item's storyboard (`storyboard_key`) depends on the style, the scenes (`scenes`: what is drawn, never
    the spoken words) and its section; a stills item's motion-graphics render (`motion_key`) on the style, the script's
    lines and its section."""
    choice = (pack.get("resolution") or {}).get("choice")
    marks = {runfolder.slug(Path(item["name"]).stem):
             [st["stage"], item["name"], item["model"], item.get("images"), item.get("seconds"), item.get("face"),
              choice, redo_lines(pack, runfolder.slug(Path(item["name"]).stem))]
             for st in pack["stages"] for item in st["items"] if _text(item["model"])}
    lines = [[line["text"], line["at"]] for line in pack["script"]["lines"]]
    for kind, items, key, shown in (("storyboard", animated(pack), storyboard_key, scenes(pack)),
                                    ("motion", stills(pack), motion_key, lines)):
        for item in items:
            section = next((sec for sec in pack["sections"] if str(sec["id"]) == item), None)
            marks[key(item)] = [kind, item, pack["taste"]["style"], shown,
                                [section["from"], section["to"]] if section else None]
    return marks


def scenes(pack: dict) -> list[list]:
    """What an animation's storyboard draws, in the scenes' order: each script line's `shot` and its `on_screen` text
    (None when it shows none). The spoken `text` and its times are the voiceover's, not the storyboard's."""
    return [[line["shot"], line.get("on_screen")] for line in pack["script"]["lines"]]


def _old_marks(pack: dict) -> dict[str, list]:
    """The storyboard marks as a pack check before issue #90 stored them (the spoken lines and their times): a run
    checked then keeps its storyboard's accept across a re-check that leaves those as they were."""
    lines = [[line["text"], line["at"]] for line in pack["script"]["lines"]]
    out = {}
    for item in animated(pack):
        section = next((sec for sec in pack["sections"] if str(sec["id"]) == item), None)
        out[storyboard_key(item)] = ["storyboard", item, pack["taste"]["style"], lines,
                                     [section["from"], section["to"]] if section else None]
    return out


def _since(previous: dict, marks: dict[str, list], old: dict[str, list] | None = None) -> dict[str, str | None]:
    """Each item's pick-currency time after this check: the earlier one, kept, when the previous checked pack gave
    the item the same mark (or, for a storyboard, the mark of `_old_marks`, as a check before issue #90 stored it);
    None (this check's own time) when the item is new or changed."""
    old_marks, old_since, old_at = previous.get("marks") or {}, previous.get("since") or {}, previous.get("at")
    old = old or {}
    return {stem: (old_since.get(stem) or old_at)
            if old_at and old_marks.get(stem) in ([mark] + ([old[stem]] if stem in old else [])) else None
            for stem, mark in marks.items()}


def record(run: RunFolder, path: Path, pack: dict, *, stage: Literal["recipe", "pack"]) -> dict:
    """Write the pack's .md beside it (never over a different one), at the pack stage set run.json `planned`
    (and `planned_at`, unless the yes still holds), then mark the file as passed at this stage: a stop on the
    way leaves the pack unmarked, never marked without its plan. Returns {md, planned, replanned}.

    The yes still holds (P3-F1, the controller's ruling) when an earlier pack was planned with the same
    items and every kind's total is the same or lower; any change to the items, a new kind or a higher
    total sets `planned_at` to now, so the pack check-in needs `tm decide pack approve --change`."""
    path = Path(path).resolve()
    rel = path.relative_to(run.path.resolve()).as_posix()
    found = NAME.fullmatch(rel)
    if not found:
        raise ValueError(f"The pack is written as {FILE_PATTERN}; {rel} is not.")
    md = path.with_suffix(".md")
    md_rel = md.relative_to(run.path.resolve()).as_posix()
    text = render_md(pack, pack["lang"], version=f"v{int(found['n']):02d}")
    run.assert_writable(md)
    try:
        with open(md, "x", encoding="utf-8", newline="\n") as fh:   # never over an earlier .md (OV13)
            fh.write(text)
    except FileExistsError:
        if md.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            raise Stop(f"{md_rel} is already written, differently, and is never written over. Write the pack as a new "
                       f"version, check it, and its .md is written with it; {AGAIN}.") from None
    else:
        manifest.record(run, md_rel, WIP, SOURCE, parent=rel)
    planned, replanned, extra = None, False, None
    if stage == "pack":
        s = state.load(run)
        planned = {k: float(pack["cost"]["totals"][k]) for k in playbooks.get(ORGANIC_VIDEO).budgets}
        marks = item_marks(pack)
        extra = {"items": items_of(pack), "marks": marks,
                 "since": _since(s.checked.get("pack") or {}, marks, _old_marks(pack))}
        holds = (s.planned_at is not None and (s.checked.get("pack") or {}).get("items") == extra["items"]
                 and all(planned[k] <= float(s.planned.get(k, 0)) + TOL for k in planned))
        replanned = not holds
        s.planned = planned
        if replanned:
            s.planned_at = flow._now()
        state.save(run, s)
    stepchecks.mark(run, stage, path, extra=extra)
    return {"md": md_rel, "planned": planned, "replanned": replanned, "language_warning": md_lang(pack["lang"]).warning}


# --- the Markdown beside the pack ------------------------------------------------------------------

# templates/pack_template.md's sections, in the page language: the string table's `organic.pack_md.*` (a test
# compares the English with the template), the run's stored values shown in it (`organic_pages.value`).
_M = "organic.pack_md."
ROUTE_KEY = {r: f"{_M}route_{r}" for r in ("h3_native", "h3_narrator", "elevenlabs_narrator", "elevenlabs_lipsync",
                                           "none")}
RISK_KEY = {r: f"{_M}risk_{r}" for r in ("low", "medium", "high")}
CHECKIN_KEYS = tuple(f"{_M}checkin_{c}" for c in ("pack", "images", "video", "edit"))


def _secs(at: list) -> str:
    return f"{at[0]:g}–{at[1]:g} s"


def md_lang(lang: str | None) -> i18n.PageLang:
    """The language the pack's Markdown is written in: `lang` (the pack's, the run's working language) when its
    table has every organic string, else English, with `.warning` (`i18n.page_lang`)."""
    return i18n.page_lang(lang, "organic")


def render_md(pack: dict, lang: str, *, version: str | None = None) -> str:
    """templates/pack_template.md's sections, filled from the pack, its words in `lang` (`md_lang`).
    A recipe (no pack keys yet) gets the sections it has."""
    from tm import organic_pages   # its pages import the kit, which reads this module

    tr = i18n.translator(md_lang(lang).lang)

    def t(key: str, **values) -> str:
        return tr(_M + key, **values)

    taste = pack.get("taste") or {}
    picks = [str(taste[k]) for k in ("style", "voice", "music") if taste.get(k)]
    script = pack["script"]
    product = organic_pages.value(pack["product"]["level"], "product", tr)
    lines = [f"# {pack['id']}, {t('pack')}{' ' + version if version else ''}: “{pack['title']}”", "",
             f"{t('channel')}: {pack['channel']}. {t('product')}: {product}. "
             f"{t('taste')}: {', '.join(picks) or t('none')}.", "",
             "## " + tr.plural(_M + "h_script", script["words"], n=script["words"], s=f"{script['seconds']:g}")]
    for i, line in enumerate(script["lines"]):
        lines.append(f"{line['n']}. “{line['text']}”" + (f" ({t('hook')})" if i == 0 else ""))
    lines += ["", "## " + t("h_picture"), f"| {t('line')} | {t('see')} |", "|---|---|"]
    lines += [f"| {line['n']} ({_secs(line['at'])}) | {line['shot']} |" for line in script["lines"]]
    speech, sound = pack.get("speech"), pack.get("sound")
    if speech or sound:
        lines += ["", "## " + t("h_sound")]
        if speech:
            route = tr(ROUTE_KEY[speech["route"]]) if speech["route"] in ROUTE_KEY else speech["route"]
            lines.append(f"- {t('voice')}: {route}" + (f", {speech['voice']}" if speech.get("voice") else "") + ".")
        music = taste.get("music") or (sound or {}).get("track")
        lines.append(f"- {t('music')}: {music or t('none')}.")
        if (sound or {}).get("trending"):
            lines.append(f"- {t('trending')}: {sound['trending']}.")
        lines.append(f"- {t('loudness')}")
    if pack.get("models"):
        lines += ["", "## " + t("h_models")]
        for m in pack["models"]:
            lines.append(f"- {m['component']}: `{m['model']}`, {m['why']} ({m['ranking']['source']}, "
                         f"{m['ranking']['date']}); {t('recipe')} `{m['recipe']}`.")
        if pack.get("stages"):
            lines.append(f"- {t('stages')}: " + " → ".join(st["stage"] for st in pack["stages"]) + ".")
        res = pack.get("resolution")
        if res:
            lines.append(f"- {t('resolution')}: " + " / ".join(f"{o['id']} {_usd(o['cost'])}" for o in res["options"])
                         + f" ({t('chosen')}: {res['choice']}).")
    if pack.get("facts"):
        lines += ["", "## " + t("h_facts")] + [f"- {f['claim']}: {f['source']}." for f in pack["facts"]]
    lines += ["", "## " + t("h_checkins")] + [f"{i}. {tr(key)}" for i, key in enumerate(CHECKIN_KEYS, 1)]
    cost = pack.get("cost")
    if cost:
        lines += ["", "## " + t("h_cost"), f"| {t('step')} | {t('tool')} | {t('h_cost')} |", "|---|---|---|"]
        for line in cost["lines"]:
            amount = (_usd(line["cost"]) if line["kind"] == "ai_usd" else
                      tr.plural(_M + "credits", f"{line['cost']:g}", n=f"{line['cost']:g}"))
            lines.append(f"| {line['what']} | {line['model']} | {amount} |")
        credits = cost["totals"].get("voice_credits") or 0
        lines.append(f"| **{t('total')}** | | **{_usd(cost['totals']['ai_usd'])}**"
                     + (f" + {tr.plural(_M + 'credits', f'{credits:g}', n=f'{credits:g}')}" if credits else "") + " |")
        if cost.get("currency_note"):
            lines += ["", cost["currency_note"]]
    risk = pack.get("risk")
    if risk:
        hits = "; ".join(f"{organic_pages.value(x['item'], 'risk', tr)}: {x['mitigation']}" for x in risk["hits"])
        level = tr(RISK_KEY[risk["level"]]) if risk["level"] in RISK_KEY else risk["level"]
        lines += ["", f"**{t('risk')}:** {level}." + (f" {hits}." if hits else "")]
    return "\n".join(lines) + "\n"


# --- what other modules read -------------------------------------------------------------------------

def checked_pack(run: RunFolder) -> dict | None:
    """The latest pack, when it passed `--stage pack` and is unchanged since; else None."""
    if stepchecks.fresh(run, "pack", WIP, STEM, "json") is not None:
        return None
    try:
        data = json.loads((run.path / state.load(run).checked["pack"]["file"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, KeyError):
        return None
    return data if isinstance(data, dict) else None


def ai_label(pack: dict) -> str:
    """The AI label a pack's video needs (rules.md, OV11): required for an AI host, not required for a
    stylised animation alone, on for any other AI footage."""
    if pack["host"]["kind"] in ("image", "description"):
        return "required"
    if _types(pack) <= {"animation", "sections"}:
        return "not_required"
    return "on"


# --- step checks ---------------------------------------------------------------------------------

def recipe_gap(run: RunFolder) -> str | None:
    """The `recipe_written` step check (D1). A script to film: a script is written in 03_wip. An AI video:
    the latest pack passed `tm organic pack check --stage recipe` and is unchanged since. Reads only."""
    from tm.organic_pages import script   # it imports kit, which reads this module

    if "script_to_film" in (state.load(run).outputs or []):
        folder = run.path / WIP
        if folder.is_dir() and any(script.NAME.fullmatch(f"{WIP}/{p.name}") for p in folder.iterdir()):
            return None
        return f"the script ({script.FILE_PATTERN}) is written"
    gap = stepchecks.fresh(run, "recipe", WIP, STEM, "json")
    return None if gap is None else f"{gap} (tm organic pack check --stage recipe)"


def pack_gap(run: RunFolder) -> str | None:
    """The `pack_checked` step check (E2): the latest pack passed `tm organic pack check --stage pack` and is
    unchanged since. Reads only."""
    gap = stepchecks.fresh(run, "pack", WIP, STEM, "json")
    return None if gap is None else f"{gap} (tm organic pack check --stage pack)"
